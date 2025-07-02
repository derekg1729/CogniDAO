"""
BulkUpdateNamespaceTool: Agent-facing tool for updating namespace of multiple memory blocks in a single operation.

This tool provides efficient bulk namespace updates with independent success tracking,
allowing partial success scenarios where some blocks succeed and others fail.
"""

from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from ...schemas.common import BlockIdType
from ..memory_core.update_memory_block_core import (
    update_memory_block_core,
    UpdateMemoryBlockInput as CoreUpdateMemoryBlockInput,
)
from ..memory_core.update_memory_block_models import UpdateErrorCode
from ...dolt_writer import PERSISTED_TABLES

# Setup logging
logger = logging.getLogger(__name__)


class BlockUpdateSpec(BaseModel):
    """Specification for a single block namespace update."""

    block_id: BlockIdType = Field(..., description="ID of the block to update")
    validate_exists: bool = Field(
        True, description="Whether to validate the block exists before updating"
    )
    change_note: Optional[str] = Field(
        None, description="Optional note explaining the namespace change"
    )


class BulkUpdateNamespaceInput(BaseModel):
    """Input model for bulk updating namespace of memory blocks."""

    blocks: List[BlockUpdateSpec] = Field(
        ...,
        min_length=1,
        max_length=500,  # Reasonable limit for bulk namespace updates
        description="List of block IDs to update",
    )

    target_namespace_id: str = Field(..., description="Target namespace ID to move all blocks to")

    # Control options
    stop_on_first_error: bool = Field(
        False,
        description="If True, stop processing on first error. If False, continue and report all results.",
    )

    # System metadata
    author: str = Field("bulk_agent", description="Author of the namespace updates")
    agent_id: str = Field("BulkUpdateNamespace", description="Agent ID for tracking")
    session_id: Optional[str] = Field(None, description="Session ID for grouping updates")


class BlockUpdateResult(BaseModel):
    """Result for a single block namespace update."""

    success: bool = Field(..., description="Whether this block was updated successfully")
    block_id: BlockIdType = Field(..., description="ID of the block that was updated")
    error: Optional[str] = Field(None, description="Error message if update failed")
    error_code: Optional[UpdateErrorCode] = Field(None, description="Error code if update failed")
    previous_namespace: Optional[str] = Field(None, description="Previous namespace of the block")
    new_namespace: Optional[str] = Field(None, description="New namespace of the block")
    block_version: Optional[int] = Field(None, description="New block version after update")
    timestamp: datetime = Field(..., description="When this block update was attempted")
    processing_time_ms: float = Field(..., description="Time taken to process this block")


class BulkUpdateNamespaceOutput(BaseModel):
    """Output model for bulk namespace update results."""

    success: bool = Field(
        ..., description="Whether ALL blocks were updated successfully (failed_count == 0)"
    )
    partial_success: bool = Field(
        ..., description="Whether at least one block was updated successfully"
    )
    total_blocks: int = Field(..., description="Total number of blocks attempted")
    successful_blocks: int = Field(..., description="Number of blocks updated successfully")
    failed_blocks: int = Field(..., description="Number of blocks that failed to update")
    results: List[BlockUpdateResult] = Field(..., description="Individual results for each block")
    skipped_block_ids: List[BlockIdType] = Field(
        ..., description="Block IDs that were not processed due to early termination"
    )
    error_summary: Dict[str, int] = Field(
        ..., description="Summary of error types and their counts"
    )
    target_namespace_id: str = Field(..., description="Target namespace that was attempted")
    namespace_validated: bool = Field(
        ..., description="Whether the target namespace was validated to exist"
    )
    active_branch: str = Field(..., description="Current active branch")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="When the bulk operation completed"
    )
    total_processing_time_ms: float = Field(
        ..., description="Total time for the entire bulk operation"
    )


