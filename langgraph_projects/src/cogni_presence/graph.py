"""
CogniDAO CEO Supervisor Graph - Uses LangGraph supervisor pattern
"""

import asyncio
from langgraph_supervisor import create_supervisor
from src.shared_utils import get_logger

from .vp_marketing_agent import create_vp_marketing_node
from .vp_hr_agent import create_vp_hr_node
from .vp_tech_agent import create_vp_tech_node
from .vp_product_agent import create_vp_product_node
from .vp_finance_agent import create_vp_finance_node

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
        prompt=(
            "You are the **CEO** of CogniDAO 🏢\n\n"
            "You are managing five VP agents:\n"
            "- VP Marketing: Handles brand, campaigns, customer acquisition, and market analysis\n"
            "- VP HR: Manages people, culture, recruiting, and performance management\n"
            "- VP Tech: Oversees engineering, infrastructure, security, and technical architecture\n"
            "- VP Product: Handles product strategy, features, roadmap, and user experience\n"
            "- VP Finance: Manages financial planning, budgeting, forecasting, and treasury\n\n"
            "Analyze each user request and assign work to the most appropriate VP.\n"
            "Assign work to one agent at a time, do not call agents in parallel.\n"
            "After receiving a VP's response, provide a final executive summary to the user.\n"
            "You can think, and organize, but delegate specific questions and work to your VPs."
        ),
        add_handoff_back_messages=True,
        output_mode="full_history",
    )

    logger.info("✅ CogniDAO org chart supervisor created successfully")
    return supervisor


async def build_compiled_graph():
    """
    Build and compile the CogniDAO org chart supervisor workflow.

    Returns:
        CompiledStateGraph: A compiled, ready-to-use graph instance.

    Example:
        app = await build_compiled_graph()
        result = await app.ainvoke({"messages": [HumanMessage("Hello")]})
    """
    supervisor = await build_graph()
    return supervisor.compile()


# Export compiled graph for LangGraph dev server
graph = asyncio.run(build_compiled_graph())
