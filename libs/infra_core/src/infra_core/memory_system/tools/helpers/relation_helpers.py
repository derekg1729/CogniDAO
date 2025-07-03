"""
Relation helpers for memory system tools.

This module provides utility functions for working with relation types,
including alias resolution, inverse lookup, and validation.
"""

from typing import Dict, Optional
import logging

from infra_core.memory_system.relation_registry import (
    RELATION_ALIASES,
    INVERSE_RELATIONS,
    get_all_relation_types,
    is_valid_relation,
    get_inverse_relation,
)

# Setup logging
logger = logging.getLogger(__name__)

# Keep a lowercase normalized version of relation names for friendly matching
_normalized_relations: Dict[str, str] = {}

# Populate normalized relations at module load time
for relation in get_all_relation_types():
    _normalized_relations[relation.lower()] = relation
    # Add underscore version (e.g. "belongs to" -> "belongs_to")
    _normalized_relations[relation.lower().replace("_", " ")] = relation

# Add human readable versions with spaces
_normalized_relations["is blocked by"] = "is_blocked_by"
_normalized_relations["depends on"] = "depends_on"
_normalized_relations["blocks"] = "blocks"
_normalized_relations["related to"] = "related_to"
_normalized_relations["child of"] = "child_of"
_normalized_relations["parent of"] = "parent_of"
_normalized_relations["subtask of"] = "subtask_of"
_normalized_relations["belongs to epic"] = "belongs_to_epic"


def resolve_relation_alias(relation: str) -> str:
    """
    Resolve a relation name to its canonical form.

    Args:
        relation: Relation name or alias to resolve

    Returns:
        Canonical relation name from RelationType

    Raises:
        ValueError: If relation cannot be resolved to a valid relation type
    """
    # First check if it's already a valid relation
    if is_valid_relation(relation):
        return relation

    # Check RELATION_ALIASES for direct mapping
    if relation in RELATION_ALIASES:
        return RELATION_ALIASES[relation]

    # Try normalized versions
    normalized = relation.lower()
    if normalized in _normalized_relations:
        return _normalized_relations[normalized]

    # If we get here, we couldn't resolve the relation
    valid_relations = list(get_all_relation_types())
    human_readable = [r.replace("_", " ") for r in valid_relations]
    alias_options = list(RELATION_ALIASES.keys())

    raise ValueError(
        f"Invalid relation type: '{relation}'. "
        f"Must be one of the canonical types: {valid_relations}, "
        f"human readable forms: {human_readable}, "
        f"or aliases: {alias_options}"
    )


def get_relation_inverse(relation: str) -> Optional[str]:
    """
    Get the inverse relation for a given relation.

    Args:
        relation: Relation name to find inverse for

    Returns:
        Inverse relation name or None if no inverse exists

    Raises:
        ValueError: If relation is not a valid relation type
    """
    # Resolve any alias to canonical form
    canonical_relation = resolve_relation_alias(relation)

    # Use registry function to get inverse
    try:
        return get_inverse_relation(canonical_relation)
    except ValueError as e:
        # Re-raise with more context
        raise ValueError(f"Cannot find inverse for relation '{relation}': {str(e)}")


def validate_bidirectional_relation(relation: str) -> bool:
    """
    Validate that a relation has a defined inverse and can be used bidirectionally.

    Args:
        relation: Relation name to validate

    Returns:
        True if relation has a defined inverse in INVERSE_RELATIONS

    Raises:
        ValueError: If relation cannot be used bidirectionally
    """
    # Resolve any alias
    canonical_relation = resolve_relation_alias(relation)

    # Check if it has an inverse
    if canonical_relation not in INVERSE_RELATIONS:
        raise ValueError(
            f"Relation '{relation}' cannot be used bidirectionally "
            f"as it has no defined inverse in INVERSE_RELATIONS"
        )

    return True


def get_human_readable_name(relation: str) -> str:
    """
    Get a human-readable version of a relation name.

    Args:
        relation: Canonical relation name

    Returns:
        Human-readable version (spaces instead of underscores)
    """
    # Resolve any alias first
    canonical = resolve_relation_alias(relation)

    # Convert to human readable format
    return canonical.replace("_", " ")
