#!/usr/bin/env python3
"""
Pytest configuration for cogni_presence tests
"""

import os
import sys
import pytest
from unittest.mock import Mock, AsyncMock
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

# Add the project root to sys.path for imports
current_dir = os.path.dirname(__file__)
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class DummyStreamingModel:
    """Dummy model that simulates streaming behavior for testing."""

    def __init__(self, streaming=True):
        self.streaming = streaming

    async def ainvoke(self, messages):
        """Simulate model invocation that returns an AI message."""
        return AIMessage(content="Hello world!", tool_calls=[])

    async def astream(self, messages):
        """Simulate streaming tokens."""
        for token in ["Hello", " ", "world", "!"]:
            yield token


@tool
def dummy_search_tool(query: str) -> str:
    """A dummy search tool for testing."""
    return f"Search results for: {query}"


@tool
def dummy_work_items_tool() -> str:
    """A dummy work items tool for testing."""
    return "Active work items: Task 1, Task 2"


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up minimal test environment."""
    # Set test API keys to avoid missing key errors during import
    os.environ["OPENAI_API_KEY"] = "test-key-for-testing"
    os.environ["TAVILY_API_KEY"] = "test-tavily-key-for-testing"
    # Use consistent MCP URL for tests
    os.environ["COGNI_MCP_URL"] = "http://toolhive:24160/sse"
    

    yield

    # Cleanup
    if "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]
    if "TAVILY_API_KEY" in os.environ:
        del os.environ["TAVILY_API_KEY"]


@pytest.fixture
def dummy_streaming_model():
    """Dummy streaming model for testing."""
    return DummyStreamingModel(streaming=True)


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI response for testing."""
    mock_response = Mock()
    mock_response.content = "I can help you with that!"
    mock_response.tool_calls = []
    return mock_response


@pytest.fixture
def mock_openai_response_with_tools():
    """Mock OpenAI response with tool calls for testing."""
    mock_response = Mock()
    mock_response.content = "Let me search for that information."
    mock_response.tool_calls = [{"name": "tavily_search_results", "args": {"query": "test query"}}]
    return mock_response


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {"configurable": {"model_name": "gpt-4o-mini"}}


@pytest.fixture
def dummy_tools():
    """Provide real dummy tools for testing instead of mocks."""
    return [dummy_search_tool, dummy_work_items_tool]


@pytest.fixture
def mock_mcp_client():
    """Mock MCP client that returns real dummy tools."""
    mock_client = Mock()
    mock_client.get_tools = AsyncMock(return_value=[dummy_search_tool, dummy_work_items_tool])
    return mock_client
