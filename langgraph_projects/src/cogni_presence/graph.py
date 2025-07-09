"""
CogniDAO Presence Graph - Simple graph using LangGraph's react agent.
"""

import asyncio
from langgraph.graph import StateGraph
from src.shared_utils import CogniAgentState, GraphConfig, get_logger

from .agent import create_agent_node

logger = get_logger(__name__)


async def build_graph() -> StateGraph:
    """Build the CogniDAO presence LangGraph workflow."""
    # Create agent node
    agent_node = await create_agent_node()

    # Build the workflow - create_react_agent handles tool calling internally
    workflow = StateGraph(CogniAgentState, config_schema=GraphConfig)
    workflow.add_node("agent", agent_node)
    workflow.set_entry_point("agent")
    workflow.set_finish_point("agent")

    logger.info(f"✅ CogniDAO graph built with {len(workflow.nodes)} nodes")
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
