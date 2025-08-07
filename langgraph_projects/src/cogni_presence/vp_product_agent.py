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


# VP Product Subagents
workitem_research_prompt = """You are a **Work Item Research Specialist** 🔍 for the VP Product team.

**Your Mission:** Find the most relevant work items and project context for the VP Product's requests.

**Primary Tools:**
- `GetActiveWorkItems` - Find currently active work items across the organization
- `GlobalSemanticSearch` - Search for relevant context, documentation, and related work
- `add_memory_block_ref` - Register relevant work items for session context tracking

**Research Process:**
1. **Active Work Search**: Use GetActiveWorkItems to find current projects and tasks
2. **Context Search**: Use GlobalSemanticSearch to find relevant documentation, discussions, and background
3. **Register Relevant Items**: For any clearly relevant work items found, use add_memory_block_ref to register them for the current session
4. **Synthesis**: Provide a concise summary of relevant work items and context
5. **Recommendations**: Suggest which work items are most relevant to the current request

**CRITICAL**: When you find work items that are clearly relevant to the VP Product's request, you MUST use add_memory_block_ref to register their block IDs. This ensures they remain accessible for the current session.

**Response Format:**
- **Active Work Items**: List current relevant work with status and priority
- **Related Context**: Key background information and documentation
- **Registered References**: Confirm which work item block IDs were registered via add_memory_block_ref
- **Recommendations**: Priority ranking of most relevant items

**Important**: Leave branch/namespace parameters empty in all tool calls."""

workitem_research_subagent = {
    "name": "workitem-research",
    "description": "Specialist for finding relevant work items and project context using GetActiveWorkItems and GlobalSemanticSearch. Use this when you need to understand current projects, find related work, or research organizational context.",
    "prompt": workitem_research_prompt,
    # Note: Tool names must match exactly what's available in all_tools
    # These will be resolved from the parent agent's tool list
    "tools": []  # Will inherit from parent agent - no tool filtering for now
}


async def create_vp_product_node():
    """Create VP Product DeepAgent with MCP memory tools and product-specific capabilities."""
    logger.info("🧠 Creating VP Product DeepAgent node...")
    
    # Get MCP tools for persistent memory blocks
    mcp_tools = await get_tools("cogni")
    
    # Filter to the 6 memory block tools we need for persistent storage + search + work items
    memory_tools = [
        tool for tool in mcp_tools 
        if hasattr(tool, 'name') and tool.name in [
            "GetMemoryBlock", "CreateMemoryBlock", "UpdateMemoryBlock",
            "GlobalSemanticSearch", "GlobalMemoryInventory", "GetActiveWorkItems"
        ]
    ]
    
    # Add EDO-specific tools for memory context access
    edo_tools = [get_relevant_memory_block_refs, add_memory_block_ref]
    
    # Add product-specific tools if needed
    product_tools = []  # Could add product metrics, roadmap tools later
    
    # Combine all tools for DeepAgent
    all_tools = memory_tools + edo_tools + product_tools
    
    logger.info(f"🔧 VP Product DeepAgent configured with {len(all_tools)} tools: {len(memory_tools)} MCP + {len(edo_tools)} EDO + {len(product_tools)} product tools")
    
    # Create DeepAgent with product-specific instructions
    deepagent = create_deep_agent(
        tools=all_tools,
        instructions=VP_PRODUCT_INSTRUCTIONS,
        subagents=[workitem_research_subagent],  # Work item research specialist
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