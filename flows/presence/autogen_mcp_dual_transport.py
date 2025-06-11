#!/usr/bin/env python3
"""
AutoGen MCP Dual Transport Implementation
Following SaM-92/mcp_autogen_sse_stdio reference pattern exactly

Key Changes from Current POC:
- Single agent instead of two-agent system
- Dual transport: stdio (local math) + SSE (remote Apify)
- Direct MCP server connections (no ToolHive)
- Follows proven reference implementation structure

Phase 1: Validate reference pattern works
Phase 2: Replace with Cogni tools
"""

import asyncio
import logging
import os
from pathlib import Path

# AutoGen MCP Integration - Following Reference Pattern
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.tools.mcp import StdioServerParams, SseServerParams, mcp_server_tools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutoGenMCPDualTransport:
    """
    AutoGen MCP implementation following SaM-92 reference pattern

    Demonstrates dual MCP transport integration:
    - Local tools via stdio (math_server.py)
    - Remote tools via SSE (Apify or similar)

    Uses single agent approach from proven reference implementation
    """

    def __init__(self):
        self.model_client = None
        self.local_tools = []  # stdio tools
        self.remote_tools = []  # SSE tools
        self.all_tools = []  # combined tools
        self.agent = None

    def setup_model_client(self):
        """Setup OpenAI model client for AutoGen agent"""
        try:
            self.model_client = OpenAIChatCompletionClient(
                model="gpt-4o",
                # API key from environment variable
            )
            logger.info("✅ Model client setup complete")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to setup model client: {e}")
            return False

    async def setup_local_tools_stdio(self):
        """Setup local MCP tools via stdio (math_server.py)"""
        try:
            # Path to our local math server
            math_server_path = Path(__file__).parent / "math_server.py"

            if not math_server_path.exists():
                logger.error(f"❌ Math server not found: {math_server_path}")
                return False

            # StdioServerParams for local math server - following reference pattern
            server_params = StdioServerParams(
                command="python",
                args=[str(math_server_path)],
                env={**os.environ},
                read_timeout_seconds=30,
            )

            logger.info("🔧 Setting up local MCP tools via stdio...")
            self.local_tools = await mcp_server_tools(server_params)

            logger.info(f"✅ Local tools setup complete: {len(self.local_tools)} tools")
            logger.info(f"Local tools: {[tool.name for tool in self.local_tools]}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to setup local tools: {e}")
            return False

    async def setup_remote_tools_sse(self):
        """Setup remote MCP tools via SSE (Apify Web Browser)"""
        try:
            # Following reference pattern for Apify RAG Web Browser
            # This requires APIFY_API_KEY environment variable
            apify_api_key = os.getenv("APIFY_API_KEY")

            if not apify_api_key:
                logger.warning("⚠️ APIFY_API_KEY not found - skipping remote tools")
                return True  # Not required for Phase 1 testing

            # SSE server params for Apify - following reference pattern
            server_params = SseServerParams(
                url="https://api.apify.com/v2/mcp",
                headers={"Authorization": f"Bearer {apify_api_key}"},
            )

            logger.info("🌐 Setting up remote MCP tools via SSE...")
            self.remote_tools = await mcp_server_tools(server_params)

            logger.info(f"✅ Remote tools setup complete: {len(self.remote_tools)} tools")
            logger.info(f"Remote tools: {[tool.name for tool in self.remote_tools]}")
            return True

        except Exception as e:
            logger.warning(f"⚠️ Failed to setup remote tools (optional): {e}")
            # Remote tools are optional for Phase 1
            return True

    def create_agent(self) -> AssistantAgent:
        """Create single AutoGen agent with all MCP tools - following reference pattern"""

        if not self.model_client:
            raise RuntimeError("Model client must be setup first")

        # Combine all tools (local + remote)
        self.all_tools = self.local_tools + self.remote_tools

        logger.info(
            f"🔧 Combined tools: {len(self.local_tools)} local + {len(self.remote_tools)} remote = {len(self.all_tools)} total"
        )

        if not self.all_tools:
            logger.warning("⚠️ No MCP tools available")

        # Single agent with all tools - following reference pattern
        agent = AssistantAgent(
            name="mcp_assistant",
            model_client=self.model_client,
            tools=self.all_tools,  # All MCP tools available
            system_message="""You are an AI assistant with access to various tools.

Available capabilities:
- Local math operations (add, multiply, subtract, divide)
- Web search and browsing (if remote tools available)

When given a task:
1. Determine which tools are needed
2. Use appropriate tools to gather information or perform calculations
3. Provide clear, helpful responses based on the results

Be specific about which tools you're using and why.""",
            reflect_on_tool_use=True,
        )

        self.agent = agent
        logger.info(f"✅ Created agent with {len(self.all_tools)} MCP tools")
        return agent

    async def run_demonstration(self):
        """Run demonstration following reference pattern"""
        logger.info("🚀 Starting AutoGen MCP Dual Transport Demonstration")

        try:
            # Setup model client
            if not self.setup_model_client():
                return False

            # Setup local tools (stdio)
            if not await self.setup_local_tools_stdio():
                return False

            # Setup remote tools (SSE) - optional
            await self.setup_remote_tools_sse()

            # Create agent AFTER setting up tools
            agent = self.create_agent()

            if not self.all_tools:
                logger.warning("⚠️ No MCP tools available - check server connections")
                return False

            # Create simple team for demonstration
            team = RoundRobinGroupChat(
                [agent], termination_condition=MaxMessageTermination(max_messages=5)
            )

            # Run demonstration tasks following reference pattern
            logger.info("🔄 Running demonstration tasks...")

            # Task 1: Math problem (should use local stdio tools)
            math_task = "Calculate (3 + 5) × 12. Show your work step by step."
            logger.info(f"📝 Task 1 (Math): {math_task}")

            await Console(team.run_stream(task=math_task))

            logger.info("\n" + "=" * 50 + "\n")

            # Task 2: General question (could use remote tools if available)
            if self.remote_tools:
                web_task = "What are the latest news headlines about AI developments?"
                logger.info(f"📝 Task 2 (Web): {web_task}")
                await Console(team.run_stream(task=web_task))
            else:
                simple_task = (
                    "Explain the benefits of the Model Context Protocol (MCP) for AI development."
                )
                logger.info(f"📝 Task 2 (General): {simple_task}")
                await Console(team.run_stream(task=simple_task))

            logger.info("✅ AutoGen MCP Dual Transport demonstration completed successfully!")
            return True

        except Exception as e:
            logger.error(f"❌ AutoGen MCP demonstration failed: {e}")
            return False


async def main():
    """Main execution function"""
    demo = AutoGenMCPDualTransport()
    success = await demo.run_demonstration()

    if success:
        print("\n✅ AutoGen MCP Dual Transport: SUCCESS")
        print("🎯 Phase 1 Complete - Reference pattern validated")
        print("🚀 Ready for Phase 2 - Cogni tool integration")
    else:
        print("\n❌ AutoGen MCP Dual Transport: FAILED")
        print("🔍 Check logs for protocol handshake issues")


if __name__ == "__main__":
    asyncio.run(main())
