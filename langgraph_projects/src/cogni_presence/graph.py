"""
CogniDAO Presence Graph.

A streamlined graph definition using shared utilities for MCP client management,
model binding, and state management.
"""

import asyncio

from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from src.shared_utils import (
    CogniAgentState,
    GraphConfig,
    get_logger,
    get_mcp_tools,
    log_graph_compilation,
)

from .agent import create_agent_node, should_continue

logger = get_logger(__name__)


async def build_graph() -> StateGraph:
    """
    Build the CogniDAO presence LangGraph workflow.

    Returns:
        StateGraph: An uncompiled StateGraph instance.
        Call .compile() on the result to get a runnable graph.

    Example:
        workflow = await build_graph()
        app = workflow.compile()
        result = await app.ainvoke({"messages": [HumanMessage("Hello")]})
    """
    # Get MCP tools for Cogni server
    tools = await get_mcp_tools(server_type="cogni")

    # Build the workflow
    workflow = StateGraph(CogniAgentState, config_schema=GraphConfig)

    # Add nodes
    workflow.add_node("agent", create_agent_node())
    workflow.add_node("action", ToolNode(tools))

    # Set entry point
    workflow.set_entry_point("agent")

    # Add edges
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
    log_graph_compilation("cogni_presence", len(workflow.nodes))

    return workflow


async def build_compiled_graph():
    """
    Build and compile the CogniDAO presence LangGraph workflow.

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
