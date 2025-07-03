import pytest
from pydantic import BaseModel
from infra_core.memory_system.schemas.registry import (
    resolve_schema_model_and_version,
    register_metadata,  # Needed for testing the TypeError case
    _metadata_registry,  # Need access for cleanup
    SCHEMA_VERSIONS,  # Need access for setup
)


# Define dummy models for testing
class TaskMetaV2(BaseModel):
    name: str


class ProjectMetaV2(BaseModel):
    title: str


@pytest.fixture(autouse=True)
def manage_registry():
    """Fixture to ensure registry is clean before each test and restored after."""
    original_registry = _metadata_registry.copy()
    original_versions = SCHEMA_VERSIONS.copy()

    # Clear before test
    _metadata_registry.clear()
    SCHEMA_VERSIONS.clear()

    # Setup for tests - ensure at least one type is registered
    SCHEMA_VERSIONS["task"] = 2
    register_metadata("task", TaskMetaV2)
    SCHEMA_VERSIONS["project"] = 2  # Type exists, but no model registered initially for one test

    yield  # Run the test

    # Restore after test
    _metadata_registry.clear()
    _metadata_registry.update(original_registry)
    SCHEMA_VERSIONS.clear()
    SCHEMA_VERSIONS.update(original_versions)


def test_resolve_success_latest():
    "Test successful resolution with 'latest' version string."
    model, version = resolve_schema_model_and_version("task", "latest")
    assert model is TaskMetaV2
    assert version == 2


def test_resolve_success_specific_version():
    "Test successful resolution with correct integer version string."
    model, version = resolve_schema_model_and_version("task", "2")
    assert model is TaskMetaV2
    assert version == 2


def test_resolve_fail_unknown_type():
    "Test failure with an unknown block type."
    with pytest.raises(KeyError, match="Unknown block type: unknown"):
        resolve_schema_model_and_version("unknown", "latest")


def test_resolve_fail_invalid_version_string():
    "Test failure with a non-integer, non-'latest' version string."
    with pytest.raises(ValueError, match="Version must be an integer string or 'latest'"):
        resolve_schema_model_and_version("task", "abc")


def test_resolve_fail_mismatched_version_number():
    "Test failure with an integer version that doesn't match the latest."
    with pytest.raises(
        ValueError,
        match=r"Version 1 not found for type task. Only latest \(2\) is currently supported.",
    ):
        resolve_schema_model_and_version("task", "1")


def test_resolve_fail_no_model_registered():
    "Test failure when version exists but no model is registered (internal inconsistency)."
    # 'project' has version 2 in SCHEMA_VERSIONS but no model registered in fixture setup
    with pytest.raises(TypeError, match="No schema model registered for block type: project"):
        resolve_schema_model_and_version("project", "latest")

    with pytest.raises(TypeError, match="No schema model registered for block type: project"):
        resolve_schema_model_and_version("project", "2")
