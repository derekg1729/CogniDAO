"""
BulkDeleteBlocksTool: Agent-facing tool for deleting multiple memory blocks in a single operation.

This tool provides efficient bulk deletion of memory blocks with independent success tracking,
allowing partial success scenarios where some blocks succeed and others fail.
"""

from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from ...schemas.common import BlockIdType
from ..base.cogni_tool import CogniTool
from ..memory_core.delete_memory_block_core import (
    delete_memory_block_core,
    DeleteMemoryBlockInput as CoreDeleteMemoryBlockInput,
)
from ..memory_core.delete_memory_block_models import DeleteErrorCode

# Setup logging
logger = logging.getLogger(__name__)


class DeleteSpec(BaseModel):
    """Specification for a single block to be deleted."""

    # Required fields
    block_id: BlockIdType = Field(..., description="ID of the memory block to delete")

    # Optional control behavior per block
    validate_dependencies: Optional[bool] = Field(
        None, description="Override default dependency validation for this specific block"
    )

    # Optional metadata per block
    change_note: Optional[str] = Field(
        None, description="Optional note explaining why this specific block is being deleted"
    )


class BulkDeleteBlocksInput(BaseModel):
    """Input model for bulk deleting memory blocks."""

    blocks: List[DeleteSpec] = Field(
        ...,
        min_length=1,
        max_length=1000,  # Reasonable limit for bulk operations
        description="List of block specifications to delete",
    )

    # Control options
    stop_on_first_error: bool = Field(
        False,
        description="If True, stop processing on first error. If False, continue and report all results.",
    )

    # Default control behavior
    default_validate_dependencies: bool = Field(
        True,
        description="Default dependency validation setting for blocks that don't specify it",
    )

    # Agent context
    author: str = Field("agent", description="Identifier for who is performing the deletions")
    agent_id: str = Field("cogni_agent", description="Agent identifier for tracking")
    session_id: Optional[str] = Field(None, description="Session ID for grouping related deletions")


class DeleteResult(BaseModel):
    """Result for a single block deletion."""

    success: bool = Field(..., description="Whether this block was deleted successfully")
    block_id: BlockIdType = Field(
        ..., description="ID of the block that was attempted for deletion"
    )
    error: Optional[str] = Field(None, description="Error message if deletion failed")
    error_code: Optional[DeleteErrorCode] = Field(None, description="Structured error code")
    deleted_block_type: Optional[str] = Field(None, description="Type of the deleted block")
    deleted_block_version: Optional[int] = Field(None, description="Version of the deleted block")
    timestamp: datetime = Field(..., description="When this block deletion was attempted")
    processing_time_ms: Optional[float] = Field(None, description="Processing time for this block")


class BulkDeleteBlocksOutput(BaseModel):
    """Output model for bulk block deletion results."""

    success: bool = Field(
        ..., description="Whether ALL blocks were deleted successfully (failed_count == 0)"
    )
    partial_success: bool = Field(
        ..., description="Whether at least one block was deleted successfully"
    )
    total_blocks: int = Field(..., description="Total number of blocks attempted")
    successful_blocks: int = Field(..., description="Number of blocks deleted successfully")
    failed_blocks: int = Field(..., description="Number of blocks that failed to delete")
    results: List[DeleteResult] = Field(..., description="Individual results for each block")
    skipped_block_ids: List[BlockIdType] = Field(
        default_factory=list,
        description="Block IDs that were skipped due to stop_on_first_error=True",
    )
    error_summary: Dict[str, int] = Field(
        default_factory=dict,
        description="Summary of error types and their counts for quick client analysis",
    )
    active_branch: str = Field(..., description="Current active branch")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="When the bulk operation completed"
    )
    total_processing_time_ms: Optional[float] = Field(
        None, description="Total time taken to process all deletions in milliseconds"
    )


