"""
Tests for namespace functionality in blocks router.

This test suite validates that the blocks router properly supports namespace operations
and maintains proper isolation between namespaces.
"""

import pytest
import datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from infra_core.memory_system.schemas.memory_block import MemoryBlock
from services.web_api.app import app


@pytest.fixture
def mock_memory_bank():
    """Create a mock StructuredMemoryBank with namespace-aware data."""
    bank = MagicMock()

    # Mock blocks in different namespaces
    legacy_blocks = [
        MemoryBlock(
            id="legacy-block-1",
            type="doc",
            text="Legacy namespace content",
            namespace_id="legacy",
            tags=["test"],
            metadata={"source": "legacy"},
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow(),
        ),
        MemoryBlock(
            id="legacy-task-1",
            type="task",
            text="Legacy task content",
            namespace_id="legacy",
            tags=["task"],
            metadata={"priority": "high"},
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow(),
        ),
    ]

    custom_blocks = [
        MemoryBlock(
            id="custom-block-1",
            type="doc",
            text="Custom namespace content",
            namespace_id="custom-namespace",
            tags=["test"],
            metadata={"source": "custom"},
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow(),
        ),
    ]

    # All blocks combined
    all_blocks = legacy_blocks + custom_blocks

    # Mock get_all_memory_blocks to return all blocks (filtering happens in the router)
    bank.get_all_memory_blocks.return_value = all_blocks

    # Mock dolt_writer for active branch
    bank.dolt_writer.active_branch = "feat/namespaces"

    return bank


@pytest.fixture
def client_with_mock_bank(mock_memory_bank):
    """Create a test client with mocked memory bank."""
    app.state.memory_bank = mock_memory_bank
    return TestClient(app)


class TestBlocksRouterNamespace:
    """Test namespace functionality in blocks router."""

    def test_get_all_blocks_default_namespace(self, client_with_mock_bank):
        """Test that GET /blocks defaults to legacy namespace."""
        response = client_with_mock_bank.get("/api/v1/blocks")

        assert response.status_code == 200
        response_data = response.json()

        # Check that namespace context is set to legacy (default)
        assert response_data["namespace_context"] == "legacy"

        # Check that only legacy blocks are returned
        assert response_data["total_count"] == 2
        assert len(response_data["blocks"]) == 2

        # Verify all returned blocks are from legacy namespace
        for block in response_data["blocks"]:
            assert block["namespace_id"] == "legacy"

        # Check filters applied
        assert response_data["filters_applied"]["namespace"] == "legacy"

    def test_get_all_blocks_custom_namespace(self, client_with_mock_bank):
        """Test that GET /blocks can filter by custom namespace."""
        response = client_with_mock_bank.get("/api/v1/blocks?namespace=custom-namespace")

        assert response.status_code == 200
        response_data = response.json()

        # Check that namespace context is set to custom namespace
        assert response_data["namespace_context"] == "custom-namespace"

        # Check that only custom namespace blocks are returned
        assert response_data["total_count"] == 1
        assert len(response_data["blocks"]) == 1

        # Verify returned block is from custom namespace
        assert response_data["blocks"][0]["namespace_id"] == "custom-namespace"
        assert response_data["blocks"][0]["id"] == "custom-block-1"

        # Check filters applied
        assert response_data["filters_applied"]["namespace"] == "custom-namespace"

    def test_get_all_blocks_namespace_with_type_filter(self, client_with_mock_bank):
        """Test that namespace and type filters work together."""
        response = client_with_mock_bank.get("/api/v1/blocks?namespace=legacy&type=task")

        assert response.status_code == 200
        response_data = response.json()

        # Check that both filters are applied
        assert response_data["namespace_context"] == "legacy"
        assert response_data["total_count"] == 1
        assert len(response_data["blocks"]) == 1

        # Verify returned block matches both filters
        block = response_data["blocks"][0]
        assert block["namespace_id"] == "legacy"
        assert block["type"] == "task"
        assert block["id"] == "legacy-task-1"

        # Check filters applied
        assert response_data["filters_applied"]["namespace"] == "legacy"
        assert response_data["filters_applied"]["type"] == "task"

    def test_get_all_blocks_nonexistent_namespace(self, client_with_mock_bank):
        """Test that filtering by nonexistent namespace returns empty results."""
        response = client_with_mock_bank.get("/api/v1/blocks?namespace=nonexistent")

        assert response.status_code == 200
        response_data = response.json()

        # Check that namespace context is set but no blocks returned
        assert response_data["namespace_context"] == "nonexistent"
        assert response_data["total_count"] == 0
        assert len(response_data["blocks"]) == 0

        # Check filters applied
        assert response_data["filters_applied"]["namespace"] == "nonexistent"
