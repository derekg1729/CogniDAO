"""
Test suite for registry.py functionality.

This module tests the schema versioning, metadata registration, and validation
functionality provided by the registry module.
"""

import pytest
from pydantic import BaseModel
from src.memory_system.schemas.registry import (
    SCHEMA_VERSIONS,
    get_schema_version,
    register_metadata,
    get_metadata_model,
    get_all_metadata_models,
    validate_metadata,
    get_available_node_types,
    _metadata_registry,
)


class MockMetadataModel(BaseModel):
    """Mock metadata model for testing."""

    field1: str
    field2: int


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset the registry state before each test."""
    # Store original registry state
    original_registry = _metadata_registry.copy()
    # Clear registry
    _metadata_registry.clear()
    # Run test
    yield
    # Restore original registry state
    _metadata_registry.clear()
    _metadata_registry.update(original_registry)


def test_schema_versions_initialization():
    """Test that SCHEMA_VERSIONS is properly initialized with all required block types."""
    required_types = ["project", "task", "doc", "knowledge"]
    for block_type in required_types:
        assert block_type in SCHEMA_VERSIONS
        assert isinstance(SCHEMA_VERSIONS[block_type], int)
        assert SCHEMA_VERSIONS[block_type] >= 1


def test_get_schema_version():
    """Test schema version retrieval for valid and invalid block types."""
    # Test valid block types
    assert get_schema_version("project") == 1
    assert get_schema_version("task") == 1

    # Test invalid block type
    with pytest.raises(KeyError):
        get_schema_version("invalid_type")


def test_metadata_registration():
    """Test metadata model registration and retrieval."""
    # Register a test model
    register_metadata("test_type", MockMetadataModel)

    # Verify registration
    retrieved_model = get_metadata_model("test_type")
    assert retrieved_model == MockMetadataModel

    # Verify unregistered type returns None
    assert get_metadata_model("unregistered_type") is None


def test_get_all_metadata_models():
    """Test retrieval of all registered metadata models."""
    # Get initial models (should be empty due to fixture)
    initial_models = get_all_metadata_models()
    assert len(initial_models) == 0

    # Register a test model
    register_metadata("test_type", MockMetadataModel)

    # Verify new model is included
    all_models = get_all_metadata_models()
    assert "test_type" in all_models
    assert all_models["test_type"] == MockMetadataModel
    assert len(all_models) == 1


def test_validate_metadata():
    """Test metadata validation against registered models."""
    # Register test model
    register_metadata("test_type", MockMetadataModel)

    # Test valid metadata
    valid_metadata = {"field1": "test", "field2": 42}
    assert validate_metadata("test_type", valid_metadata) is True

    # Test invalid metadata
    invalid_metadata = {"field1": "test"}  # Missing required field2
    assert validate_metadata("test_type", invalid_metadata) is False

    # Test validation for unregistered type
    assert validate_metadata("unregistered_type", {}) is False


def test_get_available_node_types():
    """Test retrieval of available node types."""
    # Register a test model
    register_metadata("test_type", MockMetadataModel)

    # Get available types
    types = get_available_node_types()

    # Verify test type is included
    assert "test_type" in types
    # Verify all types are strings
    assert all(isinstance(t, str) for t in types)
