"""
Minimal test configuration for Playwright Basic LangGraph tests
===============================================================

Simple, isolated test configuration without heavy dependencies.
"""

import os
import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up minimal test environment."""
    # Set test API key to avoid missing key errors
    os.environ["OPENAI_API_KEY"] = "test-key-for-testing"

    yield

    # Cleanup
    if "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]


@pytest.fixture
def sample_thread_config():
    """Sample thread configuration for graph execution."""
    return {"configurable": {"thread_id": "test-thread-123"}}
