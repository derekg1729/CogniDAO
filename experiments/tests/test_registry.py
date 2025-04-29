#!/usr/bin/env python3
"""
Test suite for registry.py functionality.

This module tests the schema versioning, metadata registration, and validation
functionality provided by the registry module.
"""

# Standard library imports
import sys
import tempfile
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

# Third-party imports
import pytest
from pydantic import BaseModel

# Add project root to path before local imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Local imports
from src.memory_system.schemas.registry import (  # noqa: E402
    SCHEMA_VERSIONS,
    get_schema_version,
    register_metadata,
    get_all_metadata_models,
    validate_metadata,
    get_available_node_types,
    _metadata_registry,
)
from src.memory_system.initialize_dolt import initialize_dolt_db, validate_schema_versions  # noqa: E402
from scripts.validate_schema_versions import get_modified_metadata_files  # noqa: E402


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


@pytest.fixture
def temp_dolt_db():
    """Create a temporary Dolt database for testing."""
    # Create temp directory
    temp_dir = tempfile.mkdtemp()
    try:
        # Initialize Dolt repository
        subprocess.run(["dolt", "init"], cwd=temp_dir, check=True)

        # Initialize Dolt database
        initialize_dolt_db(temp_dir)
        yield temp_dir
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)


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


def test_metadata_model_registration():
    """Test metadata model registration and retrieval."""
    # Register a test model
    register_metadata("test_type", MockMetadataModel)

    # Verify registration
    models = get_all_metadata_models()
    assert "test_type" in models
    assert models["test_type"] == MockMetadataModel


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


def test_node_schemas_table_creation(temp_dolt_db):
    """Test that node_schemas table is created during initialization."""
    # Check if node_schemas table exists
    result = subprocess.run(
        ["dolt", "sql", "-q", 'SHOW TABLES LIKE "node_schemas"'],
        cwd=temp_dolt_db,
        capture_output=True,
        text=True,
    )
    assert "node_schemas" in result.stdout

    # Check table structure
    result = subprocess.run(
        ["dolt", "sql", "-q", "DESCRIBE node_schemas"],
        cwd=temp_dolt_db,
        capture_output=True,
        text=True,
    )
    output = result.stdout.lower()
    assert "node_type" in output
    assert "schema_version" in output
    assert "json_schema" in output
    assert "created_at" in output


def test_schema_version_validation(temp_dolt_db):
    """Test that schema version validation works correctly."""
    # Test with a clean database (should pass)
    assert validate_schema_versions(temp_dolt_db)

    # Add a schema with a mismatched version
    subprocess.run(
        [
            "dolt",
            "sql",
            "-q",
            """INSERT INTO node_schemas (node_type, schema_version, json_schema, created_at)
               VALUES ('memory_block', 999, '{"type": "object"}', CURRENT_TIMESTAMP())""",
        ],
        cwd=str(temp_dolt_db),
        check=True,
    )

    # Validation should fail due to version mismatch
    assert not validate_schema_versions(temp_dolt_db)


def test_schema_version_missing_type(temp_dolt_db):
    """Test validation when a registered type is missing from SCHEMA_VERSIONS."""
    # Store original SCHEMA_VERSIONS and registry state
    original_versions = SCHEMA_VERSIONS.copy()
    original_registry = _metadata_registry.copy()

    try:
        # Clear both registries to start fresh
        SCHEMA_VERSIONS.clear()
        _metadata_registry.clear()

        # Add a test model to the registry
        register_metadata("test_missing_type", MockMetadataModel)

        # Verify the model is registered
        registered_models = get_all_metadata_models()
        assert "test_missing_type" in registered_models

        # Add an unrelated type to SCHEMA_VERSIONS
        SCHEMA_VERSIONS.update({"other_type": 1})

        # Mock get_all_metadata_models to return only our test model
        with patch("src.memory_system.initialize_dolt.get_all_metadata_models") as mock_get_models:
            mock_get_models.return_value = {"test_missing_type": MockMetadataModel}

            # Validation should fail because test_missing_type is not in SCHEMA_VERSIONS
            result = validate_schema_versions(temp_dolt_db)
            assert not result, (
                "Validation should fail when a registered type is missing from SCHEMA_VERSIONS"
            )
    finally:
        # Restore original state
        SCHEMA_VERSIONS.clear()
        SCHEMA_VERSIONS.update(original_versions)
        _metadata_registry.clear()
        _metadata_registry.update(original_registry)


def test_future_path_structure_does_not_trigger_hook():
    """Ensure that files outside expected path do not trigger validation (and warn us)."""
    with patch("subprocess.run") as mock_run:
        # Simulate a new future path structure
        mock_run.return_value.stdout = """
infra_core/src/memory_system/schemas/metadata/task.py
"""

        result = get_modified_metadata_files()

        # Should be empty since it doesn't match hardcoded "experiments/..."
        assert result == [], (
            "Future path structure was incorrectly matched. This test will fail when code is moved to infra_core, reminding us to update file paths."
        )
