"""
DeleteMemoryBlockCore: Orchestration logic for deleting memory blocks.

This tool handles deleting memory blocks with:
- Validation that the block exists
- Atomic deletion from both Dolt and LlamaIndex
- Comprehensive error handling and structured logging
- Version tracking and proof generation

Follows the refactored 3-layer architecture pattern established by update_memory_block_core.py
"""

from typing import Optional
from datetime import datetime
import logging

from .delete_memory_block_models import (
    DeleteMemoryBlockInput,
    DeleteMemoryBlockOutput,
    DeleteErrorCode,
)
from ...structured_memory_bank import StructuredMemoryBank

# Setup logging
logger = logging.getLogger(__name__)


def delete_memory_block_core(
    input_data: DeleteMemoryBlockInput, memory_bank: StructuredMemoryBank
) -> DeleteMemoryBlockOutput:
    """
    Delete an existing memory block with comprehensive validation and atomic persistence.

    This function implements the delete tool with:
    - Block existence validation
    - Atomic deletion from both Dolt and LlamaIndex
    - Structured error reporting with performance metrics
    - Clean separation of concerns

    Args:
        input_data: Input data for deleting the block
        memory_bank: StructuredMemoryBank instance for persistence

    Returns:
        DeleteMemoryBlockOutput with detailed status and error information
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

    logger.info("Starting memory block deletion", extra={"context": log_context})

    try:
        # 1. Retrieve existing block to validate it exists and get metadata
        existing_block = memory_bank.get_memory_block(input_data.block_id)
        if not existing_block:
            return _create_error_response(
                DeleteErrorCode.BLOCK_NOT_FOUND,
                f"Memory block with ID '{input_data.block_id}' not found",
                timestamp,
                start_time,
                log_context,
            )

        # 2. Validate that the block can be deleted (no dependent blocks if specified)
        if input_data.validate_dependencies:
            dependency_error = _validate_block_dependencies(
                input_data.block_id, memory_bank, log_context
            )
            if dependency_error:
                return _create_error_response(
                    DeleteErrorCode.DEPENDENCIES_EXIST,
                    dependency_error,
                    timestamp,
                    start_time,
                    log_context,
                )

        # 3. Store block metadata for response before deletion
        deleted_block_type = existing_block.type
        deleted_block_version = getattr(existing_block, "block_version", 0) or 0

        # 4. Perform atomic deletion using memory bank
        success = memory_bank.delete_memory_block(input_data.block_id)

        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        if success:
            logger.info(
                "Successfully deleted memory block",
                extra={
                    "context": {
                        **log_context,
                        "deleted_block_type": deleted_block_type,
                        "deleted_block_version": deleted_block_version,
                        "processing_time_ms": processing_time,
                    }
                },
            )

            return DeleteMemoryBlockOutput(
                success=True,
                id=input_data.block_id,
                deleted_block_type=deleted_block_type,
                deleted_block_version=deleted_block_version,
                timestamp=timestamp,
                processing_time_ms=processing_time,
            )
        else:
            return _create_error_response(
                DeleteErrorCode.DELETION_FAILED,
                f"Failed to delete memory block {input_data.block_id}",
                timestamp,
                start_time,
                log_context,
            )

    except Exception as e:
        logger.exception(
            "Unexpected error during memory block deletion",
            extra={"context": {**log_context, "error": str(e)}},
        )
        return _create_error_response(
            DeleteErrorCode.INTERNAL_ERROR,
            f"Unexpected error during deletion: {str(e)}",
            timestamp,
            start_time,
            log_context,
        )


def _validate_block_dependencies(
    block_id: str, memory_bank: StructuredMemoryBank, log_context: dict
) -> Optional[str]:
    """
    Validate that the block can be safely deleted by checking for dependencies.

    Args:
        block_id: ID of the block to check
        memory_bank: Memory bank instance for querying
        log_context: Logging context

    Returns:
        Error message if dependencies exist, None if safe to delete
    """
    try:
        # Check for blocks that depend on this block (incoming links)
        backlinks = memory_bank.get_backlinks(block_id)
        if backlinks:
            dependent_blocks = [link.from_id for link in backlinks]
            logger.warning(
                "Block has dependencies",
                extra={
                    "context": {
                        **log_context,
                        "dependent_blocks": dependent_blocks,
                        "dependency_count": len(dependent_blocks),
                    }
                },
            )
            return (
                f"Cannot delete block {block_id} - it has {len(dependent_blocks)} "
                f"dependent blocks: {', '.join(dependent_blocks[:5])}"
                + ("..." if len(dependent_blocks) > 5 else "")
            )

        return None

    except Exception as e:
        logger.error(
            "Error checking block dependencies",
            extra={"context": {**log_context, "error": str(e)}},
        )
        return f"Failed to check dependencies: {str(e)}"


def _create_error_response(
    error_code: DeleteErrorCode,
    error_message: str,
    timestamp: datetime,
    start_time: datetime,
    log_context: dict,
) -> DeleteMemoryBlockOutput:
    """Create a standardized error response for deletion failures."""
    processing_time = (datetime.now() - start_time).total_seconds() * 1000

    logger.error(
        "Memory block deletion failed",
        extra={
            "context": {
                **log_context,
                "error_code": error_code.value,
                "error_message": error_message,
                "processing_time_ms": processing_time,
            }
        },
    )

    return DeleteMemoryBlockOutput(
        success=False,
        error=error_message,
        error_code=error_code,
        timestamp=timestamp,
        processing_time_ms=processing_time,
    )
