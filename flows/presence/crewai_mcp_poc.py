#!/usr/bin/env python3
"""
CrewAI MCP Proof-of-Concept
Implements native MCP integration using MCPServerAdapter with ToolHive MCP server

Based on research findings:
- Uses crewai-tools[mcp] MCPServerAdapter (official CrewAI MCP integration)
- Connects to ToolHive MCP server via correct SSE endpoint pattern
- Replaces HTTP glue approach with official MCP protocol

Phase 3 of MCP Integration Implementation Task
"""

import asyncio
import logging
from typing import List, Any

# CrewAI MCP Integration - CORRECT OFFICIAL IMPLEMENTATION
from crewai import Agent, Task, Crew
from crewai_tools import MCPServerAdapter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CrewAIMCPProofOfConcept:
    """
    Proof-of-concept demonstrating official CrewAI MCP integration

    Uses official MCPServerAdapter from crewai-tools to connect to
    ToolHive MCP server and access Cogni memory tools
    """

    def __init__(self):
        self.crew = None

    def create_crew(self, mcp_tools: List[Any]) -> Crew:
        """Create CrewAI crew with MCP-enabled agents"""

        # Create agents with MCP tools
        memory_agent = Agent(
            role="Memory Retrieval Specialist",
            goal="Retrieve and analyze memory blocks from Cogni memory system",
            backstory="You are an expert at accessing and interpreting stored memories and work items.",
            tools=mcp_tools,  # MCP tools automatically available
            verbose=True,
        )

        analysis_agent = Agent(
            role="Analysis Specialist",
            goal="Analyze retrieved information and provide insights",
            backstory="You excel at synthesizing information and providing actionable insights.",
            tools=mcp_tools,  # Also provide tools to analysis agent
            verbose=True,
        )

        # Create tasks
        memory_task = Task(
            description="""
            Use the available MCP tools to:
            1. Retrieve active work items from the memory system
            2. Search for relevant memory blocks about current projects
            3. Summarize findings for the analysis agent
            """,
            agent=memory_agent,
            expected_output="A comprehensive summary of active work items and relevant memory blocks",
        )

        analysis_task = Task(
            description="""
            Analyze the memory retrieval results and provide:
            1. Key insights about current project status
            2. Recommendations for next steps
            3. Priority areas requiring attention
            """,
            agent=analysis_agent,
            expected_output="Strategic analysis with actionable recommendations",
        )

        # Create crew
        crew = Crew(
            agents=[memory_agent, analysis_agent], tasks=[memory_task, analysis_task], verbose=True
        )

        return crew

    async def run_proof_of_concept(self):
        """Run the CrewAI MCP proof-of-concept"""
        logger.info("🚀 Starting CrewAI MCP Proof-of-Concept")

        try:
            # Use correct ToolHive SSE endpoint from thv list output
            # The server is running on port 26902 with SSE transport
            server_params = {"url": "http://localhost:26902/sse#cogni-mcp", "transport": "sse"}

            # This is the CORRECT usage pattern from CrewAI docs
            logger.info(f"🔌 Attempting MCP connection to: {server_params['url']}")
            async with MCPServerAdapter(server_params) as mcp_tools:
                logger.info(f"✅ Connected to MCP server with {len(mcp_tools)} tools")
                logger.info(f"Available tools: {[tool.name for tool in mcp_tools]}")

                # Add detailed tool inspection for debugging
                for i, tool in enumerate(mcp_tools):
                    logger.info(
                        f"Tool {i + 1}: {tool.name} - {getattr(tool, 'description', 'No description')}"
                    )

                if not mcp_tools:
                    logger.warning("⚠️ No MCP tools available - check server connection")
                    logger.info("🔍 Debugging: Returning False due to no tools")
                    return False

                # Create crew with MCP tools
                crew = self.create_crew(mcp_tools)

                # Run the crew with async kickoff
                logger.info("🔄 Running CrewAI crew with MCP tools...")
                result = await crew.kickoff_async(inputs={"topic": "current project status"})

                logger.info("✅ CrewAI MCP proof-of-concept completed successfully!")
                logger.info(f"Result: {result}")
                return True

        except Exception as e:
            logger.error(f"❌ CrewAI MCP proof-of-concept failed: {e}")
            return False


async def main():
    """Main execution function"""
    poc = CrewAIMCPProofOfConcept()
    success = await poc.run_proof_of_concept()

    if success:
        print("\n✅ CrewAI MCP Integration Proof-of-Concept: SUCCESS")
    else:
        print("\n❌ CrewAI MCP Integration Proof-of-Concept: FAILED")


if __name__ == "__main__":
    asyncio.run(main())
