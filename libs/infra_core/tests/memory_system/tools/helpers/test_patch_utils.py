"""
Tests for the patch utilities module.

This module tests all aspects of patch application including:
- Text patch application using unidiff library
- JSON patch application using jsonpatch library
- Performance limits and size validation
- Error handling for malformed patches and missing libraries
"""

import pytest
import json
from unittest.mock import patch, MagicMock

from infra_core.memory_system.tools.helpers.patch_utils import (
    apply_text_patch_safe,
    apply_json_patch_safe,
    validate_patch_size,
    validate_json_patch_size,
    PatchError,
    PatchSizeError,
    PatchLibraryMissing,
    MAX_TEXT_PATCH_LINES,
    MAX_STRUCTURED_PATCH_OPS,
)


# Test text patch functionality


@patch("infra_core.memory_system.tools.helpers.patch_utils.PatchSet")
def test_apply_text_patch_safe_success(mock_patch_set_class):
    """Test successful text patch application."""
    # Mock the unidiff PatchSet and its behavior
    mock_patch_set = MagicMock()
    mock_patch_set_class.return_value = mock_patch_set
    mock_patch_set.__len__ = MagicMock(return_value=1)
    mock_patch_set.__getitem__ = MagicMock()

    # Mock a single patched file with hunks
    mock_patched_file = MagicMock()
    mock_patch_set.__getitem__.return_value = mock_patched_file

    # Mock hunk with simple line changes
    mock_hunk = MagicMock()
    mock_line_added = MagicMock()
    mock_line_added.is_added = True
    mock_line_added.is_removed = False
    mock_line_added.value = "New line\n"

    mock_hunk.__iter__ = MagicMock(return_value=iter([mock_line_added]))
    mock_hunk.source_start = 1
    mock_hunk.source_length = 1

    mock_patched_file.__iter__ = MagicMock(return_value=iter([mock_hunk]))

    original_text = "Original line\n"
    patch_str = "@@ -1,1 +1,1 @@\n-Original line\n+New line"

    result = apply_text_patch_safe(original_text, patch_str)

    # Should call PatchSet with the patch string
    mock_patch_set_class.assert_called_once_with(patch_str)
    assert result == "New line\n"


def test_apply_text_patch_safe_empty_patch():
    """Test text patch application with empty patch."""
    original_text = "Some content"
    empty_patch = ""

    result = apply_text_patch_safe(original_text, empty_patch)

    assert result == original_text


def test_apply_text_patch_safe_whitespace_only_patch():
    """Test text patch application with whitespace-only patch."""
    original_text = "Some content"
    whitespace_patch = "   \n\t  "

    result = apply_text_patch_safe(original_text, whitespace_patch)

    assert result == original_text


@patch("infra_core.memory_system.tools.helpers.patch_utils.PatchSet", None)
def test_apply_text_patch_safe_missing_library():
    """Test error when unidiff library is not available."""
    original_text = "Some content"
    patch_str = "@@ -1,1 +1,1 @@\n-Some content\n+New content"

    with pytest.raises(PatchLibraryMissing) as exc_info:
        apply_text_patch_safe(original_text, patch_str)

    assert "unidiff library required" in str(exc_info.value)


def test_apply_text_patch_safe_size_limit():
    """Test patch size limit enforcement."""
    original_text = "Some content"
    # Create a patch that exceeds the line limit
    large_patch = "\n".join([f"line {i}" for i in range(MAX_TEXT_PATCH_LINES + 10)])

    with pytest.raises(PatchSizeError) as exc_info:
        apply_text_patch_safe(original_text, large_patch)

    assert "exceeds limit" in str(exc_info.value)
    assert str(MAX_TEXT_PATCH_LINES) in str(exc_info.value)


@patch("infra_core.memory_system.tools.helpers.patch_utils.PatchSet")
def test_apply_text_patch_safe_parse_error(mock_patch_set_class):
    """Test error when patch cannot be parsed."""
    mock_patch_set_class.side_effect = Exception("Invalid patch format")

    original_text = "Some content"
    invalid_patch = "not a valid patch"

    with pytest.raises(PatchError) as exc_info:
        apply_text_patch_safe(original_text, invalid_patch)

    assert "Text patch application failed" in str(exc_info.value)
    assert "Invalid patch format" in str(exc_info.value)


