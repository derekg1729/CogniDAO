"""
Tests for the InMemoryLinkManager implementation.
"""

import pytest
import uuid
from datetime import datetime

from infra_core.memory_system.link_manager import (
    InMemoryLinkManager,
    LinkError,
    LinkErrorType,
    BlockLink,
    LinkQuery,
)


@pytest.fixture
def link_manager():
    """Fixture for an InMemoryLinkManager instance."""
    return InMemoryLinkManager()


@pytest.fixture
def valid_block_ids():
    """Fixture for valid block IDs to use in tests."""
    return {
        "block1": str(uuid.uuid4()),
        "block2": str(uuid.uuid4()),
        "block3": str(uuid.uuid4()),
        "block4": str(uuid.uuid4()),
    }


def test_create_link_basic(link_manager, valid_block_ids):
    """Test basic link creation works."""
    link = link_manager.create_link(
        from_id=valid_block_ids["block1"],
        to_id=valid_block_ids["block2"],
        relation="related_to",
    )

    # Verify returned BlockLink
    assert isinstance(link, BlockLink)
    assert link.to_id == valid_block_ids["block2"]
    assert link.relation == "related_to"
    assert link.priority == 0
    assert link.link_metadata is None
    assert link.created_by is None
    assert isinstance(link.created_at, datetime)


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


def test_create_link_duplicate(link_manager, valid_block_ids):
    """Test that creating a duplicate link raises a VALIDATION_ERROR."""
    # First creation should succeed
    link_manager.create_link(
        from_id=valid_block_ids["block1"],
        to_id=valid_block_ids["block2"],
        relation="related_to",
    )

    # Second creation with same composite key should raise
    with pytest.raises(LinkError) as exc_info:
        link_manager.create_link(
            from_id=valid_block_ids["block1"],
            to_id=valid_block_ids["block2"],
            relation="related_to",
        )
    assert exc_info.value.error_type == LinkErrorType.VALIDATION_ERROR


def test_delete_link(link_manager, valid_block_ids):
    """Test link deletion."""
    # Create a link
    link_manager.create_link(
        from_id=valid_block_ids["block1"],
        to_id=valid_block_ids["block2"],
        relation="related_to",
    )

    # Delete the link
    result = link_manager.delete_link(
        from_id=valid_block_ids["block1"],
        to_id=valid_block_ids["block2"],
        relation="related_to",
    )

    # Verify deletion succeeded
    assert result is True

    # Verify link no longer exists
    links = link_manager.links_from(valid_block_ids["block1"]).links
    assert len(links) == 0


def test_delete_nonexistent_link(link_manager, valid_block_ids):
    """Test deleting a link that doesn't exist."""
    result = link_manager.delete_link(
        from_id=valid_block_ids["block1"],
        to_id=valid_block_ids["block2"],
        relation="related_to",
    )
    assert result is False


def test_cycle_detection_direct(link_manager, valid_block_ids):
    """Test cycle detection for direct cycles (A -> A)."""
    # Create a self-link (should be prevented)
    with pytest.raises(LinkError) as exc_info:
        link_manager.create_link(
            from_id=valid_block_ids["block1"],
            to_id=valid_block_ids["block1"],
            relation="related_to",
        )
    assert exc_info.value.error_type == LinkErrorType.CYCLE_DETECTED


def test_cycle_detection_indirect(link_manager, valid_block_ids):
    """Test cycle detection for indirect cycles (A -> B -> C -> A)."""
    # Create A -> B
    link_manager.create_link(
        from_id=valid_block_ids["block1"],
        to_id=valid_block_ids["block2"],
        relation="is_blocked_by",
    )

    # Create B -> C
    link_manager.create_link(
        from_id=valid_block_ids["block2"],
        to_id=valid_block_ids["block3"],
        relation="is_blocked_by",
    )

    # Try to create C -> A (would create a cycle)
    with pytest.raises(LinkError) as exc_info:
        link_manager.create_link(
            from_id=valid_block_ids["block3"],
            to_id=valid_block_ids["block1"],
            relation="is_blocked_by",
        )
    assert exc_info.value.error_type == LinkErrorType.CYCLE_DETECTED


def test_has_cycle(link_manager, valid_block_ids):
    """Test the has_cycle method."""
    # Create a chain that doesn't have a cycle
    link_manager.create_link(
        from_id=valid_block_ids["block1"],
        to_id=valid_block_ids["block2"],
        relation="is_blocked_by",
    )
    link_manager.create_link(
        from_id=valid_block_ids["block2"],
        to_id=valid_block_ids["block3"],
        relation="is_blocked_by",
    )

    # Check has_cycle for each node
    assert not link_manager.has_cycle(valid_block_ids["block1"], "is_blocked_by")
    assert not link_manager.has_cycle(valid_block_ids["block2"], "is_blocked_by")
    assert not link_manager.has_cycle(valid_block_ids["block3"], "is_blocked_by")

    # Add link to create a cycle (B -> A)
    # (We need to manually add to index since create_link would detect and prevent it)
    link_manager._index.add_link(
        valid_block_ids["block3"], valid_block_ids["block1"], "is_blocked_by"
    )

    # Now check has_cycle again
    assert link_manager.has_cycle(valid_block_ids["block1"], "is_blocked_by")
    assert link_manager.has_cycle(valid_block_ids["block2"], "is_blocked_by")
    assert link_manager.has_cycle(valid_block_ids["block3"], "is_blocked_by")


