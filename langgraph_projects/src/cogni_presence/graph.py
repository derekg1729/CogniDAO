"""
CogniDAO CEO Supervisor Graph - Uses LangGraph supervisor pattern
"""

import asyncio
import os
from langgraph_supervisor import create_supervisor
from langgraph.checkpoint.redis import AsyncRedisSaver
from src.shared_utils import get_logger

from .vp_marketing_agent import create_vp_marketing_node
from .vp_hr_agent import create_vp_hr_node
from .vp_tech_agent import create_vp_tech_node
from .vp_product_agent import create_vp_product_node
from .vp_finance_agent import create_vp_finance_node
from .prompts import CEO_SUPERVISOR_PROMPT

logger = get_logger(__name__)


async def build_graph():
    """Build the CogniDAO org chart using LangGraph supervisor pattern."""
    # Create all VP agent nodes
    vp_marketing = await create_vp_marketing_node()
    vp_hr = await create_vp_hr_node()
    vp_tech = await create_vp_tech_node()
    vp_product = await create_vp_product_node()
    vp_finance = await create_vp_finance_node()
    
    # Create supervisor following the example pattern
    from langchain_openai import ChatOpenAI
    
    supervisor = create_supervisor(
        model=ChatOpenAI(model_name="gpt-4o-mini"),
        agents=[
            vp_marketing,
            vp_hr,
            vp_tech,
            vp_product,
            vp_finance,
        ],
        prompt=CEO_SUPERVISOR_PROMPT,
        add_handoff_back_messages=True,
        output_mode="full_history",
    )

    logger.info("✅ CogniDAO org chart supervisor created successfully")
    return supervisor


async def build_compiled_graph(use_checkpointer=False, checkpointer=None):
    """
    Build and compile the CogniDAO org chart supervisor workflow.

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
    supervisor = await build_graph()
    
    if checkpointer:
        return supervisor.compile(checkpointer=checkpointer)
    elif use_checkpointer:
        # For backward compatibility, try to create a simple checkpointer
        # Note: This approach has limitations with async context management
        logger.warning("use_checkpointer=True is deprecated. Pass checkpointer instance instead.")
        redis_uri = os.getenv("REDIS_URI", "redis://localhost:6379")
        # This creates a checkpointer but doesn't manage its lifecycle properly
        # Better to pass checkpointer instance from caller
        checkpointer = AsyncRedisSaver.from_conn_string(redis_uri)
        return supervisor.compile(checkpointer=checkpointer)
    
    return supervisor.compile()


# Export compiled graph for LangGraph dev server
graph = asyncio.run(build_compiled_graph())
