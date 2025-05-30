"""
UpdateMemoryBlockCore: Orchestration logic for updating existing memory blocks.

This tool handles updating existing memory blocks with:
- Concurrency safety via optimistic locking using canonical block_version field
- Patch-based updates using proven libraries (unidiff + jsonpatch)
- Comprehensive validation using existing helpers
- Atomic persistence with re-indexing support
- Structured logging for observability

Refactored Architecture - Phase 1: Focused orchestration using extracted modules
"""

from typing import Dict, Any
from datetime import datetime
import logging

from .update_memory_block_models import (
    UpdateMemoryBlockInput,
    UpdateMemoryBlockOutput,
    UpdateErrorCode,
    PatchType,
    DiffSummary,
)
from ..helpers.patch_utils import (
    apply_text_patch_safe,
    apply_json_patch_safe,
    validate_patch_size,
    validate_json_patch_size,
    PatchError,
    PatchSizeError,
    PatchLibraryMissing,
)
from ..helpers.relation_helpers import resolve_relation_alias
from ..helpers.block_validation import ensure_blocks_exist
from ...schemas.memory_block import MemoryBlock
from ...schemas.registry import validate_metadata
from ...structured_memory_bank import StructuredMemoryBank

# Setup logging
logger = logging.getLogger(__name__)


def update_memory_block_core(
    input_data: UpdateMemoryBlockInput, memory_bank: StructuredMemoryBank
) -> UpdateMemoryBlockOutput:
    """
    Update an existing memory block with enhanced validation and atomic persistence.

    This function implements the refactored update tool with:
    - Canonical block_version optimistic locking
    - Proven libraries for patch application (unidiff + jsonpatch)
    - Comprehensive validation using existing helpers
    - Structured error reporting with performance metrics
    - Clean separation of concerns

    Args:
        input_data: Enhanced input data for updating the block
        memory_bank: StructuredMemoryBank instance for persistence

    Returns:
        UpdateMemoryBlockOutput with detailed status, errors, and change summary
    """
    start_time = datetime.now()
    timestamp = start_time

    # Structured logging context
    log_context = {
        "block_id": input_data.block_id,
        "author": input_data.author,
        "agent_id": input_data.agent_id,
        "session_id": input_data.session_id,
        "change_note": input_data.change_note,
        "timestamp": timestamp.isoformat(),
    }

    logger.info("Starting memory block update", extra={"context": log_context})

    try:
        # 1. Retrieve existing block with version info
        existing_block = memory_bank.get_memory_block(input_data.block_id)
        if not existing_block:
            return _create_error_response(
                UpdateErrorCode.BLOCK_NOT_FOUND,
                f"Memory block with ID '{input_data.block_id}' not found",
                timestamp,
                start_time,
                log_context,
            )

        # 2. Validate concurrency controls using canonical block_version field
        current_version = getattr(existing_block, "block_version", 0) or 0
        if input_data.previous_block_version is not None:
            if current_version != input_data.previous_block_version:
                return _create_error_response(
                    UpdateErrorCode.VERSION_CONFLICT,
                    f"Version conflict: expected {input_data.previous_block_version}, got {current_version}",
                    timestamp,
                    start_time,
                    log_context,
                    previous_version=current_version,
                )

        # 3. Validate patch sizes before application (performance limits)
        try:
            if input_data.text_patch:
                validate_patch_size(input_data.text_patch)
            if input_data.structured_patch:
                validate_json_patch_size(input_data.structured_patch)
        except PatchSizeError as e:
            return _create_error_response(
                UpdateErrorCode.PATCH_SIZE_LIMIT_ERROR,
                str(e),
                timestamp,
                start_time,
                log_context,
            )

        # 4. Apply updates using proven libraries and helper methods
        update_result = _apply_all_updates(existing_block, input_data, log_context)
        if not update_result["success"]:
            return _create_error_response(
                update_result["error_code"],
                update_result["error_message"],
                timestamp,
                start_time,
                log_context,
            )

        updated_block_data = update_result["updated_data"]
        updated_fields = update_result["updated_fields"]
        patch_stats = update_result["patch_stats"]

        # 5. Increment block version and update timestamps
        new_version = current_version + 1
        updated_block_data["block_version"] = new_version
        updated_block_data["updated_at"] = timestamp
        updated_fields.extend(["block_version", "updated_at"])

        # 6. Validate updated block using schema validation
        try:
            updated_block = MemoryBlock(**updated_block_data)
        except Exception as e:
            return _create_error_response(
                UpdateErrorCode.VALIDATION_ERROR,
                f"Updated block validation failed: {str(e)}",
                timestamp,
                start_time,
                log_context,
            )

        # 7. Validate metadata if updated using existing helper
        if "metadata" in updated_fields:
            metadata_error = validate_metadata(existing_block.type, updated_block_data["metadata"])
            if metadata_error:
                return _create_error_response(
                    UpdateErrorCode.VALIDATION_ERROR,
                    f"Metadata validation failed: {metadata_error}",
                    timestamp,
                    start_time,
                    log_context,
                )

        # 8. Validate links if updated using existing helper
        if "links" in updated_fields and input_data.links:
            try:
                link_validation_error = _validate_links_simple(input_data.links, memory_bank)
                if link_validation_error:
                    return _create_error_response(
                        UpdateErrorCode.LINK_VALIDATION_ERROR,
                        f"Link validation failed: {link_validation_error}",
                        timestamp,
                        start_time,
                        log_context,
                    )
            except Exception as e:
                logger.warning(
                    f"Link validation helper failed: {str(e)}", extra={"context": log_context}
                )
                # Continue without link validation for now

        # 9. Validate tag constraints (max 20 after merge)
        if "tags" in updated_fields and updated_block_data.get("tags"):
            if len(updated_block_data["tags"]) > 20:
                return _create_error_response(
                    UpdateErrorCode.VALIDATION_ERROR,
                    f"Too many tags: {len(updated_block_data['tags'])}, maximum allowed is 20",
                    timestamp,
                    start_time,
                    log_context,
                )

        # 10. Persist using memory bank's atomic update
        success = memory_bank.update_memory_block(updated_block)

        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        if success:
            # Create diff summary
            diff_summary = DiffSummary(
                fields_updated=updated_fields,
                text_changed="text" in updated_fields,
                metadata_changed="metadata" in updated_fields,
                tags_changed="tags" in updated_fields,
                links_changed="links" in updated_fields,
                patch_stats=patch_stats if patch_stats else None,
            )

            logger.info(
                "Successfully updated memory block",
                extra={
                    "context": {
                        **log_context,
                        "updated_fields": updated_fields,
                        "new_version": new_version,
                        "processing_time_ms": processing_time,
                    }
                },
            )

            return UpdateMemoryBlockOutput(
                success=True,
                id=updated_block.id,
                timestamp=updated_block.updated_at,
                diff_summary=diff_summary,
                previous_version=current_version,
                new_version=new_version,
                processing_time_ms=processing_time,
            )
        else:
            return _create_error_response(
                UpdateErrorCode.PERSISTENCE_FAILURE,
                "Failed to persist updated memory block",
                timestamp,
                start_time,
                log_context,
            )

    except Exception as e:
        logger.exception("Unexpected error updating memory block", extra={"context": log_context})
        return _create_error_response(
            UpdateErrorCode.UNKNOWN_ERROR,
            f"Unexpected error updating memory block: {str(e)}",
            timestamp,
            start_time,
            log_context,
        )


