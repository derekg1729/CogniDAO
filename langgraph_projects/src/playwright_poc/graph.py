"""
Playwright Graph - Simple graph using LangGraph's react agent.
"""

import asyncio
import os
from langgraph.graph import StateGraph
from langgraph.checkpoint.redis import AsyncRedisSaver
from src.shared_utils import GraphConfig, PlaywrightAgentState, get_logger

from .agent import create_agent_node

logger = get_logger(__name__)


async def build_graph() -> StateGraph:
    """Build the Playwright automation LangGraph workflow."""
    # Create agent node
    agent_node = await create_agent_node()

    # Build the workflow - create_react_agent handles tool calling internally
    workflow = StateGraph(PlaywrightAgentState, config_schema=GraphConfig)
    workflow.add_node("agent", agent_node)
    workflow.set_entry_point("agent")
    workflow.set_finish_point("agent")

    logger.info(f"✅ Playwright graph built with {len(workflow.nodes)} nodes")
    return workflow


async def build_compiled_graph(use_checkpointer=False, checkpointer=None):
    """
    Build and compile the Playwright automation LangGraph workflow.

    Args:
        use_checkpointer (bool): Whether to use Redis checkpointer for persistence.
        checkpointer: Optional pre-configured checkpointer instance.

    Returns:
        CompiledStateGraph: A compiled, ready-to-use graph instance.

    Example:
        # Without checkpointer
        app = await build_compiled_graph()
        
        # With checkpointer (caller manages context)
        async with AsyncRedisSaver.from_conn_string("redis://localhost:6379") as saver:
            app = await build_compiled_graph(checkpointer=saver)
            result = await app.ainvoke({"messages": [HumanMessage("Hello")]})
    """
    workflow = await build_graph()
    
    if checkpointer:
        return workflow.compile(checkpointer=checkpointer)
    elif use_checkpointer:
        # For backward compatibility, try to create a simple checkpointer
        # Note: This approach has limitations with async context management
        logger.warning("use_checkpointer=True is deprecated. Pass checkpointer instance instead.")
        redis_uri = os.getenv("REDIS_URI", "redis://localhost:6379")
        # This creates a checkpointer but doesn't manage its lifecycle properly
        # Better to pass checkpointer instance from caller
        checkpointer = AsyncRedisSaver.from_conn_string(redis_uri)
        return workflow.compile(checkpointer=checkpointer)
    
    return workflow.compile()


# Export compiled graph for LangGraph dev server
graph = asyncio.run(build_compiled_graph())
