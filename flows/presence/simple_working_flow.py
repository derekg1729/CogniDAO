#!/usr/bin/env python3
"""
Ultra-Simple Working MCP Flow for Prefect Container
===================================================

Minimal Prefect flow that uses our PROVEN working MCP integration.
Based on autogen_mcp_cogni_simple_working.py that achieved 21/21 tools discovery.

Goal: 3 agents read active work items and summarize them.
Enhanced with DoltMySQLReader to provide work item context in agent prompts.
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Ensure proper Python path for container environment
# In container: working dir is /workspace/flows/presence, but infra_core is at /workspace/infra_core
current_dir = Path(__file__).parent
workspace_root = current_dir.parent.parent  # Go up two levels: flows/presence -> flows -> workspace
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

from prefect import flow, task  # noqa: E402
from prefect.logging import get_run_logger  # noqa: E402

# AutoGen MCP Integration - Using PROVEN working pattern
from autogen_agentchat.agents import AssistantAgent  # noqa: E402
from autogen_agentchat.teams import RoundRobinGroupChat  # noqa: E402
from autogen_agentchat.conditions import MaxMessageTermination  # noqa: E402
from autogen_agentchat.ui import Console  # noqa: E402
from autogen_ext.models.openai import OpenAIChatCompletionClient  # noqa: E402
from autogen_ext.tools.mcp import StdioServerParams, mcp_server_tools  # noqa: E402

# Dolt integration for work item context
from infra_core.memory_system.dolt_reader import DoltMySQLReader  # noqa: E402
from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO)


@task(name="read_current_work_items")
async def read_current_work_items() -> Dict[str, Any]:
    """Read current work items using DoltMySQLReader for agent context"""
    logger = get_run_logger()

    try:
        # Setup Dolt connection
        config = DoltConnectionConfig()
        reader = DoltMySQLReader(config)

        logger.info("🔍 Reading current work items from work_items_core view...")

        # Read latest work items (limit 10 for context)
        work_items = reader.read_work_items_core_view(limit=10, branch="main")

        if work_items:
            logger.info(f"✅ Found {len(work_items)} work items for agent context")

            # Create summary for agent prompts
            summary_lines = ["## Current Work Items Context:"]
            for item in work_items:
                item_line = f"- {item['work_item_type'].upper()}: {item['id']} | {item['state']} | by {item['created_by']} | {item['created_at']}"
                summary_lines.append(item_line)

            work_items_summary = "\n".join(summary_lines)

            return {
                "success": True,
                "work_items": work_items,
                "work_items_summary": work_items_summary,
                "count": len(work_items),
            }
        else:
            logger.info("📝 No work items found in work_items_core view")
            return {
                "success": True,
                "work_items": [],
                "work_items_summary": "## Current Work Items Context:\n- No active work items found in the system.",
                "count": 0,
            }

    except Exception as e:
        logger.error(f"❌ Failed to read work items: {e}")
        return {
            "success": False,
            "error": str(e),
            "work_items_summary": "## Current Work Items Context:\n- Error reading work items from database.",
            "count": 0,
        }


@task(name="setup_simple_mcp_connection")
async def setup_simple_mcp_connection() -> Dict[str, Any]:
    """Setup MCP connection using the PROVEN working approach"""
    logger = get_run_logger()

    try:
        # CRITICAL: Use container-aware path resolution
        # In container: /workspace/services/mcp_server/app/mcp_server.py
        cogni_mcp_path = Path("/workspace/services/mcp_server/app/mcp_server.py")

        if not cogni_mcp_path.exists():
            logger.error(f"❌ Cogni MCP server not found at: {cogni_mcp_path}")
            return {"success": False, "error": "MCP server file not found"}

        logger.info(f"🔧 Using MCP server at: {cogni_mcp_path}")

        # StdioServerParams for Cogni MCP server - PROVEN working config
        server_params = StdioServerParams(
            command="python",
            args=[str(cogni_mcp_path)],
            env={
                # Python path fix for container - CRITICAL
                "PYTHONPATH": "/workspace",  # Add workspace to Python path
                # Dolt connection config
                "DOLT_HOST": "dolt-db",  # Container network hostname
                "DOLT_PORT": "3306",
                "DOLT_USER": "root",
                "DOLT_ROOT_PASSWORD": "kXMnM6firYohXzK+2r0E0DmSjOl6g3A2SmXc6ALDOlA=",
                "DOLT_DATABASE": "cogni-dao-memory",
                "MYSQL_DATABASE": "cogni-dao-memory",
                "CHROMA_PATH": "/tmp/chroma",
                "CHROMA_COLLECTION_NAME": "cogni_mcp_collection",
            },
            read_timeout_seconds=30,
        )

        logger.info("🔧 Setting up Cogni MCP tools via stdio...")
        cogni_tools = await mcp_server_tools(server_params)

        logger.info(f"✅ Cogni MCP tools setup complete: {len(cogni_tools)} tools")
        logger.info(f"🔧 Available tools: {[tool.name for tool in cogni_tools]}")

        return {
            "success": True,
            "tools_count": len(cogni_tools),
            "tools": cogni_tools,
            "tool_names": [tool.name for tool in cogni_tools],
        }

    except Exception as e:
        logger.error(f"❌ Failed to setup Cogni MCP tools: {e}")
        return {"success": False, "error": str(e)}


@task(name="run_simple_3_agent_summary")
async def run_simple_3_agent_summary(
    mcp_setup: Dict[str, Any], work_items_context: Dict[str, Any]
) -> Dict[str, Any]:
    """Run 3 agents to read and summarize active work items - Enhanced with work item context"""
    logger = get_run_logger()

    if not mcp_setup.get("success"):
        return {"success": False, "error": "MCP setup failed"}

    try:
        # Setup OpenAI client
        model_client = OpenAIChatCompletionClient(model="gpt-4o")
        logger.info("✅ OpenAI client configured")

        cogni_tools = mcp_setup["tools"]

        # Get work items context for agent prompts
        work_items_summary = work_items_context.get(
            "work_items_summary", "## Current Work Items Context:\n- No context available."
        )

        # Create 3 enhanced agents with work item context
        agents = []

        # Agent 1: Work Item Reader - Enhanced with current context
        work_reader = AssistantAgent(
            name="work_reader",
            model_client=model_client,
            tools=cogni_tools,
            system_message=f"""You read active work items from Cogni memory. Use GetActiveWorkItems to retrieve current work items and report what you find.

