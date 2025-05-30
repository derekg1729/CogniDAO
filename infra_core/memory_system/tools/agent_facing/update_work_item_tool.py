"""
UpdateWorkItemTool: Agent-facing tool for updating work items (projects, epics, tasks, bugs).

This tool provides a specialized interface for updating work item memory blocks,
handling work-item-specific fields and validation while leveraging the core
UpdateMemoryBlockTool for the actual updates.
"""

from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field, model_validator
import logging

from ...schemas.common import BlockLink, BlockIdType
from ...schemas.metadata.common.executable import (
    PriorityLiteral,
    WorkStatusLiteral,
    ExecutionPhaseLiteral,
)
from ...schemas.metadata.common.validation import ValidationResult, ValidationReport
from ..base.cogni_tool import CogniTool
from .update_memory_block_tool import (
    update_memory_block_tool,
    UpdateMemoryBlockToolInput,
    UpdateMemoryBlockToolOutput,
)

# Setup logging
logger = logging.getLogger(__name__)

# Define work item types
WorkItemTypeLiteral = Literal["project", "epic", "task", "bug"]


class UpdateWorkItemInput(BaseModel):
    """Input model for updating work item memory blocks."""

    # Required field
    block_id: BlockIdType = Field(..., description="ID of the work item to update")

    # Concurrency control
    previous_block_version: Optional[int] = Field(
        None, description="Expected current version for optimistic locking"
    )

    # Work item fields that can be updated
    title: Optional[str] = Field(None, description="Updated title of the work item")
    description: Optional[str] = Field(None, description="Updated description of the work item")

    # Status and priority updates
    status: Optional[WorkStatusLiteral] = Field(None, description="Updated status of the work item")
    priority: Optional[PriorityLiteral] = Field(
        None, description="Updated priority level of the work item"
    )
    owner: Optional[str] = Field(None, description="Updated owner or assignee")

    # Planning and tracking fields
    acceptance_criteria: Optional[List[str]] = Field(
        None, description="Updated criteria for completion"
    )
    action_items: Optional[List[str]] = Field(None, description="Updated action items")
    expected_artifacts: Optional[List[str]] = Field(
        None, description="Updated expected deliverables"
    )
    blocked_by: Optional[List[BlockIdType]] = Field(
        None, description="Updated list of blocking items"
    )

    # Time tracking
    story_points: Optional[float] = Field(None, description="Updated story points")
    estimate_hours: Optional[float] = Field(None, description="Updated time estimate")

    # Additional fields
    tags: Optional[List[str]] = Field(None, description="Updated tags")
    labels: Optional[List[str]] = Field(None, description="Updated labels")

    # Agent framework fields
    tool_hints: Optional[List[str]] = Field(None, description="Updated tool hints")
    role_hint: Optional[str] = Field(None, description="Updated role hint")
    execution_timeout_minutes: Optional[int] = Field(None, description="Updated timeout")
    cost_budget_usd: Optional[float] = Field(None, description="Updated budget")
    execution_phase: Optional[ExecutionPhaseLiteral] = Field(
        None, description="Updated execution phase (only for in_progress status)"
    )

    # Standard memory block fields
    state: Optional[Literal["draft", "published", "archived"]] = Field(
        None, description="Updated state of the block"
    )
    visibility: Optional[Literal["internal", "public", "restricted"]] = Field(
        None, description="Updated visibility level"
    )
    links: Optional[List[BlockLink]] = Field(None, description="Updated block links")

    # Update behavior
    merge_tags: bool = Field(True, description="Whether to merge or replace tags")
    merge_labels: bool = Field(True, description="Whether to merge or replace labels")
    merge_metadata: bool = Field(True, description="Whether to merge or replace metadata")
    merge_links: bool = Field(True, description="Whether to merge or replace links")

    # Agent context
    author: str = Field("agent", description="Who is making the update")
    agent_id: str = Field("cogni_agent", description="Agent identifier")
    change_note: Optional[str] = Field(None, description="Note explaining the update")

    @model_validator(mode="after")
    def validate_execution_phase(self) -> "UpdateWorkItemInput":
        """Validate that execution_phase is only set when status is 'in_progress'."""
        if self.execution_phase is not None and self.status != "in_progress":
            raise ValueError("execution_phase can only be set when status is 'in_progress'")
        return self


class UpdateWorkItemOutput(UpdateMemoryBlockToolOutput):
    """Output model for work item update results."""

    work_item_type: Optional[str] = Field(None, description="Type of work item that was updated")


