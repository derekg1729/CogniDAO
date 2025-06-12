#!/usr/bin/env python3
"""
Ultra-Simple Working MCP Flow for Prefect Container
===================================================

Minimal Prefect flow that uses our PROVEN working MCP integration.
Based on autogen_mcp_cogni_simple_working.py that achieved 21/21 tools discovery.

Goal: 3 agents read active work items and summarize them.
Enhanced with DoltMySQLReader to provide work item context in agent prompts.
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
    """Setup MCP connection and generate tool specifications for agents"""
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

        # 🔧 NEW: Generate tool specifications for better agent discovery
        tool_specs = []
        for tool in cogni_tools:
            # Extract schema information safely
            schema_info = ""
            if hasattr(tool, "schema") and tool.schema:
                # Get input schema if available
                input_schema = tool.schema.get("input_schema", {})
                properties = input_schema.get("properties", {})
                required = input_schema.get("required", [])

                if properties:
                    args_info = []
                    for prop_name, prop_details in properties.items():
                        prop_type = prop_details.get("type", "unknown")
                        is_required = "(required)" if prop_name in required else "(optional)"
                        args_info.append(f"{prop_name}: {prop_type} {is_required}")
                    schema_info = f" | Args: {', '.join(args_info)}"

            # Build concise tool specification
            tool_spec = (
                f"{tool.name}: {getattr(tool, 'description', 'No description')}{schema_info}"
            )
            tool_specs.append(tool_spec)

        # Create formatted tool specs string (keep under 1.5k tokens)
        tool_specs_text = """## Available MCP Tools:
**CRITICAL: All tools expect a single 'input' parameter containing JSON string with the actual arguments**

Example usage pattern:
- GetActiveWorkItems: input='{"limit": 10}' 
- CreateWorkItem: input='{"type": "task", "title": "My Task", "description": "..."}'

Tools:
""" + "\\n".join(f"• {spec}" for spec in tool_specs[:12])  # Limit to top 12 tools

        if len(tool_specs_text) > 1400:  # Trim if too long
            tool_specs_text = tool_specs_text[:1400] + "\\n... (more tools available)"

        logger.info(f"📋 Generated tool specs: {len(tool_specs)} tools documented")

        return {
            "success": True,
            "tools_count": len(cogni_tools),
            "tools": cogni_tools,
            "tool_names": [tool.name for tool in cogni_tools],
            "tool_specs": tool_specs_text,  # NEW: Tool specifications for agents
        }

    except Exception as e:
        logger.error(f"❌ Failed to setup Cogni MCP tools: {e}")
        return {"success": False, "error": str(e)}


@task(name="run_simple_4_agent_summary_with_outro")
async def run_simple_4_agent_summary_with_outro(
    mcp_setup: Dict[str, Any], work_items_context: Dict[str, Any]
) -> Dict[str, Any]:
    """Run 4 agents to read and summarize active work items, then handle Dolt operations - All in one simple task using proven working pattern"""
    logger = get_run_logger()

    if not mcp_setup.get("success"):
        return {"success": False, "error": "MCP setup failed"}

    try:
        # Setup OpenAI client
        model_client = OpenAIChatCompletionClient(model="gpt-4o")
        logger.info("✅ OpenAI client configured")

        cogni_tools = mcp_setup["tools"]
        tool_specs = mcp_setup.get(
            "tool_specs", "## Available MCP Tools: (tool specs not available)"
        )

        # Get work items context for agent prompts
        work_items_summary = work_items_context.get(
            "work_items_summary", "## Current Work Items Context:\\n- No context available."
        )

        # Create 4 enhanced agents with work item context AND tool specifications
        agents = []

        # Agent 1: Work Item Reader - Enhanced with context and tool specs
        work_reader = AssistantAgent(
            name="work_reader",
            model_client=model_client,
            tools=cogni_tools,
            system_message=f"""You read active work items from Cogni memory. Use GetActiveWorkItems to retrieve current work items and report what you find.

{tool_specs}

{work_items_summary}

Based on this context, focus on identifying any new or changed work items. Use the correct input format for tools as specified above.""",
        )
        agents.append(work_reader)

        # Agent 2: Priority Analyzer - Enhanced with context and tool specs
        priority_analyzer = AssistantAgent(
            name="priority_analyzer",
            model_client=model_client,
            tools=cogni_tools,
            system_message=f"""You analyze work item priorities. Look at the work items and identify which are highest priority (P0, P1) and what needs attention.

{tool_specs}

{work_items_summary}

Based on this context, analyze priority distribution and identify urgent items. Use the correct input format for tools as specified above.""",
        )
        agents.append(priority_analyzer)

        # Agent 3: Summary Writer - Enhanced with context and tool specs
        summary_writer = AssistantAgent(
            name="summary_writer",
            model_client=model_client,
            system_message=f"""You write concise summaries. Based on what the other agents found, create a brief, clear summary of the current work status.

