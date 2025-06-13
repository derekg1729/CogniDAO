#!/usr/bin/env python3
"""
AI Swarm Team Template with Cogni Memory MCP Integration
=========================================================

A simple starter template for creating AI agent swarms that can:
- Access and modify Cogni memory (work items, memory blocks, links)
- Coordinate through shared memory system
- Use reliable stdio MCP transport (no networking issues)

Based on successful commit 77a6b4b with 21/21 tools discovery.

Usage:
    python ai_swarm_team_template.py
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict

# AutoGen imports for multi-agent coordination
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.tools.mcp import StdioServerParams, mcp_server_tools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CogniAISwarmTemplate:
    """
    Simple template for AI swarm teams with Cogni memory access

    Features:
    - Multiple specialized AI agents
    - Shared Cogni memory system access via MCP
    - Reliable stdio transport (no Docker/networking dependencies)
    - 21 available tools for memory operations
    """

    def __init__(self):
        self.model_client = None
        self.cogni_tools = []
        self.agents = {}

    def setup_openai_client(self) -> bool:
        """Setup OpenAI client for all agents"""
        try:
            import os

            if not os.getenv("OPENAI_API_KEY"):
                logger.error("❌ OPENAI_API_KEY environment variable not set")
                return False

            self.model_client = OpenAIChatCompletionClient(model="gpt-4o")
            logger.info("✅ OpenAI client configured")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to setup OpenAI client: {e}")
            return False

    async def setup_cogni_memory_tools(self) -> bool:
        """Setup Cogni MCP tools via stdio - WORKING VERSION"""
        try:
            # CRITICAL: Use absolute path resolution relative to this file
            this_file = Path(__file__).resolve()
            project_root = this_file.parent.parent.parent  # flows/presence -> flows -> project_root
            cogni_mcp_path = project_root / "services" / "mcp_server" / "app" / "mcp_server.py"

            if not cogni_mcp_path.exists():
                logger.error(f"❌ Cogni MCP server not found at: {cogni_mcp_path}")
                return False

            logger.info(f"🔧 Connecting to Cogni MCP server at: {cogni_mcp_path}")

            # Stdio transport to MCP server
            server_params = StdioServerParams(
                command="python",
                args=[str(cogni_mcp_path)],
                env={
                    **os.environ,
                    # Cogni environment variables
                    "DOLT_HOST": os.getenv("DOLT_HOST", "localhost"),
                    "DOLT_PORT": os.getenv("DOLT_PORT", "3306"),
                    "DOLT_USER": os.getenv("DOLT_USER", "root"),
                    "DOLT_ROOT_PASSWORD": os.getenv(
                        "DOLT_ROOT_PASSWORD", "kXMnM6firYohXzK+2r0E0DmSjOl6g3A2SmXc6ALDOlA="
                    ),
                    "DOLT_DATABASE": "cogni-dao-memory",
                    "MYSQL_DATABASE": "cogni-dao-memory",
                    "CHROMA_PATH": os.getenv("CHROMA_PATH", "/tmp/chroma"),
                    "CHROMA_COLLECTION_NAME": os.getenv(
                        "CHROMA_COLLECTION_NAME", "cogni_mcp_collection"
                    ),
                },
                read_timeout_seconds=30,
            )

            self.cogni_tools = await mcp_server_tools(server_params)
            logger.info(f"✅ Cogni Memory Tools Connected: {len(self.cogni_tools)} tools available")
            logger.info(f"🔧 Available tools: {[tool.name for tool in self.cogni_tools]}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to setup Cogni memory tools: {e}")
            return False

    def create_specialized_agents(self) -> Dict[str, AssistantAgent]:
        """Create specialized AI agents for different swarm roles"""
        if not self.model_client:
            raise RuntimeError("OpenAI client must be setup first")

        agents = {}

        # 1. Memory Manager Agent - Handles memory operations
        agents["memory_manager"] = AssistantAgent(
            name="memory_manager",
            model_client=self.model_client,
            tools=self.cogni_tools,
            system_message="""You are the Memory Manager for the AI swarm team.

Your responsibilities:
- Create and update work items and memory blocks
- Manage memory links and relationships
- Query memory for information needed by the team
- Keep the memory system organized and clean

Available Cogni memory tools:
- CreateWorkItem, UpdateWorkItem, GetActiveWorkItems
- CreateMemoryBlock, UpdateMemoryBlock, GetMemoryBlock
- CreateBlockLink, GetLinkedBlocks, GetMemoryLinks
- QueryMemoryBlocksSemantic for semantic search
- Dolt tools for version control (DoltCommit, DoltStatus, etc.)

