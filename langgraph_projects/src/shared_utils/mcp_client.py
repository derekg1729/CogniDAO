"""
MCP Client Management for LangGraph Projects.

Provides centralized MCP client initialization, tool management, and fallback handling.
"""

import asyncio
import os
from functools import lru_cache
from typing import Any

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from .logging_utils import get_logger

logger = get_logger(__name__)

# Default fallback tools for when MCP is not available
try:
    from langchain_tavily import TavilySearch

    _fallback_tools = [TavilySearch(max_results=1)]
except ImportError:
    # Fallback to the deprecated version if langchain_tavily is not installed
    try:
        from langchain_community.tools.tavily_search import TavilySearchResults

        _fallback_tools = [TavilySearchResults(max_results=1)]
    except ImportError:
        _fallback_tools = []


class MCPClientManager:
    """Manages MCP client connections and tool initialization."""

    def __init__(
        self,
        server_configs: dict[str, dict[str, Any]],
        fallback_tools: list[BaseTool] | None = None,
    ):
        """
        Initialize MCP client manager.

        Args:
            server_configs: Dictionary of server configurations
            fallback_tools: List of fallback tools to use when MCP is unavailable
        """
        self.server_configs = server_configs
        self.fallback_tools = fallback_tools or _fallback_tools
        self._tools: list[BaseTool] | None = None
        self._tools_lock = asyncio.Lock()
        self._client: MultiServerMCPClient | None = None

    async def initialize_tools(self, timeout: float = 30.0) -> list[BaseTool]:
        """
        Initialize MCP tools with fallback.

        Args:
            timeout: Timeout for MCP connection in seconds

        Returns:
            List of tools (either from MCP or fallback)
        """
        # Check if already initialized (fast path)
        if self._tools is not None:
            return self._tools

        # Use lock to prevent race conditions
        async with self._tools_lock:
            # Double-check pattern
            if self._tools is not None:
                return self._tools

            # Log the server configurations
            logger.info(f"Attempting MCP connection to servers: {list(self.server_configs.keys())}")

            self._client = MultiServerMCPClient(self.server_configs)

            try:
                logger.info("Starting MCP client initialization...")
                # Add timeout to prevent hanging during MCP initialization
                mcp_tools = await asyncio.wait_for(self._client.get_tools(), timeout=timeout)
                logger.info(f"Successfully connected to MCP servers. Got {len(mcp_tools)} tools")
                self._tools = mcp_tools
            except TimeoutError:
                logger.warning(
                    f"MCP server connection timed out after {timeout} seconds. Using fallback tools."
                )
                self._tools = self.fallback_tools
            except Exception as e:
                # Log the full exception details for debugging
                logger.error(f"Failed to connect to MCP servers: {type(e).__name__}: {e}")
                logger.error(f"Exception details: {repr(e)}")
                import traceback

                logger.error(f"Full traceback: {traceback.format_exc()}")
                logger.warning("Using fallback tools due to MCP connection failure.")
                self._tools = self.fallback_tools

            return self._tools

    async def get_tools(self) -> list[BaseTool]:
        """Get initialized tools."""
        if self._tools is None:
            return await self.initialize_tools()
        return self._tools

    def clear_cache(self):
        """Clear the tools cache."""
        self._tools = None


# Global MCP client managers for common configurations
_cogni_mcp_manager: MCPClientManager | None = None
_playwright_mcp_manager: MCPClientManager | None = None


def get_cogni_mcp_manager() -> MCPClientManager:
    """Get the global Cogni MCP manager."""
    global _cogni_mcp_manager
    if _cogni_mcp_manager is None:
        mcp_url = os.getenv("COGNI_MCP_URL", "http://toolhive:24160/sse")
        server_configs = {
            "cogni-mcp": {
                "url": mcp_url,
                "transport": "sse",
            }
        }
        _cogni_mcp_manager = MCPClientManager(server_configs)
    return _cogni_mcp_manager


def get_playwright_mcp_manager() -> MCPClientManager:
    """Get the global Playwright MCP manager."""
    global _playwright_mcp_manager
    if _playwright_mcp_manager is None:
        mcp_url = os.getenv("PLAYWRIGHT_MCP_URL", "http://localhost:58462/sse#playwright")
        server_configs = {
            "playwright": {
                "url": mcp_url,
                "transport": "sse",
            }
        }
        _playwright_mcp_manager = MCPClientManager(server_configs)
    return _playwright_mcp_manager


async def get_mcp_tools(server_type: str = "cogni") -> list[BaseTool]:
    """
    Get MCP tools for a specific server type.

    Args:
        server_type: Either "cogni" or "playwright"

    Returns:
        List of tools
    """
    if server_type == "cogni":
        manager = get_cogni_mcp_manager()
    elif server_type == "playwright":
        manager = get_playwright_mcp_manager()
    else:
        raise ValueError(f"Unknown server type: {server_type}")

    return await manager.get_tools()


@lru_cache(maxsize=4)
def create_mcp_manager(server_type: str, mcp_url: str) -> MCPClientManager:
    """
    Create an MCP manager for custom configurations.

    Args:
        server_type: Name of the server type
        mcp_url: MCP server URL

    Returns:
        MCPClientManager instance
    """
    server_configs = {
        server_type: {
            "url": mcp_url,
            "transport": "sse",
        }
    }
    return MCPClientManager(server_configs)
