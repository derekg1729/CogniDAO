"""
Test the Links Router endpoints in the Web API.

These tests ensure the links API endpoints work correctly and handle
error cases appropriately.
"""

import pytest
import uuid
from datetime import datetime
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from services.web_api.app import app
from infra_core.memory_system.schemas.common import BlockLink
from infra_core.memory_system.link_manager import (
    LinkManager,
    LinkError,
    LinkErrorType,
    LinkQueryResult,
)


@pytest.fixture(scope="module")
def client():
    """Test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_link_manager():
    """Mock LinkManager for testing."""
    mock = MagicMock(spec=LinkManager)
    return mock


@pytest.fixture
def mock_memory_bank(mock_link_manager):
    """Mock memory bank with attached link manager."""
    mock_bank = MagicMock()
    mock_bank.link_manager = mock_link_manager
    return mock_bank


@pytest.fixture
def sample_block_links():
    """Sample block links for testing."""
    return [
        BlockLink(
            from_id="source-1",
            to_id="target-1",
            relation="depends_on",
            priority=1,
            link_metadata={"test": "metadata"},
            created_at=datetime.utcnow(),
            created_by="test_user",
        ),
        BlockLink(
            from_id="source-2",
            to_id="target-2",
            relation="is_blocked_by",
            priority=2,
            link_metadata=None,
            created_at=datetime.utcnow(),
            created_by=None,
        ),
    ]


@pytest.fixture
def valid_uuids():
    """Valid UUIDs for testing."""
    return {
        "source": str(uuid.uuid4()),
        "target": str(uuid.uuid4()),
        "block_id": str(uuid.uuid4()),
    }


class TestCreateLink:
    """Test POST /api/v1/links endpoint."""

    def test_create_link_success(self, client, mock_memory_bank, mock_link_manager, valid_uuids):
        """Test successful link creation."""
        # Setup mock
        created_link = BlockLink(
            from_id=valid_uuids["source"],
            to_id=valid_uuids["target"],
            relation="depends_on",
            priority=1,
            link_metadata={"test": "data"},
            created_at=datetime.utcnow(),
            created_by="test_user",
        )
        mock_link_manager.create_link.return_value = created_link

        # Set the memory bank on app state
        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            response = client.post(
                "/api/v1/links",
                params={
                    "from_id": valid_uuids["source"],
                    "to_id": valid_uuids["target"],
                    "relation": "depends_on",
                    "priority": 1,
                    "created_by": "test_user",
                },
                json={"test": "data"},  # link_metadata
            )

            assert response.status_code == 201
            response_data = response.json()
            assert response_data["to_id"] == valid_uuids["target"]
            assert response_data["relation"] == "depends_on"
            assert response_data["priority"] == 1
            assert response_data["created_by"] == "test_user"

            mock_link_manager.create_link.assert_called_once_with(
                from_id=valid_uuids["source"],
                to_id=valid_uuids["target"],
                relation="depends_on",
                priority=1,
                link_metadata={"test": "data"},
                created_by="test_user",
            )
        finally:
            # Clean up
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")

    def test_create_link_invalid_uuid(self, client, mock_memory_bank):
        """Test link creation with invalid UUID."""
        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            response = client.post(
                "/api/v1/links",
                params={
                    "from_id": "invalid-uuid",
                    "to_id": "also-invalid",
                    "relation": "depends_on",
                },
            )

            assert response.status_code == 400
            assert "Invalid UUID format" in response.json()["detail"]
        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")

    def test_create_link_link_error(self, client, mock_memory_bank, mock_link_manager, valid_uuids):
        """Test link creation with LinkError."""
        # Setup mock to raise LinkError
        mock_link_manager.create_link.side_effect = LinkError(
            LinkErrorType.VALIDATION_ERROR, "Link already exists"
        )

        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            response = client.post(
                "/api/v1/links",
                params={
                    "from_id": valid_uuids["source"],
                    "to_id": valid_uuids["target"],
                    "relation": "depends_on",
                },
            )

            assert response.status_code == 400  # VALIDATION_ERROR maps to 400
            response_data = response.json()
            assert response_data["detail"]["code"] == "validation_error"
            assert response_data["detail"]["message"] == "Link already exists"
        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")

    def test_create_link_memory_bank_unavailable(self, client):
        """Test error when memory bank is unavailable."""
        # Ensure no memory_bank attribute exists
        if hasattr(app.state, "memory_bank"):
            delattr(app.state, "memory_bank")

        response = client.post(
            "/api/v1/links",
            params={
                "from_id": str(uuid.uuid4()),
                "to_id": str(uuid.uuid4()),
                "relation": "depends_on",
            },
        )

        assert response.status_code == 500
        assert "Memory bank not configured" in response.json()["detail"]


class TestDeleteLink:
    """Test DELETE /api/v1/links endpoint."""

    def test_delete_link_success(self, client, mock_memory_bank, mock_link_manager, valid_uuids):
        """Test successful link deletion."""
        mock_link_manager.delete_link.return_value = True

        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            response = client.delete(
                "/api/v1/links",
                params={
                    "from_id": valid_uuids["source"],
                    "to_id": valid_uuids["target"],
                    "relation": "depends_on",
                },
            )

            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
            assert "Link deleted successfully" in response_data["message"]

            mock_link_manager.delete_link.assert_called_once_with(
                from_id=valid_uuids["source"],
                to_id=valid_uuids["target"],
                relation="depends_on",
            )
        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")

    def test_delete_link_not_found(self, client, mock_memory_bank, mock_link_manager, valid_uuids):
        """Test deleting non-existent link."""
        mock_link_manager.delete_link.return_value = False

        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            response = client.delete(
                "/api/v1/links",
                params={
                    "from_id": valid_uuids["source"],
                    "to_id": valid_uuids["target"],
                    "relation": "depends_on",
                },
            )

            assert response.status_code == 404
            assert "Link not found" in response.json()["detail"]
        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")

    def test_delete_link_invalid_uuid(self, client, mock_memory_bank):
        """Test deleting link with invalid UUID."""
        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            response = client.delete(
                "/api/v1/links",
                params={
                    "from_id": "invalid-uuid",
                    "to_id": "also-invalid",
                    "relation": "depends_on",
                },
            )

            assert response.status_code == 400
            assert "Invalid UUID format" in response.json()["detail"]
        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")


class TestGetLinksFrom:
    """Test GET /api/v1/links/from/{block_id} endpoint."""

    def test_get_links_from_success(
        self, client, mock_memory_bank, mock_link_manager, valid_uuids, sample_block_links
    ):
        """Test successful retrieval of links from a block."""
        mock_result = LinkQueryResult(links=sample_block_links, next_cursor=None)
        mock_link_manager.links_from.return_value = mock_result

        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            response = client.get(f"/api/v1/links/from/{valid_uuids['block_id']}")

            assert response.status_code == 200
            response_data = response.json()
            assert len(response_data) == 2
            assert response_data[0]["to_id"] == "target-1"
            assert response_data[0]["relation"] == "depends_on"
            assert response_data[1]["to_id"] == "target-2"
            assert response_data[1]["relation"] == "is_blocked_by"

            mock_link_manager.links_from.assert_called_once()
        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")

    def test_get_links_from_with_filters(
        self, client, mock_memory_bank, mock_link_manager, valid_uuids, sample_block_links
    ):
        """Test getting links from block with query filters."""
        filtered_links = [sample_block_links[0]]  # Only first link
        mock_result = LinkQueryResult(links=filtered_links, next_cursor=None)
        mock_link_manager.links_from.return_value = mock_result

        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            response = client.get(
                f"/api/v1/links/from/{valid_uuids['block_id']}",
                params={
                    "relation": "depends_on",
                    "depth": 2,
                    "direction": "outbound",
                    "limit": 50,
                },
            )

            assert response.status_code == 200
            response_data = response.json()
            assert len(response_data) == 1
            assert response_data[0]["relation"] == "depends_on"

            # Verify link_manager was called with correct parameters
            mock_link_manager.links_from.assert_called_once()
            call_args = mock_link_manager.links_from.call_args
            assert call_args[1]["block_id"] == valid_uuids["block_id"]
            # The query parameter will be a LinkQuery object with the filters
        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")

    def test_get_links_from_invalid_uuid(self, client, mock_memory_bank):
        """Test getting links from block with invalid UUID."""
        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            response = client.get("/api/v1/links/from/invalid-uuid")

            assert response.status_code == 400
            assert "Invalid UUID format" in response.json()["detail"]
        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")

    def test_get_links_from_invalid_direction(self, client, mock_memory_bank, valid_uuids):
        """Test getting links with invalid direction parameter."""
        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            response = client.get(
                f"/api/v1/links/from/{valid_uuids['block_id']}",
                params={"direction": "invalid_direction"},
            )

            assert response.status_code == 400
            assert "Invalid direction" in response.json()["detail"]
        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")


class TestGetLinksTo:
    """Test GET /api/v1/links/to/{block_id} endpoint."""

    def test_get_links_to_success(
        self, client, mock_memory_bank, mock_link_manager, valid_uuids, sample_block_links
    ):
        """Test successful retrieval of links to a block."""
        mock_result = LinkQueryResult(links=sample_block_links, next_cursor=None)
        mock_link_manager.links_to.return_value = mock_result

        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            response = client.get(f"/api/v1/links/to/{valid_uuids['block_id']}")

            assert response.status_code == 200
            response_data = response.json()
            assert len(response_data) == 2

            mock_link_manager.links_to.assert_called_once()
        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")

    def test_get_links_to_with_filters(
        self, client, mock_memory_bank, mock_link_manager, valid_uuids, sample_block_links
    ):
        """Test getting links to block with query filters."""
        filtered_links = [sample_block_links[1]]  # Only second link
        mock_result = LinkQueryResult(links=filtered_links, next_cursor=None)
        mock_link_manager.links_to.return_value = mock_result

        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            response = client.get(
                f"/api/v1/links/to/{valid_uuids['block_id']}",
                params={
                    "relation": "is_blocked_by",
                    "limit": 10,
                },
            )

            assert response.status_code == 200
            response_data = response.json()
            assert len(response_data) == 1
            assert response_data[0]["relation"] == "is_blocked_by"

            mock_link_manager.links_to.assert_called_once()
        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")

    def test_get_links_to_invalid_uuid(self, client, mock_memory_bank):
        """Test getting links to block with invalid UUID."""
        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            response = client.get("/api/v1/links/to/invalid-uuid")

            assert response.status_code == 400
            assert "Invalid UUID format" in response.json()["detail"]
        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")

    def test_get_links_to_contains_from_id_field(
        self, client, mock_memory_bank, mock_link_manager, valid_uuids
    ):
        """Test that links/to endpoint returns from_id field to identify source blocks.

        This test reproduces the bug where frontend gets 'to_id' but needs 'from_id'
        to know which blocks are linking TO the target block.
        """
        target_block_id = valid_uuids["block_id"]
        source_block_id = str(uuid.uuid4())

        # Mock a link where source_block_id depends on target_block_id
        mock_link = BlockLink(
            from_id=source_block_id,  # The source block that links TO the target
            to_id=target_block_id,  # The target block we're querying for
            relation="depends_on",
            priority=1,
            link_metadata=None,
            created_at=datetime.utcnow(),
            created_by=None,
        )

        mock_result = LinkQueryResult(links=[mock_link], next_cursor=None)
        mock_link_manager.links_to.return_value = mock_result

        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            response = client.get(f"/api/v1/links/to/{target_block_id}")

            assert response.status_code == 200
            response_data = response.json()
            assert len(response_data) == 1

            link_data = response_data[0]

            # FAILING EXPECTATION: Frontend needs from_id to know source of the link
            # Currently this will fail because BlockLink schema only has to_id
            assert "from_id" in link_data, (
                "Response should contain from_id field for links_to endpoint"
            )
            assert link_data["from_id"] == source_block_id, f"from_id should be {source_block_id}"

            # to_id should still be present and be the target block
            assert "to_id" in link_data, "Response should still contain to_id field"
            assert link_data["to_id"] == target_block_id, f"to_id should be {target_block_id}"

        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")

    def test_api_block_link_structure_comprehensive(
        self, client, mock_memory_bank, mock_link_manager, valid_uuids
    ):
        """Comprehensive test of ApiBlockLink structure for both from and to endpoints."""
        target_block_id = valid_uuids["block_id"]
        source_block_id = valid_uuids["source"]

        # Test data
        test_relation = "depends_on"
        test_priority = 5
        test_metadata = {"importance": "high"}
        test_creator = "test-user"
        test_time = datetime.utcnow()

        # Mock link data
        mock_link = BlockLink(
            from_id=source_block_id,  # The source block that links TO the target
            to_id=target_block_id,  # The target block we're querying for
            relation=test_relation,
            priority=test_priority,
            link_metadata=test_metadata,
            created_at=test_time,
            created_by=test_creator,
        )

        mock_result = LinkQueryResult(links=[mock_link], next_cursor=None)
        mock_link_manager.links_to.return_value = mock_result

        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            # Test links/to endpoint
            response = client.get(f"/api/v1/links/to/{target_block_id}")
            assert response.status_code == 200
            response_data = response.json()
            assert len(response_data) == 1

            link_data = response_data[0]

            # Verify all ApiBlockLink fields are present and correct
            assert link_data["from_id"] == source_block_id, "from_id should identify source block"
            assert link_data["to_id"] == target_block_id, "to_id should identify target block"
            assert link_data["relation"] == test_relation
            assert link_data["priority"] == test_priority
            assert link_data["link_metadata"] == test_metadata
            assert link_data["created_by"] == test_creator
            assert "created_at" in link_data

            # Reset mock for from endpoint test
            mock_link_from = BlockLink(
                from_id=source_block_id,  # For links_from, this is the source
                to_id=target_block_id,  # For links_from, this is correct
                relation=test_relation,
                priority=test_priority,
                link_metadata=test_metadata,
                created_at=test_time,
                created_by=test_creator,
            )
            mock_result_from = LinkQueryResult(links=[mock_link_from], next_cursor=None)
            mock_link_manager.links_from.return_value = mock_result_from

            # Test links/from endpoint
            response_from = client.get(f"/api/v1/links/from/{source_block_id}")
            assert response_from.status_code == 200
            response_from_data = response_from.json()
            assert len(response_from_data) == 1

            link_from_data = response_from_data[0]

            # Verify from endpoint returns correct structure
            assert link_from_data["from_id"] == source_block_id, (
                "from_id should be query block for links_from"
            )
            assert link_from_data["to_id"] == target_block_id, "to_id should be the target"
            assert link_from_data["relation"] == test_relation
            assert link_from_data["priority"] == test_priority

        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")


class TestDeleteLinksForBlock:
    """Test DELETE /api/v1/links/block/{block_id} endpoint."""

    def test_delete_links_for_block_success(
        self, client, mock_memory_bank, mock_link_manager, valid_uuids
    ):
        """Test successful deletion of all links for a block."""
        mock_link_manager.delete_links_for_block.return_value = 3

        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            response = client.delete(f"/api/v1/links/block/{valid_uuids['block_id']}")

            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
            assert "Deleted 3 links" in response_data["message"]

            mock_link_manager.delete_links_for_block.assert_called_once_with(
                block_id=valid_uuids["block_id"]
            )
        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")

    def test_delete_links_for_block_no_links(
        self, client, mock_memory_bank, mock_link_manager, valid_uuids
    ):
        """Test deleting links for block with no existing links."""
        mock_link_manager.delete_links_for_block.return_value = 0

        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            response = client.delete(f"/api/v1/links/block/{valid_uuids['block_id']}")

            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
            assert "Deleted 0 links" in response_data["message"]
        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")

    def test_delete_links_for_block_invalid_uuid(self, client, mock_memory_bank):
        """Test deleting links for block with invalid UUID."""
        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            response = client.delete("/api/v1/links/block/invalid-uuid")

            assert response.status_code == 400
            assert "Invalid UUID format" in response.json()["detail"]
        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")


class TestLinkManagerDependency:
    """Test the get_link_manager dependency function."""

    def test_link_manager_unavailable(self, client):
        """Test error when LinkManager is not attached to memory bank."""
        mock_bank = MagicMock()
        mock_bank.link_manager = None

        setattr(app.state, "memory_bank", mock_bank)
        try:
            response = client.get(f"/api/v1/links/from/{str(uuid.uuid4())}")

            assert response.status_code == 500
            assert "LinkManager service unavailable" in response.json()["detail"]
        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")

    def test_memory_bank_not_configured(self, client):
        """Test error when memory bank is not configured."""
        # Ensure no memory_bank attribute exists
        if hasattr(app.state, "memory_bank"):
            delattr(app.state, "memory_bank")

        response = client.get(f"/api/v1/links/from/{str(uuid.uuid4())}")

        assert response.status_code == 500
        assert "Memory bank not configured" in response.json()["detail"]


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_full_link_lifecycle(
        self, client, mock_memory_bank, mock_link_manager, valid_uuids, sample_block_links
    ):
        """Test creating, retrieving, and deleting a link."""
        # Create a link that matches our test UUIDs
        created_link = BlockLink(
            from_id=valid_uuids["source"],
            to_id=valid_uuids["target"],
            relation="depends_on",
            priority=1,
            link_metadata=None,
            created_at=datetime.utcnow(),
            created_by=None,
        )

        # Mock responses for each operation
        mock_link_manager.create_link.return_value = created_link
        mock_link_manager.links_from.return_value = LinkQueryResult(
            links=[created_link], next_cursor=None
        )
        mock_link_manager.delete_link.return_value = True

        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            # 1. Create a link
            create_response = client.post(
                "/api/v1/links",
                params={
                    "from_id": valid_uuids["source"],
                    "to_id": valid_uuids["target"],
                    "relation": "depends_on",
                    "priority": 1,
                },
            )
            assert create_response.status_code == 201

            # 2. Retrieve links from the source block
            get_response = client.get(f"/api/v1/links/from/{valid_uuids['source']}")
            assert get_response.status_code == 200
            links = get_response.json()
            assert len(links) == 1
            assert links[0]["to_id"] == valid_uuids["target"]

            # 3. Delete the link
            delete_response = client.delete(
                "/api/v1/links",
                params={
                    "from_id": valid_uuids["source"],
                    "to_id": valid_uuids["target"],
                    "relation": "depends_on",
                },
            )
            assert delete_response.status_code == 200

            # Verify all operations were called
            mock_link_manager.create_link.assert_called_once()
            mock_link_manager.links_from.assert_called_once()
            mock_link_manager.delete_link.assert_called_once()
        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")

    def test_concurrent_link_operations(
        self, client, mock_memory_bank, mock_link_manager, valid_uuids
    ):
        """Test multiple concurrent link operations."""
        # Setup different responses for different calls
        mock_link_manager.links_from.return_value = LinkQueryResult(links=[], next_cursor=None)
        mock_link_manager.links_to.return_value = LinkQueryResult(links=[], next_cursor=None)

        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            # Multiple concurrent GET requests
            responses = []
            for i in range(3):
                block_id = str(uuid.uuid4())
                responses.append(client.get(f"/api/v1/links/from/{block_id}"))
                responses.append(client.get(f"/api/v1/links/to/{block_id}"))

            # All should succeed
            for response in responses:
                assert response.status_code == 200

            # Verify link_manager was called multiple times
            assert mock_link_manager.links_from.call_count == 3
            assert mock_link_manager.links_to.call_count == 3
        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")


class TestGetAllLinks:
    """Test GET /api/v1/links endpoint."""

    def test_get_all_links_success(
        self, client, mock_memory_bank, mock_link_manager, sample_block_links
    ):
        """Test successful retrieval of all links."""
        mock_result = LinkQueryResult(links=sample_block_links, next_cursor=None)
        mock_link_manager.get_all_links.return_value = mock_result

        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            response = client.get("/api/v1/links")

            assert response.status_code == 200
            response_data = response.json()
            assert len(response_data) == 2
            assert response_data[0]["to_id"] == "target-1"
            assert response_data[0]["relation"] == "depends_on"
            assert response_data[1]["to_id"] == "target-2"
            assert response_data[1]["relation"] == "is_blocked_by"

            mock_link_manager.get_all_links.assert_called_once()
        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")

    def test_get_all_links_with_relation_filter(
        self, client, mock_memory_bank, mock_link_manager, sample_block_links
    ):
        """Test getting all links with relation filter."""
        filtered_links = [sample_block_links[0]]  # Only first link
        mock_result = LinkQueryResult(links=filtered_links, next_cursor=None)
        mock_link_manager.get_all_links.return_value = mock_result

        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            response = client.get(
                "/api/v1/links",
                params={
                    "relation": "depends_on",
                    "limit": 50,
                },
            )

            assert response.status_code == 200
            response_data = response.json()
            assert len(response_data) == 1
            assert response_data[0]["relation"] == "depends_on"

            mock_link_manager.get_all_links.assert_called_once()
        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")

    def test_get_all_links_empty_result(self, client, mock_memory_bank, mock_link_manager):
        """Test getting all links when no links exist."""
        mock_result = LinkQueryResult(links=[], next_cursor=None)
        mock_link_manager.get_all_links.return_value = mock_result

        setattr(app.state, "memory_bank", mock_memory_bank)
        try:
            response = client.get("/api/v1/links")

            assert response.status_code == 200
            response_data = response.json()
            assert len(response_data) == 0

            mock_link_manager.get_all_links.assert_called_once()
        finally:
            if hasattr(app.state, "memory_bank"):
                delattr(app.state, "memory_bank")
