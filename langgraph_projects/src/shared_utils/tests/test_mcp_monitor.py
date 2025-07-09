#!/usr/bin/env python3
"""
Test suite for MCP Monitor functionality.

Tests the updated MCP monitor that no longer references fallback_tools
and properly handles the new connection states.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from io import StringIO

from src.shared_utils.mcp_monitor import (
    check_mcp_health,
    check_all_mcp_health,
    force_mcp_reconnection,
    print_mcp_status,
)


class TestMCPMonitor:
    """Test MCP monitor functionality."""

    @pytest.mark.asyncio
    async def test_check_mcp_health_healthy_server(self):
        """Test check_mcp_health with healthy server."""
        mock_connection_info = {
            "state": "connected",
            "is_connected": True,
            "retry_count": 0,
            "max_retries": 5,
            "tools_count": 3,
            "server_configs": ["cogni-mcp"],
        }

        with patch("src.shared_utils.mcp_monitor.get_mcp_connection_info") as mock_get_info:
            mock_get_info.return_value = mock_connection_info

            result = await check_mcp_health("cogni")

            assert result["server_type"] == "cogni"
            assert result["healthy"] is True
            assert result["state"] == "connected"
            assert result["tools_count"] == 3
            assert "timestamp" in result
            assert result["is_connected"] is True
            assert result["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_check_mcp_health_failed_server(self):
        """Test check_mcp_health with failed server."""
        mock_connection_info = {
            "state": "failed",
            "is_connected": False,
            "retry_count": 5,
            "max_retries": 5,
            "tools_count": 0,
            "server_configs": ["cogni-mcp"],
        }

        with patch("src.shared_utils.mcp_monitor.get_mcp_connection_info") as mock_get_info:
            mock_get_info.return_value = mock_connection_info

            result = await check_mcp_health("cogni")

            assert result["server_type"] == "cogni"
            assert result["healthy"] is False
            assert result["state"] == "failed"
            assert result["tools_count"] == 0
            assert result["is_connected"] is False
            assert result["retry_count"] == 5

    @pytest.mark.asyncio
    async def test_check_mcp_health_exception_handling(self):
        """Test check_mcp_health handles exceptions gracefully."""
        with patch("src.shared_utils.mcp_monitor.get_mcp_connection_info") as mock_get_info:
            mock_get_info.side_effect = RuntimeError("Connection info error")

            result = await check_mcp_health("cogni")

            assert result["server_type"] == "cogni"
            assert result["healthy"] is False
            assert result["state"] == "error"
            assert "error" in result
            assert result["error"] == "Connection info error"

    @pytest.mark.asyncio
    async def test_check_all_mcp_health_all_healthy(self):
        """Test check_all_mcp_health when all servers are healthy."""
        mock_cogni_health = {
            "server_type": "cogni",
            "healthy": True,
            "state": "connected",
            "tools_count": 3,
        }
        mock_playwright_health = {
            "server_type": "playwright",
            "healthy": True,
            "state": "connected",
            "tools_count": 5,
        }

        with patch("src.shared_utils.mcp_monitor.check_mcp_health") as mock_check:
            mock_check.side_effect = [mock_cogni_health, mock_playwright_health]

            result = await check_all_mcp_health()

            assert "cogni" in result
            assert "playwright" in result
            assert "summary" in result

            summary = result["summary"]
            assert summary["all_healthy"] is True
            assert summary["healthy_count"] == 2
            assert summary["total_count"] == 2
            assert summary["health_percentage"] == 100.0

    @pytest.mark.asyncio
    async def test_check_all_mcp_health_mixed_health(self):
        """Test check_all_mcp_health with mixed server health."""
        mock_cogni_health = {
            "server_type": "cogni",
            "healthy": True,
            "state": "connected",
            "tools_count": 3,
        }
        mock_playwright_health = {
            "server_type": "playwright",
            "healthy": False,
            "state": "failed",
            "tools_count": 0,
        }

        with patch("src.shared_utils.mcp_monitor.check_mcp_health") as mock_check:
            mock_check.side_effect = [mock_cogni_health, mock_playwright_health]

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
    async def test_check_all_mcp_health_all_unhealthy(self):
        """Test check_all_mcp_health when all servers are unhealthy."""
        mock_cogni_health = {
            "server_type": "cogni",
            "healthy": False,
            "state": "failed",
            "tools_count": 0,
        }
        mock_playwright_health = {
            "server_type": "playwright",
            "healthy": False,
            "state": "failed",
            "tools_count": 0,
        }

        with patch("src.shared_utils.mcp_monitor.check_mcp_health") as mock_check:
            mock_check.side_effect = [mock_cogni_health, mock_playwright_health]

            result = await check_all_mcp_health()

            summary = result["summary"]
            assert summary["all_healthy"] is False
            assert summary["healthy_count"] == 0
            assert summary["total_count"] == 2
            assert summary["health_percentage"] == 0.0

    @pytest.mark.asyncio
    async def test_check_all_mcp_health_with_exceptions(self):
        """Test check_all_mcp_health handles individual server exceptions."""
        mock_cogni_health = {
            "server_type": "cogni",
            "healthy": True,
            "state": "connected",
            "tools_count": 3,
        }

        with patch("src.shared_utils.mcp_monitor.check_mcp_health") as mock_check:
            mock_check.side_effect = [
                mock_cogni_health,
                RuntimeError("Playwright check failed")
            ]

            result = await check_all_mcp_health()

            assert "cogni" in result
            assert "playwright" in result
            assert result["cogni"]["healthy"] is True
            assert result["playwright"]["healthy"] is False
            assert "error" in result["playwright"]

    @pytest.mark.asyncio
    async def test_force_mcp_reconnection_cogni_success(self):
        """Test force_mcp_reconnection for cogni server success."""
        mock_tools = [Mock() for _ in range(3)]
        mock_manager = Mock()
        mock_manager.clear_cache = Mock()
        mock_manager.get_tools = AsyncMock(return_value=mock_tools)
        mock_manager.get_connection_info = Mock(return_value={"state": "connected"})

        with patch("src.shared_utils.mcp_monitor.get_cogni_mcp_manager") as mock_get_manager:
            mock_get_manager.return_value = mock_manager

            result = await force_mcp_reconnection("cogni")

            assert result["server_type"] == "cogni"
            assert result["success"] is True
            assert result["tools_count"] == 3
            assert "connection_info" in result
            mock_manager.clear_cache.assert_called_once()
            mock_manager.get_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_force_mcp_reconnection_playwright_success(self):
        """Test force_mcp_reconnection for playwright server success."""
        mock_tools = [Mock() for _ in range(5)]
        mock_manager = Mock()
        mock_manager.clear_cache = Mock()
        mock_manager.get_tools = AsyncMock(return_value=mock_tools)
        mock_manager.get_connection_info = Mock(return_value={"state": "connected"})

        with patch("src.shared_utils.mcp_monitor.get_playwright_mcp_manager") as mock_get_manager:
            mock_get_manager.return_value = mock_manager

            result = await force_mcp_reconnection("playwright")

            assert result["server_type"] == "playwright"
            assert result["success"] is True
            assert result["tools_count"] == 5
            assert "connection_info" in result
            mock_manager.clear_cache.assert_called_once()
            mock_manager.get_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_force_mcp_reconnection_failure(self):
        """Test force_mcp_reconnection with connection failure."""
        mock_manager = Mock()
        mock_manager.clear_cache = Mock()
        mock_manager.get_tools = AsyncMock(side_effect=ConnectionError("Reconnection failed"))

        with patch("src.shared_utils.mcp_monitor.get_cogni_mcp_manager") as mock_get_manager:
            mock_get_manager.return_value = mock_manager

            result = await force_mcp_reconnection("cogni")

            assert result["server_type"] == "cogni"
            assert result["success"] is False
            assert "error" in result
            assert result["error"] == "Reconnection failed"
            mock_manager.clear_cache.assert_called_once()
            mock_manager.get_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_force_mcp_reconnection_invalid_server(self):
        """Test force_mcp_reconnection with invalid server type."""
        result = await force_mcp_reconnection("invalid_server")

        assert result["server_type"] == "invalid_server"
        assert result["success"] is False
        assert "error" in result
        assert "Unknown server type" in result["error"]

    @pytest.mark.asyncio
    async def test_force_mcp_reconnection_manager_error(self):
        """Test force_mcp_reconnection when manager retrieval fails."""
        with patch("src.shared_utils.mcp_monitor.get_cogni_mcp_manager") as mock_get_manager:
            mock_get_manager.side_effect = RuntimeError("Manager retrieval failed")

            result = await force_mcp_reconnection("cogni")

            assert result["server_type"] == "cogni"
            assert result["success"] is False
            assert "error" in result
            assert "Manager retrieval failed" in result["error"]

    def test_print_mcp_status_all_healthy(self):
        """Test print_mcp_status with all healthy servers."""
        results = {
            "cogni": {
                "healthy": True,
                "state": "connected",
                "tools_count": 3,
            },
            "playwright": {
                "healthy": True,
                "state": "connected",
                "tools_count": 5,
            },
            "summary": {
                "all_healthy": True,
                "healthy_count": 2,
                "total_count": 2,
                "health_percentage": 100.0,
            },
        }

        # Capture stdout
        import sys
        captured_output = StringIO()
        sys.stdout = captured_output

        try:
            print_mcp_status(results)
            output = captured_output.getvalue()

            # Check key elements in output
            assert "MCP CONNECTION STATUS" in output
            assert "✅ HEALTHY" in output
            assert "Healthy Servers: 2/2" in output
            assert "COGNI MCP Server:" in output
            assert "PLAYWRIGHT MCP Server:" in output
            assert "Status: ✅ Connected" in output
            assert "Tools: 3" in output
            assert "Tools: 5" in output

        finally:
            sys.stdout = sys.__stdout__

    def test_print_mcp_status_mixed_health(self):
        """Test print_mcp_status with mixed server health."""
        results = {
            "cogni": {
                "healthy": True,
                "state": "connected",
                "tools_count": 3,
            },
            "playwright": {
                "healthy": False,
                "state": "failed",
                "tools_count": 0,
                "error": "Connection timeout",
            },
            "summary": {
                "all_healthy": False,
                "healthy_count": 1,
                "total_count": 2,
                "health_percentage": 50.0,
            },
        }

        # Capture stdout
        import sys
        captured_output = StringIO()
        sys.stdout = captured_output

        try:
            print_mcp_status(results)
            output = captured_output.getvalue()

            # Check key elements in output
            assert "❌ UNHEALTHY" in output
            assert "Healthy Servers: 1/2" in output
            assert "Status: ✅ Connected" in output
            assert "Status: ❌ Disconnected" in output
            assert "Error: Connection timeout" in output
            # Should NOT contain fallback tools reference
            assert "Fallback:" not in output

        finally:
            sys.stdout = sys.__stdout__

    def test_print_mcp_status_all_unhealthy(self):
        """Test print_mcp_status with all unhealthy servers."""
        results = {
            "cogni": {
                "healthy": False,
                "state": "failed",
                "tools_count": 0,
                "error": "Connection refused",
            },
            "playwright": {
                "healthy": False,
                "state": "failed",
                "tools_count": 0,
                "error": "Service unavailable",
            },
            "summary": {
                "all_healthy": False,
                "healthy_count": 0,
                "total_count": 2,
                "health_percentage": 0.0,
            },
        }

        # Capture stdout
        import sys
        captured_output = StringIO()
        sys.stdout = captured_output

        try:
            print_mcp_status(results)
            output = captured_output.getvalue()

            # Check key elements in output
            assert "❌ UNHEALTHY" in output
            assert "Healthy Servers: 0/2" in output
            assert output.count("Status: ❌ Disconnected") == 2
            assert "Error: Connection refused" in output
            assert "Error: Service unavailable" in output
            # Should NOT contain fallback tools reference
            assert "Fallback:" not in output

        finally:
            sys.stdout = sys.__stdout__

    def test_print_mcp_status_no_summary(self):
        """Test print_mcp_status handles missing summary."""
        results = {
            "cogni": {
                "healthy": True,
                "state": "connected",
                "tools_count": 3,
            },
            # No summary section
        }

        # Capture stdout
        import sys
        captured_output = StringIO()
        sys.stdout = captured_output

        try:
            print_mcp_status(results)
            output = captured_output.getvalue()

            # Should handle missing summary gracefully
            assert "MCP CONNECTION STATUS" in output
            assert "COGNI MCP Server:" in output
            # Should use default values for missing summary
            assert "Healthy Servers: 0/0" in output

        finally:
            sys.stdout = sys.__stdout__

    def test_print_mcp_status_empty_results(self):
        """Test print_mcp_status with empty results."""
        results = {}

        # Capture stdout
        import sys
        captured_output = StringIO()
        sys.stdout = captured_output

        try:
            print_mcp_status(results)
            output = captured_output.getvalue()

            # Should handle empty results gracefully
            assert "MCP CONNECTION STATUS" in output
            assert "Healthy Servers: 0/0" in output

        finally:
            sys.stdout = sys.__stdout__

    def test_print_mcp_status_unknown_states(self):
        """Test print_mcp_status with unknown/missing states."""
        results = {
            "cogni": {
                "healthy": True,
                # Missing state
                "tools_count": 3,
            },
            "playwright": {
                "healthy": False,
                "state": "unknown_state",
                "tools_count": 0,
            },
            "summary": {
                "all_healthy": False,
                "healthy_count": 1,
                "total_count": 2,
            },
        }

        # Capture stdout
        import sys
        captured_output = StringIO()
        sys.stdout = captured_output

        try:
            print_mcp_status(results)
            output = captured_output.getvalue()

            # Should handle missing/unknown states gracefully
            assert "MCP CONNECTION STATUS" in output
            assert "State: unknown" in output
            assert "State: unknown_state" in output

        finally:
            sys.stdout = sys.__stdout__

    def test_print_mcp_status_no_fallback_tools_display(self):
        """Test that print_mcp_status doesn't display fallback tools info."""
        results = {
            "cogni": {
                "healthy": False,
                "state": "failed",
                "tools_count": 0,
                "error": "Connection failed",
            },
            "summary": {
                "all_healthy": False,
                "healthy_count": 0,
                "total_count": 1,
            },
        }

        # Capture stdout
        import sys
        captured_output = StringIO()
        sys.stdout = captured_output

        try:
            print_mcp_status(results)
            output = captured_output.getvalue()

            # Should NOT contain any fallback tools references
            assert "Fallback:" not in output
            assert "fallback" not in output.lower()
            assert "backup" not in output.lower()

        finally:
            sys.stdout = sys.__stdout__


if __name__ == "__main__":
    pytest.main([__file__, "-v"])