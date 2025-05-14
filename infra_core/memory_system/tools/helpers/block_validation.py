"""
Block validation helpers for memory system tools.

This module provides utility functions for validating memory blocks,
including efficient existence checks with caching support.
"""

import uuid
from typing import Dict, Set
import logging

# Setup logging
logger = logging.getLogger(__name__)

# Simple request-scoped cache for block IDs
# This is module-level to persist across function calls in a single request
_block_id_cache: Dict[str, bool] = {}


def clear_block_cache() -> None:
    """Clear the block existence cache."""
    global _block_id_cache
    _block_id_cache = {}


def is_valid_uuid(block_id: str) -> bool:
    """
    Check if a string is a valid UUID.

    Args:
        block_id: String to validate as UUID

    Returns:
        True if valid UUID, False otherwise
    """
    try:
        uuid.UUID(block_id)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def ensure_block_exists(block_id: str, memory_bank, raise_error: bool = True) -> bool:
    """
    Verify that a block exists in the memory bank.

    Args:
        block_id: ID of the block to check
        memory_bank: Memory bank interface to use for verification
        raise_error: Whether to raise an exception if block doesn't exist

    Returns:
        True if block exists

    Raises:
        ValueError: If block_id is not a valid UUID format
        KeyError: If block with this ID doesn't exist (only when raise_error=True)
    """
    # First validate UUID format to avoid unnecessary DB calls
    if not is_valid_uuid(block_id):
        msg = f"Invalid UUID format: {block_id}"
        logger.error(msg)
        if raise_error:
            raise ValueError(msg)
        return False

    # Check cache first
    if block_id in _block_id_cache:
        exists = _block_id_cache[block_id]
        if not exists and raise_error:
            raise KeyError(f"Block does not exist: {block_id}")
        return exists

    # Check memory bank
    try:
        # Use exists_block if available (more efficient than get_block)
        if hasattr(memory_bank, "exists_block"):
            exists = memory_bank.exists_block(block_id)
        else:
            # Fall back to get_block (will fetch full block)
            block = memory_bank.get_block(block_id)
            exists = block is not None

        # Cache result
        _block_id_cache[block_id] = exists

        if not exists and raise_error:
            raise KeyError(f"Block does not exist: {block_id}")

        return exists

    except Exception as e:
        logger.error(f"Error checking block existence: {e}")
        if raise_error:
            raise KeyError(f"Error verifying block: {block_id}. {str(e)}")
        return False


def ensure_blocks_exist(
    block_ids: Set[str], memory_bank, raise_error: bool = True
) -> Dict[str, bool]:
    """
    Efficiently check existence of multiple blocks at once.

    Args:
        block_ids: Set of block IDs to verify
        memory_bank: Memory bank interface to use for verification
        raise_error: Whether to raise an exception if any block doesn't exist

    Returns:
        Dictionary mapping block IDs to existence status

    Raises:
        ValueError: If any block_id is not a valid UUID format
        KeyError: If any block doesn't exist (only when raise_error=True)
    """
    result: Dict[str, bool] = {}
    missing_blocks = []

    # First check cache and validate UUIDs
    remaining_ids = set()
    for block_id in block_ids:
        # Validate UUID format
        if not is_valid_uuid(block_id):
            msg = f"Invalid UUID format: {block_id}"
            logger.error(msg)
            if raise_error:
                raise ValueError(msg)
            result[block_id] = False
            continue

        # Check cache
        if block_id in _block_id_cache:
            result[block_id] = _block_id_cache[block_id]
            if not result[block_id]:
                missing_blocks.append(block_id)
        else:
            remaining_ids.add(block_id)

    # If there are any remaining IDs not in cache, check them
    if remaining_ids:
        try:
            # Use bulk_exists if available
            if hasattr(memory_bank, "bulk_exists_blocks"):
                exists_map = memory_bank.bulk_exists_blocks(list(remaining_ids))
                # Update results and cache
                for block_id, exists in exists_map.items():
                    result[block_id] = exists
                    _block_id_cache[block_id] = exists
                    if not exists:
                        missing_blocks.append(block_id)
            else:
                # Fall back to individual checks
                for block_id in remaining_ids:
                    exists = ensure_block_exists(block_id, memory_bank, raise_error=False)
                    result[block_id] = exists
                    if not exists:
                        missing_blocks.append(block_id)
        except Exception as e:
            logger.error(f"Error in bulk block existence check: {e}")
            if raise_error:
                raise KeyError(f"Error verifying blocks: {str(e)}")

    # Raise error if any blocks are missing
    if missing_blocks and raise_error:
        raise KeyError(f"The following blocks do not exist: {missing_blocks}")

    return result
