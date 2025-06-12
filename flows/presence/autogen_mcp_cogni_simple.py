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

# AutoGen MCP Integration - Using SSE transport
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.tools.mcp import SseServerParams, mcp_server_tools

# Prefect for secret management
from prefect.blocks.system import Secret

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


class AutoGenCogniSimple:
    """
    Simple AutoGen + Cogni MCP integration
    Connects to existing ToolHive-managed Cogni MCP container via SSE endpoint
    Uses the running containerized MCP server instead of spawning new processes
    """

    def __init__(self):
        self.model_client = None
        self.cogni_tools = []  # Cogni MCP tools via SSE to container
        self.agent = None

    async def setup_openai_client(self) -> bool:
        """Setup OpenAI client using Prefect Secret with environment fallback"""
        try:
            # Try to get API key from Prefect Secret first
            try:
                secret_block = await Secret.load("OPENAI_API_KEY")
                api_key = secret_block.get()
                logger.info("✅ OpenAI API key loaded from Prefect Secret")
            except Exception as e:
                logger.info(f"📝 Prefect Secret not found ({e}), trying environment variable...")
                # Fallback to environment variable
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    logger.info("✅ OpenAI API key loaded from environment variable")

            if not api_key:
                logger.error(
                    "❌ OpenAI API key not found. Set OPENAI_API_KEY environment variable or create a Prefect Secret."
                )
                return False

            self.model_client = OpenAIChatCompletionClient(model="gpt-4o")
            logger.info("✅ OpenAI client configured with gpt-4o")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to setup OpenAI client: {e}")
            return False

    async def get_toolhive_sse_endpoint(self) -> str:
        """Get the SSE endpoint for cogni-mcp from ToolHive"""
        try:
            # For containerized deployment, use internal Docker network
            # ToolHive is accessible at toolhive:8080 within the network
            container_endpoints = [
                os.getenv("COGNI_MCP_SSE_ENDPOINT", "http://toolhive:8080/sse"),
                "http://toolhive:8080/sse",  # Internal Docker network
                "http://127.0.0.1:30758/sse",  # Local development fallback
            ]

            logger.info("🔍 ToolHive SSE Endpoint Discovery:")
            logger.info(
                f"   - Environment Variable COGNI_MCP_SSE_ENDPOINT: {os.getenv('COGNI_MCP_SSE_ENDPOINT', 'Not Set')}"
            )
            logger.info(f"   - Available Endpoints: {container_endpoints}")

            # Use the first available endpoint (prioritize container network)
            sse_endpoint = container_endpoints[0]
            logger.info(f"🎯 Selected SSE endpoint: {sse_endpoint}")
            logger.info(
                "   - Selection Logic: Using first endpoint (environment override or default)"
            )
            logger.info(
                f"   - Container Network: {'Yes' if 'toolhive:8080' in sse_endpoint else 'No'}"
            )
            logger.info(f"   - Local Development: {'Yes' if '127.0.0.1' in sse_endpoint else 'No'}")

            return sse_endpoint

        except Exception as e:
            logger.error(f"❌ Failed to determine ToolHive endpoint: {e}")
            logger.error("🔍 Endpoint Discovery Failure Debug:")
            logger.error(f"   - Exception Type: {type(e).__name__}")
            logger.error(f"   - Exception Details: {str(e)}")
            raise

    async def setup_cogni_tools_sse(self):
        """Setup Cogni MCP tools via SSE - connecting to existing container"""
        try:
            # Get the actual SSE endpoint from ToolHive
            sse_endpoint = await self.get_toolhive_sse_endpoint()

            # SseServerParams for existing containerized Cogni MCP server
            server_params = SseServerParams(
                url=sse_endpoint,
                headers={"Content-Type": "application/json"},
                timeout=30,
                sse_read_timeout=300,
            )

            logger.info(f"🔧 Connecting to existing Cogni MCP container at {sse_endpoint}...")
            logger.info("🔍 SSE Connection Debug Details:")
            logger.info(f"   - URL: {server_params.url}")
            logger.info(f"   - Headers: {server_params.headers}")
            logger.info(f"   - Timeout: {server_params.timeout}s")
            logger.info(f"   - SSE Read Timeout: {server_params.sse_read_timeout}s")

            # Attempt connection with detailed error capture
            try:
                logger.info("🔄 Attempting MCP server tools connection...")
                self.cogni_tools = await mcp_server_tools(server_params)
                logger.info(
                    f"✅ MCP connection successful - raw tools count: {len(self.cogni_tools)}"
                )

            except Exception as connection_error:
                logger.error("❌ MCP Connection Failed - Detailed Error Analysis:")
                logger.error(f"   - Error Type: {type(connection_error).__name__}")
                logger.error(f"   - Error Message: {str(connection_error)}")
                logger.error(f"   - Attempted URL: {sse_endpoint}")

                # Extract sub-exceptions from ExceptionGroup
                if isinstance(connection_error, ExceptionGroup):
                    logger.error("🔍 ExceptionGroup Sub-Exceptions:")
                    for i, sub_exc in enumerate(connection_error.exceptions):
                        logger.error(f"   Sub-Exception {i + 1}:")
                        logger.error(f"     - Type: {type(sub_exc).__name__}")
                        logger.error(f"     - Message: {str(sub_exc)}")
                        if hasattr(sub_exc, "__cause__") and sub_exc.__cause__:
                            logger.error(f"     - Cause: {sub_exc.__cause__}")

                # Try to extract more specific error details
                if hasattr(connection_error, "response"):
                    logger.error(f"   - HTTP Response: {connection_error.response}")
                if hasattr(connection_error, "status_code"):
                    logger.error(f"   - Status Code: {connection_error.status_code}")
                if hasattr(connection_error, "__cause__") and connection_error.__cause__:
                    logger.error(f"   - Root Cause: {connection_error.__cause__}")

                # Re-raise the ORIGINAL exception to preserve stack trace and details
                raise connection_error

            logger.info(f"✅ Cogni MCP tools connected: {len(self.cogni_tools)} tools")
            logger.info(f"🔧 Available tools: {[tool.name for tool in self.cogni_tools]}")

            # Additional debug info about the tools
            if self.cogni_tools:
                logger.info("🔍 Tool Details:")
                for i, tool in enumerate(self.cogni_tools[:5]):  # Show first 5 tools
                    logger.info(
                        f"   {i + 1}. {tool.name} - {getattr(tool, 'description', 'No description')[:50]}..."
                    )
                if len(self.cogni_tools) > 5:
                    logger.info(f"   ... and {len(self.cogni_tools) - 5} more tools")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to connect to Cogni MCP container via SSE: {e}")
            logger.error("🔍 SSE Setup Failure Debug:")
            logger.error(f"   - Exception Type: {type(e).__name__}")
            logger.error(f"   - Exception Details: {str(e)}")
            logger.error(
                f"   - Tools Discovered: {len(self.cogni_tools) if hasattr(self, 'cogni_tools') else 'N/A'}"
            )
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

    async def run_conversation_test(self) -> bool:
        """Run just the conversation test part - assumes setup is already complete"""
        logger.info("🧠 Running AutoGen conversation test with Cogni MCP tools...")

        try:
            if not self.agent:
                raise RuntimeError("Agent must be created before running conversation test")

            # Create simple team
            team = RoundRobinGroupChat(
                participants=[self.agent],
                termination_condition=MaxMessageTermination(max_messages=3),
            )

            logger.info("\n" + "=" * 50)
            logger.info("🧠 Testing Cogni Memory Access...")

            # Simple memory query task
            memory_task = (
                "Please see what Active Work Items are in the system. Show me a concise summary."
            )
            logger.info(f"📝 Task: {memory_task}")

            await Console(team.run_stream(task=memory_task))

            logger.info("✅ AutoGen conversation test completed successfully!")
            return True

        except Exception as e:
            logger.error(f"❌ AutoGen conversation test failed: {e}")
            return False

    async def run_simple_test(self) -> bool:
        """Run simple test of Cogni MCP integration"""
        logger.info("🚀 Starting AutoGen + Cogni MCP Simple Test")

        try:
            # Setup OpenAI client
            if not await self.setup_openai_client():
                return False

            # Setup Cogni MCP tools
            if not await self.setup_cogni_tools_sse():
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
            memory_task = (
                "Please see what Active Work Items are in the system. Show me a concise summary."
            )
            logger.info(f"📝 Task: {memory_task}")

            await Console(team.run_stream(task=memory_task))

            logger.info("✅ AutoGen + Cogni MCP Simple Test completed successfully!")
            return True

        except Exception as e:
            logger.error(f"❌ AutoGen + Cogni MCP test failed: {e}")
            return False

    def get_debug_state(self) -> dict:
        """Get current state of integration for debugging"""
        return {
            "openai_client": "✅ Configured" if self.model_client else "❌ Not configured",
            "cogni_tools_count": len(self.cogni_tools) if self.cogni_tools else 0,
            "cogni_tools_list": [tool.name for tool in self.cogni_tools]
            if self.cogni_tools
            else [],
            "agent": "✅ Created" if self.agent else "❌ Not created",
            "has_memory_tools": any("memory" in tool.name.lower() for tool in self.cogni_tools)
            if self.cogni_tools
            else False,
            "has_work_item_tools": any("work" in tool.name.lower() for tool in self.cogni_tools)
            if self.cogni_tools
            else False,
        }


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