# Test JSON patch functionality


@patch("infra_core.memory_system.tools.helpers.patch_utils.jsonpatch")
def test_apply_json_patch_safe_success_string_input(mock_jsonpatch):
    """Test successful JSON patch application with string input."""
    # Mock jsonpatch behavior
    mock_patch_obj = MagicMock()
    mock_jsonpatch.JsonPatch.return_value = mock_patch_obj
    mock_patch_obj.apply.return_value = {"field": "updated_value", "new_field": "new_value"}

    original_data = {"field": "original_value"}
    patch_ops_str = '[{"op": "replace", "path": "/field", "value": "updated_value"}]'

    result, affected_paths = apply_json_patch_safe(original_data, patch_ops_str)

    # Should parse the JSON string and create JsonPatch
    expected_ops = [{"op": "replace", "path": "/field", "value": "updated_value"}]
    mock_jsonpatch.JsonPatch.assert_called_once_with(expected_ops)
    mock_patch_obj.apply.assert_called_once_with(original_data)

    assert result == {"field": "updated_value", "new_field": "new_value"}
    assert "field" in affected_paths


@patch("infra_core.memory_system.tools.helpers.patch_utils.jsonpatch")
def test_apply_json_patch_safe_success_list_input(mock_jsonpatch):
    """Test successful JSON patch application with list input."""
    mock_patch_obj = MagicMock()
    mock_jsonpatch.JsonPatch.return_value = mock_patch_obj
    mock_patch_obj.apply.return_value = {"metadata": {"title": "New Title"}}

    original_data = {"metadata": {"title": "Old Title"}}
    patch_ops_list = [{"op": "replace", "path": "/metadata/title", "value": "New Title"}]

    result, affected_paths = apply_json_patch_safe(original_data, patch_ops_list)

    mock_jsonpatch.JsonPatch.assert_called_once_with(patch_ops_list)
    assert result == {"metadata": {"title": "New Title"}}
    assert "metadata" in affected_paths


def test_apply_json_patch_safe_empty_patch():
    """Test JSON patch application with empty patch."""
    original_data = {"field": "value"}
    empty_patch = []

    result, affected_paths = apply_json_patch_safe(original_data, empty_patch)

    assert result == original_data
    assert affected_paths == []


@patch("infra_core.memory_system.tools.helpers.patch_utils.jsonpatch", None)
def test_apply_json_patch_safe_missing_library():
    """Test error when jsonpatch library is not available."""
    original_data = {"field": "value"}
    patch_ops = [{"op": "replace", "path": "/field", "value": "new_value"}]

    with pytest.raises(PatchLibraryMissing) as exc_info:
        apply_json_patch_safe(original_data, patch_ops)

    assert "jsonpatch library required" in str(exc_info.value)


def test_apply_json_patch_safe_size_limit():
    """Test JSON patch operation count limit."""
    original_data = {"field": "value"}
    # Create patch that exceeds operation limit
    large_patch = [
        {"op": "add", "path": f"/field_{i}", "value": f"value_{i}"}
        for i in range(MAX_STRUCTURED_PATCH_OPS + 10)
    ]

    with pytest.raises(PatchSizeError) as exc_info:
        apply_json_patch_safe(original_data, large_patch)

    assert "exceeds limit" in str(exc_info.value)
    assert str(MAX_STRUCTURED_PATCH_OPS) in str(exc_info.value)


def test_apply_json_patch_safe_invalid_json_string():
    """Test error with invalid JSON string."""
    original_data = {"field": "value"}
    invalid_json = "not valid json"

    with pytest.raises(PatchError) as exc_info:
        apply_json_patch_safe(original_data, invalid_json)

    assert "Invalid JSON in patch operations" in str(exc_info.value)


@patch("infra_core.memory_system.tools.helpers.patch_utils.jsonpatch")
def test_apply_json_patch_safe_application_error(mock_jsonpatch):
    """Test error when patch application fails."""
    mock_patch_obj = MagicMock()
    mock_jsonpatch.JsonPatch.return_value = mock_patch_obj
    mock_patch_obj.apply.side_effect = Exception("Invalid operation")

    original_data = {"field": "value"}
    patch_ops = [{"op": "invalid_op", "path": "/field"}]

    with pytest.raises(PatchError) as exc_info:
        apply_json_patch_safe(original_data, patch_ops)

    assert "JSON patch application failed" in str(exc_info.value)


