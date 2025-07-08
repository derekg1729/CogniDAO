#!/usr/bin/env python3
"""
Test suite for MCP Client functionality.

Tests the updated MCP client implementation that removed fallback_tools
and now returns empty lists when MCP servers are unavailable.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from langchain_core.tools import BaseTool

from src.shared_utils.mcp_client import (
    MCPClientManager,
    ConnectionState,
    get_cogni_mcp_manager,
    get_playwright_mcp_manager,
    get_mcp_tools,
    get_mcp_tools_with_refresh,
    get_mcp_connection_info,
    create_mcp_manager,
)


class MockTool(BaseTool):
    """Mock tool for testing."""
    
    name: str = "mock_tool"
    description: str = "A mock tool for testing"
    
    def _run(self, *args, **kwargs):
        return "mock result"


class MockFailingMCPClient:
    """Mock MCP client that fails initially, then succeeds."""

    def __init__(self, fail_attempts: int = 3, success_tools: int = 2):
        self.fail_attempts = fail_attempts
        self.attempt_count = 0
        self.success_tools = success_tools

    async def get_tools(self):
        self.attempt_count += 1
        if self.attempt_count <= self.fail_attempts:
            raise ConnectionError(f"Mock connection failed (attempt {self.attempt_count})")

        # Return mock tools after successful connection
        return [MockTool() for _ in range(self.success_tools)]


class TestMCPClientManager:
    """Test suite for MCPClientManager class."""

    @pytest.fixture
    def server_configs(self):
        """Standard server configs for testing."""
        return {
            "test-server": {
                "url": "http://test-server:8080/sse",
                "transport": "sse",
            }
        }

    @pytest.fixture
    def manager(self, server_configs):
        """Create a test manager with fast settings."""
        return MCPClientManager(
            server_configs,
            max_retries=3,
            base_delay=0.01,  # Very fast for testing
            max_delay=0.1,
            health_check_interval=0.1,
            connection_timeout=0.5,
        )

    def test_initialization(self, server_configs):
        """Test MCPClientManager initialization."""
        manager = MCPClientManager(
            server_configs,
            max_retries=5,
            base_delay=1.0,
            max_delay=60.0,
            health_check_interval=30.0,
            connection_timeout=30.0,
        )
        
        assert manager.server_configs == server_configs
        assert manager.max_retries == 5
        assert manager.base_delay == 1.0
        assert manager.max_delay == 60.0
        assert manager.health_check_interval == 30.0
        assert manager.connection_timeout == 30.0
        assert manager.connection_state == ConnectionState.DISCONNECTED
        assert manager.is_connected is False

    def test_initialization_no_fallback_tools_param(self, server_configs):
        """Test that fallback_tools parameter is no longer accepted."""
        # This should work without fallback_tools parameter
        manager = MCPClientManager(server_configs)
        assert manager.server_configs == server_configs
        
        # Verify fallback_tools attribute doesn't exist
        assert not hasattr(manager, 'fallback_tools')

    @pytest.mark.asyncio
    async def test_successful_connection(self, manager):
        """Test successful MCP connection."""
        mock_tools = [MockTool() for _ in range(2)]
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(return_value=mock_tools)

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            tools = await manager.initialize_tools()

            assert len(tools) == 2
            assert all(isinstance(tool, MockTool) for tool in tools)
            assert manager.connection_state == ConnectionState.CONNECTED
            assert manager.is_connected is True

    @pytest.mark.asyncio
    async def test_connection_failure_returns_empty_list(self, manager):
        """Test that connection failure returns empty list (no fallback tools)."""
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=ConnectionError("Connection failed"))

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            tools = await manager.initialize_tools()

            # Should return empty list, not fallback tools
            assert tools == []
            assert manager.connection_state == ConnectionState.FAILED
            assert manager.is_connected is False

    @pytest.mark.asyncio
    async def test_connection_timeout_returns_empty_list(self, manager):
        """Test that connection timeout returns empty list."""
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=asyncio.TimeoutError("Timeout"))

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            tools = await manager.initialize_tools()

            assert tools == []
            assert manager.connection_state == ConnectionState.FAILED
            assert manager.is_connected is False

    @pytest.mark.asyncio
    async def test_retry_logic_eventual_success(self, manager):
        """Test retry logic with eventual success."""
        mock_client = MockFailingMCPClient(fail_attempts=2, success_tools=3)

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            tools = await manager.initialize_tools()

            # Should succeed on 3rd attempt
            assert len(tools) == 3
            assert manager.connection_state == ConnectionState.CONNECTED
            assert manager.is_connected is True
            assert mock_client.attempt_count == 3

    @pytest.mark.asyncio
    async def test_retry_logic_max_retries_exceeded(self, manager):
        """Test retry logic when max retries exceeded."""
        mock_client = MockFailingMCPClient(fail_attempts=10)  # Always fails

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            tools = await manager.initialize_tools()

            # Should return empty list after max retries
            assert tools == []
            assert manager.connection_state == ConnectionState.FAILED
            assert manager.is_connected is False
            assert mock_client.attempt_count == manager.max_retries + 1

    @pytest.mark.asyncio
    async def test_get_tools_caching(self, manager):
        """Test that get_tools returns cached tools."""
        mock_tools = [MockTool() for _ in range(2)]
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(return_value=mock_tools)

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            # First call should initialize
            tools1 = await manager.get_tools()
            assert len(tools1) == 2
            assert mock_client.get_tools.call_count == 1

            # Second call should return cached tools
            tools2 = await manager.get_tools()
            assert tools1 is tools2  # Same object reference
            assert mock_client.get_tools.call_count == 1  # Not called again

    @pytest.mark.asyncio
    async def test_get_tools_with_refresh_failed_state(self, manager):
        """Test get_tools_with_refresh when in failed state."""
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=ConnectionError("Failed"))

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            # First call fails
            tools1 = await manager.get_tools()
            assert tools1 == []
            assert manager.connection_state == ConnectionState.FAILED

            # Mock successful reconnection with a new client
            mock_tools = [MockTool() for _ in range(2)]
            
            # Reset the last attempt time to allow refresh
            manager._last_connection_attempt = 0.0
            
            with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp2:
                mock_client2 = Mock()
                mock_client2.get_tools = AsyncMock(return_value=mock_tools)
                mock_mcp2.return_value = mock_client2
                
                # get_tools_with_refresh should attempt reconnection
                tools2 = await manager.get_tools_with_refresh()
                assert len(tools2) == 2
                assert manager.connection_state == ConnectionState.CONNECTED

    def test_clear_cache(self, manager):
        """Test cache clearing functionality."""
        manager._tools = [MockTool()]
        manager._connection_state = ConnectionState.CONNECTED
        manager._retry_count = 2
        
        # Create a real task to test cancellation
        mock_task = Mock()
        mock_task.done.return_value = False
        manager._health_check_task = mock_task

        manager.clear_cache()

        assert manager._tools is None
        assert manager._connection_state == ConnectionState.DISCONNECTED
        assert manager._retry_count == 0
        assert mock_task.cancel.called

    def test_get_connection_info(self, manager):
        """Test connection info reporting."""
        manager._tools = [MockTool(), MockTool()]
        manager._connection_state = ConnectionState.CONNECTED
        manager._retry_count = 1

        info = manager.get_connection_info()

        assert info["state"] == ConnectionState.CONNECTED.value
        assert info["is_connected"] is True
        assert info["retry_count"] == 1
        assert info["max_retries"] == 3
        assert info["tools_count"] == 2
        assert info["server_configs"] == ["test-server"]
        
        # Verify fallback_tools_count is not in info
        assert "fallback_tools_count" not in info
        assert "using_fallback" not in info

    @pytest.mark.asyncio
    async def test_health_check_loop_reconnection(self, manager):
        """Test health check loop attempts reconnection."""
        # Start with failed state
        manager._connection_state = ConnectionState.FAILED
        manager._last_connection_attempt = 0.0  # Force immediate retry

        mock_tools = [MockTool() for _ in range(2)]
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(return_value=mock_tools)

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            # Start health check loop
            health_task = asyncio.create_task(manager._health_check_loop())
            
            # Give it time to run one iteration
            await asyncio.sleep(0.2)
            
            # Cancel the task
            health_task.cancel()
            
            try:
                await health_task
            except asyncio.CancelledError:
                pass

            # Should have attempted reconnection
            assert mock_client.get_tools.called

    @pytest.mark.asyncio
    async def test_exponential_backoff_delay(self, manager):
        """Test exponential backoff delay calculation."""
        delay0 = await manager._exponential_backoff_delay(0)
        delay1 = await manager._exponential_backoff_delay(1)
        delay2 = await manager._exponential_backoff_delay(2)

        # Each delay should be roughly double the previous (with jitter)
        assert delay0 < delay1 < delay2
        assert delay0 >= manager.base_delay * 0.9  # Account for jitter
        assert delay2 <= manager.max_delay


class TestGlobalFunctions:
    """Test suite for global MCP functions."""

    @pytest.mark.asyncio
    async def test_get_mcp_tools_cogni(self):
        """Test get_mcp_tools for cogni server."""
        mock_tools = [MockTool() for _ in range(2)]
        
        with patch("src.shared_utils.mcp_client.get_cogni_mcp_manager") as mock_get_manager:
            mock_manager = Mock()
            mock_manager.get_tools = AsyncMock(return_value=mock_tools)
            mock_get_manager.return_value = mock_manager

            tools = await get_mcp_tools("cogni")
            
            assert len(tools) == 2
            assert mock_manager.get_tools.called

    @pytest.mark.asyncio
    async def test_get_mcp_tools_playwright(self):
        """Test get_mcp_tools for playwright server."""
        mock_tools = [MockTool() for _ in range(3)]
        
        with patch("src.shared_utils.mcp_client.get_playwright_mcp_manager") as mock_get_manager:
            mock_manager = Mock()
            mock_manager.get_tools = AsyncMock(return_value=mock_tools)
            mock_get_manager.return_value = mock_manager

            tools = await get_mcp_tools("playwright")
            
            assert len(tools) == 3
            assert mock_manager.get_tools.called

    @pytest.mark.asyncio
    async def test_get_mcp_tools_invalid_server(self):
        """Test get_mcp_tools with invalid server type."""
        with pytest.raises(ValueError, match="Unknown server type: invalid"):
            await get_mcp_tools("invalid")

    @pytest.mark.asyncio
    async def test_get_mcp_tools_with_refresh(self):
        """Test get_mcp_tools_with_refresh functionality."""
        mock_tools = [MockTool() for _ in range(2)]
        
        with patch("src.shared_utils.mcp_client.get_cogni_mcp_manager") as mock_get_manager:
            mock_manager = Mock()
            mock_manager.get_tools_with_refresh = AsyncMock(return_value=mock_tools)
            mock_get_manager.return_value = mock_manager

            tools = await get_mcp_tools_with_refresh("cogni")
            
            assert len(tools) == 2
            assert mock_manager.get_tools_with_refresh.called

    def test_get_mcp_connection_info(self):
        """Test get_mcp_connection_info functionality."""
        mock_info = {"state": "connected", "tools_count": 5}
        
        with patch("src.shared_utils.mcp_client.get_cogni_mcp_manager") as mock_get_manager:
            mock_manager = Mock()
            mock_manager.get_connection_info = Mock(return_value=mock_info)
            mock_get_manager.return_value = mock_manager

            info = get_mcp_connection_info("cogni")
            
            assert info == mock_info
            assert mock_manager.get_connection_info.called

    def test_create_mcp_manager(self):
        """Test create_mcp_manager functionality."""
        manager = create_mcp_manager("custom-server", "http://custom:8080/sse")
        
        assert isinstance(manager, MCPClientManager)
        assert "custom-server" in manager.server_configs
        assert manager.server_configs["custom-server"]["url"] == "http://custom:8080/sse"

    @patch.dict('os.environ', {'COGNI_MCP_URL': 'http://custom-cogni:9999/sse'})
    def test_get_cogni_mcp_manager_env_var(self):
        """Test get_cogni_mcp_manager respects environment variable."""
        # Clear any existing global manager
        import src.shared_utils.mcp_client as mcp_module
        mcp_module._cogni_mcp_manager = None
        
        manager = get_cogni_mcp_manager()
        
        assert isinstance(manager, MCPClientManager)
        assert manager.server_configs["cogni-mcp"]["url"] == "http://custom-cogni:9999/sse"

    @patch.dict('os.environ', {'PLAYWRIGHT_MCP_URL': 'http://custom-playwright:8888/sse#playwright'})
    def test_get_playwright_mcp_manager_env_var(self):
        """Test get_playwright_mcp_manager respects environment variable."""
        # Clear any existing global manager
        import src.shared_utils.mcp_client as mcp_module
        mcp_module._playwright_mcp_manager = None
        
        manager = get_playwright_mcp_manager()
        
        assert isinstance(manager, MCPClientManager)
        assert manager.server_configs["playwright"]["url"] == "http://custom-playwright:8888/sse#playwright"


class TestConnectionStates:
    """Test suite for connection state management."""

    @pytest.fixture
    def manager(self):
        """Create a test manager."""
        return MCPClientManager({"test": {"url": "http://test", "transport": "sse"}})

    def test_initial_state(self, manager):
        """Test initial connection state."""
        assert manager.connection_state == ConnectionState.DISCONNECTED
        assert manager.is_connected is False

    def test_state_transitions(self, manager):
        """Test connection state transitions."""
        # Test all state transitions
        manager._connection_state = ConnectionState.CONNECTING
        assert manager.connection_state == ConnectionState.CONNECTING
        assert manager.is_connected is False

        manager._connection_state = ConnectionState.CONNECTED
        assert manager.connection_state == ConnectionState.CONNECTED
        assert manager.is_connected is True

        manager._connection_state = ConnectionState.FAILED
        assert manager.connection_state == ConnectionState.FAILED
        assert manager.is_connected is False

        manager._connection_state = ConnectionState.RETRYING
        assert manager.connection_state == ConnectionState.RETRYING
        assert manager.is_connected is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])