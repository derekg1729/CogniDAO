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
from pydantic import BaseModel, ValidationError
import logging

# Setup logger
logger = logging.getLogger(__name__)

# Registry to hold all metadata types
_metadata_registry: Dict[str, Type[BaseModel]] = {}

# Schema version registry - maps block_type to version number
SCHEMA_VERSIONS: Dict[str, int] = {
    "base": 2,
    "base_user": 1,
    "project": 5,
    "task": 5,
    "doc": 4,
    "knowledge": 3,
    "log": 4,
    "epic": 3,
    "bug": 3,
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


def validate_metadata(block_type: str, metadata: dict) -> Optional[str]:
    """
    Validate metadata against the registered model for the given block type.

    Args:
        block_type: The block type identifier
        metadata: The metadata dictionary to validate

    Returns:
        None if validation succeeds, otherwise a string containing the validation error details.
    """
    model_class = get_metadata_model(block_type)
    if model_class is None:
        # If no specific metadata model is registered, consider it valid (empty metadata is always okay)
        # If metadata is provided for a type with no model, that's an issue handled elsewhere potentially,
        # or we assume any dict is okay if no stricter schema exists.
        # Let's assume it's valid if no model exists to validate against.
        # Alternative: return f"No metadata model registered for type: {block_type}" if metadata else None
        if metadata:  # Only return error if metadata was provided but no model exists
            logger.warning(
                f"Metadata provided for type '{block_type}' but no metadata model is registered."
            )
            # We could return an error string here, but for now, let's allow it.
        return None  # Consider valid if no model registered or if metadata is empty

    try:
        model_class.model_validate(metadata)
        return None  # Success
    except ValidationError as e:
        error_details = str(e)
        logger.error(f"Metadata validation failed for {block_type}: {error_details}")
        return f"Metadata validation failed for type '{block_type}': {error_details}"
    except Exception as e:
        # Catch other potential errors during validation
        logger.error(f"Unexpected error during metadata validation for {block_type}: {e}")
        return f"Unexpected error during metadata validation for type '{block_type}': {e}"


def get_available_node_types() -> List[str]:
    """
    Returns a list of all available node types in the memory system.

    Returns:
        List[str]: List of available node type strings (e.g., ["project", "task", "doc", "knowledge"])
    """
    return list(get_all_metadata_models().keys())


def resolve_schema_model_and_version(
    block_type: str, version_str: str
) -> tuple[Type[BaseModel], int]:
    """
    Resolves the block type and version string to a Pydantic model class and integer version.

    Args:
        block_type: The block type identifier.
        version_str: The version identifier ('latest' or an integer string).

    Returns:
        A tuple containing the resolved Pydantic model class and the integer schema version.

    Raises:
        KeyError: If the block_type is unknown.
        ValueError: If the version_str is invalid or doesn't match the known latest version.
        TypeError: If no model is registered for the block_type.
    """
    # 1. Validate block_type
    if block_type not in SCHEMA_VERSIONS:
        raise KeyError(f"Unknown block type: {block_type}")

    latest_version = get_schema_version(block_type)

    # 2. Resolve version string
    resolved_version: int
    if version_str == "latest":
        resolved_version = latest_version
    else:
        try:
            resolved_version = int(version_str)
        except ValueError:
            raise ValueError("Version must be an integer string or 'latest'")

        # Currently, we only support retrieving the latest version explicitly by number
        if resolved_version != latest_version:
            # In the future, this could check against a list/dict of historical versions
            raise ValueError(
                f"Version {resolved_version} not found for type {block_type}. Only latest ({latest_version}) is currently supported."
            )

    # 3. Get the model
    model = get_metadata_model(block_type)
    if model is None:
        # This case implies an internal inconsistency (version defined but no model registered)
        raise TypeError(f"No schema model registered for block type: {block_type}")

    return model, resolved_version


# Test comment AGAIN to trigger pre-commit hook
