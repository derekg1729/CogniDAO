"""
Tests for the namespaces router endpoints.

This module tests the /api/v1/namespaces endpoint functionality including:
- Successful namespace listing
- Error handling scenarios
- Response format validation
- Branch context inclusion
"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from datetime import datetime

from services.web_api.app import app
from infra_core.memory_system.tools.agent_facing.dolt_namespace_tool import (
    ListNamespacesOutput,
    NamespaceInfo,
)


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_memory_bank():
    """Create a mock memory bank for testing."""
    mock_bank = Mock()
    return mock_bank


@pytest.fixture
def sample_namespaces():
    """Create sample namespace data for testing."""
    return [
        NamespaceInfo(
            id="legacy",
            name="Legacy Namespace",
            slug="legacy",
            owner_id="system",
            created_at=datetime(2024, 1, 1, 12, 0, 0),
            description="Default legacy namespace",
            is_active=True,
        ),
        NamespaceInfo(
            id="test-namespace",
            name="Test Namespace",
            slug="test-namespace",
            owner_id="user123",
            created_at=datetime(2024, 2, 1, 12, 0, 0),
            description="Test namespace for development",
            is_active=True,
        ),
        NamespaceInfo(
            id="archived-namespace",
            name="Archived Namespace",
            slug="archived-namespace",
            owner_id="user456",
            created_at=datetime(2024, 1, 15, 12, 0, 0),
            description="Archived namespace",
            is_active=False,
        ),
    ]


class TestNamespacesRouter:
    """Test class for namespaces router functionality."""

    @patch("services.web_api.routes.namespaces_router.list_namespaces_tool")
    def test_get_all_namespaces_success(
        self, mock_tool, client, mock_memory_bank, sample_namespaces
    ):
        """Test successful retrieval of all namespaces."""
        # Setup
        app.state.memory_bank = mock_memory_bank

        mock_result = ListNamespacesOutput(
            success=True,
            namespaces=sample_namespaces,
            total_count=3,
            message="Found 3 namespaces",
            active_branch="feat/namespaces",
        )
        mock_tool.return_value = mock_result

        # Execute
        response = client.get("/api/v1/namespaces")

        # Verify
        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "namespaces" in data
        assert "total_count" in data
        assert "active_branch" in data
        assert "requested_branch" in data
        assert "timestamp" in data

        # Check namespace data
        assert len(data["namespaces"]) == 3
        assert data["total_count"] == 3
        assert data["active_branch"] == "feat/namespaces"
        assert data["requested_branch"] is None

        # Check first namespace details
        first_namespace = data["namespaces"][0]
        assert first_namespace["id"] == "legacy"
        assert first_namespace["name"] == "Legacy Namespace"
        assert first_namespace["slug"] == "legacy"
        assert first_namespace["owner_id"] == "system"
        assert first_namespace["is_active"] is True

        # Verify tool was called correctly
        mock_tool.assert_called_once()
        args, kwargs = mock_tool.call_args

        # Verify input_data is ListNamespacesInput instance
        input_data = args[0]
        assert input_data.__class__.__name__ == "ListNamespacesInput"

        # Verify memory_bank is passed as second argument
        memory_bank_arg = args[1]
        assert memory_bank_arg == mock_memory_bank

    @patch("services.web_api.routes.namespaces_router.list_namespaces_tool")
    def test_get_all_namespaces_empty_result(self, mock_tool, client, mock_memory_bank):
        """Test handling of empty namespace list."""
        # Setup
        app.state.memory_bank = mock_memory_bank

        mock_result = ListNamespacesOutput(
            success=True,
            namespaces=[],
            total_count=0,
            message="No namespaces found",
            active_branch="main",
        )
        mock_tool.return_value = mock_result

        # Execute
        response = client.get("/api/v1/namespaces")

        # Verify
        assert response.status_code == 200
        data = response.json()

        assert data["namespaces"] == []
        assert data["total_count"] == 0
        assert data["active_branch"] == "main"

    @patch("services.web_api.routes.namespaces_router.list_namespaces_tool")
    def test_get_all_namespaces_tool_failure(self, mock_tool, client, mock_memory_bank):
        """Test handling of tool failure."""
        # Setup
        app.state.memory_bank = mock_memory_bank

        mock_result = ListNamespacesOutput(
            success=False,
            namespaces=[],
            total_count=0,
            message="Database connection failed",
            active_branch="main",
            error="Connection timeout",
        )
        mock_tool.return_value = mock_result

        # Execute
        response = client.get("/api/v1/namespaces")

        # Verify
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Failed to retrieve namespaces" in data["detail"]

    def test_get_all_namespaces_no_memory_bank(self, client):
        """Test handling when memory bank is not available."""
        # Setup - no memory bank in app state
        app.state.memory_bank = None

        # Execute
        response = client.get("/api/v1/namespaces")

        # Verify
        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Memory bank not available"

    @patch("services.web_api.routes.namespaces_router.list_namespaces_tool")
    def test_get_all_namespaces_tool_exception(self, mock_tool, client, mock_memory_bank):
        """Test handling of unexpected exceptions from the tool."""
        # Setup
        app.state.memory_bank = mock_memory_bank
        mock_tool.side_effect = Exception("Unexpected database error")

        # Execute
        response = client.get("/api/v1/namespaces")

        # Verify
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "An unexpected error occurred" in data["detail"]

    @patch("services.web_api.routes.namespaces_router.list_namespaces_tool")
    def test_get_all_namespaces_response_format(
        self, mock_tool, client, mock_memory_bank, sample_namespaces
    ):
        """Test that the response format matches the expected schema."""
        # Setup
        app.state.memory_bank = mock_memory_bank

        mock_result = ListNamespacesOutput(
            success=True,
            namespaces=sample_namespaces,
            total_count=3,
            message="Found 3 namespaces",
            active_branch="feat/namespaces",
        )
        mock_tool.return_value = mock_result

        # Execute
        response = client.get("/api/v1/namespaces")

        # Verify response structure matches NamespacesResponse model
        assert response.status_code == 200
        data = response.json()

        # Required fields from BranchContextResponse
        assert isinstance(data["active_branch"], str)
        assert data["requested_branch"] is None
        assert isinstance(data["timestamp"], str)

        # Required fields from NamespacesResponse
        assert isinstance(data["namespaces"], list)
        assert isinstance(data["total_count"], int)

        # Each namespace should have the correct structure
        for namespace in data["namespaces"]:
            assert isinstance(namespace["id"], str)
            assert isinstance(namespace["name"], str)
            assert isinstance(namespace["slug"], str)
            assert isinstance(namespace["owner_id"], str)
            assert isinstance(namespace["created_at"], str)  # ISO datetime string
            assert isinstance(namespace["is_active"], bool)
            # description can be None
            if namespace["description"] is not None:
                assert isinstance(namespace["description"], str)

    @patch("services.web_api.routes.namespaces_router.list_namespaces_tool")
    def test_get_all_namespaces_branch_context(
        self, mock_tool, client, mock_memory_bank, sample_namespaces
    ):
        """Test that branch context is properly included in the response."""
        # Setup
        app.state.memory_bank = mock_memory_bank

        test_branch = "feature/namespace-testing"
        mock_result = ListNamespacesOutput(
            success=True,
            namespaces=sample_namespaces,
            total_count=3,
            message="Found 3 namespaces",
            active_branch=test_branch,
        )
        mock_tool.return_value = mock_result

        # Execute
        response = client.get("/api/v1/namespaces")

        # Verify
        assert response.status_code == 200
        data = response.json()

        # Branch context should be preserved
        assert data["active_branch"] == test_branch
        assert data["requested_branch"] is None  # No specific branch requested for listing

        # Timestamp should be present and valid ISO format
        assert "timestamp" in data
        timestamp_str = data["timestamp"]
        assert timestamp_str.endswith("Z")  # UTC timezone indicator

        # Should be able to parse as datetime
        from datetime import datetime

        parsed_timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        assert isinstance(parsed_timestamp, datetime)
