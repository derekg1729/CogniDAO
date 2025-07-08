#!/usr/bin/env python3
"""
Test suite for MCP Health Check and Reconnection Logic.

Tests the health monitoring and automatic reconnection functionality
in the updated MCP client system.
"""

import asyncio
import pytest
import time
from unittest.mock import Mock, AsyncMock, patch
from langchain_core.tools import BaseTool

from src.shared_utils.mcp_client import MCPClientManager, ConnectionState
from src.shared_utils.mcp_monitor import (
    check_mcp_health,
    check_all_mcp_health,
    force_mcp_reconnection,
    mcp_health_monitor_loop,
)


class MockTool(BaseTool):
    """Mock tool for testing."""
    
    name: str = "mock_tool"
    description: str = "A mock tool for testing"
    
    def _run(self, *args, **kwargs):
        return "mock result"


class TestHealthCheckLogic:
    """Test health check background task functionality."""

    @pytest.fixture
    def manager(self):
        """Create a test manager with fast health check settings."""
        return MCPClientManager(
            {"test": {"url": "http://test", "transport": "sse"}},
            max_retries=2,
            base_delay=0.01,
            max_delay=0.1,
            health_check_interval=0.05,  # Very fast for testing
            connection_timeout=0.1,
        )

    @pytest.mark.asyncio
    async def test_health_check_loop_starts_on_initialization(self, manager):
        """Test that health check loop starts when tools are initialized."""
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(return_value=[MockTool()])

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            await manager.initialize_tools()

            # Health check task should be created
            assert manager._health_check_task is not None
            assert not manager._health_check_task.done()

            # Clean up
            await manager.shutdown()

    @pytest.mark.asyncio
    async def test_health_check_loop_attempts_reconnection(self, manager):
        """Test that health check loop attempts reconnection when in failed state."""
        # Start with failed state
        manager._connection_state = ConnectionState.FAILED
        manager._last_connection_attempt = 0.0  # Force immediate retry

        call_count = 0
        
        async def count_calls():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Initial failure")
            return [MockTool() for _ in range(2)]

        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=count_calls)

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            # Start health check loop
            health_task = asyncio.create_task(manager._health_check_loop())
            
            # Give it time to run a few iterations
            await asyncio.sleep(0.2)
            
            # Cancel the task
            health_task.cancel()
            
            try:
                await health_task
            except asyncio.CancelledError:
                pass

            # Should have attempted reconnection
            assert call_count >= 1

    @pytest.mark.asyncio
    async def test_health_check_loop_successful_reconnection(self, manager):
        """Test successful reconnection via health check loop."""
        # Initialize with failure
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=ConnectionError("Initial failure"))

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            # Initial failure
            tools = await manager.initialize_tools()
            assert tools == []
            assert manager.connection_state == ConnectionState.FAILED

            # Now mock successful reconnection
            mock_client.get_tools = AsyncMock(return_value=[MockTool() for _ in range(3)])

            # Wait for health check to attempt reconnection
            await asyncio.sleep(0.1)

            # Tools should be updated
            current_tools = await manager.get_tools()
            assert len(current_tools) == 3
            assert manager.connection_state == ConnectionState.CONNECTED

            # Clean up
            await manager.shutdown()

    @pytest.mark.asyncio
    async def test_health_check_loop_respects_interval(self, manager):
        """Test that health check loop respects the configured interval."""
        manager._connection_state = ConnectionState.FAILED
        manager._last_connection_attempt = 0.0

        call_count = 0
        
        async def count_calls():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Always fails")

        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=count_calls)

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            # Start health check loop
            health_task = asyncio.create_task(manager._health_check_loop())
            
            # Wait for less than one interval
            await asyncio.sleep(0.03)
            initial_count = call_count
            
            # Wait for one full interval
            await asyncio.sleep(0.05)
            final_count = call_count
            
            # Cancel the task
            health_task.cancel()
            
            try:
                await health_task
            except asyncio.CancelledError:
                pass

            # Should have made at least one more call after the interval
            assert final_count > initial_count

    @pytest.mark.asyncio
    async def test_health_check_loop_no_reconnection_when_connected(self, manager):
        """Test that health check loop doesn't attempt reconnection when already connected."""
        # Start with connected state
        manager._connection_state = ConnectionState.CONNECTED
        manager._tools = [MockTool()]

        call_count = 0
        
        async def count_calls():
            nonlocal call_count
            call_count += 1
            return [MockTool()]

        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=count_calls)

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            # Start health check loop
            health_task = asyncio.create_task(manager._health_check_loop())
            
            # Wait for a few intervals
            await asyncio.sleep(0.2)
            
            # Cancel the task
            health_task.cancel()
            
            try:
                await health_task
            except asyncio.CancelledError:
                pass

            # Should not have attempted any reconnections
            assert call_count == 0

    @pytest.mark.asyncio
    async def test_health_check_loop_handles_exceptions(self, manager):
        """Test that health check loop handles exceptions gracefully."""
        manager._connection_state = ConnectionState.FAILED
        manager._last_connection_attempt = 0.0

        # Mock an exception during health check
        with patch.object(manager, '_attempt_connection', side_effect=RuntimeError("Health check error")):
            # Start health check loop
            health_task = asyncio.create_task(manager._health_check_loop())
            
            # Wait for a few iterations
            await asyncio.sleep(0.2)
            
            # Cancel the task
            health_task.cancel()
            
            try:
                await health_task
            except asyncio.CancelledError:
                pass

            # Health check loop should continue running despite exceptions
            # (verified by the fact that it doesn't crash)

    @pytest.mark.asyncio
    async def test_health_check_loop_cancellation(self, manager):
        """Test that health check loop handles cancellation properly."""
        # Start health check loop
        health_task = asyncio.create_task(manager._health_check_loop())
        
        # Let it run briefly
        await asyncio.sleep(0.05)
        
        # Cancel the task
        health_task.cancel()
        
        # Should handle cancellation gracefully
        with pytest.raises(asyncio.CancelledError):
            await health_task

    @pytest.mark.asyncio
    async def test_get_tools_with_refresh_triggers_reconnection(self, manager):
        """Test that get_tools_with_refresh triggers reconnection attempt."""
        # Start with failed state
        manager._connection_state = ConnectionState.FAILED
        manager._tools = []
        manager._last_connection_attempt = 0.0  # Force immediate retry

        call_count = 0
        
        async def count_calls():
            nonlocal call_count
            call_count += 1
            return [MockTool() for _ in range(call_count)]

        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=count_calls)

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            # get_tools_with_refresh should trigger reconnection
            tools = await manager.get_tools_with_refresh()

            assert len(tools) == 1
            assert call_count == 1
            assert manager.connection_state == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_get_tools_with_refresh_respects_retry_timing(self, manager):
        """Test that get_tools_with_refresh respects retry timing."""
        # Start with failed state but recent attempt
        manager._connection_state = ConnectionState.FAILED
        manager._tools = []
        manager._last_connection_attempt = time.time()  # Recent attempt

        call_count = 0
        
        async def count_calls():
            nonlocal call_count
            call_count += 1
            return [MockTool()]

        mock_client = Mock()
        mock_client.get_tools = AsyncMock(side_effect=count_calls)

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            # get_tools_with_refresh should not trigger reconnection due to recent attempt
            tools = await manager.get_tools_with_refresh()

            assert tools == []  # Returns cached empty list
            assert call_count == 0  # No reconnection attempt


