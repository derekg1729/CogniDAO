"""
Playwright Graph - Simple graph using LangGraph's react agent.
"""

import asyncio
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from src.shared_utils import GraphConfig, PlaywrightAgentState, get_logger
from src.shared_utils.tool_registry import get_tools

from .agent import create_agent_node, should_continue

logger = get_logger(__name__)


async def build_graph() -> StateGraph:
    """Build the Playwright automation LangGraph workflow."""
    # Get tools and create agent node
    tools = await get_tools("playwright")
    agent_node = await create_agent_node()

    # Build the workflow
    workflow = StateGraph(PlaywrightAgentState, config_schema=GraphConfig)
    workflow.add_node("agent", agent_node)
    workflow.add_node("action", ToolNode(tools))
    workflow.set_entry_point("agent")

    # Add edges
    workflow.add_conditional_edges("agent", should_continue, {"continue": "action", "end": END})
    workflow.add_edge("action", "agent")

    logger.info(f"✅ Playwright graph built with {len(workflow.nodes)} nodes")
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