{work_items_summary}

Based on this context, focus on identifying any new or changed work items.""",
        )
        agents.append(work_reader)

        # Agent 2: Priority Analyzer - Enhanced with current context
        priority_analyzer = AssistantAgent(
            name="priority_analyzer",
            model_client=model_client,
            tools=cogni_tools,
            system_message=f"""You analyze work item priorities. Look at the work items and identify which are highest priority (P0, P1) and what needs attention.

{work_items_summary}

Based on this context, analyze priority distribution and identify urgent items.""",
        )
        agents.append(priority_analyzer)

        # Agent 3: Summary Writer - Enhanced with current context
        summary_writer = AssistantAgent(
            name="summary_writer",
            model_client=model_client,
            system_message=f"""You write concise summaries. Based on what the other agents found, create a brief, clear summary of the current work status.

{work_items_summary}

Use this context to provide a comprehensive summary including trends and status updates.""",
        )
        agents.append(summary_writer)

        # Create simple team
        team = RoundRobinGroupChat(
            participants=agents,
            termination_condition=MaxMessageTermination(max_messages=6),  # 2 rounds
        )

        logger.info("🚀 Starting 3-agent work item summary with enhanced context...")

        # Enhanced task with context awareness
        enhanced_task = f"""Please work together to: 
1) Read the current active work items using GetActiveWorkItems
2) Analyze their priorities and status  
3) Write a brief summary of what's currently being worked on

You have the following context about recent work items:
{work_items_summary}"""

        # Run the team
        await Console(team.run_stream(task=enhanced_task))

        logger.info("✅ 3-agent summary with enhanced context completed successfully!")

        return {
            "success": True,
            "agents_count": len(agents),
            "tools_count": len(cogni_tools),
            "work_items_count": work_items_context.get("count", 0),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ 3-agent summary failed: {e}")
        return {"success": False, "error": str(e)}


@flow(name="simple_working_mcp_flow", log_prints=True)
async def simple_working_mcp_flow() -> Dict[str, Any]:
    """
    Ultra-Simple Working MCP Flow - Enhanced with Work Item Context

    Uses proven working MCP integration to run 3 agents that:
    1. Read current work items context using DoltMySQLReader
    2. Read active work items via MCP tools
    3. Analyze priorities with enhanced context
    4. Write summary with full context awareness
    """
    logger = get_run_logger()
    logger.info("🎯 Starting Enhanced Simple Working MCP Flow")
    logger.info("🔧 Using PROVEN working stdio MCP transport + DoltMySQLReader context")

    try:
        # Step 1: Read current work items for context
        work_items_context = await read_current_work_items()

        if work_items_context.get("success"):
            logger.info(f"✅ Work items context loaded: {work_items_context.get('count', 0)} items")
        else:
            logger.warning(
                f"⚠️ Work items context failed: {work_items_context.get('error', 'Unknown error')}"
            )

        # Step 2: Setup MCP connection
        mcp_setup = await setup_simple_mcp_connection()

        if not mcp_setup.get("success"):
            logger.error(f"❌ MCP setup failed: {mcp_setup.get('error')}")
            return {"status": "failed", "error": mcp_setup.get("error")}

        logger.info(f"✅ MCP setup successful: {mcp_setup['tools_count']} tools available")

        # Step 3: Run 3-agent summary with enhanced context
        summary_result = await run_simple_3_agent_summary(mcp_setup, work_items_context)

        if summary_result.get("success"):
            logger.info("🎉 FLOW SUCCESS: Enhanced simple working MCP flow completed!")
            return {
                "status": "success",
                "tools_count": summary_result.get("tools_count", 0),
                "agents_count": summary_result.get("agents_count", 0),
                "work_items_count": summary_result.get("work_items_count", 0),
                "timestamp": datetime.now().isoformat(),
            }
        else:
            logger.error(f"❌ Agent summary failed: {summary_result.get('error')}")
            return {"status": "failed", "error": summary_result.get("error")}

    except Exception as e:
        logger.error(f"💥 FLOW FAILURE: {str(e)}")
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    # For testing the flow locally
    import asyncio

    asyncio.run(simple_working_mcp_flow())
