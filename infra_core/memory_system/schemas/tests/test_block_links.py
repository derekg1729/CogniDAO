"""
Test block link relation types.
"""

import pytest
from typing import get_args

from infra_core.memory_system.schemas.common import RelationType, BlockLink


def test_relation_types_enum():
    """Test that RelationType includes all expected relation types."""
    relation_types = get_args(RelationType)

    # Basic relation types
    assert "related_to" in relation_types
    assert "subtask_of" in relation_types
    assert "depends_on" in relation_types
    assert "child_of" in relation_types
    assert "mentions" in relation_types
    assert "parent_of" in relation_types

    # Epic relation types
    assert "belongs_to_epic" in relation_types
    assert "epic_contains" in relation_types

    # Bug relation types
    assert "bug_affects" in relation_types
    assert "has_bug" in relation_types

    # Blocking relation types
    assert "blocks" in relation_types
    assert "is_blocked_by" in relation_types


def test_block_link_creation_with_relation_types():
    """Test creating BlockLinks with different relation types."""
    # Test epic relations
    epic_link = BlockLink(to_id="epic-123", relation="belongs_to_epic")
    assert epic_link.to_id == "epic-123"
    assert epic_link.relation == "belongs_to_epic"

    # Test epic contains relation
    epic_contains_link = BlockLink(to_id="task-456", relation="epic_contains")
    assert epic_contains_link.to_id == "task-456"
    assert epic_contains_link.relation == "epic_contains"

    # Test bug relations
    bug_link = BlockLink(to_id="bug-789", relation="has_bug")
    assert bug_link.to_id == "bug-789"
    assert bug_link.relation == "has_bug"

    bug_affects_link = BlockLink(to_id="project-abc", relation="bug_affects")
    assert bug_affects_link.to_id == "project-abc"
    assert bug_affects_link.relation == "bug_affects"

    # Test blocking relations
    blocks_link = BlockLink(to_id="task-def", relation="blocks")
    assert blocks_link.to_id == "task-def"
    assert blocks_link.relation == "blocks"

    blocked_by_link = BlockLink(to_id="task-ghi", relation="is_blocked_by")
    assert blocked_by_link.to_id == "task-ghi"
    assert blocked_by_link.relation == "is_blocked_by"


def test_block_link_with_invalid_relation():
    """Test that creating a BlockLink with an invalid relation raises an error."""
    with pytest.raises(ValueError):
        BlockLink(to_id="task-123", relation="invalid_relation_type")
