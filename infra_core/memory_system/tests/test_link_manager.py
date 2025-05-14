"""
Tests for the LinkManager implementation.
"""

import pytest
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from infra_core.memory_system.link_manager import LinkManager, LinkError
from infra_core.memory_system.schemas.common import BlockLink, RelationType


class MockLinkManager(LinkManager):
    """Mock implementation of LinkManager for testing the interface."""

    def create_link(
        self,
        from_id: str,
        to_id: str,
        relation: RelationType,
        priority: int = 0,
        link_metadata: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None,
    ) -> BlockLink:
        raise NotImplementedError("Mock not implemented")

    def delete_link(self, from_id: str, to_id: str, relation: RelationType) -> bool:
        raise NotImplementedError("Mock not implemented")

    def links_from(self, block_id: str, query=None):
        raise NotImplementedError("Mock not implemented")

    def links_to(self, block_id: str, query=None):
        raise NotImplementedError("Mock not implemented")

    def has_cycle(self, start_id: str, relation: RelationType, visited=None):
        raise NotImplementedError("Mock not implemented")

    def topo_sort(self, block_ids, relation):
        raise NotImplementedError("Mock not implemented")

    def bulk_upsert(self, links):
        raise NotImplementedError("Mock not implemented")

    def delete_links_for_block(self, block_id):
        raise NotImplementedError("Mock not implemented")


@pytest.fixture
def link_manager():
    """Fixture for a mock LinkManager instance."""
    return MockLinkManager()


@pytest.fixture
def valid_block_ids():
    """Fixture for valid block IDs to use in tests."""
    return {"block1": str(uuid.uuid4()), "block2": str(uuid.uuid4()), "block3": str(uuid.uuid4())}


@pytest.mark.xfail(reason="Not yet implemented")
def test_create_link_basic(link_manager, valid_block_ids):
    """Test basic link creation works."""
    link = link_manager.create_link(
        from_id=valid_block_ids["block1"], to_id=valid_block_ids["block2"], relation="related_to"
    )

    # Verify returned BlockLink
    assert isinstance(link, BlockLink)
    assert link.to_id == valid_block_ids["block2"]
    assert link.relation == "related_to"
    assert link.priority == 0
    assert link.link_metadata is None
    assert link.created_by is None
    assert isinstance(link.created_at, datetime)


@pytest.mark.xfail(reason="Not yet implemented")
def test_create_link_with_metadata(link_manager, valid_block_ids):
    """Test link creation with metadata."""
    metadata = {"strength": 0.8, "notes": "Test link"}
    link = link_manager.create_link(
        from_id=valid_block_ids["block1"],
        to_id=valid_block_ids["block2"],
        relation="related_to",
        priority=5,
        link_metadata=metadata,
        created_by="test-user",
    )

    # Verify metadata is saved
    assert link.priority == 5
    assert link.link_metadata == metadata
    assert link.created_by == "test-user"


@pytest.mark.xfail(reason="Not yet implemented")
def test_create_link_validation_error_invalid_id(link_manager):
    """Test that creating a link with invalid UUID raises a VALIDATION_ERROR."""
    with pytest.raises(ValueError) as exc_info:
        link_manager.create_link(
            from_id="not-a-valid-uuid", to_id=str(uuid.uuid4()), relation="related_to"
        )
    assert "invalid UUID" in str(exc_info.value).lower()


@pytest.mark.xfail(reason="Not yet implemented")
def test_create_link_validation_error_invalid_relation(link_manager, valid_block_ids):
    """Test that creating a link with invalid relation raises a VALIDATION_ERROR."""
    with pytest.raises(ValueError) as exc_info:
        link_manager.create_link(
            from_id=valid_block_ids["block1"],
            to_id=valid_block_ids["block2"],
            relation="not_a_valid_relation",  # type: ignore
        )
    assert "relation" in str(exc_info.value).lower()


@pytest.mark.xfail(reason="Not yet implemented")
def test_create_link_duplicate(link_manager, valid_block_ids):
    """Test that creating a duplicate link raises a VALIDATION_ERROR."""
    # First creation should succeed
    link_manager.create_link(
        from_id=valid_block_ids["block1"], to_id=valid_block_ids["block2"], relation="related_to"
    )

    # Second creation with same composite key should raise
    with pytest.raises(LinkError) as exc_info:
        link_manager.create_link(
            from_id=valid_block_ids["block1"],
            to_id=valid_block_ids["block2"],
            relation="related_to",
        )
    assert exc_info.value == LinkError.VALIDATION_ERROR


@pytest.mark.xfail(reason="Not yet implemented")
def test_cycle_detection_blocked_by(link_manager, valid_block_ids):
    """Test cycle detection for blocked_by relation."""
    # Create A -> B (A is blocked by B)
    link_manager.create_link(
        from_id=valid_block_ids["block1"], to_id=valid_block_ids["block2"], relation="is_blocked_by"
    )

    # Create B -> C (B is blocked by C)
    link_manager.create_link(
        from_id=valid_block_ids["block2"], to_id=valid_block_ids["block3"], relation="is_blocked_by"
    )

    # Try to create C -> A (C is blocked by A) - would create a cycle
    with pytest.raises(LinkError) as exc_info:
        link_manager.create_link(
            from_id=valid_block_ids["block3"],
            to_id=valid_block_ids["block1"],
            relation="is_blocked_by",
        )
    assert exc_info.value == LinkError.CYCLE_DETECTED


@pytest.mark.xfail(reason="Not yet implemented")
def test_delete_link(link_manager, valid_block_ids):
    """Test link deletion."""
    # Create a link
    link_manager.create_link(
        from_id=valid_block_ids["block1"], to_id=valid_block_ids["block2"], relation="related_to"
    )

    # Delete the link
    result = link_manager.delete_link(
        from_id=valid_block_ids["block1"], to_id=valid_block_ids["block2"], relation="related_to"
    )

    # Verify deletion succeeded
    assert result is True

    # Verify link no longer exists
    assert not link_manager.links_from(valid_block_ids["block1"]).links


@pytest.mark.xfail(reason="Not yet implemented")
def test_delete_links_for_block(link_manager, valid_block_ids):
    """Test deleting all links for a block."""
    # Create links in both directions
    link_manager.create_link(
        from_id=valid_block_ids["block1"], to_id=valid_block_ids["block2"], relation="related_to"
    )
    link_manager.create_link(
        from_id=valid_block_ids["block2"], to_id=valid_block_ids["block1"], relation="related_to"
    )
    link_manager.create_link(
        from_id=valid_block_ids["block1"], to_id=valid_block_ids["block3"], relation="mentions"
    )

    # Delete all links for block1
    count = link_manager.delete_links_for_block(valid_block_ids["block1"])

    # Should have deleted 3 links
    assert count == 3

    # Verify no links to or from block1 exist
    assert not link_manager.links_from(valid_block_ids["block1"]).links
    assert not link_manager.links_to(valid_block_ids["block1"]).links
