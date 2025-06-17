"""
Tests for the UpdateMemoryBlockModels.

This module tests the Pydantic models and validation logic for:
- UpdateMemoryBlockInput validation
- UpdateMemoryBlockOutput structure
- Error code enums
- Patch type validation
- Custom validators for patch format consistency
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from infra_core.memory_system.tools.memory_core.update_memory_block_models import (
    UpdateMemoryBlockInput,
    UpdateMemoryBlockOutput,
    UpdateErrorCode,
    PatchType,
    DiffSummary,
)
from infra_core.memory_system.schemas.memory_block import ConfidenceScore
from infra_core.memory_system.schemas.common import BlockLink


# Test UpdateMemoryBlockInput validation


def test_update_memory_block_input_minimal_valid():
    """Test minimal valid input with only required fields."""
    input_data = UpdateMemoryBlockInput(block_id="test-block-123")

    assert input_data.block_id == "test-block-123"
    assert input_data.previous_block_version is None
    assert input_data.text is None
    assert input_data.merge_metadata is True  # Default
    assert input_data.merge_tags is True  # Default


def test_update_memory_block_input_full_valid():
    """Test fully populated valid input."""
    links = [BlockLink(from_id="source-block", to_id="target-1", relation="depends_on")]
    confidence = ConfidenceScore()

    input_data = UpdateMemoryBlockInput(
        block_id="test-block-123",
        previous_block_version=5,
        text="Updated content",
        state="published",
        visibility="public",
        tags=["tag1", "tag2"],
        metadata={"title": "Updated Title"},
        source_file="updated.md",
        confidence=confidence,
        links=links,
        merge_metadata=False,
        merge_tags=False,
        author="test_user",
        agent_id="test_agent",
        session_id="session-123",
        change_note="Full update test",
    )

    assert input_data.block_id == "test-block-123"
    assert input_data.previous_block_version == 5
    assert input_data.text == "Updated content"
    assert input_data.state == "published"
    assert input_data.visibility == "public"
    assert input_data.tags == ["tag1", "tag2"]
    assert input_data.metadata == {"title": "Updated Title"}
    assert input_data.merge_metadata is False
    assert input_data.merge_tags is False


def test_update_memory_block_input_text_patch_valid():
    """Test valid text patch input."""
    input_data = UpdateMemoryBlockInput(
        block_id="test-block-123",
        text_patch="@@ -1,1 +1,1 @@\n-Old line\n+New line",
        patch_type=PatchType.UNIFIED_DIFF,
    )

    assert input_data.text_patch is not None
    assert input_data.patch_type == PatchType.UNIFIED_DIFF


def test_update_memory_block_input_json_patch_string_valid():
    """Test valid JSON patch with string input."""
    patch_str = '[{"op": "replace", "path": "/title", "value": "New Title"}]'

    input_data = UpdateMemoryBlockInput(
        block_id="test-block-123",
        structured_patch=patch_str,
        patch_type=PatchType.JSON_PATCH,
    )

    assert input_data.structured_patch == patch_str
    assert input_data.patch_type == PatchType.JSON_PATCH


def test_update_memory_block_input_json_patch_list_valid():
    """Test valid JSON patch with list input."""
    patch_ops = [{"op": "replace", "path": "/title", "value": "New Title"}]

    input_data = UpdateMemoryBlockInput(
        block_id="test-block-123",
        structured_patch=patch_ops,
        patch_type=PatchType.JSON_PATCH,
    )

    assert input_data.structured_patch == patch_ops
    assert input_data.patch_type == PatchType.JSON_PATCH


def test_update_memory_block_input_invalid_state():
    """Test validation error for invalid state value."""
    with pytest.raises(ValidationError) as exc_info:
        UpdateMemoryBlockInput(block_id="test-block-123", block_version=5, state="invalid_state")

    assert "input should be" in str(exc_info.value).lower()


def test_update_memory_block_input_invalid_visibility():
    """Test validation error for invalid visibility value."""
    with pytest.raises(ValidationError) as exc_info:
        UpdateMemoryBlockInput(
            block_id="test-block-123", block_version=5, visibility="invalid_visibility"
        )

    assert "input should be" in str(exc_info.value).lower()


def test_update_memory_block_input_too_many_tags():
    """Test validation error for too many tags."""
    tags = [f"tag_{i}" for i in range(25)]  # Exceeds 20 tag limit

    with pytest.raises(ValidationError) as exc_info:
        UpdateMemoryBlockInput(
            block_id="test-block-123",
            tags=tags,
        )

    assert "List should have at most 20 items" in str(exc_info.value)


# Test patch type validation


@pytest.mark.xfail(reason="Validation logic moved to core processing, not input validation")
def test_update_memory_block_input_patch_type_required_with_text_patch():
    """Test validation error when text patch provided without patch_type."""
    with pytest.raises(ValidationError) as exc_info:
        UpdateMemoryBlockInput(
            block_id="test-block-123",
            text_patch="@@  -1,1 +1,1 @@\n-old line\n+new line",
            # No patch_type specified
        )

    assert "patch_type required when patches provided" in str(exc_info.value)


@pytest.mark.xfail(reason="Validation logic moved to core processing, not input validation")
def test_update_memory_block_input_patch_type_required_with_structured_patch():
    """Test validation error when structured patch provided without patch_type."""
    patch_ops = [{"op": "replace", "path": "/metadata/title", "value": "New Title"}]

    with pytest.raises(ValidationError) as exc_info:
        UpdateMemoryBlockInput(
            block_id="test-block-123",
            structured_patch=patch_ops,
            # No patch_type specified
        )

    assert "patch_type required when patches provided" in str(exc_info.value)


def test_update_memory_block_input_patch_type_without_patches():
    """Test that patch_type without patches raises error."""
    with pytest.raises(ValidationError) as exc_info:
        UpdateMemoryBlockInput(
            block_id="test-block-123",
            patch_type=PatchType.UNIFIED_DIFF,
            # No patches provided
        )

    assert "patch_type specified but no patches provided" in str(exc_info.value)


# Test structured patch validation


@pytest.mark.xfail(reason="JSON validation happens in core processing, not input validation")
def test_update_memory_block_input_json_patch_invalid_json_string():
    """Test validation error for invalid JSON string in structured_patch."""
    with pytest.raises(ValidationError) as exc_info:
        UpdateMemoryBlockInput(
            block_id="test-block-123",
            structured_patch="invalid json string",
            patch_type=PatchType.JSON_PATCH,
        )

    assert "Invalid JSON" in str(exc_info.value)


@pytest.mark.xfail(reason="JSON validation happens in core processing, not input validation")
def test_update_memory_block_input_json_patch_not_list():
    """Test validation error when JSON patch is not a list."""
    with pytest.raises(ValidationError) as exc_info:
        UpdateMemoryBlockInput(
            block_id="test-block-123",
            structured_patch='{"not": "a list"}',
            patch_type=PatchType.JSON_PATCH,
        )

    assert "must be a list" in str(exc_info.value)


@pytest.mark.xfail(reason="JSON patch operation validation happens in core processing")
def test_update_memory_block_input_json_patch_invalid_operation():
    """Test validation error for invalid JSON patch operation."""
    invalid_patch = [{"invalid_op": "test"}]  # Missing required 'op' field

    with pytest.raises(ValidationError) as exc_info:
        UpdateMemoryBlockInput(
            block_id="test-block-123",
            structured_patch=invalid_patch,
            patch_type=PatchType.JSON_PATCH,
        )

    assert "Invalid JSON patch operation" in str(exc_info.value)


def test_update_memory_block_input_json_patch_invalid_type():
    """Test validation error when structured_patch is not string or list."""
    with pytest.raises(ValidationError) as exc_info:
        UpdateMemoryBlockInput(
            block_id="test-block-123",
            structured_patch=123,  # Invalid type
            patch_type=PatchType.JSON_PATCH,
        )

    # Pydantic v2 gives type validation errors, not our custom message
    assert "Input should be a valid" in str(exc_info.value)


# Test UpdateMemoryBlockOutput


def test_update_memory_block_output_success():
    """Test successful UpdateMemoryBlockOutput."""
    diff_summary = DiffSummary(
        fields_updated=["text", "metadata"],
        text_changed=True,
        metadata_changed=True,
        tags_changed=False,
        links_changed=False,
    )

    output = UpdateMemoryBlockOutput(
        success=True,
        id="test-block-123",
        active_branch="main",
        timestamp=datetime.now(),
        diff_summary=diff_summary,
        previous_version=5,
        new_version=6,
        processing_time_ms=123.45,
    )

    assert output.success is True
    assert output.id == "test-block-123"
    assert output.error is None
    assert output.error_code is None
    assert output.diff_summary == diff_summary
    assert output.previous_version == 5
    assert output.new_version == 6
    assert output.processing_time_ms == 123.45


def test_update_memory_block_output_error():
    """Test error UpdateMemoryBlockOutput."""
    timestamp = datetime.now()

    output = UpdateMemoryBlockOutput(
        success=False,
        active_branch="main",
        error="Block not found",
        error_code=UpdateErrorCode.BLOCK_NOT_FOUND,
        timestamp=timestamp,
        previous_version=5,
        processing_time_ms=15.0,
    )

    assert output.success is False
    assert output.id is None
    assert output.error == "Block not found"
    assert output.error_code == UpdateErrorCode.BLOCK_NOT_FOUND
    assert output.timestamp == timestamp
    assert output.diff_summary is None
    assert output.previous_version == 5
    assert output.new_version is None


# Test DiffSummary


def test_diff_summary_basic():
    """Test basic DiffSummary creation."""
    diff_summary = DiffSummary(
        fields_updated=["text", "tags"],
        text_changed=True,
        metadata_changed=False,
        tags_changed=True,
        links_changed=False,
    )

    assert diff_summary.fields_updated == ["text", "tags"]
    assert diff_summary.text_changed is True
    assert diff_summary.metadata_changed is False
    assert diff_summary.tags_changed is True
    assert diff_summary.links_changed is False
    assert diff_summary.patch_stats is None


def test_diff_summary_with_patch_stats():
    """Test DiffSummary with patch statistics."""
    patch_stats = {
        "text_patch_applied": True,
        "structured_patch_applied": True,
        "affected_fields": ["metadata", "tags"],
    }

    diff_summary = DiffSummary(
        fields_updated=["text", "metadata", "tags"],
        text_changed=True,
        metadata_changed=True,
        tags_changed=True,
        links_changed=False,
        patch_stats=patch_stats,
    )

    assert diff_summary.patch_stats == patch_stats


# Test Error Codes


def test_update_error_codes_enum():
    """Test that all error codes are properly defined."""
    # Test enum values
    assert UpdateErrorCode.BLOCK_NOT_FOUND == "BLOCK_NOT_FOUND"
    assert UpdateErrorCode.VERSION_CONFLICT == "VERSION_CONFLICT"
    assert UpdateErrorCode.VALIDATION_ERROR == "VALIDATION_ERROR"
    assert UpdateErrorCode.PATCH_PARSE_ERROR == "PATCH_PARSE_ERROR"
    assert UpdateErrorCode.PATCH_APPLY_ERROR == "PATCH_APPLY_ERROR"
    assert UpdateErrorCode.PATCH_SIZE_LIMIT_ERROR == "PATCH_SIZE_LIMIT_ERROR"
    assert UpdateErrorCode.LINK_VALIDATION_ERROR == "LINK_VALIDATION_ERROR"
    assert UpdateErrorCode.PERSISTENCE_FAILURE == "PERSISTENCE_FAILURE"
    assert UpdateErrorCode.RE_INDEX_FAILURE == "RE_INDEX_FAILURE"
    assert UpdateErrorCode.UNKNOWN_ERROR == "UNKNOWN_ERROR"

    # Test that we have all expected error codes
    expected_codes = {
        "BLOCK_NOT_FOUND",
        "VERSION_CONFLICT",
        "VALIDATION_ERROR",
        "PATCH_PARSE_ERROR",
        "PATCH_APPLY_ERROR",
        "PATCH_SIZE_LIMIT_ERROR",
        "LINK_VALIDATION_ERROR",
        "PERSISTENCE_FAILURE",
        "RE_INDEX_FAILURE",
        "UNKNOWN_ERROR",
    }
    actual_codes = {code.value for code in UpdateErrorCode}
    assert actual_codes == expected_codes


# Test PatchType enum


def test_patch_type_enum():
    """Test that patch types are properly defined."""
    assert PatchType.UNIFIED_DIFF == "unified_diff"
    assert PatchType.JSON_PATCH == "json_patch"

    # Test that we have expected patch types
    expected_types = {"unified_diff", "json_patch"}
    actual_types = {patch_type.value for patch_type in PatchType}
    assert actual_types == expected_types


# Test edge cases and complex validation scenarios


def test_update_memory_block_input_both_patches():
    """Test input with both text and structured patches."""
    input_data = UpdateMemoryBlockInput(
        block_id="test-block-123",
        text_patch="@@ -1,1 +1,1 @@\n-Old\n+New",
        structured_patch='[{"op": "replace", "path": "/title", "value": "New"}]',
        patch_type=PatchType.JSON_PATCH,
    )

    # Should be valid to have both types
    assert input_data.text_patch is not None
    assert input_data.structured_patch is not None
    assert input_data.patch_type == PatchType.JSON_PATCH


def test_update_memory_block_input_empty_strings():
    """Test validation with empty strings."""
    input_data = UpdateMemoryBlockInput(
        block_id="test-block-123",
        text="",  # Empty string should be valid
        author="",  # Empty string should be valid
        change_note="",  # Empty string should be valid
    )

    assert input_data.text == ""
    assert input_data.author == ""
    assert input_data.change_note == ""


def test_update_memory_block_input_zero_version():
    """Test input with version 0."""
    input_data = UpdateMemoryBlockInput(
        block_id="test-block-123",
        previous_block_version=0,  # Should be valid
    )

    assert input_data.previous_block_version == 0
