"""
MCP Client Management for LangGraph Projects.

Provides centralized MCP client initialization, tool management, and fallback handling
with automatic reconnection and retry logic.
"""

import asyncio
import os
import time
from functools import lru_cache
from typing import Any
from enum import Enum

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


class ConnectionState(Enum):
    """MCP connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    FAILED = "failed"
    RETRYING = "retrying"


class MCPClientManager:
    """Manages MCP client connections and tool initialization with automatic reconnection."""

    def __init__(
        self,
        server_configs: dict[str, dict[str, Any]],
        fallback_tools: list[BaseTool] | None = None,
        max_retries: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        health_check_interval: float = 30.0,
        connection_timeout: float = 30.0,
    ):
        """
        Initialize MCP client manager with retry and reconnection capabilities.

        Args:
            server_configs: Dictionary of server configurations
            fallback_tools: List of fallback tools to use when MCP is unavailable
            max_retries: Maximum number of retry attempts before giving up
            base_delay: Base delay in seconds for exponential backoff
            max_delay: Maximum delay in seconds between retries
            health_check_interval: Interval in seconds for periodic health checks
            connection_timeout: Timeout for individual connection attempts
        """
        self.server_configs = server_configs
        self.fallback_tools = fallback_tools or _fallback_tools
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.health_check_interval = health_check_interval
        self.connection_timeout = connection_timeout

        # Connection state management
        self._tools: list[BaseTool] | None = None
        self._tools_lock = asyncio.Lock()
        self._client: MultiServerMCPClient | None = None
        self._connection_state = ConnectionState.DISCONNECTED
        self._last_connection_attempt = 0.0
        self._retry_count = 0
        self._health_check_task: asyncio.Task | None = None
        self._using_fallback = False

    @property
    def connection_state(self) -> ConnectionState:
        """Get current connection state."""
        return self._connection_state

    @property
    def is_connected(self) -> bool:
        """Check if MCP client is currently connected."""
        return self._connection_state == ConnectionState.CONNECTED

    @property
    def is_using_fallback(self) -> bool:
        """Check if currently using fallback tools."""
        return self._using_fallback

    def _log_exception_details(self, error: Exception, context: str = "MCP connection") -> None:
        """Log detailed exception information, handling ExceptionGroup (Python 3.11+)."""
        # Handle ExceptionGroup (Python 3.11+) using duck typing for compatibility
        if hasattr(error, "exceptions"):  # Duck typing for ExceptionGroup
            logger.error(f"❌ {context} failed with {len(error.exceptions)} sub-exceptions:")
            for i, sub_exc in enumerate(error.exceptions, 1):
                logger.error(f"  #{i}: {type(sub_exc).__name__}: {sub_exc}")
                if hasattr(sub_exc, "__traceback__") and sub_exc.__traceback__:
                    import traceback

                    logger.debug(
                        f"  #{i} traceback: {''.join(traceback.format_tb(sub_exc.__traceback__))}"
                    )
        else:
            # Regular exception
            logger.error(f"❌ {context} failed: {type(error).__name__}: {error}")
            logger.debug(f"Exception details: {repr(error)}")

    async def _exponential_backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        delay = min(self.base_delay * (2**attempt), self.max_delay)
        # Add jitter to prevent thundering herd
        jitter = delay * 0.1 * (0.5 - asyncio.get_event_loop().time() % 1.0)
        return delay + jitter

    async def _attempt_connection(self) -> list[BaseTool] | None:
        """
        Attempt to connect to MCP server and get tools.

        Returns:
            List of tools if successful, None if failed
        """
        try:
            logger.info(f"Attempting MCP connection to servers: {list(self.server_configs.keys())}")
            self._connection_state = ConnectionState.CONNECTING

            # Create new client for each attempt
            self._client = MultiServerMCPClient(self.server_configs)

            # Add timeout to prevent hanging
            mcp_tools = await asyncio.wait_for(
                self._client.get_tools(), timeout=self.connection_timeout
            )

            logger.info(f"✅ Successfully connected to MCP servers. Got {len(mcp_tools)} tools")
            self._connection_state = ConnectionState.CONNECTED
            self._retry_count = 0  # Reset retry count on success
            self._using_fallback = False

            return mcp_tools

        except asyncio.TimeoutError:
            logger.warning(f"⏰ MCP connection timed out after {self.connection_timeout} seconds")
            self._connection_state = ConnectionState.FAILED
            return None

        except Exception as e:
            self._log_exception_details(e, "MCP connection")
            self._connection_state = ConnectionState.FAILED
            return None

    async def _connection_with_retry(self) -> list[BaseTool]:
        """
        Attempt connection with exponential backoff retry logic.

        Returns:
            List of tools (either from MCP or fallback)
        """
        for attempt in range(self.max_retries + 1):
            self._retry_count = attempt

            # Try to connect
            tools = await self._attempt_connection()
            if tools is not None:
                return tools

            # If this was the last attempt, give up
            if attempt >= self.max_retries:
                logger.error(
                    f"❌ Failed to connect to MCP after {self.max_retries} attempts. Using fallback tools."
                )
                self._connection_state = ConnectionState.FAILED
                self._using_fallback = True
                return self.fallback_tools

            # Calculate delay and wait
            delay = await self._exponential_backoff_delay(attempt)
            logger.info(
                f"⏳ Retrying MCP connection in {delay:.1f}s (attempt {attempt + 1}/{self.max_retries})..."
            )
            self._connection_state = ConnectionState.RETRYING

            await asyncio.sleep(delay)

        # Should never reach here, but fallback just in case
        self._using_fallback = True
        return self.fallback_tools

    async def _health_check_loop(self):
        """Background task to periodically check MCP connection health and attempt reconnection."""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)

                # Only attempt reconnection if we're currently using fallback tools
                # and haven't attempted recently
                current_time = time.time()
                time_since_last_attempt = current_time - self._last_connection_attempt

                if (
                    self._using_fallback
                    and time_since_last_attempt >= self.health_check_interval
                    and self._connection_state != ConnectionState.CONNECTING
                ):
                    logger.info("🔄 Health check: Attempting to reconnect to MCP servers...")
                    self._last_connection_attempt = current_time

                    # Try to reconnect
                    async with self._tools_lock:
                        tools = await self._attempt_connection()
                        if tools is not None:
                            logger.info("🎉 MCP reconnection successful! Refreshing tools...")
                            self._tools = tools
                            # Notify that tools have been refreshed
                            # In the future, this could trigger graph recompilation
                        else:
                            logger.debug("Health check: MCP still unavailable")

            except asyncio.CancelledError:
                logger.info("Health check loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")

    async def initialize_tools(self, timeout: float = 30.0) -> list[BaseTool]:
        """
        Initialize MCP tools with retry logic and fallback.

        Args:
            timeout: Legacy parameter for compatibility (now uses connection_timeout)

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

            self._last_connection_attempt = time.time()

            # Attempt connection with retry logic
            self._tools = await self._connection_with_retry()

            # Start health check background task if not already running
            if self._health_check_task is None or self._health_check_task.done():
                self._health_check_task = asyncio.create_task(self._health_check_loop())
                logger.debug("Started MCP health check background task")

            return self._tools

    async def get_tools(self) -> list[BaseTool]:
        """Get initialized tools."""
        if self._tools is None:
            return await self.initialize_tools()
        return self._tools

    async def get_tools_with_refresh(self) -> list[BaseTool]:
        """
        Get tools and attempt refresh if using fallback.

        This method is useful for agents that want to check if MCP has become
        available since the last check.
        """
        tools = await self.get_tools()

        # If using fallback and enough time has passed, try to refresh
        if self._using_fallback:
            current_time = time.time()
            time_since_last_attempt = current_time - self._last_connection_attempt

            if (
                time_since_last_attempt >= 10.0
            ):  # Try refresh every 10 seconds when called explicitly
                logger.debug("Attempting explicit tool refresh...")
                self._last_connection_attempt = current_time

                async with self._tools_lock:
                    fresh_tools = await self._attempt_connection()
                    if fresh_tools is not None:
                        logger.info("🔄 Tools refreshed from MCP server!")
                        self._tools = fresh_tools
                        return fresh_tools

        return tools

    def clear_cache(self):
        """Clear the tools cache and reset connection state."""
        self._tools = None
        self._connection_state = ConnectionState.DISCONNECTED
        self._retry_count = 0
        self._using_fallback = False

        # Cancel health check task
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            self._health_check_task = None

    async def shutdown(self):
        """Gracefully shutdown the MCP client manager."""
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        if self._client:
            # Future: Add proper client shutdown if langchain_mcp_adapters supports it
            pass

    def get_connection_info(self) -> dict[str, Any]:
        """Get detailed connection information for monitoring/debugging."""
        return {
            "state": self._connection_state.value,
            "is_connected": self.is_connected,
            "using_fallback": self._using_fallback,
            "retry_count": self._retry_count,
            "max_retries": self.max_retries,
            "tools_count": len(self._tools) if self._tools else 0,
            "fallback_tools_count": len(self.fallback_tools),
            "server_configs": list(self.server_configs.keys()),
        }


