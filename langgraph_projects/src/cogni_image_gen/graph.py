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
from .nodes import create_planner_node, create_image_tool_node, create_reviewer_node, create_responder_node, create_hil_node  # noqa: E402

logger = get_logger(__name__)


async def build_graph() -> StateGraph:
    """Build the CogniDAO image generation LangGraph workflow."""
    # Create all nodes
    planner_node = await create_planner_node()
    image_tool_node = await create_image_tool_node()
    reviewer_node = await create_reviewer_node()
    responder_node = await create_responder_node()
    hil_node = await create_hil_node()

    # Build the workflow
    workflow = StateGraph(ImageFlowState, config_schema=GraphConfig)
    workflow.add_node("planner", planner_node)
    workflow.add_node("image_tool", image_tool_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("responder", responder_node)
    workflow.add_node("human_checkpoint", hil_node)
    
    # Set entry point
    workflow.set_entry_point("planner")
    
    # Add edges - reviewer before image creation, HIL checkpoint after responder
    workflow.add_edge("planner", "reviewer")
    workflow.add_edge("image_tool", "responder")
    workflow.add_edge("responder", "human_checkpoint")
    
    # Conditional edge for reviewer feedback loop (max 5 cycles)
    def decide_next(state):
        needs_retry = state.get("needs_retry", False)
        attempt = state.get("attempt", 0)
        
        # Continue to planner if retry needed and under 5 attempts, otherwise go to image generation
        if needs_retry and attempt < 5:
            return "planner"
        else:
            return "image_tool"
    
    workflow.add_conditional_edges(
        "reviewer",
        decide_next,
        {"planner": "planner", "image_tool": "image_tool"}
    )
    
    # Conditional edge for human checkpoint after responder
    def decide_after_human_review(state):
        decision = state.get("decision")
        if decision == "approve":
            return "end"  # Finish workflow
        elif decision == "revise":
            # Set retry flags for planner loop
            return "planner"
        else:
            # If no decision provided yet, default to end for safety
            # The interrupt will handle pausing until human provides input
            return "end"
    
    workflow.add_conditional_edges(
        "human_checkpoint",
        decide_after_human_review,
        {"planner": "planner", "end": "__end__"}
    )
    
    # Remove the old responder -> __end__ edge since responder now goes to human_checkpoint

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
        result = await app.ainvoke(
            {"user_request": "Generate a sunset image"}, 
            config={"recursion_limit": 100}
        )
        
        # With checkpointer (caller manages context)
        async with AsyncRedisSaver.from_conn_string("redis://localhost:6379") as saver:
            app = await build_compiled_graph(checkpointer=saver)
            result = await app.ainvoke(
                {"user_request": "Generate a sunset image"},
                config={"recursion_limit": 100}
            )
    """
    workflow = await build_graph()
    
    # Note: recursion_limit is set during invocation, not compilation
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