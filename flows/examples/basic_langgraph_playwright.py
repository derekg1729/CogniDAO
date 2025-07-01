#!/usr/bin/env python3
"""
Basic LangGraph with Playwright MCP
===================================

Demonstrates the simplest possible LangGraph integration with a local playwright MCP server.
This follows the official LangGraph MCP integration pattern using langchain_mcp_adapters.

Key components:
1. MultiServerMCPClient for connecting to MCP servers
2. Streamable HTTP transport for SSE connections
3. create_react_agent for the simplest LangGraph setup
4. OpenAI GPT model for the LLM

Usage:
    python flows/examples/basic_langgraph_playwright.py

Prerequisites:
    - Playwright MCP server running at http://127.0.0.1:58462/sse
    - OPENAI_API_KEY environment variable set
    - langgraph and langchain-mcp-adapters packages installed
"""

import asyncio
import logging
import os

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_playwright_agent():
    """Create a LangGraph agent with access to playwright MCP tools."""

    # Configure the MCP client to connect to your playwright server
    # Using streamable_http transport for SSE connections
    client = MultiServerMCPClient(
        {
            "playwright": {
                "url": "http://localhost:58462/sse#playwright",
                "transport": "sse",
            }
        }
    )

    logger.info("🔗 Connecting to playwright MCP server...")

    try:
        # Get tools from the MCP server
        tools = await client.get_tools()
        logger.info(f"✅ Connected! Found {len(tools)} tools from playwright MCP")

        # Log available tools for visibility
        for tool in tools:
            logger.info(f"   🔧 {tool.name}: {tool.description or 'No description'}")

        # Create the LLM
        llm = ChatOpenAI(
            model="gpt-4o-mini",  # Using mini for cost efficiency
            temperature=0,  # Deterministic responses
        )

        # Create the ReAct agent with playwright tools
        agent = create_react_agent(
            llm,
            tools,
        )

        logger.info("🤖 LangGraph agent created successfully!")
        return agent

    except Exception as e:
        logger.error(f"❌ Failed to create agent: {e}")
        raise


async def run_agent_example(agent):
    """Run a simple example with the playwright agent."""

    # Example tasks to demonstrate playwright capabilities
    example_tasks = [
        "Take a screenshot of the current page",
        "Navigate to https://example.com and take a screenshot",
        "What browser automation tools do you have available?",
    ]

    logger.info("🚀 Running example interactions...")

    for task in example_tasks:
        logger.info(f"\n📝 User: {task}")

        try:
            # Invoke the agent with the task
            response = await agent.ainvoke({"messages": [{"role": "user", "content": task}]})

            # Extract the final response
            final_message = response["messages"][-1].content
            logger.info(f"🤖 Agent: {final_message}")

        except Exception as e:
            logger.error(f"❌ Error processing task '{task}': {e}")

        # Add a small delay between tasks
        await asyncio.sleep(1)


async def interactive_mode(agent):
    """Run the agent in interactive mode."""

    logger.info("\n🎮 Interactive mode started! Type 'quit' to exit.")
    logger.info("You can ask the agent to perform browser automation tasks.")

    while True:
        try:
            # Get user input
            user_input = input("\n👤 You: ").strip()

            if user_input.lower() in ["quit", "exit", "q"]:
                logger.info("👋 Goodbye!")
                break

            if not user_input:
                continue

            # Send to agent
            response = await agent.ainvoke({"messages": [{"role": "user", "content": user_input}]})

            # Display response
            final_message = response["messages"][-1].content
            print(f"🤖 Agent: {final_message}")

        except KeyboardInterrupt:
            logger.info("\n👋 Goodbye!")
            break
        except Exception as e:
            logger.error(f"❌ Error: {e}")


async def main():
    """Main function demonstrating basic LangGraph with playwright MCP."""

    logger.info("🎯 Starting Basic LangGraph with Playwright MCP")

    # Check for required environment variables
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("❌ OPENAI_API_KEY environment variable is required")
        return

    try:
        # Create the agent
        agent = await create_playwright_agent()

        # Run examples first
        await run_agent_example(agent)

        # Then interactive mode
        await interactive_mode(agent)

    except Exception as e:
        logger.error(f"❌ Application failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