def bulk_update_namespace(
    input_data: BulkUpdateNamespaceInput, memory_bank
) -> BulkUpdateNamespaceOutput:
    """
    Update namespace of multiple memory blocks with independent success tracking.

    Each block update is independent - if one fails, others can still succeed.
    This allows for partial success scenarios which are common in bulk operations.

    Transaction Semantics:
    - Individual updates are staged independently
    - Bulk commit at the end for atomicity
    - Rollback on commit failure

    Args:
        input_data: Input data containing list of block IDs and target namespace
        memory_bank: StructuredMemoryBank instance for persistence

    Returns:
        BulkUpdateNamespaceOutput containing overall status and individual results
    """
    start_time = datetime.now()
    logger.info(
        f"Starting bulk namespace update of {len(input_data.blocks)} blocks to namespace '{input_data.target_namespace_id}'"
    )

    results = []
    successful_count = 0
    failed_count = 0
    processed_blocks = 0
    namespace_validated = False

    # --- VALIDATION PHASE: Validate target namespace exists ---
    try:
        # Check if target namespace exists
        from ...tools.agent_facing.dolt_namespace_tool import (
            list_namespaces_tool,
            ListNamespacesInput,
        )

        namespace_result = list_namespaces_tool(ListNamespacesInput(), memory_bank)

        if namespace_result.success:
            existing_namespaces = [ns.id for ns in namespace_result.namespaces]
            if input_data.target_namespace_id not in existing_namespaces:
                logger.error(f"Target namespace '{input_data.target_namespace_id}' does not exist")
                # Create failed results for all blocks
                for block_spec in input_data.blocks:
                    results.append(
                        BlockUpdateResult(
                            success=False,
                            block_id=block_spec.block_id,
                            error=f"Target namespace '{input_data.target_namespace_id}' does not exist",
                            error_code=UpdateErrorCode.VALIDATION_ERROR,
                            previous_namespace=None,
                            new_namespace=None,
                            block_version=None,
                            timestamp=datetime.now(),
                            processing_time_ms=0,
                        )
                    )
                failed_count = len(input_data.blocks)

                return BulkUpdateNamespaceOutput(
                    success=False,
                    partial_success=False,
                    total_blocks=len(input_data.blocks),
                    successful_blocks=0,
                    failed_blocks=failed_count,
                    results=results,
                    skipped_block_ids=[],
                    error_summary={"VALIDATION_ERROR": failed_count},
                    target_namespace_id=input_data.target_namespace_id,
                    namespace_validated=False,
                    active_branch=memory_bank.branch,
                    timestamp=datetime.now(),
                    total_processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                )
            else:
                namespace_validated = True
                logger.info(
                    f"Target namespace '{input_data.target_namespace_id}' validated successfully"
                )
        else:
            logger.warning("Could not validate namespace - proceeding with updates")

    except Exception as e:
        logger.warning(f"Namespace validation failed: {e} - proceeding with updates")

    # --- UPDATE PHASE: Process each block ---
    for i, block_spec in enumerate(input_data.blocks):
        block_start_time = datetime.now()

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"Processing block {i + 1}/{len(input_data.blocks)}: {block_spec.block_id}"
            )

        try:
            # Get existing block to check current namespace
            existing_block = memory_bank.get_memory_block(block_spec.block_id)

            if not existing_block:
                if block_spec.validate_exists:
                    results.append(
                        BlockUpdateResult(
                            success=False,
                            block_id=block_spec.block_id,
                            error=f"Block {block_spec.block_id} not found",
                            error_code=UpdateErrorCode.BLOCK_NOT_FOUND,
                            previous_namespace=None,
                            new_namespace=None,
                            block_version=None,
                            timestamp=datetime.now(),
                            processing_time_ms=(datetime.now() - block_start_time).total_seconds()
                            * 1000,
                        )
                    )
                    failed_count += 1

                    if input_data.stop_on_first_error:
                        logger.info(f"Stopping on first error at block {i + 1}")
                        processed_blocks = i + 1  # Mark as processed up to this point
                        break
                    processed_blocks += 1
                    continue
                else:
                    # Skip non-existent blocks if validation is disabled
                    logger.warning(f"Block {block_spec.block_id} not found - skipping")
                    processed_blocks += 1
                    continue

            previous_namespace = existing_block.namespace_id

            # Skip if already in target namespace
            if previous_namespace == input_data.target_namespace_id:
                logger.debug(f"Block {block_spec.block_id} already in target namespace - skipping")
                results.append(
                    BlockUpdateResult(
                        success=True,
                        block_id=block_spec.block_id,
                        error=None,
                        error_code=None,
                        previous_namespace=previous_namespace,
                        new_namespace=input_data.target_namespace_id,
                        block_version=existing_block.block_version,
                        timestamp=datetime.now(),
                        processing_time_ms=(datetime.now() - block_start_time).total_seconds()
                        * 1000,
                    )
                )
                successful_count += 1
                processed_blocks += 1
                continue

            # Create update input for namespace change
            core_input = CoreUpdateMemoryBlockInput(
                block_id=block_spec.block_id,
                namespace_id=input_data.target_namespace_id,
                change_note=block_spec.change_note
                or f"Bulk namespace update to {input_data.target_namespace_id}",
                author=input_data.author,
                agent_id=input_data.agent_id,
                session_id=input_data.session_id,
            )

            # Attempt to update the block
            core_result = update_memory_block_core(core_input, memory_bank)

            # Create result record
            block_result = BlockUpdateResult(
                success=core_result.success,
                block_id=block_spec.block_id,
                error=core_result.error,
                error_code=core_result.error_code,
                previous_namespace=previous_namespace,
                new_namespace=input_data.target_namespace_id if core_result.success else None,
                block_version=core_result.new_version if core_result.success else None,
                timestamp=core_result.timestamp,
                processing_time_ms=core_result.processing_time_ms,
            )

            results.append(block_result)

            if core_result.success:
                successful_count += 1
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        f"Successfully updated block {i + 1} namespace: {block_spec.block_id}"
                    )
            else:
                failed_count += 1
                logger.warning(f"Failed to update block {i + 1} namespace: {core_result.error}")

                if input_data.stop_on_first_error:
                    logger.info(f"Stopping on first error at block {i + 1}")
                    processed_blocks = i + 1  # Mark as processed up to this point
                    break

        except Exception as e:
            logger.error(f"Exception during block {i + 1} namespace update: {e}", exc_info=True)

            results.append(
                BlockUpdateResult(
                    success=False,
                    block_id=block_spec.block_id,
                    error=f"Internal error: {str(e)}",
                    error_code=UpdateErrorCode.UNKNOWN_ERROR,
                    previous_namespace=None,
                    new_namespace=None,
                    block_version=None,
                    timestamp=datetime.now(),
                    processing_time_ms=(datetime.now() - block_start_time).total_seconds() * 1000,
                )
            )
            failed_count += 1

            if input_data.stop_on_first_error:
                logger.info(f"Stopping on first error at block {i + 1}")
                processed_blocks = i + 1  # Mark as processed up to this point
                break

        processed_blocks += 1

    # Collect IDs of blocks that were not processed
    skipped_block_ids = [spec.block_id for spec in input_data.blocks[processed_blocks:]]

    # --- COMMIT PHASE: Commit all successful updates ---
    if successful_count > 0:
        try:
            commit_msg = f"Bulk namespace update: {successful_count} blocks moved to {input_data.target_namespace_id}"
            if len(input_data.blocks) > 1:
                commit_msg += f" (out of {len(input_data.blocks)} attempted)"

            logger.info(f"Committing {successful_count} successful namespace updates...")

            # Stage changes first (required before committing)
            stage_success, stage_message = memory_bank.dolt_writer.add_to_staging(PERSISTED_TABLES)
            if not stage_success:
                raise Exception(f"Failed to stage changes: {stage_message}")

            logger.debug(f"Successfully staged changes: {stage_message}")

            commit_success, commit_hash = memory_bank.dolt_writer.commit_changes(
                commit_msg=commit_msg, tables=PERSISTED_TABLES
            )

            if commit_success:
                logger.info(f"Successfully committed bulk namespace updates: {commit_hash}")
                # Store block proof for successful updates
                for result in results:
                    if result.success:
                        memory_bank._store_block_proof(result.block_id, "update", commit_hash)
            else:
                # Commit failed - all "successful" updates are now failures
                logger.error(
                    "Failed to commit bulk namespace update changes. Rolling back all updates."
                )

                # Attempt rollback
                try:
                    memory_bank.dolt_writer.discard_changes(PERSISTED_TABLES)
                    logger.info("Successfully rolled back all namespace update changes.")
                except Exception as rollback_e:
                    logger.critical(
                        f"Failed to rollback namespace update changes: {rollback_e}. Database may be in an inconsistent state!"
                    )

                # Mark all "successful" updates as failed
                for result in results:
                    if result.success:
                        result.success = False
                        result.error = "Bulk namespace update commit failed - changes rolled back"
                        result.error_code = UpdateErrorCode.UNKNOWN_ERROR
                        result.new_namespace = None

                # Update counts
                failed_count = len(results)
                successful_count = 0

        except Exception as commit_e:
            logger.error(
                f"Exception during bulk namespace update commit: {commit_e}", exc_info=True
            )

            # Attempt rollback
            try:
                memory_bank.dolt_writer.discard_changes(PERSISTED_TABLES)
                logger.info(
                    "Successfully rolled back namespace update changes after commit exception."
                )
            except Exception as rollback_e:
                logger.critical(
                    f"Failed to rollback after commit exception: {rollback_e}. Database may be in an inconsistent state!"
                )

            # Mark all "successful" updates as failed
            for result in results:
                if result.success:
                    result.success = False
                    result.error = f"Bulk namespace update commit exception: {str(commit_e)}"
                    result.error_code = UpdateErrorCode.UNKNOWN_ERROR
                    result.new_namespace = None

            # Update counts
            failed_count = len(results)
            successful_count = 0
    else:
        logger.info("No successful namespace updates to commit.")

    # Generate error summary for client analysis
    error_summary = {}
    for result in results:
        if not result.success and result.error_code:
            error_code_str = result.error_code.value if result.error_code else "UNKNOWN"
            error_summary[error_code_str] = error_summary.get(error_code_str, 0) + 1

    # Calculate final metrics
    overall_success = failed_count == 0
    partial_success = successful_count > 0
    total_processing_time = (datetime.now() - start_time).total_seconds() * 1000

    logger.info(
        f"Bulk namespace update completed: {successful_count}/{len(input_data.blocks)} successful, "
        f"{failed_count} failed, {len(skipped_block_ids)} skipped"
    )

    return BulkUpdateNamespaceOutput(
        success=overall_success,
        partial_success=partial_success,
        total_blocks=len(input_data.blocks),
        successful_blocks=successful_count,
        failed_blocks=failed_count,
        results=results,
        skipped_block_ids=skipped_block_ids,
        error_summary=error_summary,
        target_namespace_id=input_data.target_namespace_id,
        namespace_validated=namespace_validated,
        active_branch=memory_bank.branch,
        timestamp=datetime.now(),
        total_processing_time_ms=total_processing_time,
    )


# Define the agent-facing tool wrapper
def bulk_update_namespace_tool(input_data: dict, memory_bank) -> dict:
    """
    Agent-facing wrapper for bulk namespace updates.

    Args:
        input_data: Dictionary containing the input parameters
        memory_bank: StructuredMemoryBank instance

    Returns:
        Dictionary containing the operation results
    """
    # Parse and validate input
    try:
        parsed_input = BulkUpdateNamespaceInput(**input_data)
    except Exception as e:
        return {
            "success": False,
            "error": f"Invalid input: {str(e)}",
            "timestamp": datetime.now().isoformat(),
        }

    # Execute bulk update
    result = bulk_update_namespace(parsed_input, memory_bank)

    # Convert to dictionary for JSON serialization
    return result.dict()
