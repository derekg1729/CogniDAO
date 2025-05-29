"""
Patch utilities for memory system tools.

This module provides safe, efficient patch application using proven libraries:
- unidiff library for unified diff text patches
- jsonpatch library for RFC-6902 JSON Patch operations

Includes performance limits and comprehensive error handling.
"""

from typing import Dict, Any, List, Union, Tuple
import logging

# Import proven libraries with graceful fallback
try:
    from unidiff import PatchSet
except ImportError:
    PatchSet = None

try:
    import jsonpatch
except ImportError:
    jsonpatch = None

# Setup logging
logger = logging.getLogger(__name__)

# Performance limits from task specifications
MAX_TEXT_PATCH_LINES = 1000
MAX_STRUCTURED_PATCH_OPS = 100


class PatchError(Exception):
    """Base exception for patch application errors."""

    pass


class PatchSizeError(PatchError):
    """Exception raised when patch exceeds size limits."""

    pass


class PatchLibraryMissing(PatchError):
    """Exception raised when required patch library is not available."""

    pass


def apply_text_patch_safe(
    original_text: str, patch_str: str, max_lines: int = MAX_TEXT_PATCH_LINES
) -> str:
    """
    Apply a unified diff patch to text content using the proven unidiff library.

    Args:
        original_text: The original text content
        patch_str: Unified diff patch string
        max_lines: Maximum number of patch lines allowed (default: 1000)

    Returns:
        Updated text content

    Raises:
        PatchLibraryMissing: If unidiff library is not available
        PatchSizeError: If patch exceeds size limits
        PatchError: If patch cannot be applied
    """
    if not PatchSet:
        raise PatchLibraryMissing("unidiff library required for text patch application")

    if not patch_str.strip():
        return original_text

    # Check patch size limits
    patch_lines = patch_str.count("\n") + 1
    if patch_lines > max_lines:
        raise PatchSizeError(f"Text patch has {patch_lines} lines, exceeds limit of {max_lines}")

    try:
        # Parse the patch using unidiff
        patch_set = PatchSet(patch_str)

        if not patch_set:
            return original_text

        # For memory block updates, we expect a single "file" patch
        if len(patch_set) > 1:
            logger.warning(f"Patch set contains {len(patch_set)} files, using first file only")

        patched_file = patch_set[0]

        # Apply the patch to the original text
        # Split text into lines for patch application
        original_lines = original_text.splitlines(keepends=True)
        result_lines = original_lines.copy()

        # Apply each hunk
        for hunk in patched_file:
            # unidiff provides line-by-line diff information
            # We need to apply changes based on hunk data
            result_lines = _apply_hunk_to_lines(result_lines, hunk)

        return "".join(result_lines)

    except Exception as e:
        logger.error(f"Failed to apply text patch: {str(e)}")
        raise PatchError(f"Text patch application failed: {str(e)}")


def _apply_hunk_to_lines(lines: List[str], hunk) -> List[str]:
    """
    Apply a single hunk to lines of text.

    This is a simplified implementation that handles basic cases.
    For production use, consider using a more robust patch application library.
    """
    # This is a basic implementation - unidiff provides the structure
    # but we need to implement the actual line-by-line application

    # Get hunk source line number
    source_start = hunk.source_start - 1  # Convert to 0-based indexing

    result_lines = []

    # Add lines before the hunk
    result_lines.extend(lines[:source_start])

    # Process hunk lines
    for line in hunk:
        if line.is_added:
            result_lines.append(line.value)
        elif line.is_removed:
            # Skip removed lines
            continue
        else:
            # Context line - keep it
            result_lines.append(line.value)

    # Add lines after the hunk
    source_end = source_start + hunk.source_length
    result_lines.extend(lines[source_end:])

    return result_lines


def apply_json_patch_safe(
    original_data: Dict[str, Any],
    patch_ops: Union[str, List[Dict[str, Any]]],
    max_ops: int = MAX_STRUCTURED_PATCH_OPS,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Apply JSON Patch (RFC-6902) operations to dictionary data using proven jsonpatch library.

    Args:
        original_data: Original data dictionary
        patch_ops: JSON Patch operations (string or list of operations)
        max_ops: Maximum number of patch operations allowed (default: 100)

    Returns:
        Tuple of (updated_data, affected_field_paths)

    Raises:
        PatchLibraryMissing: If jsonpatch library is not available
        PatchSizeError: If patch exceeds operation limits
        PatchError: If patch cannot be applied
    """
    import json  # Import at function level to ensure it's in scope for exception handling

    if not jsonpatch:
        raise PatchLibraryMissing("jsonpatch library required for structured patch application")

    if not patch_ops:
        return original_data, []

    try:
        # Parse patch operations
        if isinstance(patch_ops, str):
            operations = json.loads(patch_ops)
        else:
            operations = patch_ops

        # Check operation count limits
        if len(operations) > max_ops:
            raise PatchSizeError(
                f"Patch has {len(operations)} operations, exceeds limit of {max_ops}"
            )

        # Extract affected field paths for diff summary
        affected_paths = []
        for op in operations:
            if "path" in op:
                # Convert JSON Pointer to field name (e.g., "/metadata/title" -> "metadata")
                path = op["path"].lstrip("/").split("/")[0]
                if path and path not in affected_paths:
                    affected_paths.append(path)

        # Apply the patch
        patch_obj = jsonpatch.JsonPatch(operations)
        updated_data = patch_obj.apply(original_data)

        logger.debug(
            f"Applied JSON patch with {len(operations)} operations to fields: {affected_paths}"
        )

        return updated_data, affected_paths

    except PatchSizeError:
        # Re-raise PatchSizeError without wrapping
        raise
    except json.JSONDecodeError as e:
        raise PatchError(f"Invalid JSON in patch operations: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to apply JSON patch: {str(e)}")
        raise PatchError(f"JSON patch application failed: {str(e)}")


def validate_patch_size(patch_str: str, max_lines: int = MAX_TEXT_PATCH_LINES) -> None:
    """
    Validate that a text patch doesn't exceed size limits.

    Args:
        patch_str: Patch string to validate
        max_lines: Maximum allowed lines

    Raises:
        PatchSizeError: If patch exceeds limits
    """
    if not patch_str:
        return

    line_count = patch_str.count("\n") + 1
    if line_count > max_lines:
        raise PatchSizeError(f"Patch has {line_count} lines, exceeds limit of {max_lines}")


def validate_json_patch_size(
    patch_ops: Union[str, List[Dict[str, Any]]], max_ops: int = MAX_STRUCTURED_PATCH_OPS
) -> None:
    """
    Validate that JSON patch operations don't exceed size limits.

    Args:
        patch_ops: Patch operations to validate
        max_ops: Maximum allowed operations

    Raises:
        PatchSizeError: If patch exceeds limits
    """
    import json  # Import at function level for consistency

    if not patch_ops:
        return

    if isinstance(patch_ops, str):
        try:
            operations = json.loads(patch_ops)
        except json.JSONDecodeError:
            raise PatchSizeError("Invalid JSON in patch operations")
    else:
        operations = patch_ops

    if len(operations) > max_ops:
        raise PatchSizeError(f"Patch has {len(operations)} operations, exceeds limit of {max_ops}")
