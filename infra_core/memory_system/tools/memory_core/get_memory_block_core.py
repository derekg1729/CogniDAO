"""
GetMemoryBlockTool: Core tool for retrieving memory blocks by ID(s) or with literal filtering.

This tool provides interfaces for:
- Direct memory block access by ID(s) - always returns a list
- Filtered memory block retrieval by type, tags, and metadata (literal matching)
"""

from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from infra_core.memory_system.schemas.memory_block import MemoryBlock

# Setup logging
logger = logging.getLogger(__name__)


class GetMemoryBlockInput(BaseModel):
    """Input model for retrieving memory blocks by ID(s) or with filtering."""

    # Block retrieval by ID(s)
    block_ids: Optional[List[str]] = Field(
        None, description="List of unique identifiers of memory blocks to retrieve."
    )

    # Multiple block retrieval with filtering
    type_filter: Optional[
        Literal["knowledge", "task", "project", "doc", "interaction", "bug", "epic"]
    ] = Field(None, description="Optional filter by block type")
    namespace_id: Optional[str] = Field(
        None, description="Optional filter by namespace ID for multi-tenant operations"
    )
    tag_filters: Optional[List[str]] = Field(
        None, description="Optional list of tags to filter by (all must match)"
    )
    metadata_filters: Optional[Dict[str, Any]] = Field(
        None, description="Optional metadata key-value pairs to filter by (exact matches)"
    )
    limit: Optional[int] = Field(
        None, description="Maximum number of results to return", ge=1, le=100
    )

    # Branch parameter for Dolt operations
    branch: Optional[str] = Field(
        None, description="Dolt branch to read from (defaults to active branch)"
    )

    def model_post_init(self, __context):
        """Validate that either block_ids is provided OR filtering parameters are provided."""
        if self.block_ids and (
            self.type_filter or self.namespace_id or self.tag_filters or self.metadata_filters
        ):
            raise ValueError("Cannot specify both block_ids and filtering parameters")
        if not self.block_ids and not (
            self.type_filter or self.namespace_id or self.tag_filters or self.metadata_filters
        ):
            raise ValueError("Must specify either block_ids OR at least one filtering parameter")


class GetMemoryBlockOutput(BaseModel):
    """Output model for the get memory block operation."""

    success: bool = Field(..., description="Whether the operation was successful.")
    blocks: List[MemoryBlock] = Field(
        default_factory=list,
        description="The retrieved memory blocks.",
    )
    current_branch: Optional[str] = Field(None, description="Current Dolt branch")
    error: Optional[str] = Field(None, description="Error message if operation failed.")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Timestamp of when the operation was performed."
    )


def get_memory_block_core(input_data: GetMemoryBlockInput, memory_bank) -> GetMemoryBlockOutput:
    """
    Retrieve memory blocks by ID(s) or with literal filtering.

    Args:
        input_data: GetMemoryBlockInput containing block_ids OR filtering parameters
        memory_bank: An instance of StructuredMemoryBank

    Returns:
        GetMemoryBlockOutput with the retrieved blocks or error information
    """
    # Use actual active branch if no branch specified, otherwise use the requested branch
    current_branch = (
        input_data.branch
        if input_data.branch is not None
        else memory_bank.dolt_writer.active_branch
    )

    if input_data.block_ids:
        # Block retrieval by ID(s)
        logger.debug(f"Attempting to retrieve memory blocks with IDs: {input_data.block_ids}")

        try:
            # Get all blocks from the specified branch, then filter by IDs
            # This leverages the existing tested branch support in get_all_memory_blocks
            all_blocks = memory_bank.get_all_memory_blocks(branch=current_branch)
            block_dict = {block.id: block for block in all_blocks}

            retrieved_blocks = []
            missing_ids = []

            for block_id in input_data.block_ids:
                block = block_dict.get(block_id)
                if block is not None:
                    retrieved_blocks.append(block)
                else:
                    missing_ids.append(block_id)

            if missing_ids:
                error_msg = f"Memory blocks not found with IDs: {missing_ids}"
                logger.warning(error_msg)
                return GetMemoryBlockOutput(
                    success=False,
                    blocks=retrieved_blocks,  # Return any found blocks
                    current_branch=current_branch,
                    error=error_msg,
                    timestamp=datetime.now(),
                )
            else:
                logger.debug(f"Successfully retrieved {len(retrieved_blocks)} memory blocks")
                return GetMemoryBlockOutput(
                    success=True,
                    blocks=retrieved_blocks,
                    current_branch=current_branch,
                    timestamp=datetime.now(),
                )

        except Exception as e:
            error_msg = f"Error retrieving memory blocks: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return GetMemoryBlockOutput(
                success=False,
                current_branch=current_branch,
                error=error_msg,
                timestamp=datetime.now(),
            )

    else:
        # Multiple block retrieval with filtering
        logger.debug(
            f"Attempting to retrieve memory blocks with filters: type={input_data.type_filter}, namespace_id={input_data.namespace_id}, tags={input_data.tag_filters}, metadata={input_data.metadata_filters}"
        )

        try:
            # Get all blocks from the specified branch (following blocks_router.py pattern)
            all_blocks = memory_bank.get_all_memory_blocks(branch=input_data.branch)

            # Apply type filter if specified (following blocks_router.py pattern)
            if input_data.type_filter:
                logger.debug(f"Applying type filter: {input_data.type_filter}")
                all_blocks = [block for block in all_blocks if block.type == input_data.type_filter]

            # Apply namespace filter if specified (following blocks_router.py pattern)
            if input_data.namespace_id:
                logger.debug(f"Applying namespace filter: {input_data.namespace_id}")
                all_blocks = [
                    block for block in all_blocks if block.namespace_id == input_data.namespace_id
                ]

            # Apply tag filters if specified (following query_memory_blocks_tool.py pattern)
            if input_data.tag_filters:
                logger.debug(f"Applying tag filters: {input_data.tag_filters}")
                all_blocks = [
                    block
                    for block in all_blocks
                    if all(tag in block.tags for tag in input_data.tag_filters)
                ]

            # Apply metadata filters if specified (following query_memory_blocks_tool.py pattern)
            if input_data.metadata_filters:
                logger.debug(f"Applying metadata filters: {input_data.metadata_filters}")
                all_blocks = [
                    block
                    for block in all_blocks
                    if all(
                        block.metadata.get(k) == v for k, v in input_data.metadata_filters.items()
                    )
                ]

            # Apply limit if specified
            if input_data.limit:
                all_blocks = all_blocks[: input_data.limit]

            logger.debug(f"Successfully filtered blocks. Found {len(all_blocks)} matching blocks.")
            return GetMemoryBlockOutput(
                success=True,
                blocks=all_blocks,
                current_branch=current_branch,
                timestamp=datetime.now(),
            )

        except Exception as e:
            error_msg = f"Error filtering memory blocks: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return GetMemoryBlockOutput(
                success=False,
                current_branch=current_branch,
                error=error_msg,
                timestamp=datetime.now(),
            )
