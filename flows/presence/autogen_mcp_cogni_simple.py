#!/usr/bin/env python3
"""
AutoGen MCP + Cogni Memory Integration
Connecting to existing ToolHive-managed Cogni MCP container via SSE endpoint

This connects to the actual running MCP container instead of spawning a new process.
Uses SSE transport to the containerized Cogni MCP server managed by ToolHive.

Strategy: Use existing container infrastructure
"""

import asyncio
import logging
import os
from typing import Dict, Any

# AutoGen MCP Integration - Using SSE transport
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.tools.mcp import SseServerParams, mcp_server_tools

# Prefect for secret management
from prefect.variables import Variable

# Python version compatibility for ExceptionGroup
try:
    ExceptionGroup
except NameError:
    # Python < 3.11 compatibility
    class ExceptionGroup(Exception):
        def __init__(self, message, exceptions):
            super().__init__(message)
            self.exceptions = exceptions


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutoGenCogniMCPIntegration:
    """
    Minimal AutoGen + Cogni MCP Integration

    Following the minimal pattern:
    1. Fixed MCP endpoint (no runtime discovery)
    2. Direct Prefect Variable read
    3. Simple SSE connection
    """

    def __init__(self):
        self.openai_client = None
        self.cogni_tools = []
        self.agent = None

    async def setup_openai_client(self) -> bool:
        """Setup OpenAI client with API key from environment"""
        try:
            # Try Prefect Variable first, then environment variable
            try:
                openai_key = await Variable.aget("openai-api-key")
                if openai_key:
                    os.environ["OPENAI_API_KEY"] = openai_key
                    logger.info("✅ Using OpenAI API key from Prefect Variable")
            except Exception:
                logger.info("ℹ️ Using OpenAI API key from environment variable")

            self.openai_client = OpenAIChatCompletionClient(model="gpt-4o")
            logger.info("✅ OpenAI client setup complete")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to setup OpenAI client: {e}")
            return False

    async def setup_cogni_tools_sse(self) -> Dict[str, Any]:
        """Setup Cogni MCP tools via Prefect variable endpoint"""
        try:
            # Get endpoint from Prefect Variable - following minimal pattern
            mcp_url = await Variable.aget("cogni-mcp-sse-url")

            if not mcp_url:
                raise Exception("Prefect variable 'cogni-mcp-sse-url' not found")

            logger.info(f"🔗 Connecting to MCP endpoint: {mcp_url}")

            # Simple SSE connection - following minimal pattern
            server_params = SseServerParams(url=mcp_url)
            self.cogni_tools = await mcp_server_tools(server_params)

            logger.info(f"✅ Connected to Cogni MCP: {len(self.cogni_tools)} tools available")
            logger.info(f"🔧 Available tools: {[tool.name for tool in self.cogni_tools]}")

            return {
                "success": True,
                "tools_count": len(self.cogni_tools),
                "endpoint": mcp_url,
                "tools": [tool.name for tool in self.cogni_tools],
            }

        except Exception as e:
            logger.error(f"❌ MCP Connection Failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "tools_count": 0,
                "endpoint": mcp_url if "mcp_url" in locals() else "unknown",
            }

    def create_agent(self) -> AssistantAgent:
        """Create AutoGen agent with Cogni MCP tools"""
        if not self.openai_client:
            raise RuntimeError("OpenAI client must be setup first")

        if not self.cogni_tools:
            logger.warning("⚠️ No Cogni MCP tools available")

        self.agent = AssistantAgent(
            name="cogni_assistant",
            model_client=self.openai_client,
            tools=self.cogni_tools,
            system_message="""You are an AI assistant with access to Cogni memory and knowledge tools.

Available capabilities:
- Memory block creation, retrieval, and management
- Knowledge base queries and updates  
- Work item tracking and management
- Semantic search across memory blocks

When given a task:
1. Determine which Cogni tools are needed
2. Use appropriate tools to access or update information
3. Provide clear, helpful responses based on the results

Be specific about which tools you're using and why.""",
            reflect_on_tool_use=True,
        )

        logger.info(f"✅ Created agent with {len(self.cogni_tools)} Cogni MCP tools")
        return self.agent

    def get_debug_state(self) -> Dict[str, Any]:
        """Get current integration state for debugging"""
        return {
            "openai_client": "configured" if self.openai_client else "not configured",
            "cogni_tools_count": len(self.cogni_tools),
            "agent": "created" if self.agent else "not created",
            "tools": [tool.name for tool in self.cogni_tools] if self.cogni_tools else [],
        }

    async def run_demonstration(self) -> Dict[str, Any]:
        """Run a simple demonstration of the integration"""
        logger.info("🚀 Starting AutoGen Cogni MCP Demonstration")

        try:
            # Setup OpenAI client
            if not await self.setup_openai_client():
                return {"success": False, "error": "Failed to setup OpenAI client"}

            # Setup Cogni MCP tools
            mcp_result = await self.setup_cogni_tools_sse()
            if not mcp_result["success"]:
                return {"success": False, "error": f"MCP connection failed: {mcp_result['error']}"}

            # Create agent
            agent = self.create_agent()

            if not self.cogni_tools:
                logger.warning("⚠️ No Cogni MCP tools available - check server connection")
                return {"success": False, "error": "No MCP tools available"}

            # Create simple team
            team = RoundRobinGroupChat(
                [agent], termination_condition=MaxMessageTermination(max_messages=3)
            )

            # Run demonstration task
            task = "List the available Cogni memory tools and explain what each one does."
            logger.info(f"📝 Demonstration Task: {task}")

            await Console(team.run_stream(task=task))

            logger.info("✅ AutoGen Cogni MCP demonstration completed successfully!")

            return {
                "success": True,
                "tools_count": len(self.cogni_tools),
                "endpoint": mcp_result["endpoint"],
                "tools": mcp_result["tools"],
            }

        except Exception as e:
            logger.error(f"❌ AutoGen Cogni MCP demonstration failed: {e}")
            return {"success": False, "error": str(e)}


async def main():
    """Main execution function"""
    demo = AutoGenCogniMCPIntegration()
    result = await demo.run_demonstration()

    if result["success"]:
        logger.info("\n🎉 SUCCESS: AutoGen + Cogni MCP integration working!")
    else:
        logger.error("\n💥 FAILED: AutoGen + Cogni MCP integration issues")

    return result


if __name__ == "__main__":
    asyncio.run(main())
