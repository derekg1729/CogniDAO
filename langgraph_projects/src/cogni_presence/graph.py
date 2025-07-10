"""
CogniDAO Presence Graph - Simple graph using LangGraph's react agent.
"""

import asyncio
from langgraph.graph import StateGraph, START, END
from src.shared_utils import CogniAgentState, GraphConfig, get_logger

from .ceo_supervisor import create_ceo_supervisor_node
from .vp_marketing_agent import create_vp_marketing_node
from .vp_hr_agent import create_vp_hr_node
from .vp_tech_agent import create_vp_tech_node
from .vp_product_agent import create_vp_product_node
from .vp_finance_agent import create_vp_finance_node

logger = get_logger(__name__)


def route_from_ceo(state) -> str:
    """Route from CEO: either to VP or END conversation."""
    messages = state["messages"]
    
    # Check if this is a response from VP (look for VP signatures in recent messages)
    recent_messages = messages[-3:] if len(messages) >= 3 else messages
    vp_responded = any(
        msg.content and any(vp_title in msg.content for vp_title in ["VP Marketing", "VP HR", "VP Tech", "VP Product", "VP Finance"])
        for msg in recent_messages
        if hasattr(msg, 'content') and msg.content
    )
    
    # If VP already responded, CEO should end the conversation
    if vp_responded:
        return "END"
    
    # Otherwise, route to appropriate VP based on user request
    # Look at the original user message (typically the first or second message)
    user_message = None
    for msg in messages:
        if hasattr(msg, 'content') and msg.content and not any(title in msg.content for title in ["CEO", "VP"]):
            user_message = msg
            break
    
    if not user_message:
        return "END"
    
    content = user_message.content.lower()
    
    if any(word in content for word in ["marketing", "brand", "campaign", "customer", "growth"]):
        return "vp_marketing"
    elif any(word in content for word in ["hr", "people", "hiring", "culture", "employee"]):
        return "vp_hr"
    elif any(word in content for word in ["tech", "technical", "engineering", "system", "security"]):
        return "vp_tech"
    elif any(word in content for word in ["product", "feature", "roadmap", "user", "ux"]):
        return "vp_product"
    elif any(word in content for word in ["finance", "financial", "budget", "revenue", "cost"]):
        return "vp_finance"
    
    # Default to marketing for general queries
    return "vp_product"


async def build_graph() -> StateGraph:
    """Build the CogniDAO org chart LangGraph workflow."""
    # Create all agent nodes
    ceo_node = await create_ceo_supervisor_node()
    vp_marketing_node = await create_vp_marketing_node()
    vp_hr_node = await create_vp_hr_node()
    vp_tech_node = await create_vp_tech_node()
    vp_product_node = await create_vp_product_node()
    vp_finance_node = await create_vp_finance_node()

    # Build the workflow with supervisor pattern
    workflow = StateGraph(CogniAgentState, config_schema=GraphConfig)
    
    # Add all nodes
    workflow.add_node("ceo_supervisor", ceo_node)
    workflow.add_node("vp_marketing", vp_marketing_node)
    workflow.add_node("vp_hr", vp_hr_node)
    workflow.add_node("vp_tech", vp_tech_node)
    workflow.add_node("vp_product", vp_product_node)
    workflow.add_node("vp_finance", vp_finance_node)
    
    # Set entry point to CEO supervisor
    workflow.add_edge(START, "ceo_supervisor")
    
    # Add conditional edges from CEO to VPs or END
    workflow.add_conditional_edges(
        "ceo_supervisor",
        route_from_ceo,
        {
            "vp_marketing": "vp_marketing",
            "vp_hr": "vp_hr",
            "vp_tech": "vp_tech",
            "vp_product": "vp_product",
            "vp_finance": "vp_finance",
            "END": END,
        }
    )
    
    # All VPs route back to CEO for final response
    workflow.add_edge("vp_marketing", "ceo_supervisor")
    workflow.add_edge("vp_hr", "ceo_supervisor")
    workflow.add_edge("vp_tech", "ceo_supervisor")
    workflow.add_edge("vp_product", "ceo_supervisor")
    workflow.add_edge("vp_finance", "ceo_supervisor")

    logger.info(f"✅ CogniDAO org chart graph built with {len(workflow.nodes)} nodes")
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
