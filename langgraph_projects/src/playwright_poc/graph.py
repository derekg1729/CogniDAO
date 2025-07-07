"""
Playwright Basic Graph.

A streamlined graph definition using shared utilities for MCP client management,
model binding, and state management for browser automation.
"""

import asyncio

from langgraph.graph import END, StateGraph
from src.shared_utils import (
    GraphConfig,
    PlaywrightAgentState,
    get_logger,
    get_mcp_tools,
    log_graph_compilation,
)

from .agent import create_agent_nodes, should_continue

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
    # Get MCP tools for Playwright server
    tools = await get_mcp_tools(server_type="playwright")

    # Create agent nodes
    setup_node, agent_node, tool_node = create_agent_nodes(tools)

    # Build the workflow
    workflow = StateGraph(PlaywrightAgentState, config_schema=GraphConfig)

    # Add nodes
    workflow.add_node("setup", setup_node)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    # Set entry point
    workflow.set_entry_point("setup")

    # Add edges
    workflow.add_edge("setup", "agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            END: END,
        },
    )
    workflow.add_edge("tools", "agent")

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
