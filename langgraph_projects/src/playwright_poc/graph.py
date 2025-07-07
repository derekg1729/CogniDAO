"""
Playwright Graph.

A streamlined graph definition using shared utilities for MCP client management,
model binding, and state management for browser automation.
"""

import asyncio
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from src.shared_utils import (
    GraphConfig,
    PlaywrightAgentState,
    get_logger,
    get_mcp_tools_with_refresh,
    log_graph_compilation,
)

from .agent import create_agent_node, should_continue

logger = get_logger(__name__)


async def build_graph() -> StateGraph:
    """
    Build the Playwright automation LangGraph workflow.

    Returns:
        StateGraph: An uncompiled StateGraph instance.
        Call .compile() on the result to get a runnable graph.

    Example:
        workflow = await build_graph()
        app = workflow.compile()
        result = await app.ainvoke({"messages": [HumanMessage("Hello")]})
    """
    # Get MCP tools for Playwright server with refresh capability
    tools = await get_mcp_tools_with_refresh(server_type="playwright")

    # Create agent node
    agent_node = create_agent_node()

    # Build the workflow
    workflow = StateGraph(PlaywrightAgentState, config_schema=GraphConfig)

    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("action", ToolNode(tools))

    # Set entry point
    workflow.set_entry_point("agent")

    # Add conditional edges - fix the mapping issue
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "action",
            "end": END,
        },
    )
    workflow.add_edge("action", "agent")

    # Log successful compilation
    log_graph_compilation("playwright_poc", len(workflow.nodes))

    return workflow


async def build_compiled_graph():
    """
    Build and compile the Playwright automation LangGraph workflow.

    Returns:
        CompiledStateGraph: A compiled, ready-to-use graph instance.

    Example:
        app = await build_compiled_graph()
        result = await app.ainvoke({"messages": [HumanMessage("Hello")]})
    """
    workflow = await build_graph()
    return workflow.compile()


# Export compiled graph for LangGraph dev server
graph = asyncio.run(build_compiled_graph())
