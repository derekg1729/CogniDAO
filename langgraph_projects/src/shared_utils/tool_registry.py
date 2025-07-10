"""
Tool Registry - Cached MCP tools for all agents.

Handles MCP connection once per process and provides cached tool lists.

TODO: simple implementation right now. Will eventually rely on Toolhive and RBAC.
"""

from async_lru import alru_cache
from langchain_core.tools import BaseTool
from src.shared_utils import get_mcp_tools_with_refresh, get_logger

logger = get_logger(__name__)


@alru_cache(maxsize=16)
async def get_tools(server_type: str) -> list[BaseTool]:
    """Get cached MCP tools for a server type with race condition protection."""
    logger.info(f"Initializing {server_type} MCP tools...")
    return await get_mcp_tools_with_refresh(server_type=server_type)