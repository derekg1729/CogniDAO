#!/usr/bin/env python3
"""
Pytest configuration for cogni_presence tests
"""

import os
import sys
import pytest
from unittest.mock import Mock

# Add the project root to sys.path for imports
current_dir = os.path.dirname(__file__)
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up minimal test environment."""
    # Set test API keys to avoid missing key errors during import
    os.environ["OPENAI_API_KEY"] = "test-key-for-testing"
    os.environ["TAVILY_API_KEY"] = "test-tavily-key-for-testing"

    yield

    # Cleanup
    if "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]
    if "TAVILY_API_KEY" in os.environ:
        del os.environ["TAVILY_API_KEY"]


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
