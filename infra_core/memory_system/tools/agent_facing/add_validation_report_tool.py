"""
AddValidationReportTool: Agent-facing tool for adding validation reports to executable memory blocks.

This tool enables agents to validate tasks, bugs, projects, and epics against their
acceptance criteria, marking them as validated and potentially changing their status to "done".
"""

from typing import Optional, List, Dict, Literal
from datetime import datetime
from pydantic import BaseModel, Field, model_validator
import logging
import uuid

from ...schemas.memory_block import MemoryBlock
from ...schemas.metadata.common.validation import ValidationResult, ValidationReport
from ...structured_memory_bank import StructuredMemoryBank
from ..base.cogni_tool import CogniTool

# Setup logging
logger = logging.getLogger(__name__)


class ValidationResultInput(BaseModel):
    """Input model for a single validation result."""

    criterion: str = Field(..., description="The acceptance criterion being validated")
    status: Literal["pass", "fail"] = Field(
        ..., description="Whether the criterion passed validation"
    )
    notes: Optional[str] = Field(None, description="Optional notes about the validation result")


class AddValidationReportInput(BaseModel):
    """Input model for adding a validation report to an executable memory block."""

    block_id: str = Field(..., description="ID of the memory block to validate")
    results: List[ValidationResultInput] = Field(
        ..., description="List of validation results for each acceptance criterion"
    )
    validated_by: Optional[str] = Field(
        "agent", description="User or agent ID who performed the validation"
    )
    timestamp: Optional[datetime] = Field(
        None, description="When the validation was performed (defaults to current time)"
    )
    mark_as_done: bool = Field(
        True, description="Whether to mark the block as 'done' if all validation criteria pass"
    )

    @model_validator(mode="after")
    def ensure_uuid_format(self) -> "AddValidationReportInput":
        """Validate that block_id is in UUID format."""
        try:
            uuid.UUID(self.block_id)
        except ValueError:
            raise ValueError(f"block_id must be a valid UUID, got: {self.block_id}")
        return self


class AddValidationReportOutput(BaseModel):
    """Output model for validation report addition results."""

    success: bool = Field(..., description="Whether the validation report was added successfully")
    block_id: str = Field(..., description="ID of the validated memory block")
    status_updated: bool = Field(
        False, description="Whether the block status was updated to 'done'"
    )
    error: Optional[str] = Field(None, description="Error message if the operation failed")
    validation_summary: Optional[Dict[str, int]] = Field(
        None, description="Summary of validation results (e.g., {'pass': 5, 'fail': 1})"
    )


def add_validation_report(
    input_data: AddValidationReportInput, memory_bank: StructuredMemoryBank
) -> AddValidationReportOutput:
    """
    Add a validation report to an executable memory block and optionally mark it as done.

    Args:
        input_data: Input data for creating the validation report
        memory_bank: StructuredMemoryBank instance for persistence

    Returns:
        AddValidationReportOutput containing result status and validation summary
    """
    try:
        # Get the target memory block
        block = memory_bank.get_memory_block(input_data.block_id)
        if not block:
            return AddValidationReportOutput(
                success=False,
                block_id=input_data.block_id,
                error=f"Memory block with ID {input_data.block_id} not found",
            )

        # Check if the block is of an executable type
        executable_types = ["task", "project", "bug", "epic"]
        if block.type not in executable_types:
            return AddValidationReportOutput(
                success=False,
                block_id=input_data.block_id,
                error=f"Block type '{block.type}' is not an executable type. Must be one of: {executable_types}",
            )

        # Create ValidationResult objects from input
        validation_results = [
            ValidationResult(criterion=result.criterion, status=result.status, notes=result.notes)
            for result in input_data.results
        ]

        # Create the ValidationReport
        timestamp = input_data.timestamp or datetime.now()
        validation_report = ValidationReport(
            validated_by=input_data.validated_by, timestamp=timestamp, results=validation_results
        )

        # Check if we should mark as done
        all_passed = all(result.status == "pass" for result in validation_results)
        status_updated = False

        # Get the current metadata
        metadata = block.metadata.copy() if block.metadata else {}

        # Add validation report to metadata
        metadata["validation_report"] = validation_report.model_dump()

        # Update status if all criteria pass and mark_as_done is True
        if all_passed and input_data.mark_as_done:
            metadata["status"] = "done"
            status_updated = True
            logger.info(f"Block {block.id} marked as 'done' after successful validation")

        # Create a summary of validation results
        validation_summary = {
            "pass": sum(1 for r in validation_results if r.status == "pass"),
            "fail": sum(1 for r in validation_results if r.status == "fail"),
            "total": len(validation_results),
        }

        # Update the block with new metadata
        updated_block = MemoryBlock(
            id=block.id,
            type=block.type,
            text=block.text,
            state=block.state,
            visibility=block.visibility,
            tags=block.tags,
            metadata=metadata,
            source_file=block.source_file,
            confidence=block.confidence,
            links=block.links,
            created_by=block.created_by,
            created_at=block.created_at,
            schema_version=block.schema_version,
        )

        # Persist the updated block
        success = memory_bank.update_memory_block(updated_block)

        if success:
            return AddValidationReportOutput(
                success=True,
                block_id=block.id,
                status_updated=status_updated,
                validation_summary=validation_summary,
            )
        else:
            return AddValidationReportOutput(
                success=False,
                block_id=block.id,
                error="Failed to update memory block with validation report",
            )

    except Exception as e:
        logger.exception(f"Error adding validation report: {str(e)}")
        return AddValidationReportOutput(
            success=False,
            block_id=input_data.block_id,
            error=f"Error adding validation report: {str(e)}",
        )


# Create the tool instance
add_validation_report_tool = CogniTool(
    name="AddValidationReport",
    description="Adds a validation report to an executable memory block, validating the acceptance criteria and optionally marking it as done.",
    input_model=AddValidationReportInput,
    output_model=AddValidationReportOutput,
    function=add_validation_report,
    memory_linked=True,
)
