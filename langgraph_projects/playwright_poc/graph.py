#!/usr/bin/env python3
"""
Playwright Basic Graph
=====================

A compilable LangGraph StateGraph for browser automation using Playwright MCP.
This graph can be deployed, checkpointed, and used in production.

Key components:
1. StateGraph with proper state management
2. Memory-based checkpointing (Redis optional)
3. MCP tool integration for Playwright
4. Compiled graph artifact for deployment

Usage:
    from langgraph_projects.playwright_poc.graph import create_stategraph

    graph = create_stategraph()
    compiled = graph.compile()
"""

import asyncio
import logging
import os
from typing import Annotated, List
from typing_extensions import TypedDict

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI

# Try to import Redis checkpointer, fall back to memory if not available
try:
    from langgraph.checkpoint.redis import RedisSaver

    REDIS_AVAILABLE = True
except ImportError:
    try:
        from langgraph.checkpoint.memory import MemorySaver

        REDIS_AVAILABLE = False
    except ImportError:
        # No checkpointing available
        MemorySaver = None
        REDIS_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PlaywrightState(TypedDict):
    """State for the Playwright automation graph."""

    messages: Annotated[List[BaseMessage], add_messages]
    tools_available: bool
    current_task: str


async def get_mcp_tools():
    """Get tools from the MCP server."""
    # Use Docker network URL if available, fallback to localhost
    mcp_url = os.getenv("PLAYWRIGHT_MCP_URL", "http://localhost:58462/sse#playwright")

    client = MultiServerMCPClient(
        {
            "playwright": {
                "url": mcp_url,
                "transport": "sse",
            }
        }
    )

    logger.info("🔗 Connecting to playwright MCP server...")
    tools = await client.get_tools()
    logger.info(f"✅ Connected! Found {len(tools)} tools from playwright MCP")

    return tools


async def setup_agent_node(state: PlaywrightState) -> PlaywrightState:
    """Node to set up the agent with MCP tools."""
    try:
        # Verify MCP tools can be obtained (validation check)
        await get_mcp_tools()

        # Check if tools are available and set flag
        # Note: Actual agent creation happens in agent_node
        return {**state, "tools_available": True, "messages": state["messages"]}

    except Exception as e:
        logger.error(f"❌ Failed to setup agent: {e}")
        return {
            **state,
            "tools_available": False,
            "messages": state["messages"] + [AIMessage(content=f"Error setting up tools: {e}")],
        }


async def agent_node(state: PlaywrightState) -> PlaywrightState:
    """Main agent reasoning node."""
    if not state.get("tools_available", False):
        return {
            **state,
            "messages": state["messages"]
            + [AIMessage(content="Tools not available. Please check MCP server connection.")],
        }

    # Get the latest human message
    if not state["messages"]:
        return {
            **state,
            "messages": [AIMessage(content="No messages to process.")],
        }

    last_message = state["messages"][-1]
    if not isinstance(last_message, HumanMessage):
        return state

    try:
        # Get tools and create agent
        tools = await get_mcp_tools()
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        agent_with_tools = llm.bind_tools(tools)

        # Invoke the agent
        response = await agent_with_tools.ainvoke(state["messages"])

        return {
            **state,
            "messages": state["messages"] + [response],
            "current_task": last_message.content,
        }

    except Exception as e:
        logger.error(f"❌ Agent error: {e}")
        return {
            **state,
            "messages": state["messages"] + [AIMessage(content=f"Error processing request: {e}")],
        }


def should_continue(state: PlaywrightState) -> str:
    """Determine if we should continue or end."""
    last_message = state["messages"][-1]

    # If the last message has tool calls, continue to tool execution
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    # Otherwise, we're done
    return END


async def tool_execution_node(state: PlaywrightState) -> PlaywrightState:
    """Execute tool calls."""
    last_message = state["messages"][-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return state

    try:
        # Get tools
        tools = await get_mcp_tools()
        tool_map = {tool.name: tool for tool in tools}

        tool_messages = []

        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            if tool_name in tool_map:
                tool = tool_map[tool_name]
                try:
                    result = await tool.ainvoke(tool_args)
                    tool_messages.append(
                        {"role": "tool", "content": str(result), "tool_call_id": tool_call["id"]}
                    )
                except Exception as e:
                    tool_messages.append(
                        {
                            "role": "tool",
                            "content": f"Error executing {tool_name}: {e}",
                            "tool_call_id": tool_call["id"],
                        }
                    )

        return {**state, "messages": state["messages"] + tool_messages}

    except Exception as e:
        logger.error(f"❌ Tool execution error: {e}")
        return {
            **state,
            "messages": state["messages"] + [AIMessage(content=f"Tool execution failed: {e}")],
        }


def create_stategraph() -> StateGraph:
    """Create and return the compiled StateGraph."""

    # Create the state graph
    workflow = StateGraph(PlaywrightState)

    # Add nodes
    workflow.add_node("setup", setup_agent_node)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_execution_node)

    # Add edges
    workflow.add_edge(START, "setup")
    workflow.add_edge("setup", "agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    workflow.add_edge("tools", "agent")

    return workflow


def create_checkpointer():
    """Create a checkpointer for state persistence (Redis preferred, Memory fallback)."""
    if REDIS_AVAILABLE:
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            return RedisSaver.from_conn_string(redis_url)
        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed: {e}, falling back to memory")

    if MemorySaver is not None:
        logger.info("Using MemorySaver for checkpointing")
        return MemorySaver()

    logger.warning("⚠️ No checkpointing available")
    return None


def compile_graph():
    """Compile the graph for LangGraph API (persistence handled automatically)."""
    workflow = create_stategraph()

    # LangGraph API handles persistence automatically, so no custom checkpointer needed (and it throws an error if present))
    # checkpointer = create_checkpointer()
    # if checkpointer is not None:
    #     compiled = workflow.compile(checkpointer=checkpointer)
    #     checkpoint_type = "Redis" if REDIS_AVAILABLE else "Memory"
    #     logger.info(f"✅ Graph compiled with {checkpoint_type} checkpointer")
    # else:
    compiled = workflow.compile()
    logger.info("✅ Graph compiled for LangGraph API (automatic persistence)")

    return compiled


# For direct execution and testing
async def run_example():
    """Run an example interaction for testing."""
    compiled_graph = compile_graph()

    config = {"configurable": {"thread_id": "test-thread"}}

    # Example interaction
    initial_state = {
        "messages": [HumanMessage(content="Take a screenshot of the current page")],
        "tools_available": False,
        "current_task": "",
    }

    async for event in compiled_graph.astream(initial_state, config):
        for node_name, node_output in event.items():
            logger.info(f"Node '{node_name}' output: {node_output}")


# Create the graph variable that LangGraph expects
graph = compile_graph()

if __name__ == "__main__":
    # Run example for testing
    asyncio.run(run_example())