def test_links_from_basic(link_manager, valid_block_ids):
    """Test getting links from a block."""
    # Create links
    link_manager.create_link(
        from_id=valid_block_ids["block1"],
        to_id=valid_block_ids["block2"],
        relation="related_to",
    )
    link_manager.create_link(
        from_id=valid_block_ids["block1"],
        to_id=valid_block_ids["block3"],
        relation="is_blocked_by",
    )

    # Get all links from block1
    result = link_manager.links_from(valid_block_ids["block1"])
    assert len(result.links) == 2

    # Get links with specific relation
    query = LinkQuery().relation("related_to")
    result = link_manager.links_from(valid_block_ids["block1"], query)
    assert len(result.links) == 1
    assert result.links[0].to_id == valid_block_ids["block2"]
    assert result.links[0].relation == "related_to"


def test_links_to_basic(link_manager, valid_block_ids):
    """Test getting links to a block."""
    # Create links
    link_manager.create_link(
        from_id=valid_block_ids["block1"],
        to_id=valid_block_ids["block3"],
        relation="related_to",
    )
    link_manager.create_link(
        from_id=valid_block_ids["block2"],
        to_id=valid_block_ids["block3"],
        relation="is_blocked_by",
    )

    # Get all links to block3
    result = link_manager.links_to(valid_block_ids["block3"])
    assert len(result.links) == 2

    # Get links with specific relation
    query = LinkQuery().relation("is_blocked_by")
    result = link_manager.links_to(valid_block_ids["block3"], query)
    assert len(result.links) == 1
    assert result.links[0].to_id == valid_block_ids["block3"]
    assert result.links[0].relation == "is_blocked_by"


def test_topo_sort(link_manager, valid_block_ids):
    """Test topological sorting."""
    # Create a DAG (directed acyclic graph) for sorting:
    # block3 -> block2 -> block1
    link_manager.create_link(
        from_id=valid_block_ids["block2"],
        to_id=valid_block_ids["block1"],
        relation="is_blocked_by",
    )
    link_manager.create_link(
        from_id=valid_block_ids["block3"],
        to_id=valid_block_ids["block2"],
        relation="is_blocked_by",
    )

    # Create a separate link with different relation
    link_manager.create_link(
        from_id=valid_block_ids["block1"],
        to_id=valid_block_ids["block3"],
        relation="related_to",  # Different relation type
    )

    # Get topological sort for is_blocked_by relation
    sorted_ids = link_manager.topo_sort(
        [valid_block_ids["block1"], valid_block_ids["block2"], valid_block_ids["block3"]],
        "is_blocked_by",
    )

    # Verify order maintains dependencies (source comes after target for "is_blocked_by")
    # This is more robust than checking specific positions

    # Get the indices of each block in the result
    indices = {id: sorted_ids.index(id) for id in valid_block_ids.values() if id in sorted_ids}

    # block2 depends on block1, so block1 should come before block2
    assert indices[valid_block_ids["block1"]] < indices[valid_block_ids["block2"]]

    # block3 depends on block2, so block2 should come before block3
    assert indices[valid_block_ids["block2"]] < indices[valid_block_ids["block3"]]


def test_topo_sort_detects_cycles(link_manager, valid_block_ids):
    """Test that topological sort raises error when cycles are present."""
    # Create a chain
    link_manager.create_link(
        from_id=valid_block_ids["block1"],
        to_id=valid_block_ids["block2"],
        relation="is_blocked_by",
    )

    # Add a link back to create a cycle, bypassing the cycle detection in create_link
    # by directly adding to the internal links dictionary
    cycle_link_key = (valid_block_ids["block2"], valid_block_ids["block1"], "is_blocked_by")

    # Create a mock BlockLink for the cycle link
    cycle_link = BlockLink(
        from_id=valid_block_ids["block2"],
        to_id=valid_block_ids["block1"],
        relation="is_blocked_by",
        priority=0,
        created_at=datetime.now(),
    )

    # Add to both the index and the links dictionary
    link_manager._index.add_link(
        valid_block_ids["block2"], valid_block_ids["block1"], "is_blocked_by"
    )
    link_manager._links[cycle_link_key] = cycle_link

    # Now topo_sort should detect the cycle and raise ValueError
    with pytest.raises(ValueError, match="Cycle detected"):
        link_manager.topo_sort(
            [valid_block_ids["block1"], valid_block_ids["block2"]], "is_blocked_by"
        )


def test_delete_links_for_block(link_manager, valid_block_ids):
    """Test deleting all links for a block."""
    # Create links in both directions without introducing cycles
    link_manager.create_link(
        from_id=valid_block_ids["block1"],
        to_id=valid_block_ids["block2"],
        relation="related_to",
    )
    # Use a different relation type to avoid cycle detection
    link_manager.create_link(
        from_id=valid_block_ids["block2"],
        to_id=valid_block_ids["block1"],
        relation="mentions",
    )
    link_manager.create_link(
        from_id=valid_block_ids["block1"],
        to_id=valid_block_ids["block3"],
        relation="is_blocked_by",
    )
    link_manager.create_link(
        from_id=valid_block_ids["block4"],
        to_id=valid_block_ids["block3"],
        relation="is_blocked_by",
    )

    # Delete all links for block1
    count = link_manager.delete_links_for_block(valid_block_ids["block1"])

    # Should have deleted 3 links
    assert count == 3

    # Verify no links to or from block1 exist
    assert len(link_manager.links_from(valid_block_ids["block1"]).links) == 0
    assert len(link_manager.links_to(valid_block_ids["block1"]).links) == 0

    # Other links should still exist
    assert len(link_manager.links_from(valid_block_ids["block4"]).links) == 1
