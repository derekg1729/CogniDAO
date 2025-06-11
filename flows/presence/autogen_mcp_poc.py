#!/usr/bin/env python3
"""
AutoGen MCP Proof-of-Concept
Implements native MCP integration using mcp_server_tools with ToolHive MCP server

Based on research findings:
- Uses autogen-ext[mcp] mcp_server_tools (official AutoGen MCP integration)
- Connects to ToolHive MCP server via StdioServerParams
- Replaces HTTP glue approach with official MCP protocol

Phase 2 of MCP Integration Implementation Task
"""

import asyncio
import logging
import os
from typing import List

# AutoGen MCP Integration - CORRECT OFFICIAL IMPLEMENTATION
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.tools.mcp import StdioServerParams, mcp_server_tools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutoGenMCPProofOfConcept:
    """
    Proof-of-concept demonstrating official AutoGen MCP integration

    Uses official mcp_server_tools from autogen-ext to connect to
    ToolHive MCP server and access Cogni memory tools
    """

    def __init__(self):
        self.model_client = None
        self.mcp_tools = []
        self.agents = []

    def setup_model_client(self):
        """Setup OpenAI model client for AutoGen agents"""
        try:
            self.model_client = OpenAIChatCompletionClient(
                model="gpt-4o",
                # You can add API key here or use environment variable
            )
            logger.info("✅ Model client setup complete")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to setup model client: {e}")
            return False

    async def setup_mcp_tools(self):
        """Setup MCP tools via ToolHive connection"""
        try:
            # Use ToolHive to run cogni-mcp server via stdio
            # This is the correct way to connect to ToolHive MCP server
            server_params = StdioServerParams(
                command="docker",
                args=["exec", "toolhive", "thv", "run", "cogni-mcp"],
                env={**os.environ},
                read_timeout_seconds=60,
            )

            logger.info("Setting up MCP tools via ToolHive...")
            # This is the OFFICIAL AutoGen approach for MCP integration
            self.mcp_tools = await mcp_server_tools(server_params)

            logger.info(f"✅ MCP tools setup complete with {len(self.mcp_tools)} tools")
            logger.info(f"Available tools: {[tool.name for tool in self.mcp_tools]}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to setup MCP tools: {e}")
            return False

    def create_agents(self) -> List[AssistantAgent]:
        """Create AutoGen agents with MCP tools"""

        if not self.model_client or not self.mcp_tools:
            raise RuntimeError("Model client and MCP tools must be setup first")

        # Agent 1: Memory Retrieval Specialist
        memory_agent = AssistantAgent(
            name="memory_specialist",
            model_client=self.model_client,
            tools=self.mcp_tools,  # MCP tools automatically available
            system_message="""You are a memory retrieval specialist who excels at accessing and 
            analyzing stored memories and work items. Your role is to:
            - Search for relevant memory blocks using semantic search
            - Retrieve active work items and their current status
            - Gather context about recent activities and decisions
            - Provide comprehensive summaries of findings""",
            reflect_on_tool_use=True,
        )

        # Agent 2: Strategic Analysis Specialist
        analysis_agent = AssistantAgent(
            name="analysis_specialist",
            model_client=self.model_client,
            system_message="""You are a strategic analysis specialist who excels at 
            synthesizing information and providing insights. Your role is to:
            - Analyze information gathered by the memory specialist
            - Identify patterns and connections in the data
            - Generate actionable recommendations
            - Create high-level strategic insights""",
            reflect_on_tool_use=True,
        )

        self.agents = [memory_agent, analysis_agent]
        logger.info(f"✅ Created {len(self.agents)} agents with MCP tool access")
        return self.agents

    async def run_proof_of_concept(self):
        """Run the AutoGen MCP proof-of-concept"""
        logger.info("🚀 Starting AutoGen MCP Proof-of-Concept")

        try:
            # Setup model client
            if not self.setup_model_client():
                return False

            # Setup MCP tools
            if not await self.setup_mcp_tools():
                return False

            if not self.mcp_tools:
                logger.warning("⚠️ No MCP tools available - check server connection")
                return False

            # Create agents
            agents = self.create_agents()

            # Create team with termination condition
            team = RoundRobinGroupChat(
                agents, termination_condition=MaxMessageTermination(max_messages=10)
            )

            # Run the team
            logger.info("🔄 Running AutoGen team with MCP tools...")

            task_message = """Analyze the current state of our projects and work items:
            1. Search for recent memory blocks and active work items
            2. Identify high-priority tasks and current project status
            3. Provide strategic recommendations for next steps
            4. Generate a comprehensive status summary"""

            # Use Console for interactive display
            await Console(team.run_stream(task=task_message))

            logger.info("✅ AutoGen MCP proof-of-concept completed successfully!")
            return True

        except Exception as e:
            logger.error(f"❌ AutoGen MCP proof-of-concept failed: {e}")
            return False


async def main():
    """Main execution function"""
    poc = AutoGenMCPProofOfConcept()
    success = await poc.run_proof_of_concept()

    if success:
        print("\n✅ AutoGen MCP Integration Proof-of-Concept: SUCCESS")
    else:
        print("\n❌ AutoGen MCP Integration Proof-of-Concept: FAILED")


if __name__ == "__main__":
    asyncio.run(main())
