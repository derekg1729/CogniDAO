"""CogniDAO Image Generation Graph - Lean 5-node workflow with retry loop."""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path for absolute imports
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from langgraph.graph import StateGraph  # noqa: E402
from langgraph.checkpoint.redis import AsyncRedisSaver  # noqa: E402
from src.shared_utils import GraphConfig, get_logger  # noqa: E402
from .state_types import ImageFlowState  # noqa: E402
from .nodes import create_planner_node, create_image_tool_node, create_reviewer_node, create_responder_node  # noqa: E402

logger = get_logger(__name__)


async def build_graph() -> StateGraph:
    """Build the CogniDAO image generation LangGraph workflow."""
    # Create all nodes
    planner_node = await create_planner_node()
    image_tool_node = await create_image_tool_node()
    reviewer_node = await create_reviewer_node()
    responder_node = await create_responder_node()

    # Build the workflow
    workflow = StateGraph(ImageFlowState, config_schema=GraphConfig)
    workflow.add_node("planner", planner_node)
    workflow.add_node("image_tool", image_tool_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("responder", responder_node)
    
    # Set entry point
    workflow.set_entry_point("planner")
    
    # Add edges
    workflow.add_edge("planner", "image_tool")
    workflow.add_edge("image_tool", "reviewer")
    
    # Conditional edge for retry logic (decider)
    def should_retry(state):
        score = state.get("score", 0.8)  # Default to decent score
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 2)
        
        if score < 0.7 and retry_count < max_retries:
            return "planner"
        else:
            return "responder"
    
    workflow.add_conditional_edges(
        "reviewer",
        should_retry,
        {"planner": "planner", "responder": "responder"}
    )
    
    workflow.add_edge("responder", "__end__")

    logger.info(f"✅ CogniDAO image generation graph built with {len(workflow.nodes)} nodes")
    return workflow


async def build_compiled_graph(use_checkpointer=False, checkpointer=None):
    """
    Build and compile the CogniDAO image generation LangGraph workflow.

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
            result = await app.ainvoke({"user_request": "Generate a sunset image"})
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