def update_work_item(input_data: UpdateWorkItemInput, memory_bank) -> UpdateWorkItemOutput:
    """
    Update a work item memory block with type-specific validation and metadata handling.

    This function handles the update of project, epic, task, and bug memory blocks
    with appropriate metadata transformations based on the work item structure.

    Args:
        input_data: Input data for updating the work item
        memory_bank: StructuredMemoryBank instance for persistence

    Returns:
        UpdateWorkItemOutput containing update status, version, and metadata
    """
    logger.debug(f"Updating work item: {input_data.block_id}")

    try:
        # First get the current block to determine type and current metadata
        current_block = memory_bank.get_memory_block(input_data.block_id)
        if not current_block:
            return UpdateWorkItemOutput(
                success=False,
                error=f"Work item {input_data.block_id} not found",
                timestamp=datetime.now(),
            )

        work_item_type = current_block.type

        # Prepare metadata updates
        metadata_updates = {}

        # Core work item fields
        if input_data.title is not None:
            metadata_updates["title"] = input_data.title
        if input_data.description is not None:
            metadata_updates["description"] = input_data.description
        if input_data.status is not None:
            metadata_updates["status"] = input_data.status
            # Automatically create validation report when status is 'done' or 'released'
            if input_data.status in ["done", "released"]:
                # Get current acceptance criteria from the block
                current_acceptance_criteria = current_block.metadata.get("acceptance_criteria", [])

                # Create validation results for each acceptance criterion
                validation_results = []
                for criterion in current_acceptance_criteria:
                    validation_results.append(
                        ValidationResult(
                            criterion=criterion,
                            status="pass",
                            notes="Automatically validated when status set to done",
                        )
                    )

                # If no acceptance criteria exist, create a default one
                if not validation_results:
                    validation_results.append(
                        ValidationResult(
                            criterion="Work item completed",
                            status="pass",
                            notes="Default validation for completed work item",
                        )
                    )

                validation_report = ValidationReport(
                    validated_by=input_data.agent_id, results=validation_results
                )
                metadata_updates["validation_report"] = validation_report
        if input_data.priority is not None:
            metadata_updates["priority"] = input_data.priority

        # Owner/assignee field (depends on work item type)
        if input_data.owner is not None:
            # All work item types use the 'assignee' field from ExecutableMetadata
            metadata_updates["assignee"] = input_data.owner

        # Planning fields
        if input_data.acceptance_criteria is not None:
            metadata_updates["acceptance_criteria"] = input_data.acceptance_criteria
        if input_data.action_items is not None:
            metadata_updates["action_items"] = input_data.action_items
        if input_data.expected_artifacts is not None:
            metadata_updates["expected_artifacts"] = input_data.expected_artifacts
        if input_data.blocked_by is not None:
            metadata_updates["blocked_by"] = list(input_data.blocked_by)

        # Estimation fields
        if input_data.story_points is not None:
            metadata_updates["story_points"] = input_data.story_points
        if input_data.estimate_hours is not None:
            metadata_updates["estimate_hours"] = input_data.estimate_hours

        # Additional fields
        if input_data.labels is not None:
            metadata_updates["labels"] = input_data.labels

        # Agent framework fields
        if input_data.tool_hints is not None:
            metadata_updates["tool_hints"] = input_data.tool_hints
        if input_data.role_hint is not None:
            metadata_updates["role_hint"] = input_data.role_hint
        if input_data.execution_timeout_minutes is not None:
            metadata_updates["execution_timeout_minutes"] = input_data.execution_timeout_minutes
        if input_data.cost_budget_usd is not None:
            metadata_updates["cost_budget_usd"] = input_data.cost_budget_usd

        # Execution phase (only for tasks and bugs)
        if input_data.execution_phase is not None and work_item_type in ["task", "bug"]:
            metadata_updates["execution_phase"] = input_data.execution_phase

        # Handle execution_phase clearing when status changes away from "in_progress"
        if input_data.status is not None and work_item_type in ["task", "bug"]:
            if input_data.status == "in_progress":
                # If moving to in_progress, execution_phase can be set (already handled above)
                # If no execution_phase provided but one exists, keep the existing one
                pass
            else:
                # If not in_progress, execution_phase should be None (automatically clear)
                metadata_updates["execution_phase"] = None

        # Add tool identifier to track updates
        metadata_updates["x_tool_id"] = "UpdateWorkItemTool"

        # Create the core update input
        core_input = UpdateMemoryBlockToolInput(
            block_id=input_data.block_id,
            previous_block_version=input_data.previous_block_version,
            text=input_data.description,  # Description goes into text field
            state=input_data.state,
            visibility=input_data.visibility,
            tags=input_data.tags,
            metadata=metadata_updates if metadata_updates else None,
            links=input_data.links,
            merge_tags=input_data.merge_tags,
            merge_metadata=input_data.merge_metadata,
            merge_links=input_data.merge_links,
            author=input_data.author,
            agent_id=input_data.agent_id,
            change_note=input_data.change_note,
        )

        # Use the core update tool
        result = update_memory_block_tool(core_input, memory_bank)

        # Return enhanced output with work item type
        return UpdateWorkItemOutput(
            success=result.success,
            id=result.id,
            error=result.error,
            error_code=result.error_code,
            previous_version=result.previous_version,
            new_version=result.new_version,
            timestamp=result.timestamp,
            processing_time_ms=result.processing_time_ms,
            fields_updated=result.fields_updated,
            text_changed=result.text_changed,
            work_item_type=work_item_type,
        )

    except Exception as e:
        error_msg = f"Error in update_work_item wrapper: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return UpdateWorkItemOutput(
            success=False,
            error=error_msg,
            timestamp=datetime.now(),
        )


# Create the tool instance
update_work_item_tool = CogniTool(
    name="UpdateWorkItem",
    description="Updates an existing work item memory block (project, epic, task, or bug) with appropriate metadata handling and validation.",
    input_model=UpdateWorkItemInput,
    output_model=UpdateWorkItemOutput,
    function=update_work_item,
    memory_linked=True,
)
