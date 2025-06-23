#!/usr/bin/env python3
"""
Dolt Staging Crew Flow for Prefect Container
============================================

Staging-focused Prefect flow that merges feature branches into staging.
Based on proven working MCP integration pattern.

Goal: 2 agents focused on branch management - detect conflicts and merge clean branches into staging.
"""

import sys
from pathlib import Path

# Ensure proper Python path for container environment
current_dir = Path(__file__).parent
workspace_root = current_dir.parent.parent  # Go up two levels: flows/presence -> flows -> workspace
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

import asyncio  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
from datetime import datetime  # noqa: E402
from typing import Any, Dict  # noqa: E402

from prefect import flow, task  # noqa: E402
from prefect.logging import get_run_logger  # noqa: E402

# AutoGen MCP Integration - Using PROVEN working pattern
from autogen_agentchat.agents import AssistantAgent  # noqa: E402
from autogen_agentchat.teams import RoundRobinGroupChat  # noqa: E402
from autogen_agentchat.conditions import MaxMessageTermination  # noqa: E402
from autogen_agentchat.ui import Console  # noqa: E402
from autogen_ext.models.openai import OpenAIChatCompletionClient  # noqa: E402

# SSE MCP Integration - matching cleanup_cogni_flow pattern
from utils.setup_connection_to_cogni_mcp import configure_cogni_mcp, MCPConnectionError  # noqa: E402
from utils.cogni_memory_mcp_outro import automated_dolt_outro  # noqa: E402

# Prompt template integration
from infra_core.prompt_templates import render_branch_merger_prompt  # noqa: E402
from infra_core.prompt_templates import render_conflict_detector_prompt  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO)

# Staging Configuration
MCP_DOLT_BRANCH = "staging"
MCP_DOLT_NAMESPACE = "cogni-project-management"


