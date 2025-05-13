"""
GetMemoryBlockTool: Core tool for retrieving a specific memory block by ID.

This tool provides a simple interface for direct memory block access by ID.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from infra_core.memory_system.schemas.memory_block import MemoryBlock

# Setup logging
logger = logging.getLogger(__name__)


class GetMemoryBlockInput(BaseModel):
    """Input model for retrieving a specific memory block by ID."""

    block_id: str = Field(..., description="The unique identifier of the memory block to retrieve.")


class GetMemoryBlockOutput(BaseModel):
    """Output model for the get memory block operation."""

    success: bool = Field(..., description="Whether the operation was successful.")
    block: Optional[MemoryBlock] = Field(None, description="The retrieved memory block, if found.")
    error: Optional[str] = Field(None, description="Error message if operation failed.")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Timestamp of when the operation was performed."
    )


def get_memory_block_core(input_data: GetMemoryBlockInput, memory_bank) -> GetMemoryBlockOutput:
    """
    Retrieve a specific memory block by ID.

    Args:
        input_data: GetMemoryBlockInput containing the block_id
        memory_bank: An instance of StructuredMemoryBank

    Returns:
        GetMemoryBlockOutput with the retrieved block or error information
    """
    logger.debug(f"Attempting to retrieve memory block with ID: {input_data.block_id}")

    try:
        # Call the memory bank's get_memory_block method
        block = memory_bank.get_memory_block(input_data.block_id)

        if block is not None:
            logger.debug(f"Successfully retrieved memory block: {input_data.block_id}")
            return GetMemoryBlockOutput(success=True, block=block, timestamp=datetime.now())
        else:
            logger.warning(f"Memory block not found with ID: {input_data.block_id}")
            return GetMemoryBlockOutput(
                success=False,
                error=f"Memory block with ID '{input_data.block_id}' not found.",
                timestamp=datetime.now(),
            )
    except Exception as e:
        error_msg = f"Error retrieving memory block: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return GetMemoryBlockOutput(success=False, error=error_msg, timestamp=datetime.now())
