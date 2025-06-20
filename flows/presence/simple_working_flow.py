#!/usr/bin/env python3
"""
Ultra-Simple Working MCP Flow for Prefect Container
===================================================

Minimal Prefect flow that uses our PROVEN working MCP integration.
Based on autogen_mcp_cogni_simple_working.py that achieved 21/21 tools discovery.

Goal: 3 agents read active work items and summarize them.
Enhanced with DoltMySQLReader to provide work item context in agent prompts.
Enhanced with official MCP Python SDK for direct tool calling.
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

# Official MCP Python SDK - Direct usage!
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

# Shared tasks - import the functions we'll use
from .shared_tasks import setup_cogni_mcp_connection, read_work_items_context  # noqa: E402

# Prompt template integration
from infra_core.prompt_templates import render_work_reader_prompt  # noqa: E402
from infra_core.prompt_templates import render_priority_analyzer_prompt  # noqa: E402
from infra_core.prompt_templates import render_summary_writer_prompt  # noqa: E402
from infra_core.prompt_templates import render_cogni_leader_prompt  # noqa: E402
from infra_core.prompt_templates import render_dolt_commit_agent_prompt  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO)


@task(name="setup_official_mcp_connection")
async def setup_official_mcp_connection() -> Dict[str, Any]:
    """Setup MCP connection using the official MCP Python SDK directly"""
    logger = get_run_logger()
    logger.info("🔧 Setting up MCP connection using official MCP Python SDK")

    try:
        # Configure MCP server parameters for stdio transport
        # This connects to the cogni-mcp server using the MCP SDK directly
        server_params = StdioServerParameters(
            command="python",  # or whatever command runs your MCP server
            args=["-m", "services.mcp_server.app.mcp_server"],  # adjust path as needed
            env=None,
        )

        # Create stdio client connection using official MCP SDK
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                # Initialize the MCP session
                await session.initialize()

                # List available tools using official SDK
                tools_response = await session.list_tools()
                available_tools = tools_response.tools

                logger.info(f"✅ Official MCP SDK connected! Found {len(available_tools)} tools:")
                for tool in available_tools:
                    logger.info(f"   - {tool.name}: {tool.description}")

                # Test a simple tool call
                if available_tools:
                    test_tool = available_tools[0]
                    logger.info(f"🧪 Testing tool call: {test_tool.name}")

                    # Example: Call DoltStatus or another simple tool
                    if test_tool.name == "DoltStatus":
                        result = await session.call_tool("DoltStatus", {})
                        logger.info(f"✅ Test tool call successful: {result.content}")

                return {
                    "success": True,
                    "tools_count": len(available_tools),
                    "tools": [
                        {"name": tool.name, "description": tool.description}
                        for tool in available_tools
                    ],
                    "connection_type": "official_mcp_sdk",
                    "transport": "stdio",
                    "session": session,  # Note: This won't persist outside the context
                    "timestamp": datetime.now().isoformat(),
                }

    except Exception as e:
        logger.error(f"❌ Official MCP SDK connection failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "connection_type": "official_mcp_sdk",
            "timestamp": datetime.now().isoformat(),
        }


@task(name="call_mcp_tool_directly")
async def call_mcp_tool_directly(
    tool_name: str, tool_args: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Call an MCP tool directly using the official MCP Python SDK"""
    logger = get_run_logger()
    logger.info(f"🔧 Calling MCP tool '{tool_name}' directly using official SDK")

    if tool_args is None:
        tool_args = {}

    try:
        # Configure MCP server parameters
        server_params = StdioServerParameters(
            command="python", args=["-m", "services.mcp_server.app.mcp_server"], env=None
        )

        # Create connection and call tool
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call the specified tool
                result = await session.call_tool(tool_name, tool_args)

                logger.info(f"✅ Tool '{tool_name}' called successfully")

                return {
                    "success": True,
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "result": result.content,
                    "timestamp": datetime.now().isoformat(),
                }

    except Exception as e:
        logger.error(f"❌ MCP tool call failed: {e}")
        return {
            "success": False,
            "tool_name": tool_name,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


@task(name="run_simple_4_agent_summary_with_outro")
async def run_simple_4_agent_summary_with_outro(
    mcp_setup: Dict[str, Any],
    work_items_context: Dict[str, Any],
    official_mcp_setup: Dict[str, Any],
) -> Dict[str, Any]:
    """Run 4 agents to read and summarize active work items, then handle Dolt operations - All in one simple task using proven working pattern"""
    logger = get_run_logger()

    if not mcp_setup.get("success"):
        return {"success": False, "error": "MCP setup failed"}

    try:
        # Setup OpenAI client - Helicone observability handled automatically by sitecustomize.py
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

        # Log the official MCP SDK connection status
        if official_mcp_setup.get("success"):
            logger.info(
                f"🚀 Official MCP SDK also connected with {official_mcp_setup.get('tools_count', 0)} tools!"
            )

            # Demonstrate direct tool calling with official SDK
            logger.info("🧪 Testing direct MCP tool call...")
            direct_tool_result = await call_mcp_tool_directly("DoltStatus")
            if direct_tool_result.get("success"):
                logger.info(
                    f"✅ Direct MCP tool call successful: {direct_tool_result.get('result')}"
                )
            else:
                logger.warning(f"⚠️ Direct MCP tool call failed: {direct_tool_result.get('error')}")

        # Create 4 enhanced agents with work item context AND tool specifications
        agents = []

        # Agent 1: Work Item Reader - Enhanced with context and tool specs
        work_reader = AssistantAgent(
            name="work_reader",
            model_client=model_client,
            tools=cogni_tools,
            system_message=render_work_reader_prompt(tool_specs_text, work_items_summary),
        )
        agents.append(work_reader)

        # Agent 2: Priority Analyzer - Enhanced with context and tool specs
        priority_analyzer = AssistantAgent(
            name="priority_analyzer",
            model_client=model_client,
            tools=cogni_tools,
            system_message=render_priority_analyzer_prompt(tool_specs_text, work_items_summary),
        )
        agents.append(priority_analyzer)

        # Agent 3: Summary Writer - Enhanced with context and tool specs
        summary_writer = AssistantAgent(
            name="summary_writer",
            model_client=model_client,
            system_message=render_summary_writer_prompt(tool_specs_text, work_items_summary),
        )
        agents.append(summary_writer)

        # Agent 4: Omnipresent Cogni Leader - The visionary strategic agent
        cogni_leader = AssistantAgent(
            name="cogni_leader",
            model_client=model_client,
            tools=cogni_tools,
            system_message=render_cogni_leader_prompt(tool_specs_text, work_items_summary),
        )
        agents.append(cogni_leader)

        # Create simple team
        team = RoundRobinGroupChat(
            participants=agents,
            termination_condition=MaxMessageTermination(max_messages=8),  # Increased for 4 agents
        )

        logger.info("🚀 Starting 4-agent work item summary with omnipresent Cogni leader...")

        # Enhanced task with context awareness and Cogni leadership
        enhanced_task = f"""Please work together to: 
1) Read the current active work items using GetActiveWorkItems
2) Analyze their priorities and status  
3) Write a brief summary of what's currently being worked on
4) **COGNI LEADER**: Query Cogni Memory and identify the most important, easiest to implement improvement for the next run. Create a log memory block with your strategic insights.

You have the following context about recent work items:
{work_items_summary}

Important: Use the tool specifications provided in your system message to ensure correct input formats and avoid validation errors.

🆕 NOTE: We now have BOTH the original MCP connection AND the official MCP Python SDK running in parallel! This demonstrates dual connectivity approaches."""

        # Run the team
        await Console(team.run_stream(task=enhanced_task))

        logger.info("✅ 4-agent summary with omnipresent Cogni leader completed successfully!")

        # === OUTRO ROUTINE: Dolt Operations (Simplified) ===
        logger.info("🔄 Starting outro routine: Systematic Dolt operations...")

        # Create dedicated Dolt commit agent using the same MCP connection
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

        logger.info("🚀 Starting Dolt commit operations...")

        # Run Dolt operations
        await Console(dolt_team.run_stream(task="Begin the dolt commit and push process."))

        logger.info("✅ Outro routine completed successfully!")

        return {
            "success": True,
            "agents_count": len(agents),
            "tools_count": len(cogni_tools),
            "work_items_count": work_items_context.get("count", 0),
            "outro_success": True,
            "official_mcp_success": official_mcp_setup.get("success", False),
            "official_mcp_tools_count": official_mcp_setup.get("tools_count", 0),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Enhanced flow with outro failed: {e}")
        return {"success": False, "error": str(e)}


@flow(name="simple_working_mcp_flow", log_prints=True)
async def simple_working_mcp_flow() -> Dict[str, Any]:
    """
    Ultra-Simple Working MCP Flow - Enhanced with Official MCP SDK

    Uses proven working AutoGen pattern to run 4 agents + Dolt operations in one streamlined task:
    1. Read current work items context using DoltMySQLReader
    2. Setup MCP connection with proven stdio transport
    3. Setup ADDITIONAL connection using official MCP Python SDK
    4. Run unified agent workflow that includes:
       - Work item reader with context
       - Priority analyzer with enhanced context
       - Summary writer with comprehensive context
       - **Omnipresent Cogni Leader** for strategic insights
       - **Integrated Dolt operations** for automatic persistence

    All using the PROVEN working import pattern PLUS official MCP SDK for maximum reliability.
    """
    logger = get_run_logger()
    logger.info("🎯 Starting Enhanced Simple Working MCP Flow with Official MCP SDK")
    logger.info(
        "🔧 Using PROVEN working stdio MCP transport + Official MCP Python SDK + DoltMySQLReader context + Omnipresent AI"
    )

    try:
        # Step 1: Read current work items for context
        work_items_context = await read_work_items_context(branch="main")

        if work_items_context.get("success"):
            logger.info(f"✅ Work items context loaded: {work_items_context.get('count', 0)} items")
        else:
            logger.warning(
                f"⚠️ Work items context failed: {work_items_context.get('error', 'Unknown error')}"
            )

        # Step 2: Setup original MCP connection (proven working)
        mcp_setup = await setup_cogni_mcp_connection()

        if not mcp_setup.get("success"):
            logger.error(f"❌ Original MCP setup failed: {mcp_setup.get('error')}")
            return {"status": "failed", "error": mcp_setup.get("error")}

        logger.info(f"✅ Original MCP setup successful: {mcp_setup['tools_count']} tools available")

        # Step 3: Setup OFFICIAL MCP Python SDK connection (NEW!)
        official_mcp_setup = await setup_official_mcp_connection()

        if official_mcp_setup.get("success"):
            logger.info(
                f"✅ Official MCP SDK setup successful: {official_mcp_setup['tools_count']} tools available"
            )
        else:
            logger.warning(f"⚠️ Official MCP SDK setup failed: {official_mcp_setup.get('error')}")

        # Step 4: Run 4-agent summary with integrated outro routine (enhanced with both MCP connections)
        summary_result = await run_simple_4_agent_summary_with_outro(
            mcp_setup, work_items_context, official_mcp_setup
        )

        if not summary_result.get("success"):
            logger.error(f"❌ Agent summary with outro failed: {summary_result.get('error')}")
            return {"status": "failed", "error": summary_result.get("error")}

        logger.info(
            "🤖 Cogni Leader has provided strategic insights and Dolt operations completed!"
        )

        # Final success
        logger.info(
            "🎉 FLOW SUCCESS: Enhanced simple working MCP flow with Official MCP SDK completed!"
        )
        return {
            "status": "success",
            "tools_count": summary_result.get("tools_count", 0),
            "agents_count": summary_result.get("agents_count", 0),
            "work_items_count": summary_result.get("work_items_count", 0),
            "outro_success": summary_result.get("outro_success", False),
            "official_mcp_success": summary_result.get("official_mcp_success", False),
            "official_mcp_tools_count": summary_result.get("official_mcp_tools_count", 0),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Enhanced flow failed: {e}")
        return {"status": "failed", "error": str(e)}
    finally:
        # Note: MCP client cleanup is handled automatically by async context managers
        logger.info("🧹 MCP clients cleanup handled by context managers")


if __name__ == "__main__":
    # For testing the flow locally
    import asyncio

    asyncio.run(simple_working_mcp_flow())