def _apply_all_updates(
    existing_block: MemoryBlock, input_data: UpdateMemoryBlockInput, log_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Apply all updates (patches and direct field updates) to the existing block.

    Returns:
        Dict with success status, updated data, fields changed, and patch stats
    """
    updated_fields = []
    updated_block_data = existing_block.model_dump()
    patch_stats = {}

    try:
        # Handle text updates with proven unidiff library
        if input_data.text_patch:
            try:
                updated_text = apply_text_patch_safe(existing_block.text, input_data.text_patch)
                updated_block_data["text"] = updated_text
                updated_fields.append("text")
                patch_stats["text_patch_applied"] = True
                logger.debug(
                    "Applied text patch using unidiff library", extra={"context": log_context}
                )
            except (PatchError, PatchLibraryMissing) as e:
                return {
                    "success": False,
                    "error_code": UpdateErrorCode.PATCH_APPLY_ERROR,
                    "error_message": f"Text patch application failed: {str(e)}",
                }
        elif input_data.text is not None:
            updated_block_data["text"] = input_data.text
            updated_fields.append("text")

        # Handle structured field updates with proven jsonpatch library
        if input_data.structured_patch and input_data.patch_type == PatchType.JSON_PATCH:
            try:
                updated_data, affected_paths = apply_json_patch_safe(
                    updated_block_data, input_data.structured_patch
                )
                updated_block_data = updated_data
                updated_fields.extend(affected_paths)
                patch_stats["structured_patch_applied"] = True
                patch_stats["affected_fields"] = affected_paths
                logger.debug(
                    f"Applied JSON patch to fields: {affected_paths}",
                    extra={"context": log_context},
                )
            except (PatchError, PatchLibraryMissing) as e:
                return {
                    "success": False,
                    "error_code": UpdateErrorCode.PATCH_APPLY_ERROR,
                    "error_message": f"Structured patch application failed: {str(e)}",
                }

        # Handle traditional full field updates
        if input_data.state is not None:
            updated_block_data["state"] = input_data.state
            updated_fields.append("state")

        if input_data.visibility is not None:
            updated_block_data["visibility"] = input_data.visibility
            updated_fields.append("visibility")

        if input_data.source_file is not None:
            updated_block_data["source_file"] = input_data.source_file
            updated_fields.append("source_file")

        if input_data.confidence is not None:
            updated_block_data["confidence"] = input_data.confidence
            updated_fields.append("confidence")

        # Handle tags merging/replacement with deduplication
        if input_data.tags is not None:
            if input_data.merge_tags and existing_block.tags:
                merged_tags = list(set(existing_block.tags + input_data.tags))
                updated_block_data["tags"] = merged_tags
            else:
                updated_block_data["tags"] = input_data.tags
            updated_fields.append("tags")

        # Handle metadata merging/replacement (only if not handled by structured patch)
        if input_data.metadata is not None and not input_data.structured_patch:
            if input_data.merge_metadata and existing_block.metadata:
                merged_metadata = {**existing_block.metadata, **input_data.metadata}
                updated_block_data["metadata"] = merged_metadata
            else:
                updated_block_data["metadata"] = input_data.metadata
            updated_fields.append("metadata")

        # Handle links replacement
        if input_data.links is not None:
            updated_block_data["links"] = input_data.links
            updated_fields.append("links")

        return {
            "success": True,
            "updated_data": updated_block_data,
            "updated_fields": updated_fields,
            "patch_stats": patch_stats,
        }

    except Exception as e:
        logger.error(f"Error applying updates: {str(e)}", extra={"context": log_context})
        return {
            "success": False,
            "error_code": UpdateErrorCode.UNKNOWN_ERROR,
            "error_message": f"Error applying updates: {str(e)}",
        }


def _create_error_response(
    error_code: UpdateErrorCode,
    error_message: str,
    timestamp: datetime,
    start_time: datetime,
    log_context: Dict[str, Any],
    previous_version: int = None,
) -> UpdateMemoryBlockOutput:
    """Helper to create consistent error responses."""
    processing_time = (datetime.now() - start_time).total_seconds() * 1000

    logger.warning(error_message, extra={"context": log_context})

    return UpdateMemoryBlockOutput(
        success=False,
        error=error_message,
        error_code=error_code,
        timestamp=timestamp,
        previous_version=previous_version,
        processing_time_ms=processing_time,
    )


def _validate_links_simple(links: list, memory_bank: StructuredMemoryBank) -> str:
    """
    Simple link validation using existing helpers.

    Args:
        links: List of BlockLink objects to validate
        memory_bank: Memory bank for existence checks

    Returns:
        Error message if validation fails, empty string if success
    """
    if not links:
        return ""

    try:
        # Extract target block IDs for existence check
        target_ids = set()
        for link in links:
            if hasattr(link, "target_id"):
                target_ids.add(link.target_id)
            elif isinstance(link, dict) and "target_id" in link:
                target_ids.add(link["target_id"])

        # Check that all target blocks exist
        if target_ids:
            existence_result = ensure_blocks_exist(target_ids, memory_bank, raise_error=False)
            missing_blocks = [
                block_id for block_id, exists in existence_result.items() if not exists
            ]
            if missing_blocks:
                return f"Linked blocks do not exist: {missing_blocks}"

        # Validate relation types
        for link in links:
            relation = None
            if hasattr(link, "relation"):
                relation = link.relation
            elif isinstance(link, dict) and "relation" in link:
                relation = link["relation"]

            if relation:
                try:
                    resolve_relation_alias(relation)
                except ValueError as e:
                    return f"Invalid relation type in link: {str(e)}"

        return ""  # No errors

    except Exception as e:
        return f"Link validation error: {str(e)}"
