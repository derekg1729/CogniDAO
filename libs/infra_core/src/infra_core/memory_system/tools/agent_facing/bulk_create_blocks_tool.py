"""
BulkCreateBlocksTool: Agent-facing tool for creating multiple memory blocks in a single operation.

This tool provides efficient bulk creation of memory blocks with independent success tracking,
allowing partial success scenarios where some blocks succeed and others fail.
"""

from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from ...schemas.common import BlockIdType
from ...schemas.memory_block import ConfidenceScore
from ..base.cogni_tool import CogniTool
from ..memory_core.create_memory_block_tool import (
    create_memory_block,
    CreateMemoryBlockInput as CoreCreateMemoryBlockInput,
)

# Setup logging
logger = logging.getLogger(__name__)

# Define valid block types (addresses API-TYPE-003)
ValidBlockType = Literal["knowledge", "task", "project", "doc", "interaction", "log", "epic", "bug"]


class BlockSpec(BaseModel):
    """Specification for a single block to be created."""

    # Required fields - now with proper type validation
    type: ValidBlockType = Field(..., description="Type of memory block to create")
    text: str = Field(..., description="Primary content of the memory block")

    # Optional fields
    state: Optional[Literal["draft", "published", "archived"]] = Field(
        "draft", description="Initial state of the block"
    )
    visibility: Optional[Literal["internal", "public", "restricted"]] = Field(
        "internal", description="Visibility level of the block"
    )
    tags: List[str] = Field(
        default_factory=list, description="Optional tags for filtering and metadata"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Type-specific metadata for the block"
    )
    source_file: Optional[str] = Field(None, description="Optional source file or markdown name")
    confidence: Optional[ConfidenceScore] = Field(
        None, description="Optional confidence scores for the block"
    )
    created_by: Optional[str] = Field(
        None, description="Optional identifier for creator (agent name or user ID)"
    )

    # System metadata fields (addresses FIELD-DEFAULT-102)
    x_agent_id: Optional[str] = Field(
        None, description="Agent ID for this block (defaults to bulk operation agent)"
    )
    x_tool_id: Optional[str] = Field(
        None, description="Tool ID for this block (defaults to BulkCreateBlocks)"
    )
    x_parent_block_id: Optional[str] = Field(
        None, description="Parent block ID if this block is part of a hierarchy"
    )
    x_session_id: Optional[str] = Field(None, description="Session ID for grouping related blocks")


class BulkCreateBlocksInput(BaseModel):
    """Input model for bulk creating memory blocks."""

    blocks: List[BlockSpec] = Field(
        ...,
        min_length=1,
        max_length=1000,  # Reasonable limit for bulk operations
        description="List of block specifications to create",
    )

    # Control options
    stop_on_first_error: bool = Field(
        False,
        description="If True, stop processing on first error. If False, continue and report all results.",
    )

    # Default system metadata (addresses FIELD-DEFAULT-102)
    default_x_agent_id: str = Field(
        "bulk_agent", description="Default agent ID for blocks that don't specify one"
    )
    default_x_tool_id: str = Field(
        "BulkCreateBlocks", description="Default tool ID for blocks that don't specify one"
    )
    default_x_session_id: Optional[str] = Field(
        None, description="Default session ID for grouping all blocks in this bulk operation"
    )


class BlockResult(BaseModel):
    """Result for a single block creation."""

    success: bool = Field(..., description="Whether this block was created successfully")
    id: Optional[BlockIdType] = Field(None, description="ID of the created block if successful")
    error: Optional[str] = Field(None, description="Error message if creation failed")
    block_type: str = Field(..., description="Type of the block that was attempted")
    timestamp: datetime = Field(..., description="When this block creation was attempted")


class BulkCreateBlocksOutput(BaseModel):
    """Output model for bulk block creation results."""

    success: bool = Field(
        ..., description="Whether ALL blocks were created successfully (failed_count == 0)"
    )
    partial_success: bool = Field(
        ..., description="Whether at least one block was created successfully"
    )
    total_blocks: int = Field(..., description="Total number of blocks attempted")
    successful_blocks: int = Field(..., description="Number of blocks created successfully")
    failed_blocks: int = Field(..., description="Number of blocks that failed to create")
    results: List[BlockResult] = Field(..., description="Individual results for each block")
    active_branch: str = Field(..., description="Current active branch")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="When the bulk operation completed"
    )