def test_apply_json_patch_safe_affected_paths_extraction():
    """Test extraction of affected field paths from operations."""
    # Test with mock since we're focusing on path extraction logic
    with patch("infra_core.memory_system.tools.helpers.patch_utils.jsonpatch") as mock_jsonpatch:
        mock_patch_obj = MagicMock()
        mock_jsonpatch.JsonPatch.return_value = mock_patch_obj
        mock_patch_obj.apply.return_value = {"updated": "data"}

        original_data = {"metadata": {"title": "old"}, "tags": ["old_tag"]}
        patch_ops = [
            {"op": "replace", "path": "/metadata/title", "value": "new"},
            {"op": "add", "path": "/tags/-", "value": "new_tag"},
            {"op": "replace", "path": "/state", "value": "published"},
        ]

        result, affected_paths = apply_json_patch_safe(original_data, patch_ops)

        # Should extract top-level field names
        expected_paths = ["metadata", "tags", "state"]
        assert set(affected_paths) == set(expected_paths)


# Test validation functions


def test_validate_patch_size_success():
    """Test successful patch size validation."""
    small_patch = "\n".join([f"line {i}" for i in range(10)])

    # Should not raise any exception
    validate_patch_size(small_patch)


def test_validate_patch_size_failure():
    """Test patch size validation failure."""
    large_patch = "\n".join([f"line {i}" for i in range(MAX_TEXT_PATCH_LINES + 10)])

    with pytest.raises(PatchSizeError) as exc_info:
        validate_patch_size(large_patch)

    assert "exceeds limit" in str(exc_info.value)


def test_validate_patch_size_custom_limit():
    """Test patch size validation with custom limit."""
    patch = "line1\nline2\nline3"
    custom_limit = 2

    with pytest.raises(PatchSizeError):
        validate_patch_size(patch, max_lines=custom_limit)


def test_validate_json_patch_size_success_list():
    """Test successful JSON patch size validation with list."""
    small_patch = [{"op": "replace", "path": "/field", "value": "new"}]

    # Should not raise any exception
    validate_json_patch_size(small_patch)


def test_validate_json_patch_size_success_string():
    """Test successful JSON patch size validation with JSON string."""
    small_patch = '[{"op": "replace", "path": "/field", "value": "new"}]'

    # Should not raise any exception
    validate_json_patch_size(small_patch)


def test_validate_json_patch_size_failure_list():
    """Test JSON patch size validation failure with list."""
    large_patch = [
        {"op": "add", "path": f"/field_{i}", "value": f"value_{i}"}
        for i in range(MAX_STRUCTURED_PATCH_OPS + 10)
    ]

    with pytest.raises(PatchSizeError) as exc_info:
        validate_json_patch_size(large_patch)

    assert "exceeds limit" in str(exc_info.value)


def test_validate_json_patch_size_failure_string():
    """Test JSON patch size validation failure with JSON string."""
    large_patch_list = [
        {"op": "add", "path": f"/field_{i}", "value": f"value_{i}"}
        for i in range(MAX_STRUCTURED_PATCH_OPS + 10)
    ]
    large_patch_str = json.dumps(large_patch_list)

    with pytest.raises(PatchSizeError) as exc_info:
        validate_json_patch_size(large_patch_str)

    assert "exceeds limit" in str(exc_info.value)


def test_validate_json_patch_size_invalid_json():
    """Test JSON patch size validation with invalid JSON."""
    invalid_json = "not valid json"

    with pytest.raises(PatchSizeError) as exc_info:
        validate_json_patch_size(invalid_json)

    assert "Invalid JSON" in str(exc_info.value)


def test_validate_json_patch_size_custom_limit():
    """Test JSON patch size validation with custom limit."""
    patch = [{"op": "add", "path": "/field1"}, {"op": "add", "path": "/field2"}]
    custom_limit = 1

    with pytest.raises(PatchSizeError):
        validate_json_patch_size(patch, max_ops=custom_limit)
