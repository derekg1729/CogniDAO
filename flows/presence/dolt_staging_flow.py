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

# Shared tasks - import the functions we'll use
from .shared_tasks import setup_cogni_mcp_connection, read_work_items_context  # noqa: E402

# Prompt template integration
from infra_core.prompt_templates import render_branch_merger_prompt  # noqa: E402
from infra_core.prompt_templates import render_conflict_detector_prompt  # noqa: E402
from infra_core.prompt_templates import render_dolt_commit_agent_prompt  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO)

# Staging Configuration
MCP_DOLT_BRANCH = "staging"
MCP_DOLT_NAMESPACE = "cogni-project-management"


# Duplicate tasks removed - now using shared_tasks.py:
# - read_current_work_items -> read_work_items_context
# - setup_simple_mcp_connection -> setup_cogni_mcp_connection


@task(name="run_dolt_staging_crew")
async def run_dolt_staging_crew(
    mcp_setup: Dict[str, Any], work_items_context: Dict[str, Any]
) -> Dict[str, Any]:
    """Run 2 dolt staging agents to detect conflicts and merge branches into staging"""
    logger = get_run_logger()

    if not mcp_setup.get("success"):
        return {"success": False, "error": "MCP setup failed"}

    try:
        # Setup OpenAI client - Helicone observability handled automatically
        model_client = OpenAIChatCompletionClient(model="gpt-4o")
        logger.info("✅ OpenAI client configured")

        cogni_tools = mcp_setup["tools"]
        tool_specs_text = mcp_setup.get(
            "tool_specs", "## Available MCP Tools: (tool specs not available)"
        )

        # Get work items context for agent prompts
        work_items_summary = work_items_context.get(
            "work_items_summary", "## Current Work Items Context:\\n- No context available."
        )

        # Create 2 dolt staging agents
        agents = []

        # Agent 1: Conflict Detector - Analyzes branches for merge conflicts
        conflict_detector = AssistantAgent(
            name="conflict_detector",
            model_client=model_client,
            tools=cogni_tools,
            system_message=render_conflict_detector_prompt(tool_specs_text, work_items_summary),
        )
        agents.append(conflict_detector)

        # Agent 2: Branch Merger - Merges clean branches into staging
        branch_merger = AssistantAgent(
            name="branch_merger",
            model_client=model_client,
            tools=cogni_tools,
            system_message=render_branch_merger_prompt(tool_specs_text, work_items_summary),
        )
        agents.append(branch_merger)

        # Create simple team
        team = RoundRobinGroupChat(
            participants=agents,
            termination_condition=MaxMessageTermination(max_messages=8),  # 4 rounds each
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

        # === OUTRO ROUTINE: Dolt Operations (Simplified) ===
        logger.info("🔄 Starting outro routine: Final staging operations...")

        # Create dedicated Dolt commit agent
        dolt_commit_agent = AssistantAgent(
            name="dolt_commit_agent",
            model_client=model_client,
            tools=cogni_tools,
            system_message=render_dolt_commit_agent_prompt(tool_specs_text),
        )

        # Create simple team for Dolt operations
        dolt_team = RoundRobinGroupChat(
            participants=[dolt_commit_agent],
            termination_condition=MaxMessageTermination(max_messages=5),
        )

        logger.info("🚀 Starting final Dolt operations...")

        # Run Dolt operations to finalize staging
        await Console(
            dolt_team.run_stream(
                task="Finalize the staging branch with commit and push operations."
            )
        )

        logger.info("✅ Outro routine completed successfully!")

        return {
            "success": True,
            "agents_count": len(agents),
            "tools_count": len(cogni_tools),
            "work_items_count": work_items_context.get("count", 0),
            "outro_success": True,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Dolt staging crew failed: {e}")
        return {"success": False, "error": str(e)}


@flow(name="dolt_staging_crew_flow", log_prints=True)
async def dolt_staging_crew_flow() -> Dict[str, Any]:
    """
    Dolt Staging Crew Flow - Branch Management and Merge Operations

    Uses proven working AutoGen pattern to run 2 dolt-focused agents + finalization:
    1. Read current work items context using DoltMySQLReader
    2. Setup MCP connection with proven stdio transport
    3. Run unified staging crew workflow that includes:
       - **Conflict Detector** analyzing branches for merge safety
       - **Branch Merger** merging clean branches into staging
       - **Integrated Dolt operations** for automatic finalization

    All using the PROVEN working import pattern with branch management focus.
    """
    logger = get_run_logger()
    logger.info("🎯 Starting Dolt Staging Crew Flow for Branch Management")
    logger.info("🔧 Using PROVEN working stdio MCP transport + Branch Merge Operations")

    logger.info(
        f"🔧 FLOW CONFIGURATION: Working on Branch='{MCP_DOLT_BRANCH}', Namespace='{MCP_DOLT_NAMESPACE}'"
    )

    try:
        # Step 1: Read current work items for context
        work_items_context = await read_work_items_context(branch=MCP_DOLT_BRANCH)

        if work_items_context.get("success"):
            logger.info(f"✅ Work items context loaded: {work_items_context.get('count', 0)} items")
        else:
            logger.warning(
                f"⚠️ Work items context failed: {work_items_context.get('error', 'Unknown error')}"
            )

        # Step 2: Setup MCP connection with explicit branch and namespace
        mcp_setup = await setup_cogni_mcp_connection(
            branch=MCP_DOLT_BRANCH, namespace=MCP_DOLT_NAMESPACE
        )

        if not mcp_setup.get("success"):
            logger.error(f"❌ MCP setup failed: {mcp_setup.get('error')}")
            return {"status": "failed", "error": mcp_setup.get("error")}

        logger.info(f"✅ MCP setup successful: {mcp_setup['tools_count']} tools available")

        # Step 3: Run dolt staging crew
        staging_result = await run_dolt_staging_crew(mcp_setup, work_items_context)

        if not staging_result.get("success"):
            logger.error(f"❌ Staging crew failed: {staging_result.get('error')}")
            return {"status": "failed", "error": staging_result.get("error")}

        logger.info("🤖 Dolt Staging Crew has completed branch analysis and merge operations!")

        # Final success
        logger.info("🎉 FLOW SUCCESS: Dolt Staging Crew flow completed!")
        return {
            "status": "success",
            "tools_count": staging_result.get("tools_count", 0),
            "agents_count": staging_result.get("agents_count", 0),
            "work_items_count": staging_result.get("work_items_count", 0),
            "outro_success": staging_result.get("outro_success", False),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Staging flow failed: {e}")
        return {"status": "failed", "error": str(e)}
    finally:
        # Ensure the MCP client is disconnected at the end of the flow
        if "mcp_setup" in locals() and mcp_setup.get("client"):
            await mcp_setup["client"].disconnect()


if __name__ == "__main__":
    # For testing the Dolt Staging Crew flow locally
    import asyncio

    asyncio.run(dolt_staging_crew_flow())
