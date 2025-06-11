#!/usr/bin/env python3
"""
AutoGen MCP + Cogni Memory Integration
Building on our working math server pattern, now connecting to actual Cogni MCP tools

This follows our PROVEN pattern from autogen_mcp_dual_transport.py but replaces
the local math server with the working Cogni MCP server from healthcheck.

Strategy: Simple, elegant adaptation of working approach
"""

import asyncio
import logging
import os
from pathlib import Path

# AutoGen MCP Integration - Following our WORKING pattern
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.tools.mcp import StdioServerParams, mcp_server_tools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutoGenCogniSimple:
    """
    Simple AutoGen + Cogni MCP integration
    Uses the EXACT working pattern from our math server success
    Just swaps the tool source from math_server.py to Cogni MCP
    """

    def __init__(self):
        self.model_client = None
        self.cogni_tools = []  # Cogni MCP tools via stdio
        self.agent = None

    def setup_openai_client(self) -> bool:
        """Setup OpenAI client - same as working version"""
        try:
            if not os.getenv("OPENAI_API_KEY"):
                logger.error("❌ OPENAI_API_KEY environment variable not set")
                return False

            self.model_client = OpenAIChatCompletionClient(model="gpt-4o")
            logger.info("✅ OpenAI client configured")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to setup OpenAI client: {e}")
            return False

    async def setup_cogni_tools_stdio(self):
        """Setup Cogni MCP tools via stdio - adapting our working math pattern"""
        try:
            # Path to the actual Cogni MCP server
            cogni_mcp_path = (
                Path.cwd().parent.parent / "services" / "mcp_server" / "app" / "mcp_server.py"
            )

            if not cogni_mcp_path.exists():
                logger.error("❌ Cogni MCP server not found at expected paths")
                return False

            # StdioServerParams for Cogni MCP server - same pattern as math server
            server_params = StdioServerParams(
                command="python",
                args=[str(cogni_mcp_path)],
                env={
                    **os.environ,
                    # Add Cogni environment variables from deploy/.env
                    "DOLT_HOST": os.getenv(
                        "DOLT_HOST", "localhost"
                    ),  # localhost since we're outside Docker
                    "DOLT_PORT": os.getenv("DOLT_PORT", "3306"),
                    "DOLT_USER": os.getenv("DOLT_USER", "root"),
                    "DOLT_ROOT_PASSWORD": os.getenv(
                        "DOLT_ROOT_PASSWORD", "kXMnM6firYohXzK+2r0E0DmSjOl6g3A2SmXc6ALDOlA="
                    ),
                    "DOLT_DATABASE": "cogni-dao-memory",  # Override the memory_dolt default
                    "MYSQL_DATABASE": "cogni-dao-memory",  # Primary env var used by DoltConnectionConfig
                    "CHROMA_PATH": os.getenv("CHROMA_PATH", "/tmp/chroma"),
                    "CHROMA_COLLECTION_NAME": os.getenv(
                        "CHROMA_COLLECTION_NAME", "cogni_mcp_collection"
                    ),
                },
                read_timeout_seconds=30,
            )

            logger.info("🔧 Setting up Cogni MCP tools via stdio...")
            self.cogni_tools = await mcp_server_tools(server_params)

            logger.info(f"✅ Cogni MCP tools setup complete: {len(self.cogni_tools)} tools")
            logger.info(f"Cogni tools: {[tool.name for tool in self.cogni_tools]}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to setup Cogni MCP tools: {e}")
            return False

    def create_agent(self) -> AssistantAgent:
        """Create AutoGen agent with Cogni MCP tools - same as working version"""

        if not self.model_client:
            raise RuntimeError("Model client must be setup first")

        if not self.cogni_tools:
            logger.warning("⚠️ No Cogni MCP tools available")

        logger.info(f"🔧 Creating agent with {len(self.cogni_tools)} Cogni tools")

        # Create assistant agent with Cogni memory tools
        agent = AssistantAgent(
            name="cogni_assistant",
            model_client=self.model_client,
            tools=self.cogni_tools,
            system_message="""You are an AI assistant with access to the Cogni memory system.

Available capabilities:
- Query and search memory blocks (knowledge, tasks, projects, docs)
- Create and update work items and memory blocks  
- Manage memory links and relationships
- Search semantic memory using embeddings

When given a task:
1. Determine which memory operations are needed
2. Use appropriate Cogni tools to access or modify memory
3. Provide clear, helpful responses based on the memory system

Be specific about which memory tools you're using and why.""",
        )

        logger.info("✅ Cogni assistant agent created successfully")
        return agent

    async def run_simple_test(self) -> bool:
        """Run simple test of Cogni MCP integration"""
        logger.info("🚀 Starting AutoGen + Cogni MCP Simple Test")

        try:
            # Setup OpenAI client
            if not self.setup_openai_client():
                return False

            # Setup Cogni MCP tools
            if not await self.setup_cogni_tools_stdio():
                return False

            # Create agent
            self.agent = self.create_agent()

            # Create simple team
            team = RoundRobinGroupChat(
                participants=[self.agent],
                termination_condition=MaxMessageTermination(max_messages=3),
            )

            logger.info("\n" + "=" * 50)
            logger.info("🧠 Testing Cogni Memory Access...")

            # Simple memory query task
            memory_task = "Please check what memory blocks are currently available in the system. Show me a summary of what's in the Cogni memory."
            logger.info(f"📝 Task: {memory_task}")

            await Console(team.run_stream(task=memory_task))

            logger.info("✅ AutoGen + Cogni MCP Simple Test completed successfully!")
            return True

        except Exception as e:
            logger.error(f"❌ AutoGen + Cogni MCP test failed: {e}")
            return False


async def main():
    """Main execution function"""
    demo = AutoGenCogniSimple()
    success = await demo.run_simple_test()

    if success:
        logger.info("\n🎉 SUCCESS: AutoGen + Cogni MCP integration working!")
    else:
        logger.error("\n💥 FAILED: AutoGen + Cogni MCP integration issues")

    return success


if __name__ == "__main__":
    asyncio.run(main())
