"""
EDO Layered Agent - Event-Decision-Outcome pattern with memory-driven hooks.
"""

from src.shared_utils import get_logger
from src.shared_utils.tool_registry import get_tools
from src.shared_utils.edo_tools import get_relevant_memory_block_refs, add_memory_block_ref
from src.shared_utils.state_types import BaseAgentState

# DeepAgent integration
from src.shared_agent_frameworks.deepagents import create_deep_agent

# EDO functionality moved to explicit graph nodes
from .prompts import EDO_DEEPAGENT_INSTRUCTIONS

logger = get_logger(__name__)


async def test_tool() -> str:
    """Testing tool for the layered agent."""
    print("🔧 TEST-TOOL: Tool invoked successfully!")
    return "Test tool executed successfully"


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


async def create_deepagent_node():
    """Create EDO DeepAgent with MCP memory tools and EDO-specific capabilities."""
    logger.info("🧠 Creating EDO DeepAgent node...")
    
    # Get MCP tools for persistent memory blocks
    mcp_tools = await get_tools("cogni")
    
    # Filter to the 3 memory block tools we need for persistent storage
    memory_tools = [
        tool for tool in mcp_tools 
        if hasattr(tool, 'name') and tool.name in ["GetMemoryBlock", "CreateMemoryBlock", "UpdateMemoryBlock"]
    ]
    
    # Add EDO-specific tools including memory context access
    edo_tools = [get_relevant_memory_block_refs, add_memory_block_ref]
    
    # Combine all tools for DeepAgent
    all_tools = memory_tools + edo_tools
    
    logger.info(f"🔧 DeepAgent configured with {len(all_tools)} tools: {len(memory_tools)} memory + {len(edo_tools)} EDO tools")
    
    # Create DeepAgent with EDO-specific instructions and state schema
    deepagent = create_deep_agent(
        tools=all_tools,
        instructions=EDO_DEEPAGENT_INSTRUCTIONS,
        subagents=[],  # Could add research/critique subagents later
        state_schema=BaseAgentState,  # Use EDO state schema for compatibility
    )
    
    logger.info("✅ EDO DeepAgent node created successfully")
    return deepagent
