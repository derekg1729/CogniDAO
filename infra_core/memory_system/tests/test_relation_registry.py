"""
Tests for the relation registry module.
"""

import pytest
from typing import get_args

from infra_core.memory_system.relation_registry import (
    CoreRelationType,
    PMRelationType,
    BugRelationType,
    KnowledgeRelationType,
    RelationType,
    RELATION_CATEGORIES,
    INVERSE_RELATIONS,
    get_all_relation_types,
    get_relation_category,
    get_inverse_relation,
    is_valid_relation,
    is_blocking_relation,
    is_parent_relation,
)


def test_relation_enums():
    """Test that relation enums contain expected values."""
    # Core relations
    assert CoreRelationType.RELATED_TO.value == "related_to"
    assert CoreRelationType.MENTIONS.value == "mentions"
    assert CoreRelationType.CHILD_OF.value == "child_of"
    assert CoreRelationType.PARENT_OF.value == "parent_of"

    # Project management relations
    assert PMRelationType.SUBTASK_OF.value == "subtask_of"
    assert PMRelationType.DEPENDS_ON.value == "depends_on"
    assert PMRelationType.BLOCKS.value == "blocks"
    assert PMRelationType.IS_BLOCKED_BY.value == "is_blocked_by"

    # Bug relations
    assert BugRelationType.BUG_AFFECTS.value == "bug_affects"
    assert BugRelationType.HAS_BUG.value == "has_bug"

    # Knowledge relations
    assert KnowledgeRelationType.DERIVED_FROM.value == "derived_from"


def test_relation_type_literal():
    """Test that RelationType contains all expected values."""
    relation_types = get_args(RelationType)

    # Test that we have all relations from each category
    for relation in [r.value for r in CoreRelationType]:
        assert relation in relation_types

    for relation in [r.value for r in PMRelationType]:
        assert relation in relation_types

    for relation in [r.value for r in BugRelationType]:
        assert relation in relation_types

    for relation in [r.value for r in KnowledgeRelationType]:
        assert relation in relation_types


def test_relation_categories():
    """Test that RELATION_CATEGORIES contains all relations organized by category."""
    # Check core category
    assert set(RELATION_CATEGORIES["core"]) == {r.value for r in CoreRelationType}

    # Check project_management category
    assert set(RELATION_CATEGORIES["project_management"]) == {r.value for r in PMRelationType}

    # Check bug_tracking category
    assert set(RELATION_CATEGORIES["bug_tracking"]) == {r.value for r in BugRelationType}

    # Check knowledge category
    assert set(RELATION_CATEGORIES["knowledge"]) == {r.value for r in KnowledgeRelationType}


def test_inverse_relations():
    """Test that inverse relations are correctly defined."""
    # Test core inverse relations
    assert INVERSE_RELATIONS[CoreRelationType.CHILD_OF.value] == CoreRelationType.PARENT_OF.value
    assert INVERSE_RELATIONS[CoreRelationType.PARENT_OF.value] == CoreRelationType.CHILD_OF.value

    # Test PM inverse relations
    assert INVERSE_RELATIONS[PMRelationType.BLOCKS.value] == PMRelationType.IS_BLOCKED_BY.value
    assert INVERSE_RELATIONS[PMRelationType.IS_BLOCKED_BY.value] == PMRelationType.BLOCKS.value

    # Test symmetry of inverse relations
    for relation, inverse in INVERSE_RELATIONS.items():
        assert INVERSE_RELATIONS[inverse] == relation


def test_get_all_relation_types():
    """Test get_all_relation_types returns all relation types."""
    relations = get_all_relation_types()

    # Should contain all relations from all categories
    expected_count = (
        len(CoreRelationType)
        + len(PMRelationType)
        + len(BugRelationType)
        + len(KnowledgeRelationType)
    )

    assert len(relations) == expected_count

    # Check a few specific relations
    assert "related_to" in relations
    assert "is_blocked_by" in relations
    assert "derived_from" in relations


def test_get_relation_category():
    """Test get_relation_category returns the correct category."""
    assert get_relation_category("related_to") == "core"
    assert get_relation_category("is_blocked_by") == "project_management"
    assert get_relation_category("bug_affects") == "bug_tracking"
    assert get_relation_category("derived_from") == "knowledge"

    # Test invalid relation
    with pytest.raises(ValueError):
        get_relation_category("invalid_relation")


def test_get_inverse_relation():
    """Test get_inverse_relation returns the correct inverse."""
    assert get_inverse_relation("child_of") == "parent_of"
    assert get_inverse_relation("blocks") == "is_blocked_by"
    assert get_inverse_relation("bug_affects") == "has_bug"

    # Test relation with no inverse
    assert get_inverse_relation("related_to") == "related_to"
    assert get_inverse_relation("mentions") == "mentions"


def test_is_valid_relation():
    """Test is_valid_relation correctly validates relations."""
    assert is_valid_relation("related_to") is True
    assert is_valid_relation("is_blocked_by") is True
    assert is_valid_relation("invalid_relation") is False


def test_is_blocking_relation():
    """Test is_blocking_relation correctly identifies blocking relations."""
    assert is_blocking_relation("blocks") is True
    assert is_blocking_relation("is_blocked_by") is True
    assert is_blocking_relation("related_to") is False


def test_is_parent_relation():
    """Test is_parent_relation correctly identifies parent relations."""
    assert is_parent_relation("child_of") is True
    assert is_parent_relation("parent_of") is True
    assert is_parent_relation("subtask_of") is True
    assert is_parent_relation("blocks") is False
