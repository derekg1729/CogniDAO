"""
EDO Layered Agent Graph - Event-Decision-Outcome workflow with explicit nodes.
"""

import os
from langgraph.graph import StateGraph
from langgraph.checkpoint.redis import AsyncRedisSaver
from src.shared_utils import GraphConfig, get_logger
from .state_types import CogniAgentState

from .agent import create_agent_node
from .nodes import create_edo_event_loader, create_edo_decision_writer

logger = get_logger(__name__)


async def build_graph() -> StateGraph:
    """Build the EDO Layered Agent workflow with explicit EDO nodes."""
    # Create all nodes
    edo_event_loader = create_edo_event_loader()
    agent_node = await create_agent_node()
    edo_decision_writer = create_edo_decision_writer()

    # Build the workflow - EDO pattern: Event Loader -> Agent -> Decision Writer
    workflow = StateGraph(CogniAgentState, config_schema=GraphConfig)
    workflow.add_node("edo_event_loader", edo_event_loader)
    workflow.add_node("agent", agent_node)
    workflow.add_node("edo_decision_writer", edo_decision_writer)
    
    # EDO flow: Load Event -> Agent Decision -> Write Decision & Outcome
    workflow.set_entry_point("edo_event_loader")
    workflow.add_edge("edo_event_loader", "agent")
    workflow.add_edge("agent", "edo_decision_writer")
    workflow.set_finish_point("edo_decision_writer")

    logger.info(f"✅ EDO Layered Agent graph built with {len(workflow.nodes)} nodes")
    return workflow


async def build_compiled_graph(use_checkpointer=False, checkpointer=None):
    """
    Build and compile the EDO Layered Agent LangGraph workflow.

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


# Note: Graph is exported from main.py for LangGraph deployment