# Global MCP client managers for common configurations
_cogni_mcp_manager: MCPClientManager | None = None
_playwright_mcp_manager: MCPClientManager | None = None


def get_cogni_mcp_manager() -> MCPClientManager:
    """Get the global Cogni MCP manager with reconnection capabilities."""
    global _cogni_mcp_manager
    if _cogni_mcp_manager is None:
        mcp_url = os.getenv("COGNI_MCP_URL", "http://toolhive:24160/sse")
        server_configs = {
            "cogni-mcp": {
                "url": mcp_url,
                "transport": "sse",
            }
        }
        # Configure with environment variables or sensible defaults
        max_retries = int(os.getenv("MCP_MAX_RETRIES", "5"))
        health_check_interval = float(os.getenv("MCP_HEALTH_CHECK_INTERVAL", "30.0"))
        connection_timeout = float(os.getenv("MCP_CONNECTION_TIMEOUT", "30.0"))

        _cogni_mcp_manager = MCPClientManager(
            server_configs,
            max_retries=max_retries,
            health_check_interval=health_check_interval,
            connection_timeout=connection_timeout,
        )
    return _cogni_mcp_manager


def get_playwright_mcp_manager() -> MCPClientManager:
    """Get the global Playwright MCP manager with reconnection capabilities."""
    global _playwright_mcp_manager
    if _playwright_mcp_manager is None:
        mcp_url = os.getenv("PLAYWRIGHT_MCP_URL", "http://toolhive:24162/sse#playwright")
        server_configs = {
            "playwright": {
                "url": mcp_url,
                "transport": "sse",
            }
        }
        # Configure with environment variables or sensible defaults
        max_retries = int(os.getenv("MCP_MAX_RETRIES", "5"))
        health_check_interval = float(os.getenv("MCP_HEALTH_CHECK_INTERVAL", "30.0"))
        connection_timeout = float(os.getenv("MCP_CONNECTION_TIMEOUT", "30.0"))

        _playwright_mcp_manager = MCPClientManager(
            server_configs,
            max_retries=max_retries,
            health_check_interval=health_check_interval,
            connection_timeout=connection_timeout,
        )
    return _playwright_mcp_manager


