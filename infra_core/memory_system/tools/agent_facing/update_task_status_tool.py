"""
UpdateTaskStatusTool: Agent-facing tool for updating the status of task memory blocks.

This tool enables agents to update the status of tasks, with validation for allowed
status transitions and automatic management of related fields like completed flag
and execution_phase.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ValidationError
import logging
import uuid

from ...schemas.metadata.common.executable import WorkStatusLiteral, ExecutionPhaseLiteral
from ...structured_memory_bank import StructuredMemoryBank
from ..base.cogni_tool import CogniTool
from ...schemas.metadata.task import TaskMetadata

# Setup logging
logger = logging.getLogger(__name__)


class UpdateTaskStatusInput(BaseModel):
    """Input model for updating a task's status."""

    block_id: str = Field(..., description="ID of the task memory block to update")
    status: WorkStatusLiteral = Field(..., description="New status to set for the task")
    execution_phase: Optional[ExecutionPhaseLiteral] = Field(
        None,
        description="Optional execution phase to set (only valid when status is 'in_progress')",
    )
    update_message: Optional[str] = Field(
        None, description="Optional message describing the reason for the status update"
    )
    force: bool = Field(
        False,
        description="Whether to force the status update even if it might be invalid",
    )

    @field_validator("block_id")
    def ensure_uuid_format(cls, v):
        """Validate that block_id is a valid UUID."""
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("block_id must be a valid UUID")
        return v


class UpdateTaskStatusOutput(BaseModel):
    """Output model for the task status update operation."""

    success: bool = Field(..., description="Whether the operation was successful")
    block_id: Optional[str] = Field(None, description="ID of the task memory block")
    previous_status: Optional[WorkStatusLiteral] = Field(
        None, description="Previous status of the task"
    )
    new_status: Optional[WorkStatusLiteral] = Field(None, description="New status of the task")
    error: Optional[str] = Field(None, description="Error message if the operation failed")
    updated_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Updated metadata of the task after the operation"
    )


def update_task_status(
    input_data: UpdateTaskStatusInput, memory_bank: StructuredMemoryBank
) -> UpdateTaskStatusOutput:
    """
    Update the status of a task memory block.

    Args:
        input_data: The status update data
        memory_bank: The memory bank to update

    Returns:
        Result of the operation
    """
    try:
        # Retrieve the memory block
        block = memory_bank.get_memory_block(input_data.block_id)
        if not block:
            return UpdateTaskStatusOutput(
                success=False,
                error=f"Memory block with ID {input_data.block_id} not found",
            )

        # Check if block is a task
        if block.type != "task":
            return UpdateTaskStatusOutput(
                success=False,
                block_id=block.id,
                error=f"Memory block with ID {input_data.block_id} is not a task (type: {block.type})",
            )

        # Load task metadata into the Pydantic model to validate against the schema
        try:
            task_metadata = TaskMetadata.model_validate(block.metadata)
        except ValidationError as e:
            return UpdateTaskStatusOutput(
                success=False,
                block_id=block.id,
                error=f"Failed to validate existing metadata: {str(e)}",
            )

        # Store previous status for reference
        previous_status = task_metadata.status

        # Check if the target status is different
        if task_metadata.status == input_data.status and not input_data.force:
            return UpdateTaskStatusOutput(
                success=True,
                block_id=block.id,
                previous_status=previous_status,
                new_status=task_metadata.status,
                error="No status change needed (current and target status are the same)",
                updated_metadata=block.metadata,
            )

        # Update the status
        task_metadata.status = input_data.status

        # When setting to 'done', check for validation report
        if (
            input_data.status == "done"
            and not task_metadata.validation_report
            and not input_data.force
        ):
            return UpdateTaskStatusOutput(
                success=False,
                block_id=block.id,
                previous_status=previous_status,
                error="Cannot set status to 'done' without a validation report. Add a validation report first or use force=True.",
            )

        # Handle execution_phase
        if input_data.status == "in_progress":
            # If moving to in_progress, we can set the execution_phase
            if input_data.execution_phase:
                task_metadata.execution_phase = input_data.execution_phase
            # If no execution_phase is provided and none exists, set a default
            elif not task_metadata.execution_phase:
                task_metadata.execution_phase = "implementing"
        else:
            # If not in_progress, execution_phase should be None
            task_metadata.execution_phase = None

        # Create an update history entry if update_message is provided
        if input_data.update_message:
            # Convert to dictionary for metadata updates
            metadata_dict = task_metadata.model_dump()

            # Initialize status_history if it doesn't exist
            if "status_history" not in metadata_dict:
                metadata_dict["status_history"] = []

            # Add the new status entry
            metadata_dict["status_history"].append(
                {
                    "timestamp": datetime.now(),
                    "from_status": previous_status,
                    "to_status": input_data.status,
                    "message": input_data.update_message,
                }
            )

            # Update the block with the new metadata dictionary directly
            updated_block = block.model_copy(deep=True)
            updated_block.metadata = metadata_dict
            updated_block.updated_at = datetime.now()  # Update the timestamp
        else:
            # No update message, just update the block with the standard metadata
            updated_block = block.model_copy(deep=True)
            updated_block.metadata = task_metadata.model_dump()
            updated_block.updated_at = datetime.now()  # Update the timestamp

        # Persist the updated block
        update_success = memory_bank.update_memory_block(updated_block)
        if not update_success:
            return UpdateTaskStatusOutput(
                success=False,
                block_id=block.id,
                previous_status=previous_status,
                error="Failed to update memory block in database",
            )

        return UpdateTaskStatusOutput(
            success=True,
            block_id=block.id,
            previous_status=previous_status,
            new_status=task_metadata.status,
            updated_metadata=updated_block.metadata,
        )

    except Exception as e:
        logger.exception(f"Error updating task status: {str(e)}")
        return UpdateTaskStatusOutput(
            success=False,
            block_id=input_data.block_id if hasattr(input_data, "block_id") else None,
            error=f"An error occurred: {str(e)}",
        )


# Create the CogniTool wrapper
update_task_status_tool = CogniTool(
    name="update_task_status",
    description="Update the status of a task memory block with validation",
    input_model=UpdateTaskStatusInput,
    output_model=UpdateTaskStatusOutput,
    function=update_task_status,
)