def bulk_delete_blocks(input_data: BulkDeleteBlocksInput, memory_bank) -> BulkDeleteBlocksOutput:
    """
    Delete multiple memory blocks with independent success tracking.

    Each block deletion is independent - if one fails, others can still succeed.
    This allows for partial success scenarios which are common in bulk operations.

    Transaction Semantics:
    - Each block deletion uses the existing delete_memory_block_core() function
    - Individual blocks are deleted independently (current implementation)
    - Each deletion is atomic at the individual block level

    Timing Semantics:
    - total_processing_time_ms: Total wall-clock time for the entire bulk operation
    - Individual processing_time_ms: Time for each block's deletion attempt
    - Timing includes validation, core deletion, and result processing

    Stop Behavior:
    - stop_on_first_error=False: Process all blocks, report all results
    - stop_on_first_error=True: Stop on first failure, remaining blocks are skipped
    - skipped_block_ids: Contains IDs of blocks not processed due to early termination

    Dependency Validation Precedence:
    - Per-block validate_dependencies (if specified) overrides default_validate_dependencies
    - If block spec doesn't specify, uses default_validate_dependencies from input

    Args:
        input_data: Input data containing list of block specifications to delete
        memory_bank: StructuredMemoryBank instance for persistence

    Returns:
        BulkDeleteBlocksOutput containing overall status and individual results

    Examples:
        >>> # Basic bulk deletion
        >>> input_data = BulkDeleteBlocksInput(
        ...     blocks=[
        ...         DeleteSpec(block_id="12345678-1234-1234-1234-123456789001"),
        ...         DeleteSpec(block_id="12345678-1234-1234-1234-123456789002")
        ...     ]
        ... )
        >>> result = bulk_delete_blocks(input_data, memory_bank)
        >>> # result.success = True if ALL deletions succeeded
        >>> # result.partial_success = True if ANY deletions succeeded
        >>> # result.skipped_block_ids = [] (no blocks skipped)

        >>> # Partial success scenario with dependency validation
        >>> input_data = BulkDeleteBlocksInput(
        ...     blocks=[
        ...         DeleteSpec(block_id="valid-id", validate_dependencies=True),
        ...         DeleteSpec(block_id="has-deps-id", validate_dependencies=False)
        ...     ],
        ...     stop_on_first_error=False
        ... )
        >>> result = bulk_delete_blocks(input_data, memory_bank)
        >>> # First may fail due to dependencies, second force-deletes
        >>> # result.partial_success = True if at least one succeeded
    """
    start_time = datetime.now()
    logger.info(f"Starting bulk deletion of {len(input_data.blocks)} blocks")

    results = []
    successful_count = 0
    failed_count = 0

    for i, delete_spec in enumerate(input_data.blocks):
        if logger.isEnabledFor(logging.DEBUG):  # Gate debug logging
            logger.debug(
                f"Processing block {i + 1}/{len(input_data.blocks)}: {delete_spec.block_id}"
            )

        try:
            # Determine validation setting (spec override or default)
            validate_deps = (
                delete_spec.validate_dependencies
                if delete_spec.validate_dependencies is not None
                else input_data.default_validate_dependencies
            )

            # Create core input for deletion
            core_input = CoreDeleteMemoryBlockInput(
                block_id=delete_spec.block_id,
                validate_dependencies=validate_deps,
                author=input_data.author,
                agent_id=input_data.agent_id,
                session_id=input_data.session_id,
                change_note=delete_spec.change_note,
            )

            # Attempt to delete the block
            core_result = delete_memory_block_core(core_input, memory_bank)

            # Create result record
            delete_result = DeleteResult(
                success=core_result.success,
                block_id=delete_spec.block_id,
                error=core_result.error,
                error_code=core_result.error_code,
                deleted_block_type=core_result.deleted_block_type,
                deleted_block_version=core_result.deleted_block_version,
                timestamp=core_result.timestamp,
                processing_time_ms=core_result.processing_time_ms,
            )

            results.append(delete_result)

            if core_result.success:
                successful_count += 1
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Successfully deleted block {i + 1}: {delete_spec.block_id}")
            else:
                failed_count += 1
                logger.warning(f"Failed to delete block {i + 1}: {core_result.error}")

                # Stop on first error if requested
                if input_data.stop_on_first_error:
                    logger.info("Stopping bulk operation on first error as requested")
                    break

        except Exception as e:
            # Handle unexpected errors during block processing
            error_msg = f"Unexpected error processing block {i + 1}: {str(e)}"
            logger.error(error_msg, exc_info=True)

            delete_result = DeleteResult(
                success=False,
                block_id=delete_spec.block_id,
                error=error_msg,
                error_code=DeleteErrorCode.INTERNAL_ERROR,
                deleted_block_type=None,
                deleted_block_version=None,
                timestamp=datetime.now(),
                processing_time_ms=None,
            )

            results.append(delete_result)
            failed_count += 1

            # Stop on first error if requested
            if input_data.stop_on_first_error:
                logger.info("Stopping bulk operation on unexpected error as requested")
                break

    # Clear success semantics (same pattern as bulk_create_blocks)
    overall_success = failed_count == 0  # True only if ALL blocks succeeded
    partial_success = successful_count > 0  # True if ANY blocks succeeded

    # Calculate total processing time
    total_processing_time = (datetime.now() - start_time).total_seconds() * 1000

    # Calculate skipped blocks (only when stop_on_first_error=True)
    processed_blocks = len(results)
    skipped_block_ids = []
    if input_data.stop_on_first_error and processed_blocks < len(input_data.blocks):
        # Collect IDs of blocks that were not processed
        skipped_block_ids = [spec.block_id for spec in input_data.blocks[processed_blocks:]]

    # Generate error summary for client analysis
    error_summary = {}
    for result in results:
        if not result.success and result.error_code:
            error_code_str = result.error_code.value if result.error_code else "UNKNOWN"
            error_summary[error_code_str] = error_summary.get(error_code_str, 0) + 1

    logger.info(
        f"Bulk deletion completed: {successful_count} successful, {failed_count} failed, "
        f"{len(skipped_block_ids)} skipped, total time: {total_processing_time:.2f}ms"
    )

    return BulkDeleteBlocksOutput(
        success=overall_success,
        partial_success=partial_success,
        total_blocks=len(input_data.blocks),
        successful_blocks=successful_count,
        failed_blocks=failed_count,
        results=results,
        skipped_block_ids=skipped_block_ids,
        error_summary=error_summary,
        active_branch=memory_bank.dolt_writer.active_branch,
        timestamp=datetime.now(),
        total_processing_time_ms=total_processing_time,
    )


# Create the tool instance
bulk_delete_blocks_tool = CogniTool(
    name="BulkDeleteBlocks",
    description="Delete multiple memory blocks in a single operation with independent success tracking",
    input_model=BulkDeleteBlocksInput,
    output_model=BulkDeleteBlocksOutput,
    function=bulk_delete_blocks,
    memory_linked=True,
)
