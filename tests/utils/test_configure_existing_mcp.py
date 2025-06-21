#!/usr/bin/env python3
"""
Tests for the utils configure_existing_mcp helper.

Uses mock-based testing to verify the helper behavior without requiring
a real MCP server connection.
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import List

from utils.mcp_setup import configure_existing_mcp, MCPConnectionError


class MockTool:
    """Mock tool object for testing"""

    def __init__(self, name: str, description: str = None):
        self.name = name
        self.description = description or f"Mock description for {name}"


class MockToolsResponse:
    """Mock tools response object"""

    def __init__(self, tools: List[MockTool]):
        self.tools = tools


class MockClientSession:
    """Mock ClientSession for testing"""

    def __init__(self, tools: List[MockTool]):
        self._tools = tools
        self.initialized = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def initialize(self):
        self.initialized = True

    async def list_tools(self):
        if not self.initialized:
            raise RuntimeError("Session not initialized")
        return MockToolsResponse(self._tools)

    async def call_tool(self, tool_name: str, arguments: dict = None):
        """Mock tool call"""
        if not self.initialized:
            raise RuntimeError("Session not initialized")

        result = MagicMock()
        result.content = f"Mock result for {tool_name} with args {arguments or {}}"
        return result


@pytest.mark.asyncio
async def test_configure_existing_mcp_success():
    """Test successful MCP configuration with mocked components"""

    # Create mock tools
    mock_tools = [
        MockTool("DoltStatus", "Check Dolt repository status"),
        MockTool("DoltCommit", "Commit changes to Dolt"),
        MockTool("GetMemoryBlock", "Retrieve memory blocks"),
    ]

    # Mock the SSE client and session
    mock_session = MockClientSession(mock_tools)

    with (
        patch("utils.mcp_setup.sse_client") as mock_sse_client,
        patch("utils.mcp_setup.ClientSession", return_value=mock_session),
    ):
        # Configure the mock SSE client to yield mock streams
        mock_sse_client.return_value.__aenter__.return_value = (MagicMock(), MagicMock())

        # Test the helper with required URL parameter
        test_url = "http://test-server:24160/sse"
        async with configure_existing_mcp(test_url) as (session, tools):
            # Verify session and tools are returned correctly
            assert session == mock_session
            assert len(tools) == 3
            assert tools[0].name == "DoltStatus"
            assert tools[1].name == "DoltCommit"
            assert tools[2].name == "GetMemoryBlock"

            # Verify session is initialized
            assert session.initialized

            # Test tool calling
            result = await session.call_tool("DoltStatus", {"input": "{}"})
            assert "Mock result for DoltStatus" in result.content

        # Verify the URL was passed to sse_client
        mock_sse_client.assert_called_with(test_url, timeout=30)


@pytest.mark.asyncio
async def test_configure_existing_mcp_custom_url():
    """Test MCP configuration with custom URL"""

    custom_url = "http://custom-server:8080/sse"
    mock_tools = [MockTool("TestTool")]
    mock_session = MockClientSession(mock_tools)

    with (
        patch("utils.mcp_setup.sse_client") as mock_sse_client,
        patch("utils.mcp_setup.ClientSession", return_value=mock_session),
    ):
        mock_sse_client.return_value.__aenter__.return_value = (MagicMock(), MagicMock())

        # Test with custom URL
        async with configure_existing_mcp(custom_url) as (session, tools):
            assert len(tools) == 1
            assert tools[0].name == "TestTool"

            # Verify the URL was used (would be passed to sse_client)
            mock_sse_client.assert_called_with(custom_url, timeout=30)


@pytest.mark.asyncio
async def test_configure_existing_mcp_missing_url():
    """Test that ValueError is raised when URL is missing or empty"""

    # Test with None
    with pytest.raises(ValueError) as exc_info:
        async with configure_existing_mcp(None) as (session, tools):
            pass  # Should not reach here
    assert "sse_url parameter is required" in str(exc_info.value)

    # Test with empty string
    with pytest.raises(ValueError) as exc_info:
        async with configure_existing_mcp("") as (session, tools):
            pass  # Should not reach here
    assert "sse_url parameter is required" in str(exc_info.value)


@pytest.mark.asyncio
async def test_configure_existing_mcp_connection_error():
    """Test connection error handling"""

    with patch("utils.mcp_setup.sse_client") as mock_sse_client:
        # Configure mock to raise ConnectionError
        mock_sse_client.side_effect = ConnectionError("Connection refused")

        # Test that MCPConnectionError is raised
        with pytest.raises(MCPConnectionError) as exc_info:
            async with configure_existing_mcp("http://test:24160/sse") as (session, tools):
                pass  # Should not reach here

        assert "Connection failed to MCP server" in str(exc_info.value)


@pytest.mark.asyncio
async def test_configure_existing_mcp_timeout_error():
    """Test timeout error handling"""

    with patch("utils.mcp_setup.sse_client") as mock_sse_client:
        # Configure mock to raise TimeoutError
        mock_sse_client.side_effect = TimeoutError("Connection timeout")

        # Test that MCPConnectionError is raised
        with pytest.raises(MCPConnectionError) as exc_info:
            async with configure_existing_mcp("http://test:24160/sse") as (session, tools):
                pass  # Should not reach here

        assert "Connection timeout to MCP server" in str(exc_info.value)


@pytest.mark.asyncio
async def test_configure_existing_mcp_custom_timeout():
    """Test custom timeout parameter"""

    mock_tools = [MockTool("TestTool")]
    mock_session = MockClientSession(mock_tools)

    with (
        patch("utils.mcp_setup.sse_client") as mock_sse_client,
        patch("utils.mcp_setup.ClientSession", return_value=mock_session),
    ):
        mock_sse_client.return_value.__aenter__.return_value = (MagicMock(), MagicMock())

        # Test with custom timeout
        test_url = "http://test:24160/sse"
        async with configure_existing_mcp(test_url, timeout=60) as (session, tools):
            assert len(tools) == 1

            # Verify timeout was passed to sse_client
            mock_sse_client.assert_called_with(test_url, timeout=60)


@pytest.mark.asyncio
async def test_configure_existing_mcp_no_tools():
    """Test behavior when no tools are available"""

    # Create session with no tools
    mock_session = MockClientSession([])

    with (
        patch("utils.mcp_setup.sse_client") as mock_sse_client,
        patch("utils.mcp_setup.ClientSession", return_value=mock_session),
    ):
        mock_sse_client.return_value.__aenter__.return_value = (MagicMock(), MagicMock())

        test_url = "http://test:24160/sse"
        async with configure_existing_mcp(test_url) as (session, tools):
            assert session == mock_session
            assert len(tools) == 0
            assert session.initialized
