"""
Test fixtures and configuration for prefect-mcp-bridge tests
"""

import pytest
import respx
import httpx
from typing import Dict, Any
from unittest.mock import patch


# Configure Prefect for testing - disable API calls
@pytest.fixture(autouse=True)
def configure_prefect_for_testing(monkeypatch):
    """
    Configure Prefect to run in testing mode without API server dependencies
    """
    # Set testing environment variables
    monkeypatch.setenv("PREFECT_API_URL", "http://localhost:4200/api")
    monkeypatch.setenv("PREFECT_TESTING_MODE", "1")

    # Disable Prefect's API version check and server communication
    with patch("prefect.client.orchestration.SyncPrefectClient.api_version") as mock_version:
        mock_version.return_value = "2.0.0"
        with patch("prefect.client.orchestration.SyncPrefectClient.raise_for_api_version_mismatch"):
            yield


@pytest.fixture
def mock_mcp_server():
    """
    Mock MCP server using respx for testing
    """
    with respx.mock:
        # Mock successful dolt.add response
        respx.post("http://cogni-mcp:8080/dolt.add").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "message": "Successfully added changes",
                    "tables_added": ["memory_blocks", "block_properties"],
                    "timestamp": "2025-06-20T11:00:00",
                },
            )
        )

        # Mock successful dolt.commit response
        respx.post("http://cogni-mcp:8080/dolt.commit").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "commit_hash": "abc123def456",
                    "message": "Test commit by Prefect",
                    "author": "prefect-mcp-bridge",
                    "timestamp": "2025-06-20T11:00:00",
                },
            )
        )

        # Mock successful dolt.push response
        respx.post("http://cogni-mcp:8080/dolt.push").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "message": "Successfully pushed to origin",
                    "branch": "main",
                    "remote": "origin",
                    "timestamp": "2025-06-20T11:00:00",
                },
            )
        )

        # Mock health check endpoint
        respx.post("http://cogni-mcp:8080/health").mock(
            return_value=httpx.Response(
                200,
                json={"status": "healthy", "version": "1.0.0", "timestamp": "2025-06-20T11:00:00"},
            )
        )

        # Mock error responses for testing error handling
        respx.post("http://cogni-mcp:8080/dolt.error").mock(
            return_value=httpx.Response(
                500,
                json={"error": "Internal server error", "message": "Simulated error for testing"},
            )
        )

        yield respx


@pytest.fixture
def sample_mcp_responses() -> Dict[str, Dict[str, Any]]:
    """
    Sample MCP response data for testing
    """
    return {
        "dolt_add_success": {
            "success": True,
            "message": "Successfully added changes",
            "tables_added": ["memory_blocks", "block_properties"],
            "timestamp": "2025-06-20T11:00:00",
        },
        "dolt_commit_success": {
            "success": True,
            "commit_hash": "abc123def456",
            "message": "Test commit by Prefect",
            "author": "prefect-mcp-bridge",
            "timestamp": "2025-06-20T11:00:00",
        },
        "dolt_push_success": {
            "success": True,
            "message": "Successfully pushed to origin",
            "branch": "main",
            "remote": "origin",
            "timestamp": "2025-06-20T11:00:00",
        },
        "health_check": {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": "2025-06-20T11:00:00",
        },
        "error_response": {
            "error": "Internal server error",
            "message": "Simulated error for testing",
        },
    }


@pytest.fixture
def test_env_vars(monkeypatch):
    """
    Set up test environment variables
    """
    monkeypatch.setenv("MCP_URL", "http://cogni-mcp:8080")
    monkeypatch.setenv("PREFECT_MCP_API_KEY", "test-api-key")
    return {"MCP_URL": "http://cogni-mcp:8080", "PREFECT_MCP_API_KEY": "test-api-key"}
