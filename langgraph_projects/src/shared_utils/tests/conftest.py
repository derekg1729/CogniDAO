"""
Test configuration for shared_utils tests.
"""

import os
import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up minimal test environment."""
    # Set test API keys to avoid missing key errors
    os.environ["OPENAI_API_KEY"] = "test-key-for-testing"
    os.environ["TAVILY_API_KEY"] = "test-tavily-key-for-testing"

    yield

    # Cleanup
    for key in ["OPENAI_API_KEY", "TAVILY_API_KEY"]:
        if key in os.environ:
            del os.environ[key]