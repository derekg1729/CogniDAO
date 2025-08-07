"""
CEO Supervisor Agent - Orchestrates VP agents in the org chart.
"""

from src.shared_utils import get_logger
from src.shared_utils.tool_registry import get_tools
from src.shared_agent_frameworks.deepagents.tools import write_todos

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
