"""
Relation Registry for Memory Blocks Link System.

This module provides a centralized registry of all relation types that can be
used for links between memory blocks, organized by domain categories.
"""

from enum import Enum
from typing import List, Literal, Union


# Core relation types for general usage across all block types
class CoreRelationType(str, Enum):
    """Core relation types applicable to all memory blocks."""

    RELATED_TO = "related_to"
    MENTIONS = "mentions"
    CHILD_OF = "child_of"
    PARENT_OF = "parent_of"
    DUPLICATE_OF = "duplicate_of"  # Self-inverse relation
    PART_OF = "part_of"
    CONTAINS = "contains"
    REQUIRES = "requires"
    PROVIDES = "provides"
    OWNED_BY = "owned_by"
    OWNS = "owns"


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
    SOURCE_OF = "source_of"
    CITED_BY = "cited_by"


# Collect all relation values into a flat list
_all_relation_values = [
    e.value
    for e in list(CoreRelationType)
    + list(PMRelationType)
    + list(BugRelationType)
    + list(KnowledgeRelationType)
]

# Dynamically generate the RelationType Literal type from all enum values
# This ensures we don't have duplication between enums and the Literal
RelationType = Union[Literal[tuple(_all_relation_values)]]  # type: ignore

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
    # Core relations
    CoreRelationType.CHILD_OF.value: CoreRelationType.PARENT_OF.value,
    CoreRelationType.PARENT_OF.value: CoreRelationType.CHILD_OF.value,
    CoreRelationType.DUPLICATE_OF.value: CoreRelationType.DUPLICATE_OF.value,  # Self-inverse
    CoreRelationType.PART_OF.value: CoreRelationType.CONTAINS.value,
    CoreRelationType.CONTAINS.value: CoreRelationType.PART_OF.value,
    CoreRelationType.REQUIRES.value: CoreRelationType.PROVIDES.value,
    CoreRelationType.PROVIDES.value: CoreRelationType.REQUIRES.value,
    CoreRelationType.OWNED_BY.value: CoreRelationType.OWNS.value,
    CoreRelationType.OWNS.value: CoreRelationType.OWNED_BY.value,
    # Project management relations
    PMRelationType.BLOCKS.value: PMRelationType.IS_BLOCKED_BY.value,
    PMRelationType.IS_BLOCKED_BY.value: PMRelationType.BLOCKS.value,
    PMRelationType.BELONGS_TO_EPIC.value: PMRelationType.EPIC_CONTAINS.value,
    PMRelationType.EPIC_CONTAINS.value: PMRelationType.BELONGS_TO_EPIC.value,
    # Bug tracking relations
    BugRelationType.BUG_AFFECTS.value: BugRelationType.HAS_BUG.value,
    BugRelationType.HAS_BUG.value: BugRelationType.BUG_AFFECTS.value,
    # Knowledge relations
    KnowledgeRelationType.SOURCE_OF.value: KnowledgeRelationType.CITED_BY.value,
    KnowledgeRelationType.CITED_BY.value: KnowledgeRelationType.SOURCE_OF.value,
}


# Helper function to check if a relation is valid
def is_valid_relation(relation: str) -> bool:
    """
    Check if a relation is valid.

    Args:
        relation: The relation string to check

    Returns:
        True if the relation is valid, False otherwise
    """
    return relation in _all_relation_values


# Validation: Check for duplicate relation values across all categories
_all_values = set()
for enum_class in [CoreRelationType, PMRelationType, BugRelationType, KnowledgeRelationType]:
    for member in enum_class:
        if member.value in _all_values:
            raise ValueError(f"Duplicate relation value: {member.value}")
        _all_values.add(member.value)

# Validation: Ensure each inverse relation maps back correctly (symmetry check)
for relation, inverse in INVERSE_RELATIONS.items():
    if inverse not in INVERSE_RELATIONS:
        raise ValueError(
            f"Inverse relation '{inverse}' for '{relation}' is not defined in INVERSE_RELATIONS"
        )
    if INVERSE_RELATIONS[inverse] != relation:
        raise ValueError(
            f"Asymmetric inverse relation: {relation} -> {inverse} but {inverse} -> {INVERSE_RELATIONS[inverse]}"
        )

# Validation: Check that all relations have inverses defined if they should
for relation in _all_relation_values:
    if relation not in INVERSE_RELATIONS:
        # For relations without explicit inverses, they might be self-inverses
        # or relations that don't have an inverse by design
        pass


# Helper functions for relation operations
def get_all_relation_types() -> List[str]:
    """Get a list of all valid relation types."""
    return _all_relation_values


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
        The inverse relation

    Raises:
        ValueError: If the relation is not a valid relation type
    """
    if not is_valid_relation(relation):
        raise ValueError(f"Invalid relation: {relation}")

    return INVERSE_RELATIONS.get(relation, relation)


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


# Reference to canonical dependency relation
CANONICAL_DEPENDENCY_RELATION = PMRelationType.IS_BLOCKED_BY.value

# Alias map for relations that have semantic equivalents in different domains
RELATION_ALIASES = {
    # Dependency aliases
    PMRelationType.DEPENDS_ON.value: CANONICAL_DEPENDENCY_RELATION,
    # Hierarchy aliases
    PMRelationType.SUBTASK_OF.value: CoreRelationType.CHILD_OF.value,
}
