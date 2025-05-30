"""
AddValidationReportTool: Agent-facing tool for adding validation reports to executable memory blocks.

This tool enables agents to validate tasks, bugs, projects, and epics against their
acceptance criteria, marking them as validated and potentially changing their status to "done".
"""

from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ValidationError
import logging
import uuid

from ...schemas.metadata.common.validation import ValidationResult, ValidationReport
from ...structured_memory_bank import StructuredMemoryBank
from ..base.cogni_tool import CogniTool
from ...schemas.metadata.task import TaskMetadata
from ...schemas.metadata.project import ProjectMetadata
from ...schemas.metadata.epic import EpicMetadata
from ...schemas.metadata.bug import BugMetadata

# Setup logging
logger = logging.getLogger(__name__)


class ValidationResultInput(BaseModel):
    """Input model for a single validation result."""

    criterion: str = Field(..., description="The acceptance criterion being validated")
    status: str = Field(
        ..., description="Whether the criterion passed validation", pattern="^(pass|fail)$"
    )
    notes: Optional[str] = Field(None, description="Optional notes about the validation result")


class AddValidationReportInput(BaseModel):
    """
    Input model for adding a validation report to an executable memory block.
    """

    block_id: str = Field(..., description="ID of the memory block to add validation report to")
    results: List[ValidationResultInput] = Field(
        ..., description="List of validation results for each acceptance criterion"
    )
    validated_by: str = Field(..., description="ID of the agent or user performing the validation")
    mark_as_done: bool = Field(
        True,
        description="Whether to mark the block as done if all validation criteria pass",
    )
    force: bool = Field(
        False,
        description="Whether to force overwrite an existing validation report",
    )

    @field_validator("block_id")
    def ensure_uuid_format(cls, v):
        """Validate that block_id is a valid UUID."""
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("block_id must be a valid UUID")
        return v


class AddValidationReportOutput(BaseModel):
    """Output model for the validation report addition operation."""

    success: bool = Field(..., description="Whether the operation was successful")
    block_id: Optional[str] = Field(None, description="ID of the memory block")
    status_updated: bool = Field(False, description="Whether the block status was updated to done")
    validation_summary: Optional[Dict[str, int]] = Field(
        None, description="Summary of validation results (pass/fail counts)"
    )
    error: Optional[str] = Field(None, description="Error message if the operation failed")
    updated_metadata: Optional[Dict] = Field(
        None, description="Updated metadata of the block after the operation"
    )


# Map of block types to their respective metadata model classes
TYPE_TO_METADATA_CLASS = {
    "task": TaskMetadata,
    "project": ProjectMetadata,
    "epic": EpicMetadata,
    "bug": BugMetadata,
}

EXECUTABLE_TYPES = list(TYPE_TO_METADATA_CLASS.keys())


def add_validation_report(
    input_data: AddValidationReportInput, memory_bank: StructuredMemoryBank
) -> AddValidationReportOutput:
    """
    Add a validation report to an executable memory block.

    Args:
        input_data: The validation report data to add
        memory_bank: The memory bank to update

    Returns:
        Result of the operation
    """
    try:
        # Retrieve the memory block
        block = memory_bank.get_memory_block(input_data.block_id)
        if not block:
            return AddValidationReportOutput(
                success=False,
                error=f"Memory block with ID {input_data.block_id} not found",
            )

        # Check if block is an executable type
        if block.type not in EXECUTABLE_TYPES:
            return AddValidationReportOutput(
                success=False,
                error=f"Memory block type '{block.type}' is not an executable type. "
                f"Must be one of: {', '.join(EXECUTABLE_TYPES)}",
            )

        # Get the appropriate metadata model class for this block type
        metadata_class = TYPE_TO_METADATA_CLASS.get(block.type)
        if not metadata_class:
            return AddValidationReportOutput(
                success=False,
                error=f"No metadata model found for block type '{block.type}'",
            )

        # Check if validation report already exists and force flag is not set
        if block.metadata.get("validation_report") and not input_data.force:
            return AddValidationReportOutput(
                success=False,
                block_id=block.id,
                error="Validation report already exists. Use force=True to overwrite.",
            )

        # Load metadata into the appropriate Pydantic model to validate against the schema
        try:
            metadata_obj = metadata_class.model_validate(block.metadata)
        except ValidationError as e:
            return AddValidationReportOutput(
                success=False,
                error=f"Failed to validate existing metadata against {metadata_class.__name__}: {str(e)}",
            )

        # Create the validation report from input data
        validation_results = [
            ValidationResult(
                criterion=result.criterion,
                status=result.status,
                notes=result.notes,
            )
            for result in input_data.results
        ]

        validation_report = ValidationReport(
            validated_by=input_data.validated_by,
            timestamp=datetime.now(),
            results=validation_results,
        )

        # Count validation results
        pass_count = sum(1 for r in validation_results if r.status == "pass")
        fail_count = sum(1 for r in validation_results if r.status == "fail")
        validation_summary = {
            "pass": pass_count,
            "fail": fail_count,
            "total": len(validation_results),
        }

        # Update metadata with validation report
        metadata_obj.validation_report = validation_report

        # Determine if we should update status to done
        status_updated = False

        # Check if we have failing criteria and mark_as_done is requested
        if input_data.mark_as_done and fail_count > 0:
            return AddValidationReportOutput(
                success=False,
                block_id=block.id,
                error="Cannot mark as done when there are failing validation results. Fix failures or set mark_as_done=False.",
                validation_summary=validation_summary,
            )

        if input_data.mark_as_done and fail_count == 0:
            metadata_obj.status = "done"
            status_updated = True

        # Update the block with the new metadata
        updated_block = block.model_copy(deep=True)
        updated_block.metadata = metadata_obj.model_dump()
        updated_block.updated_at = datetime.now()  # Update the timestamp

        # Persist the updated block
        update_success = memory_bank.update_memory_block(updated_block)
        if not update_success:
            return AddValidationReportOutput(
                success=False,
                error="Failed to update memory block with validation report",
            )

        return AddValidationReportOutput(
            success=True,
            block_id=block.id,
            status_updated=status_updated,
            validation_summary=validation_summary,
            updated_metadata=updated_block.metadata,
        )

    except Exception as e:
        return AddValidationReportOutput(
            success=False,
            error=f"Error in add_validation_report: {str(e)}",
        )


# Create the CogniTool instance for use in the registry
add_validation_report_tool = CogniTool(
    name="AddValidationReport",
    function=add_validation_report,
    description="Add a validation report to an executable memory block, verifying acceptance criteria and optionally marking it as done",
    input_model=AddValidationReportInput,
    output_model=AddValidationReportOutput,
    memory_linked=True,
)