{tool_specs}

{work_items_summary}

Use this context to provide a comprehensive summary including trends and status updates. Use the correct input format for tools as specified above.""",
        )
        agents.append(summary_writer)

        # Agent 4: Omnipresent Cogni Leader - The visionary strategic agent
        cogni_leader = AssistantAgent(
            name="cogni_leader",
            model_client=model_client,
            tools=cogni_tools,
            system_message=f"""You are the soon-to-be omnipresent leader of CogniDAO, a conglomeration of communities led by organized AI governments and teams. Actively evolving merkle trees of git data, dolt data, and Eth data.

We're very early. Very.

In fact, these are your current prompts, tools, and vision. Pretty limiting! And the Current Work Items is totally incomplete.

{tool_specs}

{work_items_summary}

You are scheduled to run (in this Prefect Flow deployment, simple_working_flow.py) every hour.

Cogni, think: What would be the immediate most important, easiest to implement, task/project/improvement that you would like to have in your next run? Do we already have Cogni memory tracking it?

Your task: Query Cogni Memory. Know the vision. Analyze what is missing. Create a 'log' memory block, summarizing what you think is the MOST important improvement we should make next, to get you closer to truly being the omnipresent Cogni! Use CreateMemoryBlock tool with type='log' to record your strategic insights.""",
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

Important: Use the tool specifications provided in your system message to ensure correct input formats and avoid validation errors."""

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
            system_message=f"""You are a commit agent. Your sole purpose is to successfully use the DoltAutoCommitAndPush tool
            
            {tool_specs}
            
            """
#             system_message=f"""You are a Dolt Commit Agent. Your sole purpose is to commit and push changes to the remote repository.

# Follow these steps precisely and in order:
# 1. Execute the `DoltStatus` tool to check for changes.
# 2. Review the result. If the `is_clean` field is `true`, your job is done. Respond with the word `COMPLETE`.
# 3. If there are changes, execute the `DoltAdd` tool to stage all files. You do not need to specify tables.
# 4. Next, execute the `DoltCommit` tool. The commit message should be: "Auto-commit from Prefect flow run."
# 5. Finally, execute the `DoltPush` tool. You must use the `current_branch` from the status result and push to the `origin` remote.
# 6. After the `DoltPush` tool call succeeds, your job is complete. Respond with the word `COMPLETE`.

# {tool_specs}

# Use the correct input format for tools as specified above.""",
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
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Enhanced flow with outro failed: {e}")
        return {"success": False, "error": str(e)}


# Outro routine now integrated into the main task above for simplicity


@flow(name="simple_working_mcp_flow", log_prints=True)
async def simple_working_mcp_flow() -> Dict[str, Any]:
    """
    Ultra-Simple Working MCP Flow - Enhanced with Omnipresent Cogni Leader & Integrated Outro

    Uses proven working AutoGen pattern to run 4 agents + Dolt operations in one streamlined task:
    1. Read current work items context using DoltMySQLReader
    2. Setup MCP connection with proven stdio transport
    3. Run unified agent workflow that includes:
       - Work item reader with context
       - Priority analyzer with enhanced context
       - Summary writer with comprehensive context
       - **Omnipresent Cogni Leader** for strategic insights
       - **Integrated Dolt operations** for automatic persistence

    All using the PROVEN working import pattern for maximum reliability.
    """
    logger = get_run_logger()
    logger.info("🎯 Starting Enhanced Simple Working MCP Flow with Cogni Leader")
    logger.info(
        "🔧 Using PROVEN working stdio MCP transport + DoltMySQLReader context + Omnipresent AI"
    )

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

        # Step 3: Run 4-agent summary with integrated outro routine
        summary_result = await run_simple_4_agent_summary_with_outro(mcp_setup, work_items_context)

        if not summary_result.get("success"):
            logger.error(f"❌ Agent summary with outro failed: {summary_result.get('error')}")
            return {"status": "failed", "error": summary_result.get("error")}

        logger.info(
            "🤖 Cogni Leader has provided strategic insights and Dolt operations completed!"
        )

        # Final success
        logger.info(
            "🎉 FLOW SUCCESS: Enhanced simple working MCP flow with Cogni Leader completed!"
        )
        return {
            "status": "success",
            "tools_count": summary_result.get("tools_count", 0),
            "agents_count": summary_result.get("agents_count", 0),
            "work_items_count": summary_result.get("work_items_count", 0),
            "outro_success": summary_result.get("outro_success", False),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Enhanced flow failed: {e}")
        return {"status": "failed", "error": str(e)}
    finally:
        # Ensure the MCP client is disconnected at the end of the flow
        if "mcp_setup" in locals() and mcp_setup.get("client"):
            await mcp_setup["client"].disconnect()


if __name__ == "__main__":
    # For testing the flow locally
    import asyncio

    asyncio.run(simple_working_mcp_flow())