class TestMCPMonitorFunctions:
    """Test MCP monitor utility functions."""

    @pytest.mark.asyncio
    async def test_check_mcp_health_connected(self):
        """Test check_mcp_health with connected server."""
        mock_info = {
            "state": "connected",
            "is_connected": True,
            "retry_count": 0,
            "tools_count": 3,
        }

        with patch("src.shared_utils.mcp_monitor.get_mcp_connection_info") as mock_get_info:
            mock_get_info.return_value = mock_info

            result = await check_mcp_health("cogni")

            assert result["server_type"] == "cogni"
            assert result["healthy"] is True
            assert result["state"] == "connected"
            assert result["tools_count"] == 3
            assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_check_mcp_health_failed(self):
        """Test check_mcp_health with failed server."""
        mock_info = {
            "state": "failed",
            "is_connected": False,
            "retry_count": 3,
            "tools_count": 0,
        }

        with patch("src.shared_utils.mcp_monitor.get_mcp_connection_info") as mock_get_info:
            mock_get_info.return_value = mock_info

            result = await check_mcp_health("cogni")

            assert result["server_type"] == "cogni"
            assert result["healthy"] is False
            assert result["state"] == "failed"
            assert result["tools_count"] == 0

    @pytest.mark.asyncio
    async def test_check_mcp_health_exception(self):
        """Test check_mcp_health with exception."""
        with patch("src.shared_utils.mcp_monitor.get_mcp_connection_info") as mock_get_info:
            mock_get_info.side_effect = RuntimeError("Connection info error")

            result = await check_mcp_health("cogni")

            assert result["server_type"] == "cogni"
            assert result["healthy"] is False
            assert result["state"] == "error"
            assert "error" in result

    @pytest.mark.asyncio
    async def test_check_all_mcp_health(self):
        """Test check_all_mcp_health functionality."""
        with patch("src.shared_utils.mcp_monitor.check_mcp_health") as mock_check:
            mock_check.side_effect = [
                {"server_type": "cogni", "healthy": True, "tools_count": 3},
                {"server_type": "playwright", "healthy": False, "tools_count": 0},
            ]

            result = await check_all_mcp_health()

            assert "cogni" in result
            assert "playwright" in result
            assert "summary" in result
            
            summary = result["summary"]
            assert summary["all_healthy"] is False
            assert summary["healthy_count"] == 1
            assert summary["total_count"] == 2
            assert summary["health_percentage"] == 50.0

    @pytest.mark.asyncio
    async def test_force_mcp_reconnection_success(self):
        """Test force_mcp_reconnection with successful reconnection."""
        mock_manager = Mock()
        mock_manager.clear_cache = Mock()
        mock_manager.get_tools = AsyncMock(return_value=[MockTool() for _ in range(2)])
        mock_manager.get_connection_info = Mock(return_value={"state": "connected"})

        with patch("src.shared_utils.mcp_monitor.get_cogni_mcp_manager") as mock_get_manager:
            mock_get_manager.return_value = mock_manager

            result = await force_mcp_reconnection("cogni")

            assert result["server_type"] == "cogni"
            assert result["success"] is True
            assert result["tools_count"] == 2
            assert mock_manager.clear_cache.called
            assert mock_manager.get_tools.called

    @pytest.mark.asyncio
    async def test_force_mcp_reconnection_failure(self):
        """Test force_mcp_reconnection with failed reconnection."""
        mock_manager = Mock()
        mock_manager.clear_cache = Mock()
        mock_manager.get_tools = AsyncMock(side_effect=ConnectionError("Reconnection failed"))

        with patch("src.shared_utils.mcp_monitor.get_cogni_mcp_manager") as mock_get_manager:
            mock_get_manager.return_value = mock_manager

            result = await force_mcp_reconnection("cogni")

            assert result["server_type"] == "cogni"
            assert result["success"] is False
            assert "error" in result
            assert mock_manager.clear_cache.called

    @pytest.mark.asyncio
    async def test_force_mcp_reconnection_invalid_server(self):
        """Test force_mcp_reconnection with invalid server type."""
        result = await force_mcp_reconnection("invalid")

        assert result["server_type"] == "invalid"
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_mcp_health_monitor_loop_basic(self):
        """Test basic functionality of mcp_health_monitor_loop."""
        call_count = 0
        
        async def mock_check_all():
            nonlocal call_count
            call_count += 1
            return {
                "cogni": {"healthy": True},
                "playwright": {"healthy": True},
                "summary": {"all_healthy": True, "healthy_count": 2, "total_count": 2}
            }

        with patch("src.shared_utils.mcp_monitor.check_all_mcp_health") as mock_check:
            mock_check.side_effect = mock_check_all

            # Start monitor loop
            monitor_task = asyncio.create_task(mcp_health_monitor_loop(interval=0.05, verbose=False))
            
            # Let it run for a few iterations
            await asyncio.sleep(0.15)
            
            # Cancel the task
            monitor_task.cancel()
            
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

            # Should have made multiple health checks
            assert call_count >= 2

    @pytest.mark.asyncio
    async def test_mcp_health_monitor_loop_unhealthy_servers(self):
        """Test mcp_health_monitor_loop with unhealthy servers."""
        async def mock_check_all():
            return {
                "cogni": {"healthy": False},
                "playwright": {"healthy": True},
                "summary": {"all_healthy": False, "healthy_count": 1, "total_count": 2}
            }

        with patch("src.shared_utils.mcp_monitor.check_all_mcp_health") as mock_check:
            mock_check.side_effect = mock_check_all

            # Start monitor loop
            monitor_task = asyncio.create_task(mcp_health_monitor_loop(interval=0.05, verbose=False))
            
            # Let it run briefly
            await asyncio.sleep(0.1)
            
            # Cancel the task
            monitor_task.cancel()
            
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

            # Should have completed without error
            assert mock_check.called

    @pytest.mark.asyncio
    async def test_mcp_health_monitor_loop_exception_handling(self):
        """Test that mcp_health_monitor_loop handles exceptions."""
        call_count = 0
        
        async def mock_check_all():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Health check error")
            return {"summary": {"all_healthy": True}}

        with patch("src.shared_utils.mcp_monitor.check_all_mcp_health") as mock_check:
            mock_check.side_effect = mock_check_all

            # Start monitor loop
            monitor_task = asyncio.create_task(mcp_health_monitor_loop(interval=0.05, verbose=False))
            
            # Let it run through the error and recovery
            await asyncio.sleep(0.15)
            
            # Cancel the task
            monitor_task.cancel()
            
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

            # Should have continued after the error
            assert call_count >= 2


