"""
DeleteMemoryBlockTool: Agent-facing tool for deleting memory blocks.

This tool provides a unified interface for agents to delete memory blocks with
comprehensive validation, dependency checking, and error handling.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from ...schemas.common import BlockIdType
from ..base.cogni_tool import CogniTool
from ..memory_core.delete_memory_block_core import delete_memory_block_core
from ..memory_core.delete_memory_block_models import (
    DeleteMemoryBlockInput,
    DeleteErrorCode,
)
from ...structured_memory_bank import StructuredMemoryBank

# Setup logging
logger = logging.getLogger(__name__)


class DeleteMemoryBlockToolInput(BaseModel):
    """Simplified input model for agent-facing memory block deletion."""

    # Required fields
    block_id: BlockIdType = Field(..., description="ID of the memory block to delete")

    # Control behavior
    validate_dependencies: bool = Field(
        True,
        description="If True, check for dependent blocks and fail if any exist. If False, force deletion.",
    )

    # Agent context
    author: str = Field("agent", description="Identifier for who is performing the deletion")
    agent_id: str = Field("cogni_agent", description="Agent identifier for tracking")
    change_note: Optional[str] = Field(
        None, description="Optional note explaining the reason for this deletion"
    )


class DeleteMemoryBlockToolOutput(BaseModel):
    """Output model for memory block deletion results."""

    success: bool = Field(..., description="Whether the deletion was successful")
    id: Optional[BlockIdType] = Field(None, description="ID of the deleted block")
    error: Optional[str] = Field(None, description="Error message if deletion failed")
    error_code: Optional[DeleteErrorCode] = Field(None, description="Structured error code")

    # Metadata about deleted block
    deleted_block_type: Optional[str] = Field(None, description="Type of the deleted block")
    deleted_block_version: Optional[int] = Field(None, description="Version of the deleted block")

    # Metadata
    timestamp: datetime = Field(..., description="When the deletion was processed")
    processing_time_ms: Optional[float] = Field(None, description="Processing time in milliseconds")


def delete_memory_block_tool(
    input_data: DeleteMemoryBlockToolInput,
    memory_bank: StructuredMemoryBank,
) -> DeleteMemoryBlockToolOutput:
    """
    Agent-facing wrapper for deleting memory blocks.

    This tool provides a user-friendly interface for agents to delete memory blocks
    with comprehensive validation, dependency checking, and error handling.

    Args:
        input_data: Deletion parameters including block ID and options
        memory_bank: Memory bank interface for persistence

    Returns:
        DeleteMemoryBlockToolOutput with success status and details
    """
    start_time = datetime.now()

    try:
        # Convert DeleteMemoryBlockToolInput to DeleteMemoryBlockInput for core function
        core_input = DeleteMemoryBlockInput(
            block_id=input_data.block_id,
            validate_dependencies=input_data.validate_dependencies,
            author=input_data.author,
            agent_id=input_data.agent_id,
            change_note=input_data.change_note,
        )

        # Call the core deletion function
        core_result = delete_memory_block_core(core_input, memory_bank)

        # Convert core result to tool output
        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        return DeleteMemoryBlockToolOutput(
            success=core_result.success,
            id=core_result.id,
            error=core_result.error,
            error_code=core_result.error_code,
            deleted_block_type=core_result.deleted_block_type,
            deleted_block_version=core_result.deleted_block_version,
            timestamp=core_result.timestamp,
            processing_time_ms=processing_time,
        )

    except Exception as e:
        logger.exception("Error in delete_memory_block wrapper: %s", str(e))
        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        return DeleteMemoryBlockToolOutput(
            success=False,
            error=f"Error in delete_memory_block wrapper: {str(e)}",
            timestamp=datetime.now(),
            processing_time_ms=processing_time,
        )


# Create the CogniTool instance
delete_memory_block_tool_instance = CogniTool(
    name="DeleteMemoryBlock",
    description="Delete memory blocks with dependency validation and error handling",
    input_model=DeleteMemoryBlockToolInput,
    output_model=DeleteMemoryBlockToolOutput,
    function=delete_memory_block_tool,
    memory_linked=True,
)
