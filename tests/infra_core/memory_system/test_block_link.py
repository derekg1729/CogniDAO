from datetime import datetime
from typing import Dict, Any
import pytest
from infra_core.memory_system.schemas.common import BlockLink, RelationType
from typing import get_args


def test_block_link_creation_with_defaults():
    """Test creating a BlockLink with minimal required fields."""
    link = BlockLink(from_id="source-block-123", to_id="target-block-123", relation="related_to")

    assert link.from_id == "source-block-123"
    assert link.to_id == "target-block-123"
    assert link.relation == "related_to"
    assert link.priority == 0
    assert link.link_metadata is None
    assert link.created_by is None
    assert isinstance(link.created_at, datetime)


def test_block_link_creation_with_all_fields():
    """Test creating a BlockLink with all fields specified."""
    test_metadata: Dict[str, Any] = {"strength": 0.8, "context": "test"}
    test_time = datetime.now()

    link = BlockLink(
        from_id="source-block-123",
        to_id="target-block-123",
        relation="subtask_of",
        priority=5,
        link_metadata=test_metadata,
        created_by="agent-123",
        created_at=test_time,
    )

    assert link.from_id == "source-block-123"
    assert link.to_id == "target-block-123"
    assert link.relation == "subtask_of"
    assert link.priority == 5
    assert link.link_metadata == test_metadata
    assert link.created_by == "agent-123"
    assert link.created_at == test_time


def test_block_link_priority_validation():
    """Test validation of priority field."""
    # Test valid priority
    link = BlockLink(from_id="source-123", to_id="target-123", relation="related_to", priority=0)
    assert link.priority == 0

    link = BlockLink(from_id="source-123", to_id="target-123", relation="related_to", priority=100)
    assert link.priority == 100

    # Test invalid priority
    with pytest.raises(ValueError, match="Priority must be non-negative"):
        BlockLink(from_id="source-123", to_id="target-123", relation="related_to", priority=-1)


def test_block_link_relation_validation():
    """Test validation of relation field."""
    # Test valid relations
    valid_relations = get_args(RelationType)
    for relation in valid_relations:
        link = BlockLink(from_id="source-123", to_id="target-123", relation=relation)
        assert link.relation == relation

    # Test invalid relation
    with pytest.raises(ValueError):
        BlockLink(from_id="source-123", to_id="target-123", relation="invalid_relation")


def test_block_link_metadata_validation():
    """Test validation of link_metadata field."""
    # Test valid metadata
    valid_metadata = {
        "strength": 0.8,
        "context": "test",
        "tags": ["important", "urgent"],
        "confidence": 0.95,
    }
    link = BlockLink(
        from_id="source-123",
        to_id="target-123",
        relation="related_to",
        link_metadata=valid_metadata,
    )
    assert link.link_metadata == valid_metadata

    # Test empty metadata
    link = BlockLink(
        from_id="source-123", to_id="target-123", relation="related_to", link_metadata={}
    )
    assert link.link_metadata == {}


def test_block_link_created_at_auto_generation():
    """Test that created_at is automatically generated if not provided."""
    before = datetime.now()
    link = BlockLink(from_id="source-123", to_id="target-123", relation="related_to")
    after = datetime.now()

    assert isinstance(link.created_at, datetime)
    assert before <= link.created_at <= after


def test_block_link_serialization():
    """Test serialization of BlockLink to dict."""
    test_time = datetime.now()
    link = BlockLink(
        from_id="source-123",
        to_id="target-123",
        relation="related_to",
        priority=5,
        link_metadata={"strength": 0.8},
        created_by="agent-123",
        created_at=test_time,
    )

    serialized = link.model_dump()
    assert serialized == {
        "from_id": "source-123",
        "to_id": "target-123",
        "relation": "related_to",
        "priority": 5,
        "link_metadata": {"strength": 0.8},
        "created_by": "agent-123",
        "created_at": test_time,
    }
