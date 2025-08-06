"""
CEO Supervisor Agent - Orchestrates VP agents in the org chart.
"""

from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from src.shared_utils import get_logger
from src.shared_utils.tool_registry import get_tools
from src.shared_agent_frameworks.deepagents.tools import write_todos
from .prompts import CEO_SUPERVISOR_PROMPT

logger = get_logger(__name__)


async def get_ceo_tools():
    """Get CEO strategic tools: imported write_todos + MCP memory tools."""
    logger.info("🏢 Loading CEO strategic tools...")
    
    # Get MCP tools for persistent memory and search
    mcp_tools = await get_tools("cogni")
    
    # Filter to CEO-relevant tools for strategic planning and research
    ceo_memory_tools = [
        tool for tool in mcp_tools 
        if hasattr(tool, 'name') and tool.name in [
            "GetMemoryBlock", "CreateMemoryBlock", "UpdateMemoryBlock",
            "GlobalSemanticSearch", "GlobalMemoryInventory"
        ]
    ]
    
    # Import write_todos tool from deepagents framework
    imported_tools = [write_todos]
    
    # Combine for CEO strategic capabilities
    all_ceo_tools = imported_tools + ceo_memory_tools
    
    logger.info(f"🔧 CEO configured with {len(all_ceo_tools)} tools: {len(imported_tools)} deepagent + {len(ceo_memory_tools)} MCP tools")
    
    return all_ceo_tools


async def create_ceo_supervisor_node():
    """Create CEO supervisor agent using LangGraph's create_react_agent."""
    # Get CEO strategic tools
    tools = await get_ceo_tools()
    
    # No tool spec generation needed - tools handle their own descriptions
    model = ChatOpenAI(model_name='gpt-4o-mini')
    return create_react_agent(
        model=model, 
        tools=tools,                    # Tools passed directly
        prompt=CEO_SUPERVISOR_PROMPT    # String prompt, no .partial() needed
    )


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