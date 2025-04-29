"""
Registry for managing metadata model types.

This module provides functions to register and retrieve metadata models
for different MemoryBlock types. Each metadata model should register
itself with this registry using the register_metadata function.

Schema Versioning Policy:
- Each block type must have an entry in SCHEMA_VERSIONS dict
- Version numbers start at 1 and increment by 1 for each breaking change
- Breaking changes include:
  * Adding required fields
  * Removing fields
  * Changing field types
  * Changing validation rules
- Non-breaking changes (no version bump needed):
  * Adding optional fields
  * Adding validation rules that don't invalidate existing data
  * Documentation changes
"""

from typing import Dict, Type, Optional, List
from pydantic import BaseModel
import logging

# Setup logger
logger = logging.getLogger(__name__)

# Registry to hold all metadata types
_metadata_registry: Dict[str, Type[BaseModel]] = {}

# Schema version registry - maps block_type to version number
SCHEMA_VERSIONS: Dict[str, int] = {
    "project": 1,
    "task": 1,
    "doc": 1,
    "knowledge": 1,
    "log": 1,
}


def get_schema_version(block_type: str) -> int:
    """
    Get the schema version for a block type.

    Args:
        block_type: The block type identifier

    Returns:
        The schema version number

    Raises:
        KeyError: If block_type is not found in SCHEMA_VERSIONS
    """
    if block_type not in SCHEMA_VERSIONS:
        raise KeyError(f"No schema version defined for block type: {block_type}")
    return SCHEMA_VERSIONS[block_type]


def register_metadata(block_type: str, model_class: Type[BaseModel]) -> None:
    """
    Register a metadata model for a block type.

    Args:
        block_type: The block type identifier (e.g., "project", "task")
        model_class: The Pydantic model class for this block type's metadata
    """
    logger.debug(f"Registering metadata model for '{block_type}': {model_class.__name__}")
    _metadata_registry[block_type] = model_class


def get_metadata_model(block_type: str) -> Optional[Type[BaseModel]]:
    """
    Get the metadata model for a block type.

    Args:
        block_type: The block type identifier

    Returns:
        The metadata model class or None if not found
    """
    model = _metadata_registry.get(block_type)
    if model is None:
        logger.warning(f"No metadata model registered for block type: {block_type}")
    return model


def get_all_metadata_models() -> Dict[str, Type[BaseModel]]:
    """
    Get all registered metadata models.

    Returns:
        Dictionary mapping block types to their metadata model classes
    """
    return _metadata_registry.copy()


def validate_metadata(block_type: str, metadata: dict) -> bool:
    """
    Validate metadata against the registered model for the given block type.

    Args:
        block_type: The block type identifier
        metadata: The metadata dictionary to validate

    Returns:
        True if validation succeeds, False otherwise
    """
    model_class = get_metadata_model(block_type)
    if model_class is None:
        return False

    try:
        model_class.model_validate(metadata)
        return True
    except Exception as e:
        logger.error(f"Metadata validation failed for {block_type}: {e}")
        return False


def get_available_node_types() -> List[str]:
    """
    Returns a list of all available node types in the memory system.

    Returns:
        List[str]: List of available node type strings (e.g., ["project", "task", "doc", "knowledge"])
    """
    return list(get_all_metadata_models().keys())
