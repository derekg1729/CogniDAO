#!/usr/bin/env python3
"""
MCP Integration Tests for LangGraph
===================================

Integration tests for MCP tool connectivity, fallback behavior, and
tool execution within the LangGraph workflow.

Key test areas:
1. MCP tool initialization and connectivity
2. Fallback to Tavily when MCP unavailable
3. Tool execution with mocked responses
4. Error handling in tool connectivity
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock

# Import components under test
from utils.build_graph import (
    _initialize_tools,
    build_graph,
    build_compiled_graph,
    fallback_tools,
    mcp_url,
)


class TestMCPToolInitialization:
    """Test MCP tool initialization and fallback behavior."""

    @pytest.mark.asyncio
    async def test_initialize_tools_fallback_on_connection_failure(self):
        """Test that _initialize_tools falls back to Tavily when MCP connection fails."""

        with patch("utils.build_graph.MultiServerMCPClient") as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.get_tools = AsyncMock(side_effect=Exception("Connection failed"))

            # Clear global tools cache
            import utils.build_graph as bg

            bg._tools = None

            tools = await _initialize_tools()

            # Should fallback to Tavily tools
            assert tools == fallback_tools
            assert len(tools) == 1
            assert hasattr(tools[0], "name")

    @pytest.mark.asyncio
    async def test_initialize_tools_with_timeout(self):
        """Test timeout handling in MCP initialization."""

        with patch("utils.build_graph.MultiServerMCPClient") as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.get_tools = AsyncMock(side_effect=asyncio.TimeoutError())

            # Clear global tools cache
            import utils.build_graph as bg

            bg._tools = None

            tools = await _initialize_tools()

            # Should fallback to Tavily tools on timeout
            assert tools == fallback_tools


class TestMCPToolTypes:
    """Test MCP tool types and interfaces."""

    @pytest.mark.asyncio
    async def test_initialize_tools_with_cogni_mcp_tools(self, mock_mcp_client, dummy_tools):
        """Test successful MCP tool initialization."""

        with patch("utils.build_graph.MultiServerMCPClient") as mock_client_class:
            mock_client_class.return_value = mock_mcp_client

            # Clear global tools cache
            import utils.build_graph as bg

            bg._tools = None

            tools = await _initialize_tools()

            # Should get the dummy tools from mock
            assert len(tools) == 2
            assert tools[0].name == "dummy_search_tool"
            assert tools[1].name == "dummy_work_items_tool"

    @pytest.mark.asyncio
    async def test_tools_have_proper_interface(self, dummy_tools):
        """Test that tools have the required LangChain interface."""

        for tool in dummy_tools:
            assert hasattr(tool, "name")
            assert hasattr(tool, "description")
            assert callable(tool.invoke)


class TestMCPToolIntegrationWithGraph:
    """Test MCP tools integration with LangGraph workflow."""

    @pytest.mark.asyncio
    async def test_graph_compilation_with_mcp_tools(self, mock_mcp_client):
        """Test that build_graph works with MCP tools."""

        with patch("utils.build_graph.MultiServerMCPClient") as mock_client_class:
            mock_client_class.return_value = mock_mcp_client

            # Clear global tools cache
            import utils.build_graph as bg

            bg._tools = None

            workflow = await build_graph()

            # Should compile successfully
            assert workflow is not None
            assert "agent" in workflow.nodes
            assert "action" in workflow.nodes

    @pytest.mark.asyncio
    async def test_build_compiled_graph_with_mcp_tools(self, mock_mcp_client):
        """Test that build_compiled_graph works with MCP tools."""

        with patch("utils.build_graph.MultiServerMCPClient") as mock_client_class:
            mock_client_class.return_value = mock_mcp_client

            # Clear global tools cache
            import utils.build_graph as bg

            bg._tools = None

            compiled_graph = await build_compiled_graph()

            # Should compile successfully
            assert compiled_graph is not None
            assert hasattr(compiled_graph, "ainvoke")


class TestMCPConfiguration:
    """Test MCP client configuration."""

    @pytest.mark.asyncio
    async def test_mcp_client_configuration(self):
        """Test MCP client configuration parameters."""
        with patch("utils.build_graph.MultiServerMCPClient") as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.get_tools = AsyncMock(return_value=[])

            # Clear global tools cache
            import utils.build_graph as bg

            bg._tools = None

            await _initialize_tools()

            # Verify client was configured correctly
            mock_client_class.assert_called_once_with(
                {
                    "cogni-mcp": {
                        "url": mcp_url,
                        "transport": "sse",
                    }
                }
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
