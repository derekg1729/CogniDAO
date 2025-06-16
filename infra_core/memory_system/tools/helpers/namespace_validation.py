"""
Namespace validation helpers for memory system tools.

This module provides utility functions for validating namespace existence,
following the established patterns from block_validation.py.
"""

import logging
from typing import Dict, Set

# Setup logging
logger = logging.getLogger(__name__)

# Default namespace that always exists (fast path)
DEFAULT_NAMESPACE = "legacy"


def clear_namespace_cache() -> None:
    """
    Clear the namespace existence cache.

    Note: Currently a no-op since we removed the process-wide cache
    to avoid ASGI request cross-pollution. Reserved for future
    per-request caching implementation.
    """
    logger.debug("Namespace cache clear requested (no-op)")


def invalidate_namespace_cache(namespace_id: str) -> None:
    """
    Invalidate a specific namespace from the cache.

    Note: Currently a no-op since we removed the process-wide cache
    to avoid ASGI request cross-pollution. Reserved for future
    per-request caching implementation.

    Args:
        namespace_id: The namespace ID to remove from cache
    """
    logger.debug(f"Namespace cache invalidation requested for: {namespace_id} (no-op)")


def validate_namespace_exists(namespace_id: str, memory_bank, raise_error: bool = True) -> bool:
    """
    Verify that a namespace exists in the memory bank.

    Args:
        namespace_id: ID of the namespace to check (case-insensitive)
        memory_bank: Memory bank interface to use for verification
        raise_error: Whether to raise an exception if namespace doesn't exist

    Returns:
        True if namespace exists

    Raises:
        ValueError: If namespace_id is invalid format
        KeyError: If namespace doesn't exist (only when raise_error=True)
    """
    # Validate namespace_id format (basic string validation)
    if not namespace_id or not isinstance(namespace_id, str):
        msg = f"Invalid namespace_id format: {namespace_id}"
        logger.error(msg)
        if raise_error:
            raise ValueError(msg)
        return False

    # Normalize namespace_id to lowercase for case-insensitive comparison
    normalized_id = namespace_id.lower().strip()

    # Fast path for default namespace - always exists
    if normalized_id == DEFAULT_NAMESPACE:
        return True

    # Check memory bank using high-level interface
    try:
        # Use namespace_exists if available (more efficient)
        if hasattr(memory_bank, "namespace_exists"):
            exists = memory_bank.namespace_exists(
                namespace_id
            )  # Pass original casing, method handles normalization
        else:
            # Fall back to direct query via dolt_reader with case-insensitive comparison
            query = "SELECT id FROM namespaces WHERE LOWER(id) = %s"
            result = memory_bank.dolt_reader._execute_query(query, (normalized_id,))
            exists = len(result) > 0

        if not exists and raise_error:
            raise KeyError(f"Namespace does not exist: {namespace_id}")

        return exists

    except Exception as e:
        logger.error(f"Error checking namespace existence: {e}")
        if raise_error:
            raise KeyError(f"Error verifying namespace: {namespace_id}. {str(e)}")
        return False


def validate_namespaces_exist(
    namespace_ids: Set[str], memory_bank, raise_error: bool = True
) -> Dict[str, bool]:
    """
    Efficiently check existence of multiple namespaces at once.

    Args:
        namespace_ids: Set of namespace IDs to verify (case-insensitive)
        memory_bank: Memory bank interface to use for verification
        raise_error: Whether to raise an exception if any namespace doesn't exist

    Returns:
        Dictionary mapping original namespace IDs to existence status

    Raises:
        ValueError: If any namespace_id is invalid format
        KeyError: If any namespace doesn't exist (only when raise_error=True)
    """
    result: Dict[str, bool] = {}
    missing_namespaces = []
    remaining_ids = set()
    normalized_to_original = {}  # Track original casing

    for namespace_id in namespace_ids:
        # Validate format
        if not namespace_id or not isinstance(namespace_id, str):
            msg = f"Invalid namespace_id format: {namespace_id}"
            logger.error(msg)
            if raise_error:
                raise ValueError(msg)
            result[namespace_id] = False
            continue

        # Normalize for comparison
        normalized_id = namespace_id.lower().strip()
        normalized_to_original[normalized_id] = namespace_id

        # Fast path for default namespace
        if normalized_id == DEFAULT_NAMESPACE:
            result[namespace_id] = True
            continue

        # All namespaces need checking since we removed the cache
        remaining_ids.add(normalized_id)

    # Check all remaining namespaces
    if remaining_ids:
        try:
            # Build bulk query for remaining namespaces with case-insensitive comparison
            placeholders = ", ".join(["%s"] * len(remaining_ids))
            query = f"SELECT LOWER(id) as normalized_id FROM namespaces WHERE LOWER(id) IN ({placeholders})"
            existing_results = memory_bank.dolt_reader._execute_query(query, tuple(remaining_ids))

            # Extract existing namespace IDs (normalized)
            existing_normalized_ids = {row["normalized_id"] for row in existing_results}

            # Update results
            for normalized_id in remaining_ids:
                original_id = normalized_to_original[normalized_id]
                exists = normalized_id in existing_normalized_ids
                result[original_id] = exists
                if not exists:
                    missing_namespaces.append(original_id)

        except Exception as e:
            logger.error(f"Error in bulk namespace existence check: {e}")
            if raise_error:
                raise KeyError(f"Error verifying namespaces: {str(e)}")

    # Raise error if any namespaces are missing
    if missing_namespaces and raise_error:
        raise KeyError(f"The following namespaces do not exist: {missing_namespaces}")

    return result


def get_available_namespaces(memory_bank) -> Dict[str, str]:
    """
    Get all available namespaces with their names.

    Args:
        memory_bank: Memory bank interface to use for querying

    Returns:
        Dictionary mapping namespace IDs to namespace names

    Raises:
        Exception: If database query fails
    """
    try:
        query = "SELECT id, name FROM namespaces ORDER BY name"
        result = memory_bank.dolt_reader._execute_query(query)

        return {row["id"]: row["name"] for row in result}

    except Exception as e:
        logger.error(f"Error retrieving available namespaces: {e}")
        raise Exception(f"Failed to retrieve namespaces: {str(e)}")