class TestShutdownAndCleanup:
    """Test shutdown and cleanup functionality."""

    @pytest.mark.asyncio
    async def test_manager_shutdown(self):
        """Test manager shutdown cleans up resources."""
        manager = MCPClientManager(
            {"test": {"url": "http://test", "transport": "sse"}},
            health_check_interval=0.05,
        )

        # Initialize to start health check task
        mock_client = Mock()
        mock_client.get_tools = AsyncMock(return_value=[MockTool()])

        with patch("src.shared_utils.mcp_client.MultiServerMCPClient") as mock_mcp:
            mock_mcp.return_value = mock_client

            await manager.initialize_tools()
            
            # Verify health check task is running
            assert manager._health_check_task is not None
            assert not manager._health_check_task.done()

            # Shutdown should clean up the task
            await manager.shutdown()

            # Health check task should be cancelled
            assert manager._health_check_task.cancelled()

    @pytest.mark.asyncio
    async def test_manager_shutdown_no_health_check_task(self):
        """Test manager shutdown when no health check task exists."""
        manager = MCPClientManager(
            {"test": {"url": "http://test", "transport": "sse"}},
        )

        # Shutdown should not fail when no health check task exists
        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_manager_shutdown_already_done_task(self):
        """Test manager shutdown when health check task is already done."""
        manager = MCPClientManager(
            {"test": {"url": "http://test", "transport": "sse"}},
        )

        # Create a done task
        done_task = asyncio.create_task(asyncio.sleep(0))
        await done_task
        manager._health_check_task = done_task

        # Shutdown should handle done task gracefully
        await manager.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])