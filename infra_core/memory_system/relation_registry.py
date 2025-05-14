"""
Relation Registry for Memory Blocks Link System.

This module provides a centralized registry of all relation types that can be
used for links between memory blocks, organized by domain categories.
"""

from enum import Enum
from typing import List, Literal, get_args


# Core relation types for general usage across all block types
class CoreRelationType(str, Enum):
    """Core relation types applicable to all memory blocks."""

    RELATED_TO = "related_to"
    MENTIONS = "mentions"
    CHILD_OF = "child_of"
    PARENT_OF = "parent_of"


# Project management specific relation types
class PMRelationType(str, Enum):
    """Project management specific relation types."""

    SUBTASK_OF = "subtask_of"
    DEPENDS_ON = "depends_on"
    BLOCKS = "blocks"
    IS_BLOCKED_BY = "is_blocked_by"
    BELONGS_TO_EPIC = "belongs_to_epic"
    EPIC_CONTAINS = "epic_contains"


# Bug tracking specific relation types
class BugRelationType(str, Enum):
    """Bug tracking specific relation types."""

    BUG_AFFECTS = "bug_affects"
    HAS_BUG = "has_bug"


# Knowledge management specific relation types
class KnowledgeRelationType(str, Enum):
    """Knowledge management specific relation types."""

    DERIVED_FROM = "derived_from"
    SUPERSEDES = "supersedes"
    REFERENCES = "references"


# Combine all relation types for validation
# This creates the Literal union type used by Pydantic
RelationType = Literal[
    # Core relations
    "related_to",
    "mentions",
    "child_of",
    "parent_of",
    # Project management relations
    "subtask_of",
    "depends_on",
    "blocks",
    "is_blocked_by",
    "belongs_to_epic",
    "epic_contains",
    # Bug tracking relations
    "bug_affects",
    "has_bug",
    # Knowledge relations
    "derived_from",
    "supersedes",
    "references",
]


# Relation category mapping for organizational purposes
RELATION_CATEGORIES = {
    "core": [r.value for r in CoreRelationType],
    "project_management": [r.value for r in PMRelationType],
    "bug_tracking": [r.value for r in BugRelationType],
    "knowledge": [r.value for r in KnowledgeRelationType],
}


# Relation pairs (bidirectional relationships)
# When one relation is created, the inverse is implied
INVERSE_RELATIONS = {
    CoreRelationType.CHILD_OF.value: CoreRelationType.PARENT_OF.value,
    CoreRelationType.PARENT_OF.value: CoreRelationType.CHILD_OF.value,
    PMRelationType.BLOCKS.value: PMRelationType.IS_BLOCKED_BY.value,
    PMRelationType.IS_BLOCKED_BY.value: PMRelationType.BLOCKS.value,
    PMRelationType.BELONGS_TO_EPIC.value: PMRelationType.EPIC_CONTAINS.value,
    PMRelationType.EPIC_CONTAINS.value: PMRelationType.BELONGS_TO_EPIC.value,
    BugRelationType.BUG_AFFECTS.value: BugRelationType.HAS_BUG.value,
    BugRelationType.HAS_BUG.value: BugRelationType.BUG_AFFECTS.value,
}


# Helper functions for relation operations
def get_all_relation_types() -> List[str]:
    """Get a list of all valid relation types."""
    return get_args(RelationType)


def get_relation_category(relation: str) -> str:
    """
    Get the category of a relation.

    Args:
        relation: The relation string

    Returns:
        The category name ("core", "project_management", etc.)

    Raises:
        ValueError: If the relation is not found in any category
    """
    for category, relations in RELATION_CATEGORIES.items():
        if relation in relations:
            return category

    raise ValueError(f"Unknown relation: {relation}")


def get_inverse_relation(relation: str) -> str:
    """
    Get the inverse relation for a given relation.

    Args:
        relation: The relation string

    Returns:
        The inverse relation if one exists, or the original relation
    """
    return INVERSE_RELATIONS.get(relation, relation)


def is_valid_relation(relation: str) -> bool:
    """
    Check if a relation is valid.

    Args:
        relation: The relation string to check

    Returns:
        True if the relation is valid, False otherwise
    """
    return relation in get_all_relation_types()


# Specific domain helper functions
def is_blocking_relation(relation: str) -> bool:
    """
    Check if a relation is a blocking relation.

    Args:
        relation: The relation string to check

    Returns:
        True if the relation is a blocking relation
    """
    return relation in (PMRelationType.BLOCKS.value, PMRelationType.IS_BLOCKED_BY.value)


def is_parent_relation(relation: str) -> bool:
    """
    Check if a relation represents a parent-child relationship.

    Args:
        relation: The relation string to check

    Returns:
        True if the relation represents a parent-child relationship
    """
    parent_relations = {
        CoreRelationType.PARENT_OF.value,
        CoreRelationType.CHILD_OF.value,
        PMRelationType.SUBTASK_OF.value,
    }
    return relation in parent_relations