Be efficient and always explain what memory operations you're performing.""",
        )

        # 2. Project Coordinator Agent - Coordinates work and planning
        agents["coordinator"] = AssistantAgent(
            name="coordinator",
            model_client=self.model_client,
            tools=self.cogni_tools,
            system_message="""You are the Project Coordinator for the AI swarm team.

Your responsibilities:
- Plan and coordinate team activities
- Track progress on work items and projects
- Identify blockers and dependencies
- Make strategic decisions about priorities

You have access to Cogni memory tools to:
- Review active work items and project status
- Create new tasks and update existing ones
- Link related work items together
- Query for relevant information and context

Focus on high-level coordination and strategic thinking.""",
        )

        # 3. Technical Specialist Agent - Handles technical tasks
        agents["technical_specialist"] = AssistantAgent(
            name="technical_specialist",
            model_client=self.model_client,
            tools=self.cogni_tools,
            system_message="""You are the Technical Specialist for the AI swarm team.

Your responsibilities:
- Analyze technical problems and propose solutions
- Research technical documentation and requirements
- Create detailed technical specifications
- Validate technical implementations

You can use Cogni memory tools to:
- Research existing technical knowledge
- Document technical decisions and solutions
- Track technical work items and bugs
- Link technical dependencies

Focus on technical accuracy and detailed analysis.""",
        )

        logger.info(f"✅ Created {len(agents)} specialized agents with Cogni memory access")
        return agents

    async def run_swarm_demo(self, task: str) -> bool:
        """Run a demonstration of the AI swarm working together"""
        logger.info("🚀 Starting AI Swarm Team Demo")

        try:
            # Setup
            if not self.setup_openai_client():
                return False

            if not await self.setup_cogni_memory_tools():
                return False

            # Create agents
            self.agents = self.create_specialized_agents()

            # Create team with round-robin coordination
            team = RoundRobinGroupChat(
                participants=list(self.agents.values()),
                termination_condition=MaxMessageTermination(
                    max_messages=9
                ),  # 3 rounds with 3 agents
            )

            logger.info("\n" + "=" * 60)
            logger.info("🤖 AI SWARM TEAM COLLABORATION")
            logger.info("=" * 60)
            logger.info(f"📝 Task: {task}")
            logger.info(f"👥 Team: {list(self.agents.keys())}")
            logger.info(f"🔧 Memory Tools: {len(self.cogni_tools)} available")
            logger.info("=" * 60)

            # Run team collaboration
            await Console(team.run_stream(task=task))

            logger.info("\n✅ AI Swarm Team Demo completed successfully!")
            return True

        except Exception as e:
            logger.error(f"❌ AI Swarm Team Demo failed: {e}")
            return False


# Example usage scenarios
DEMO_TASKS = {
    "project_planning": """
        We need to plan a new project for implementing automated testing workflows. 
        Please work together to:
        1. Research what active work items exist that might be related
        2. Create a new project work item with proper planning
        3. Break it down into specific tasks
        4. Establish dependencies and priorities
    """,
    "technical_research": """
        We need to research the current state of MCP integration issues in our system.
        Please collaborate to:
        1. Query for existing bugs and issues related to MCP/ToolHive
        2. Analyze the technical problems and their root causes
        3. Create a knowledge block with findings and recommendations
        4. Update relevant work items with your analysis
    """,
    "memory_organization": """
        Our memory system needs organization and cleanup.
        Please work together to:
        1. Review current active work items and their status
        2. Identify any duplicate or outdated items
        3. Create proper links between related work items
        4. Suggest improvements to our memory organization
    """,
}


async def main():
    """Main function - run the AI swarm demo"""
    import os

    # Initialize swarm template
    swarm = CogniAISwarmTemplate()

    # Choose demo task
    task_name = os.getenv("DEMO_TASK", "memory_organization")
    task = DEMO_TASKS.get(task_name, DEMO_TASKS["memory_organization"])

    logger.info(f"🎯 Running demo task: {task_name}")

    # Run demonstration
    success = await swarm.run_swarm_demo(task)

    if success:
        logger.info("\n🎉 SUCCESS: AI Swarm Team with Cogni Memory integration working!")
        logger.info("💡 To try different scenarios, set DEMO_TASK environment variable:")
        logger.info("   - project_planning")
        logger.info("   - technical_research")
        logger.info("   - memory_organization")
    else:
        logger.error("\n💥 FAILED: AI Swarm Team Demo encountered issues")

    return success


if __name__ == "__main__":
    import os

    os.chdir(Path(__file__).parent)  # Ensure we're in the right directory
    asyncio.run(main())