async def get_mcp_tools(server_type: str = "cogni") -> list[BaseTool]:
    """
    Get MCP tools for a specific server type with automatic reconnection.

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


async def get_mcp_tools_with_refresh(server_type: str = "cogni") -> list[BaseTool]:
    """
    Get MCP tools with explicit refresh attempt if using fallback.

    This function is useful for agents that want to check if MCP servers
    have become available since the last check.

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

    return await manager.get_tools_with_refresh()


def get_mcp_connection_info(server_type: str = "cogni") -> dict[str, Any]:
    """
    Get connection information for a specific MCP server type.

    Args:
        server_type: Either "cogni" or "playwright"

    Returns:
        Dictionary with connection details
    """
    if server_type == "cogni":
        manager = get_cogni_mcp_manager()
    elif server_type == "playwright":
        manager = get_playwright_mcp_manager()
    else:
        raise ValueError(f"Unknown server type: {server_type}")

    return manager.get_connection_info()


@lru_cache(maxsize=4)
def create_mcp_manager(server_type: str, mcp_url: str) -> MCPClientManager:
    """
    Create an MCP manager for custom configurations.

    Args:
        server_type: Name of the server type
        mcp_url: MCP server URL

    Returns:
        MCPClientManager instance with reconnection capabilities
    """
    server_configs = {
        server_type: {
            "url": mcp_url,
            "transport": "sse",
        }
    }
    return MCPClientManager(server_configs)
