#!/usr/bin/env python3
"""
Ultra-Simple Working MCP Flow for Prefect Container
===================================================

Minimal Prefect flow that uses our PROVEN working MCP integration.
Based on autogen_mcp_cogni_simple_working.py that achieved 21/21 tools discovery.

Goal: 3 agents read active work items and summarize them.
"""

import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from prefect import flow, task
from prefect.logging import get_run_logger

# AutoGen MCP Integration - Using PROVEN working pattern
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.tools.mcp import StdioServerParams, mcp_server_tools

# Configure logging
logging.basicConfig(level=logging.INFO)


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
async def run_simple_3_agent_summary(mcp_setup: Dict[str, Any]) -> Dict[str, Any]:
    """Run 3 agents to read and summarize active work items - ULTRA SIMPLE"""
    logger = get_run_logger()

    if not mcp_setup.get("success"):
        return {"success": False, "error": "MCP setup failed"}

    try:
        # Setup OpenAI client
        model_client = OpenAIChatCompletionClient(model="gpt-4o")
        logger.info("✅ OpenAI client configured")

        cogni_tools = mcp_setup["tools"]

        # Create 3 ultra-simple agents
        agents = []

        # Agent 1: Work Item Reader
        work_reader = AssistantAgent(
            name="work_reader",
            model_client=model_client,
            tools=cogni_tools,
            system_message="You read active work items from Cogni memory. Use GetActiveWorkItems to retrieve current work items and report what you find.",
        )
        agents.append(work_reader)

        # Agent 2: Priority Analyzer
        priority_analyzer = AssistantAgent(
            name="priority_analyzer",
            model_client=model_client,
            tools=cogni_tools,
            system_message="You analyze work item priorities. Look at the work items and identify which are highest priority (P0, P1) and what needs attention.",
        )
        agents.append(priority_analyzer)

        # Agent 3: Summary Writer
        summary_writer = AssistantAgent(
            name="summary_writer",
            model_client=model_client,
            system_message="You write concise summaries. Based on what the other agents found, create a brief, clear summary of the current work status.",
        )
        agents.append(summary_writer)

        # Create simple team
        team = RoundRobinGroupChat(
            participants=agents,
            termination_condition=MaxMessageTermination(max_messages=6),  # 2 rounds
        )

        logger.info("🚀 Starting 3-agent work item summary...")

        # Ultra-simple task
        simple_task = "Please work together to: 1) Read the current active work items, 2) Analyze their priorities, 3) Write a brief summary of what's currently being worked on."

        # Run the team
        await Console(team.run_stream(task=simple_task))

        logger.info("✅ 3-agent summary completed successfully!")

        return {
            "success": True,
            "agents_count": len(agents),
            "tools_count": len(cogni_tools),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ 3-agent summary failed: {e}")
        return {"success": False, "error": str(e)}


@flow(name="simple_working_mcp_flow", log_prints=True)
async def simple_working_mcp_flow() -> Dict[str, Any]:
    """
    Ultra-Simple Working MCP Flow

    Uses proven working MCP integration to run 3 agents that:
    1. Read active work items
    2. Analyze priorities
    3. Write summary
    """
    logger = get_run_logger()
    logger.info("🎯 Starting Ultra-Simple Working MCP Flow")
    logger.info("🔧 Using PROVEN working stdio MCP transport")

    try:
        # Setup MCP connection
        mcp_setup = await setup_simple_mcp_connection()

        if not mcp_setup.get("success"):
            logger.error(f"❌ MCP setup failed: {mcp_setup.get('error')}")
            return {"status": "failed", "error": mcp_setup.get("error")}

        logger.info(f"✅ MCP setup successful: {mcp_setup['tools_count']} tools available")

        # Run 3-agent summary
        summary_result = await run_simple_3_agent_summary(mcp_setup)

        if summary_result.get("success"):
            logger.info("🎉 FLOW SUCCESS: Simple working MCP flow completed!")
            return {
                "status": "success",
                "tools_count": summary_result.get("tools_count", 0),
                "agents_count": summary_result.get("agents_count", 0),
                "timestamp": datetime.now().isoformat(),
            }
        else:
            logger.error(f"❌ Agent summary failed: {summary_result.get('error')}")
            return {"status": "failed", "error": summary_result.get("error")}

    except Exception as e:
        logger.error(f"💥 FLOW FAILURE: {str(e)}")
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    # For local testing
    asyncio.run(simple_working_mcp_flow())