@task(name="run_dolt_staging_crew", cache_policy=None)
async def run_dolt_staging_crew(
    autogen_tools: list,
    tool_specs_text: str,
    session,
    work_items_context: Dict[str, Any],
    branch_inventory_summary: str,
) -> Dict[str, Any]:
    """Run 2 dolt staging agents to detect conflicts and merge branches into staging - Following cleanup_cogni_flow pattern"""
    logger = get_run_logger()

    if not autogen_tools:
        return {"success": False, "error": "No MCP tools available"}

    try:
        # Setup OpenAI client - Helicone observability handled automatically
        model_client = OpenAIChatCompletionClient(model="gpt-4o")
        logger.info("✅ OpenAI client configured")

        cogni_tools = autogen_tools

        # Get work items context for agent prompts
        work_items_summary = work_items_context.get(
            "work_items_summary", "## Current Work Items Context:\\n- No context available."
        )

        # Create 2 dolt staging agents with branch inventory context
        agents = []

        # Agent 1: Conflict Detector - Analyzes branches for merge conflicts
        conflict_detector = AssistantAgent(
            name="conflict_detector",
            model_client=model_client,
            tools=cogni_tools,
            system_message=render_conflict_detector_prompt(
                tool_specs_text, work_items_summary, branch_inventory_summary
            ),
        )
        agents.append(conflict_detector)

        # Agent 2: Branch Merger - Merges clean branches into staging
        branch_merger = AssistantAgent(
            name="branch_merger",
            model_client=model_client,
            tools=cogni_tools,
            system_message=render_branch_merger_prompt(
                tool_specs_text, work_items_summary, branch_inventory_summary
            ),
        )
        agents.append(branch_merger)

        # Create simple team - Increased message limit for many branch merges
        team = RoundRobinGroupChat(
            participants=agents,
            termination_condition=MaxMessageTermination(
                max_messages=16
            ),  # 8 rounds each for many merges
        )

        logger.info("🚀 Starting 2-agent dolt staging crew...")

        # Dolt Staging task with branch management focus
        staging_task = """Please work together as the Dolt Staging Crew to prepare the staging branch:

## STAGING GOALS:

1) **CONFLICT DETECTOR**: Analyze all branches for merge safety
   - Use DoltListBranches to get complete branch inventory  
   - Use DoltCompareBranches to check each feature branch vs staging
   - Categorize branches by merge risk (HIGH/MEDIUM/LOW)
   - Flag any potential conflicts before merging
   - Provide merge order recommendations

2) **BRANCH MERGER**: Merge clean branches into staging
   - Focus on feat/* and fix/* branches with "dirty": false (pushed changes)
   - Use DoltCompareBranches to verify merge compatibility  
   - Use DoltMerge to merge safe branches into staging
   - Skip branches with conflicts or risks
   - Report successful merges and any failures

## SUCCESS CRITERIA:
- All safe feature branches merged into staging
- Conflict risks clearly documented  
- Staging branch ready for testing/review
- Clear summary of what was merged vs. what needs manual attention

## SAFETY RULES:
- Never force merge if conflicts detected
- Max 10 branches per run for safety
- Stop immediately if staging becomes unstable
- Always work on staging branch

Work systematically and coordinate your efforts!"""

        # Run the staging crew
        await Console(team.run_stream(task=staging_task))

        logger.info("✅ Dolt staging crew completed successfully!")

        logger.info("📝 Calling shared automated_dolt_outro helper…")
        outro = await automated_dolt_outro(session, flow_context="Dolt Staging flow")

        return {
            "success": True,
            "agents_count": len(agents),
            "tools_count": len(cogni_tools),
            "outro": outro,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Dolt staging crew failed: {e}")
        return {"success": False, "error": str(e)}


@flow(name="dolt_staging_crew_flow", log_prints=True)
async def dolt_staging_crew_flow() -> Dict[str, Any]:
    """
    Dolt Staging Crew Flow - Branch Management and Merge Operations

    Uses SSE MCP pattern matching cleanup_cogni_flow exactly:
    1. Setup SSE MCP connection with branch/namespace switching
    2. Load branch inventory via DoltListBranches MCP tool
    3. Run 2 dolt-focused agents with branch context:
       - **Conflict Detector** analyzing branches for merge safety
       - **Branch Merger** merging clean branches into staging
    4. Automated Dolt outro operations

    All using the PROVEN SSE MCP pattern with branch inventory injection.
    """
    logger = get_run_logger()
    logger.info("🎯 Starting Dolt Staging Crew Flow for Branch Management")
    logger.info("🔧 Using SSE MCP transport + Branch Inventory Injection")

    # Pick branch / namespace from env *or* fallback constants
    branch = os.getenv("MCP_DOLT_BRANCH", MCP_DOLT_BRANCH)
    namespace = os.getenv("MCP_DOLT_NAMESPACE", MCP_DOLT_NAMESPACE)
    sse_url = os.getenv("COGNI_MCP_SSE_URL", "http://toolhive:24160/sse")

    logger.info(f"🔧 FLOW CONFIGURATION: Working on Branch='{branch}', Namespace='{namespace}'")

    try:
        # Step 1: Skip work items reading for now (legacy pattern causing MySQL connection issues)
        work_items_context = {
            "success": True,
            "work_items_summary": "Work items context skipped for SSE testing",
        }

        # Step 2: Setup SSE MCP connection with branch/namespace switching
        async with configure_cogni_mcp(sse_url=sse_url, branch=branch, namespace=namespace) as (
            session,
            sdk_tools,
        ):
            logger.info("🔗 MCP attached (%d tools) on %s/%s", len(sdk_tools), branch, namespace)

            # --- build AutoGen adapters exactly like cleanup_cogni_flow ---
            from autogen_ext.tools.mcp import SseMcpToolAdapter, SseServerParams

            autogen_tools = [
                SseMcpToolAdapter(SseServerParams(url=sse_url), t, session) for t in sdk_tools
            ]

            tool_specs_text = "\n".join(
                [f"• {t.name}: {t.description or 'No description'}" for t in sdk_tools[:12]]
            )

            # Step 2.5: Load branch inventory via DoltListBranches MCP tool
            logger.info("Loading branch inventory via DoltListBranches MCP tool")

            try:
                # Call DoltListBranches directly using the session - following cleanup_cogni_flow pattern
                branch_inventory_summary = await session.call_tool(
                    "DoltListBranches", {"input": "{}"}
                )
                logger.info("✅ Branch inventory loaded successfully via DoltListBranches")

                # Pretty-print the branch inventory for visibility
                import json

                try:
                    # If it's a string, try to parse it as JSON for pretty printing
                    if isinstance(branch_inventory_summary, str):
                        parsed_data = json.loads(branch_inventory_summary)
                        pretty_json = json.dumps(parsed_data, indent=2)
                    else:
                        # If it's already a dict/object, convert to pretty JSON
                        pretty_json = json.dumps(branch_inventory_summary, indent=2, default=str)

                    logger.info("📊 Branch Inventory:\n%s", pretty_json)
                except (json.JSONDecodeError, TypeError):
                    # Fallback: just log the raw data if JSON parsing fails
                    logger.info("📊 Branch Inventory (raw): %s", str(branch_inventory_summary))

            except Exception as e:
                logger.warning(f"Failed to load branch inventory via MCP: {e}")
                branch_inventory_summary = (
                    "## Branch Inventory:\n- Branch inventory unavailable due to MCP error"
                )

            # Step 3: Run dolt staging crew with integrated outro routine
            staging_result = await run_dolt_staging_crew(
                autogen_tools,
                tool_specs_text,
                session,
                work_items_context,
                branch_inventory_summary,
            )

            if not staging_result.get("success"):
                logger.error(f"❌ Staging crew failed: {staging_result.get('error')}")
                return {"status": "failed", "error": staging_result.get("error")}

            logger.info("🤖 Dolt Staging Crew has completed branch analysis and merge operations!")

            # Final success
            logger.info(
                "🎉 FLOW SUCCESS: Dolt Staging Crew flow with branch inventory integration completed!"
            )
            return {
                "status": "success",
                "tools_count": len(sdk_tools),
                "agents_count": staging_result.get("agents_count", 0),
                "work_items_count": work_items_context.get("count", 0),
                "outro": staging_result.get("outro", {}),
                "timestamp": datetime.now().isoformat(),
            }

    except MCPConnectionError as e:
        logger.error(f"❌ MCP connection failed: {e}")
        return {"status": "failed", "error": f"MCP connection failed: {e}"}
    except Exception as e:
        logger.error(f"❌ Staging flow failed: {e}")
        return {"status": "failed", "error": str(e)}


if __name__ == "__main__":
    # For testing the Dolt Staging Crew flow locally
    import asyncio

    asyncio.run(dolt_staging_crew_flow())
