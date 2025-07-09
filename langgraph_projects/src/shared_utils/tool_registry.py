"""
Tool Registry - Cached MCP tools for all agents.

Handles MCP connection once per process and provides cached tool lists.
"""

from src.shared_utils import get_mcp_tools_with_refresh, get_logger

logger = get_logger(__name__)

# Global tool cache - initialized once per process
_TOOLS = {}

async def get_tools(server_type: str):
    """Get cached MCP tools for a server type."""
    if server_type not in _TOOLS:
        logger.info(f"Initializing {server_type} MCP tools...")
        _TOOLS[server_type] = await get_mcp_tools_with_refresh(server_type=server_type)
    return _TOOLS[server_type]