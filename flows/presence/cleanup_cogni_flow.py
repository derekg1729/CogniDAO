#!/usr/bin/env python3
"""
Cleanup Cogni Flow for Prefect Container
========================================

Cleanup-focused Prefect flow

Goal: 2 agents focused on system cleanup - identify test artifacts for deletion and migrate legacy blocks to proper namespaces.
Enhanced with bulk operations for efficient cleanup.
"""

import sys
from pathlib import Path

# Ensure proper Python path for container environment
# In container: working dir is /workspace/flows/presence, but infra_core is at /workspace/infra_core
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

# New SSE pattern imports
from utils.setup_connection_to_cogni_mcp import configure_cogni_mcp, MCPConnectionError  # noqa: E402
from utils.cogni_memory_mcp_outro import automated_dolt_outro  # noqa: E402

# Prompt template integration
from infra_core.prompt_templates import render_test_artifact_detector_prompt  # noqa: E402
from infra_core.prompt_templates import render_namespace_migrator_prompt  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO)

# Cleanup Configuration
MCP_DOLT_BRANCH = "feat/cleanup"
MCP_DOLT_NAMESPACE = "legacy"


@task(name="run_cleanup_team_with_outro", cache_policy=None)
async def run_cleanup_team_with_outro(
    autogen_tools: list,
    tool_specs_text: str,
    session,
    work_items_context: Dict[str, Any],
    memory_overview_summary: str,
) -> Dict[str, Any]:
    """Run 2 cleanup agents to identify test artifacts and migrate legacy blocks - All in one simple task using proven working pattern"""
    logger = get_run_logger()

    if not autogen_tools:
        return {"success": False, "error": "No MCP tools available"}

    try:
        # Setup OpenAI client - Helicone observability handled automatically by sitecustomize.py
        model_client = OpenAIChatCompletionClient(model="gpt-4o")
        logger.info("✅ OpenAI client configured")

        cogni_tools = autogen_tools

        # Get work items context for agent prompts
        work_items_summary = work_items_context.get(
            "work_items_summary", "## Current Work Items Context:\\n- No context available."
        )

        # Create 2 cleanup agents with system cleanup focus AND tool specifications
        agents = []

        # Agent 1: Test Artifact Detector - Finds and deletes test artifacts
        test_detector = AssistantAgent(
            name="test_artifact_detector",
            model_client=model_client,
            tools=cogni_tools,
            system_message=render_test_artifact_detector_prompt(
                tool_specs_text, work_items_summary, memory_overview_summary
            ),
        )
        agents.append(test_detector)

        # Agent 2: Namespace Migrator - Moves legacy blocks to proper namespaces
        namespace_migrator = AssistantAgent(
            name="namespace_migrator",
            model_client=model_client,
            tools=cogni_tools,
            system_message=render_namespace_migrator_prompt(
                tool_specs_text, work_items_summary, memory_overview_summary
            ),
        )
        agents.append(namespace_migrator)

        # Create simple team
        team = RoundRobinGroupChat(
            participants=agents,
            termination_condition=MaxMessageTermination(max_messages=6),  # 3 rounds each
        )

        logger.info("🚀 Starting 2-agent cleanup team...")

        # Cleanup Team task with system cleanup focus
        cleanup_task = """Please work together as the Cogni Cleanup Team to organize and clean up the memory system:

## CLEANUP GOALS:

1) **TEST ARTIFACT DETECTOR**: Find and delete blocks created during testing
   - Look for "test" tags, test agent creators, obvious test content
   - Use QueryMemoryBlocksSemantic to search for test-related content
   - Use BulkDeleteBlocks for efficient cleanup (max 10 at a time for safety)
   - Report what was removed

2) **NAMESPACE MIGRATOR**: Move all legacy blocks to proper namespaces
   - AI/Education content → "ai-education" namespace  
   - Work items & project management → "cogni-project-management" namespace
   - Use GetMemoryBlock with namespace_id="legacy" to find legacy blocks
   - Use BulkUpdateNamespace for efficient migration (max 20 at a time)
   - Report migration statistics

## SUCCESS CRITERIA:
- All test artifacts identified and removed
- Legacy namespace cleaned out (minimal remaining blocks)
- Blocks properly categorized in appropriate namespaces
- Clear summary of cleanup actions taken

## SAFETY RULES:
- NEVER delete blocks with "keep" tag
- When in doubt about deletion, preserve the block
- Use bulk operations efficiently but safely
- Process in manageable batches

Work systematically and report your progress!"""

        # Run the cleanup team
        await Console(team.run_stream(task=cleanup_task))

        logger.info("✅ Cleanup team analysis completed successfully!")

        logger.info("📝 Calling shared automated_dolt_outro helper…")
        outro = await automated_dolt_outro(session, flow_context="Cleanup flow")

        return {
            "success": True,
            "agents_count": len(agents),
            "tools_count": len(cogni_tools),
            "outro": outro,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Cleanup flow with outro failed: {e}")
        return {"success": False, "error": str(e)}


@flow(name="cleanup_team_flow", log_prints=True)
async def cleanup_team_flow() -> Dict[str, Any]:
    """Cleanup flow – now using SSE MCP + shared outro"""
    logger = get_run_logger()
    logger.info("🚀 Starting Cleanup flow (SSE edition)")

    # Pick branch / namespace from env *or* fallback constants
    branch = os.getenv("MCP_DOLT_BRANCH", MCP_DOLT_BRANCH)
    namespace = os.getenv("MCP_DOLT_NAMESPACE", MCP_DOLT_NAMESPACE)
    sse_url = os.getenv("COGNI_MCP_SSE_URL", "http://toolhive:24160/sse")

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

            # --- build AutoGen adapters exactly like autogen_work_reader_flow ---
            from autogen_ext.tools.mcp import SseMcpToolAdapter, SseServerParams

            autogen_tools = [
                SseMcpToolAdapter(SseServerParams(url=sse_url), t, session) for t in sdk_tools
            ]

            tool_specs_text = "\n".join(
                [f"• {t.name}: {t.description or 'No description'}" for t in sdk_tools[:12]]
            )

            # Step 2.5: Load memory system overview via GlobalMemoryInventory MCP tool
            logger.info("Loading memory system overview via GlobalMemoryInventory MCP tool")

            try:
                # Call GlobalMemoryInventory directly using the session - following autogen_work_reader pattern
                memory_overview_summary = await session.call_tool(
                    "GlobalMemoryInventory", {"input": "{}"}
                )
                logger.info("✅ Memory overview loaded successfully via GlobalMemoryInventory")

                # Pretty-print the memory inventory for visibility
                import json

                try:
                    # If it's a string, try to parse it as JSON for pretty printing
                    if isinstance(memory_overview_summary, str):
                        parsed_data = json.loads(memory_overview_summary)
                        pretty_json = json.dumps(parsed_data, indent=2)
                    else:
                        # If it's already a dict/object, convert to pretty JSON
                        pretty_json = json.dumps(memory_overview_summary, indent=2, default=str)

                    logger.info("📊 Memory System Inventory:\n%s", pretty_json)
                except (json.JSONDecodeError, TypeError):
                    # Fallback: just log the raw data if JSON parsing fails
                    logger.info(
                        "📊 Memory System Inventory (raw): %s", str(memory_overview_summary)
                    )

            except Exception as e:
                logger.warning(f"Failed to load memory overview via MCP: {e}")
                memory_overview_summary = (
                    "## Memory System Overview:\n- Memory inventory unavailable due to MCP error"
                )

            # Step 3: Run cleanup team with integrated outro routine
            summary_result = await run_cleanup_team_with_outro(
                autogen_tools, tool_specs_text, session, work_items_context, memory_overview_summary
            )

            if not summary_result.get("success"):
                logger.error(f"❌ Agent summary with outro failed: {summary_result.get('error')}")
                return {"status": "failed", "error": summary_result.get("error")}

            logger.info(
                "🤖 Cleanup Team has provided strategic insights and Dolt operations completed!"
            )

            # Final success
            logger.info(
                "🎉 FLOW SUCCESS: Cleanup Team flow with Knowledge Graph integration completed!"
            )
            return {
                "status": "success",
                "tools_count": len(sdk_tools),
                "agents_count": summary_result.get("agents_count", 0),
                "work_items_count": work_items_context.get("count", 0),
                "outro": summary_result.get("outro", {}),
                "timestamp": datetime.now().isoformat(),
            }

    except MCPConnectionError as e:
        logger.error(f"❌ MCP connection failed: {e}")
        return {"status": "failed", "error": f"MCP connection failed: {e}"}
    except Exception as e:
        logger.error(f"❌ Enhanced flow failed: {e}")
        return {"status": "failed", "error": str(e)}


if __name__ == "__main__":
    # For testing the Cleanup Team flow locally
    import asyncio

    asyncio.run(cleanup_team_flow())
