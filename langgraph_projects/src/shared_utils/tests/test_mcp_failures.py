#!/usr/bin/env python3
"""
Test suite for MCP Client failure scenarios.

Tests various failure modes and edge cases for the MCP client system,
focusing on the new behavior where failures result in empty tool lists
rather than fallback tools.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from langchain_core.tools import BaseTool

from src.shared_utils.mcp_client import MCPClientManager, ConnectionState


class MockTool(BaseTool):
    """Mock tool for testing."""
    
    name: str = "mock_tool"
    description: str = "A mock tool for testing"
    
    def _run(self, *args, **kwargs):
        return "mock result"


class TestConnectionFailureScenarios:
    """Test various connection failure scenarios."""

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
            max_retries=2,
            base_delay=0.01,
            max_delay=0.1,
            health_check_interval=0.1,
            connection_timeout=0.1,
        )

    @pytest.mark.asyncio
    async def test_connection_refused(self, manager):
        """Test behavior when connection is refused."""
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=ConnectionRefusedError("Connection refused"))

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            tools = await manager.initialize_tools()

            assert tools == []
            assert manager.connection_state == ConnectionState.FAILED
            assert manager.is_connected is False

    @pytest.mark.asyncio
    async def test_network_timeout(self, manager):
        """Test behavior when network times out."""
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=asyncio.TimeoutError("Network timeout"))

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            tools = await manager.initialize_tools()

            assert tools == []
            assert manager.connection_state == ConnectionState.FAILED
            assert manager.is_connected is False

    @pytest.mark.asyncio
    async def test_ssl_error(self, manager):
        """Test behavior when SSL error occurs."""
        import ssl
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=ssl.SSLError("SSL handshake failed"))

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            tools = await manager.initialize_tools()

            assert tools == []
            assert manager.connection_state == ConnectionState.FAILED
            assert manager.is_connected is False

    @pytest.mark.asyncio
    async def test_json_decode_error(self, manager):
        """Test behavior when JSON decoding fails."""
        import json
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=json.JSONDecodeError("Invalid JSON", "doc", 0))

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            tools = await manager.initialize_tools()

            assert tools == []
            assert manager.connection_state == ConnectionState.FAILED
            assert manager.is_connected is False

    @pytest.mark.asyncio
    async def test_unexpected_exception(self, manager):
        """Test behavior when unexpected exception occurs."""
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=RuntimeError("Unexpected error"))

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            tools = await manager.initialize_tools()

            assert tools == []
            assert manager.connection_state == ConnectionState.FAILED
            assert manager.is_connected is False

    @pytest.mark.asyncio
    async def test_intermittent_failures(self, manager):
        """Test behavior with intermittent connection failures."""
        call_count = 0
        
        async def failing_get_tools():
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                raise ConnectionError("Intermittent failure")
            return [MockTool() for _ in range(2)]

        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=failing_get_tools)

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            tools = await manager.initialize_tools()

            # Should succeed on second attempt
            assert len(tools) == 2
            assert manager.connection_state == ConnectionState.CONNECTED
            assert manager.is_connected is True
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_connection_drop_during_get_tools(self, manager):
        """Test behavior when connection drops during get_tools call."""
        mock_client = Mock()
        
        async def connection_drop():
            await asyncio.sleep(0.05)  # Simulate some delay
            raise ConnectionResetError("Connection dropped")

        mock_client.get_tools = AsyncMock(side_effect=connection_drop)

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            tools = await manager.initialize_tools()

            assert tools == []
            assert manager.connection_state == ConnectionState.FAILED
            assert manager.is_connected is False

    @pytest.mark.asyncio
    async def test_empty_tools_response(self, manager):
        """Test behavior when server returns empty tools list."""
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(return_value=[])

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            tools = await manager.initialize_tools()

            # Empty list is valid response from server
            assert tools == []
            assert manager.connection_state == ConnectionState.CONNECTED
            assert manager.is_connected is True

    @pytest.mark.asyncio
    async def test_malformed_tools_response(self, manager):
        """Test behavior when server returns malformed tools."""
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(return_value=["not_a_tool", None, 123])

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            tools = await manager.initialize_tools()

            # Should accept whatever the server returns
            assert tools == ["not_a_tool", None, 123]
            assert manager.connection_state == ConnectionState.CONNECTED
            assert manager.is_connected is True

    @pytest.mark.asyncio
    async def test_connection_timeout_with_retry(self, manager):
        """Test that connection timeout triggers retry logic."""
        call_count = 0
        
        async def timeout_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise asyncio.TimeoutError("First attempt timeout")
            return [MockTool()]

        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=timeout_then_succeed)

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            tools = await manager.initialize_tools()

            # Should succeed on second attempt
            assert len(tools) == 1
            assert manager.connection_state == ConnectionState.CONNECTED
            assert manager.is_connected is True
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self, manager):
        """Test behavior when max retries are exhausted."""
        call_count = 0
        
        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise ConnectionError(f"Failure {call_count}")

        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=always_fail)

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            tools = await manager.initialize_tools()

            # Should fail after max_retries + 1 attempts
            assert tools == []
            assert manager.connection_state == ConnectionState.FAILED
            assert manager.is_connected is False
            assert call_count == manager.max_retries + 1

    @pytest.mark.asyncio
    async def test_client_creation_failure(self, manager):
        """Test behavior when MCP client creation fails."""
        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.side_effect = RuntimeError("Client creation failed")

            tools = await manager.initialize_tools()

            # Should handle client creation failure gracefully
            assert tools == []
            assert manager.connection_state == ConnectionState.FAILED
            assert manager.is_connected is False

    @pytest.mark.asyncio
    async def test_memory_error_during_connection(self, manager):
        """Test behavior when memory error occurs during connection."""
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=MemoryError("Out of memory"))

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            tools = await manager.initialize_tools()

            assert tools == []
            assert manager.connection_state == ConnectionState.FAILED
            assert manager.is_connected is False

    @pytest.mark.asyncio
    async def test_keyboard_interrupt_during_connection(self, manager):
        """Test behavior when KeyboardInterrupt occurs during connection."""
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=KeyboardInterrupt("User interrupt"))

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            # KeyboardInterrupt should propagate up
            with pytest.raises(KeyboardInterrupt):
                await manager.initialize_tools()

    @pytest.mark.asyncio
    async def test_system_exit_during_connection(self, manager):
        """Test behavior when SystemExit occurs during connection."""
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=SystemExit("System exit"))

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            # SystemExit should propagate up
            with pytest.raises(SystemExit):
                await manager.initialize_tools()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_zero_max_retries(self):
        """Test behavior with zero max retries."""
        manager = MCPClientManager(
            {"test": {"url": "http://test", "transport": "sse"}},
            max_retries=0,
            base_delay=0.01,
            max_delay=0.1,
            connection_timeout=0.1,
        )

        call_count = 0
        
        async def count_calls():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Always fails")

        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=count_calls)

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            tools = await manager.initialize_tools()

            # Should only try once (max_retries=0 means 1 attempt total)
            assert tools == []
            assert call_count == 1

    @pytest.mark.asyncio
    async def test_very_short_timeout(self):
        """Test behavior with very short timeout."""
        manager = MCPClientManager(
            {"test": {"url": "http://test", "transport": "sse"}},
            max_retries=1,
            base_delay=0.01,
            max_delay=0.1,
            connection_timeout=0.001,  # Very short timeout
        )

        async def slow_response():
            await asyncio.sleep(0.1)  # Longer than timeout
            return [MockTool()]

        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=slow_response)

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            tools = await manager.initialize_tools()

            # Should timeout and return empty list
            assert tools == []
            assert manager.connection_state == ConnectionState.FAILED

    @pytest.mark.asyncio
    async def test_large_number_of_tools(self):
        """Test behavior with large number of tools."""
        manager = MCPClientManager(
            {"test": {"url": "http://test", "transport": "sse"}},
            max_retries=1,
            connection_timeout=1.0,
        )

        # Create 1000 mock tools
        large_tools_list = [MockTool() for _ in range(1000)]

        mock_client = Mock()
        mock_client.get_tools = AsyncMock(return_value=large_tools_list)

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            tools = await manager.initialize_tools()

            # Should handle large number of tools
            assert len(tools) == 1000
            assert manager.connection_state == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_concurrent_initialization_calls(self):
        """Test concurrent calls to initialize_tools."""
        manager = MCPClientManager(
            {"test": {"url": "http://test", "transport": "sse"}},
            max_retries=1,
            connection_timeout=0.5,
        )

        call_count = 0
        
        async def count_calls():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # Simulate some work
            return [MockTool() for _ in range(call_count)]

        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=count_calls)

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            # Start multiple concurrent initialization calls
            tasks = [manager.initialize_tools() for _ in range(5)]
            results = await asyncio.gather(*tasks)

            # Should only call get_tools once due to locking
            assert call_count == 1
            
            # All results should be the same (cached)
            for result in results:
                assert len(result) == 1
                assert result is results[0]  # Same object reference


if __name__ == "__main__":
    pytest.main([__file__, "-v"])