"""
CogniDAO Presence Agent - Simple memory management agent using LangGraph's create_react_agent.
"""

from src.shared_utils import get_logger
from src.shared_utils.tool_registry import get_tools
from src.shared_utils.state_types import BaseAgentState
from src.shared_utils.edo_tools import get_relevant_memory_block_refs, add_memory_block_ref
from src.shared_agent_frameworks.deepagents import create_deep_agent
from .prompts import VP_PRODUCT_INSTRUCTIONS

logger = get_logger(__name__)


async def create_vp_product_node():
    """Create VP Product DeepAgent with MCP memory tools and product-specific capabilities."""
    logger.info("🧠 Creating VP Product DeepAgent node...")
    
    # Get MCP tools for persistent memory blocks
    mcp_tools = await get_tools("cogni")
    
    # Filter to the 5 memory block tools we need for persistent storage + search
    memory_tools = [
        tool for tool in mcp_tools 
        if hasattr(tool, 'name') and tool.name in [
            "GetMemoryBlock", "CreateMemoryBlock", "UpdateMemoryBlock",
            "GlobalSemanticSearch", "GlobalMemoryInventory"
        ]
    ]
    
    # Add EDO-specific tools for memory context access
    edo_tools = [get_relevant_memory_block_refs, add_memory_block_ref]
    
    # Add product-specific tools if needed
    product_tools = []  # Could add product metrics, roadmap tools later
    
    # Combine all tools for DeepAgent
    all_tools = memory_tools + edo_tools + product_tools
    
    logger.info(f"🔧 VP Product DeepAgent configured with {len(all_tools)} tools: {len(memory_tools)} memory + {len(edo_tools)} EDO + {len(product_tools)} product tools")
    
    # Create DeepAgent with product-specific instructions
    deepagent = create_deep_agent(
        tools=all_tools,
        instructions=VP_PRODUCT_INSTRUCTIONS,
        subagents=[],  # Could add UX research, analytics subagents later
        state_schema=BaseAgentState,
    )
    
    # Set the agent name for supervisor compatibility
    deepagent.name = "vp_product"
    
    logger.info("✅ VP Product DeepAgent node created successfully")
    return deepagent


def should_continue(state) -> str:
    """
    Determine whether to continue or end based on the last message.

    Args:
        state: Current agent state

    Returns:
        "continue" to call tools, "end" to finish
    """
    messages = state["messages"]
    last_message = messages[-1]

    # If the last message has tool calls, continue
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "continue"

    return "end"