def bulk_create_blocks(input_data: BulkCreateBlocksInput, memory_bank) -> BulkCreateBlocksOutput:
    """
    Create multiple memory blocks with independent success tracking.

    Each block creation is independent - if one fails, others can still succeed.
    This allows for partial success scenarios which are common in bulk operations.

    Transaction Semantics:
    - Each block creation uses the existing create_memory_block() function
    - Individual blocks are committed independently (current implementation)
    - TODO: Future enhancement could wrap in single transaction for atomicity

    Args:
        input_data: Input data containing list of block specifications
        memory_bank: StructuredMemoryBank instance for persistence

    Returns:
        BulkCreateBlocksOutput containing overall status and individual results
    """
    logger.info(f"Starting bulk creation of {len(input_data.blocks)} blocks")

    results = []
    successful_count = 0
    failed_count = 0

    for i, block_spec in enumerate(input_data.blocks):
        if logger.isEnabledFor(logging.DEBUG):  # Gate debug logging (addresses LOGGING-101)
            logger.debug(f"Processing block {i + 1}/{len(input_data.blocks)}: {block_spec.type}")

        try:
            # Prepare metadata with system fields
            final_metadata = block_spec.metadata.copy()

            # Add system metadata fields with defaults (addresses FIELD-DEFAULT-102)
            final_metadata["x_agent_id"] = block_spec.x_agent_id or input_data.default_x_agent_id
            final_metadata["x_tool_id"] = block_spec.x_tool_id or input_data.default_x_tool_id

            if block_spec.x_parent_block_id:
                final_metadata["x_parent_block_id"] = block_spec.x_parent_block_id
            if block_spec.x_session_id or input_data.default_x_session_id:
                final_metadata["x_session_id"] = (
                    block_spec.x_session_id or input_data.default_x_session_id
                )

            # Create core input from block spec
            core_input = CoreCreateMemoryBlockInput(
                type=block_spec.type,
                text=block_spec.text,
                state=block_spec.state,
                visibility=block_spec.visibility,
                tags=block_spec.tags,
                metadata=final_metadata,
                source_file=block_spec.source_file,
                confidence=block_spec.confidence,
                created_by=block_spec.created_by,
            )

            # Attempt to create the block
            core_result = create_memory_block(core_input, memory_bank)

            # Create result record
            block_result = BlockResult(
                success=core_result.success,
                id=core_result.id,
                error=core_result.error,
                block_type=block_spec.type,
                timestamp=core_result.timestamp,
            )

            results.append(block_result)

            if core_result.success:
                successful_count += 1
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Successfully created block {i + 1}: {core_result.id}")
            else:
                failed_count += 1
                logger.warning(f"Failed to create block {i + 1}: {core_result.error}")

                # Stop on first error if requested
                if input_data.stop_on_first_error:
                    logger.info("Stopping bulk operation on first error as requested")
                    break

        except Exception as e:
            # Handle unexpected errors during block processing
            error_msg = f"Unexpected error processing block {i + 1}: {str(e)}"
            logger.error(error_msg, exc_info=True)

            block_result = BlockResult(
                success=False,
                id=None,
                error=error_msg,
                block_type=block_spec.type,
                timestamp=datetime.now(),
            )

            results.append(block_result)
            failed_count += 1

            # Stop on first error if requested
            if input_data.stop_on_first_error:
                logger.info("Stopping bulk operation on unexpected error as requested")
                break

    # Clear success semantics (addresses CONSISTENCY-002)
    overall_success = failed_count == 0  # True only if ALL blocks succeeded
    partial_success = successful_count > 0  # True if ANY blocks succeeded

    logger.info(
        f"Bulk creation completed: {successful_count} successful, {failed_count} failed, "
        f"{len(input_data.blocks) - len(results)} skipped"
    )

    return BulkCreateBlocksOutput(
        success=overall_success,
        partial_success=partial_success,
        total_blocks=len(input_data.blocks),
        successful_blocks=successful_count,
        failed_blocks=failed_count,
        results=results,
        active_branch=memory_bank.dolt_writer.active_branch,
        timestamp=datetime.now(),
    )


# Create the tool instance
bulk_create_blocks_tool = CogniTool(
    name="BulkCreateBlocks",
    description="Create multiple memory blocks in a single operation with independent success tracking",
    input_model=BulkCreateBlocksInput,
    output_model=BulkCreateBlocksOutput,
    function=bulk_create_blocks,
    memory_linked=True,
)
