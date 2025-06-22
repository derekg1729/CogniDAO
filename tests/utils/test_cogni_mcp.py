#!/usr/bin/env python3
"""
Tests for Cogni-Specific MCP Setup
==================================

Tests the configure_cogni_mcp wrapper that adds Dolt branch/namespace functionality
to the generic MCP connection helper.
"""

import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from utils.setup_connection_to_cogni_mcp import configure_cogni_mcp, MCPConnectionError


class TestConfigureCogniMcp:
    """Test suite for configure_cogni_mcp wrapper"""

    @pytest.mark.asyncio
    async def test_configure_cogni_mcp_basic_success(self):
        """Test basic successful connection without branch/namespace"""
        mock_session = AsyncMock()
        mock_tools = [MagicMock(name="tool1"), MagicMock(name="tool2")]

        with patch("utils.setup_connection_to_cogni_mcp.configure_existing_mcp") as mock_configure:
            mock_configure.return_value.__aenter__.return_value = (mock_session, mock_tools)

            async with configure_cogni_mcp(sse_url="http://test:8080/sse") as (session, tools):
                assert session == mock_session
                assert tools == mock_tools

            # Verify the generic helper was called correctly
            mock_configure.assert_called_once_with("http://test:8080/sse", timeout=30)

    @pytest.mark.asyncio
    async def test_configure_cogni_mcp_with_branch(self):
        """Test connection with Dolt branch switching"""
        mock_session = AsyncMock()
        mock_tools = [MagicMock(name="tool1")]

        with patch("utils.setup_connection_to_cogni_mcp.configure_existing_mcp") as mock_configure:
            mock_configure.return_value.__aenter__.return_value = (mock_session, mock_tools)

            async with configure_cogni_mcp(
                sse_url="http://test:8080/sse", branch="feature-branch"
            ) as (session, tools):
                assert session == mock_session
                assert tools == mock_tools

            # Verify DoltCheckout was called
            mock_session.call_tool.assert_called_once_with(
                "DoltCheckout", {"input": '{"branch_name": "feature-branch"}'}
            )

    @pytest.mark.asyncio
    async def test_configure_cogni_mcp_with_namespace(self):
        """Test connection with namespace specification"""
        mock_session = AsyncMock()
        mock_tools = [MagicMock(name="tool1")]

        with patch("utils.setup_connection_to_cogni_mcp.configure_existing_mcp") as mock_configure:
            mock_configure.return_value.__aenter__.return_value = (mock_session, mock_tools)

            async with configure_cogni_mcp(
                sse_url="http://test:8080/sse", namespace="test-namespace"
            ) as (session, tools):
                assert session == mock_session
                assert tools == mock_tools

            # Namespace switching is logged but not executed (handled by env vars)
            mock_session.call_tool.assert_not_called()

    @pytest.mark.asyncio
    async def test_configure_cogni_mcp_env_var_defaults(self):
        """Test that environment variables are used as defaults"""
        mock_session = AsyncMock()
        mock_tools = [MagicMock(name="tool1")]

        env_vars = {
            "COGNI_MCP_SSE_URL": "http://env-test:9090/sse",
            "MCP_DOLT_BRANCH": "env-branch",
            "MCP_DOLT_NAMESPACE": "env-namespace",
        }

        with (
            patch("utils.setup_connection_to_cogni_mcp.configure_existing_mcp") as mock_configure,
            patch.dict(os.environ, env_vars),
        ):
            mock_configure.return_value.__aenter__.return_value = (mock_session, mock_tools)

            # Call without explicit parameters to test env var defaults
            async with configure_cogni_mcp() as (session, tools):
                assert session == mock_session
                assert tools == mock_tools

            # Verify env vars were used
            mock_configure.assert_called_once_with("http://env-test:9090/sse", timeout=30)
            mock_session.call_tool.assert_called_once_with(
                "DoltCheckout", {"input": '{"branch_name": "env-branch"}'}
            )

    @pytest.mark.asyncio
    async def test_configure_cogni_mcp_explicit_overrides_env(self):
        """Test that explicit parameters override environment variables"""
        mock_session = AsyncMock()
        mock_tools = [MagicMock(name="tool1")]

        env_vars = {
            "COGNI_MCP_SSE_URL": "http://env-test:9090/sse",
            "MCP_DOLT_BRANCH": "env-branch",
        }

        with (
            patch("utils.setup_connection_to_cogni_mcp.configure_existing_mcp") as mock_configure,
            patch.dict(os.environ, env_vars),
        ):
            mock_configure.return_value.__aenter__.return_value = (mock_session, mock_tools)

            # Explicit parameters should override env vars
            async with configure_cogni_mcp(
                sse_url="http://explicit:8080/sse", branch="explicit-branch"
            ) as (session, tools):
                assert session == mock_session

            # Verify explicit values were used, not env vars
            mock_configure.assert_called_once_with("http://explicit:8080/sse", timeout=30)
            mock_session.call_tool.assert_called_once_with(
                "DoltCheckout", {"input": '{"branch_name": "explicit-branch"}'}
            )

    @pytest.mark.asyncio
    async def test_configure_cogni_mcp_missing_url_error(self):
        """Test error when no URL is provided and no env var is set"""
        # Clear environment variables including the fallback URL env var
        with patch.dict(os.environ, {"COGNI_MCP_SSE_URL": ""}, clear=True):
            with pytest.raises(ValueError, match="sse_url must be provided"):
                async with configure_cogni_mcp():
                    pass

    @pytest.mark.asyncio
    async def test_configure_cogni_mcp_dolt_checkout_error(self):
        """Test error handling when DoltCheckout fails"""
        mock_session = AsyncMock()
        mock_tools = [MagicMock(name="tool1")]
        mock_session.call_tool.side_effect = Exception("DoltCheckout failed")

        with patch("utils.setup_connection_to_cogni_mcp.configure_existing_mcp") as mock_configure:
            mock_configure.return_value.__aenter__.return_value = (mock_session, mock_tools)

            with pytest.raises(MCPConnectionError, match="Failed to configure Cogni MCP"):
                async with configure_cogni_mcp(
                    sse_url="http://test:8080/sse", branch="test-branch"
                ):
                    pass

    @pytest.mark.asyncio
    async def test_configure_cogni_mcp_custom_timeout(self):
        """Test custom timeout parameter is passed through"""
        mock_session = AsyncMock()
        mock_tools = [MagicMock(name="tool1")]

        with patch("utils.setup_connection_to_cogni_mcp.configure_existing_mcp") as mock_configure:
            mock_configure.return_value.__aenter__.return_value = (mock_session, mock_tools)

            async with configure_cogni_mcp(sse_url="http://test:8080/sse", timeout=60):
                pass

            # Verify custom timeout was passed through
            mock_configure.assert_called_once_with("http://test:8080/sse", timeout=60)


# Smoke test for integration (can be run manually when MCP server is available)
async def _smoke_test():
    """Manual smoke test for when MCP server is running"""
    try:
        async with configure_cogni_mcp(branch="main") as (session, tools):
            assert len(tools) > 0
            # Try calling a simple tool
            if tools:
                await session.call_tool(tools[0].name, {"input": "{}"})
        print("✅ Smoke test passed!")
    except Exception as e:
        print(f"❌ Smoke test failed: {e}")


def test_cogni_mcp_smoke():
    """Wrapper for pytest to run smoke test"""
    # This test is mainly for manual verification when MCP server is running
    # It will be skipped in CI/automated environments
    if os.getenv("RUN_SMOKE_TESTS"):
        asyncio.run(_smoke_test())
    else:
        pytest.skip("Smoke test skipped (set RUN_SMOKE_TESTS=1 to enable)")


if __name__ == "__main__":
    # For direct testing
    print("Running Cogni MCP tests...")
    asyncio.run(_smoke_test())
