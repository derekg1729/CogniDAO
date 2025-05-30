"""
CreateWorkItemTool: Agent-facing tool for creating different types of work items.

This tool provides a unified interface for creating project, epic, task, and bug memory blocks,
ensuring correct type, metadata structure, and schema validation.
"""

from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field, model_validator
import logging

from ...schemas.common import BlockLink, BlockIdType
from ...schemas.memory_block import ConfidenceScore
from ...schemas.metadata.common.executable import (
    PriorityLiteral,
    WorkStatusLiteral,
    ExecutionPhaseLiteral,
)
from ..base.cogni_tool import CogniTool
from ..memory_core.create_memory_block_tool import (
    create_memory_block,
    CreateMemoryBlockInput as CoreCreateMemoryBlockInput,
    CreateMemoryBlockOutput as CoreCreateMemoryBlockOutput,
)

# Setup logging
logger = logging.getLogger(__name__)

# Define work item types
WorkItemTypeLiteral = Literal["project", "epic", "task", "bug"]


class CreateWorkItemInput(BaseModel):
    """Input model for creating various types of work item memory blocks."""

    # Required fields
    type: WorkItemTypeLiteral = Field(
        ..., description="Type of work item to create: project, epic, task, or bug"
    )
    title: str = Field(..., description="Short, descriptive title of the work item")
    description: str = Field(..., description="Detailed description of the work item")

    # Common fields across work item types
    owner: Optional[str] = Field(None, description="Owner or assignee of the work item")
    status: Optional[WorkStatusLiteral] = Field(
        "backlog", description="Current status of the work item"
    )
    priority: Optional[PriorityLiteral] = Field(None, description="Priority level of the work item")

    # Planning and tracking fields
    acceptance_criteria: List[str] = Field(
        ..., description="Criteria that must be met for this item to be considered complete"
    )
    action_items: List[str] = Field(
        default_factory=list, description="Specific actions needed to complete this item"
    )
    expected_artifacts: List[str] = Field(
        default_factory=list, description="Expected deliverables or artifacts to be produced"
    )
    blocked_by: List[BlockIdType] = Field(
        default_factory=list,
        description="IDs of items that must be completed before this one can start",
    )

    # Time tracking and estimation
    story_points: Optional[float] = Field(None, description="Story points assigned to this item")
    estimate_hours: Optional[float] = Field(
        None, description="Estimated hours to complete this item"
    )

    # Additional fields
    tags: List[str] = Field(
        default_factory=list, description="Tags for categorizing this work item"
    )
    labels: List[str] = Field(
        default_factory=list, description="Labels for categorizing this work item"
    )

    # Agent framework fields
    tool_hints: List[str] = Field(
        default_factory=list, description="Suggested tools to use for executing this item"
    )
    role_hint: Optional[str] = Field(
        None, description="Suggested agent role (e.g., 'developer', 'researcher')"
    )
    execution_timeout_minutes: Optional[int] = Field(
        None, description="Maximum time allowed for execution in minutes"
    )
    cost_budget_usd: Optional[float] = Field(
        None, description="Maximum budget allowed for execution in USD"
    )

    # Additional type-specific fields
    execution_phase: Optional[ExecutionPhaseLiteral] = Field(
        None, description="Current phase of execution when status is 'in_progress'"
    )

    # Standard memory block fields
    source_file: Optional[str] = Field(None, description="Optional source file or markdown name")
    state: Optional[Literal["draft", "published", "archived"]] = Field(
        "draft", description="Initial state of the block"
    )
    visibility: Optional[Literal["internal", "public", "restricted"]] = Field(
        "internal", description="Visibility level of the block"
    )
    confidence: Optional[ConfidenceScore] = Field(
        None, description="Confidence scores for the block"
    )
    created_by: Optional[str] = Field(
        "agent", description="Identifier for creator (agent name or user ID)"
    )
    links: Optional[List[BlockLink]] = Field(
        default_factory=list, description="Optional links to other blocks"
    )

    @model_validator(mode="after")
    def validate_execution_phase(self) -> "CreateWorkItemInput":
        """Validate that execution_phase is only set when status is 'in_progress'."""
        if self.execution_phase is not None and self.status != "in_progress":
            raise ValueError("execution_phase can only be set when status is 'in_progress'")
        return self


class CreateWorkItemOutput(CoreCreateMemoryBlockOutput):
    """Output model for work item creation results."""

    work_item_type: Optional[str] = Field(None, description="Type of work item that was created")


def create_work_item(input_data: CreateWorkItemInput, memory_bank) -> CreateWorkItemOutput:
    """
    Create a work item memory block with type-specific validation and metadata.

    This function handles the creation of project, epic, task, and bug memory blocks
    with appropriate metadata based on the specified type.

    Args:
        input_data: Input data for creating the work item
        memory_bank: StructuredMemoryBank instance for persistence

    Returns:
        CreateWorkItemOutput containing creation status, ID, and timestamp
    """
    logger.debug(f"Attempting to create '{input_data.type}' work item: {input_data.title}")

    # Validate owner field for project and epic types
    if input_data.type in ["project", "epic"] and not input_data.owner:
        error_msg = f"{input_data.type} owner cannot be null or empty"
        logger.error(error_msg)
        return CreateWorkItemOutput(
            success=False, error=error_msg, timestamp=datetime.now(), work_item_type=input_data.type
        )

    # Prepare common metadata fields
    metadata = {
        # Core fields
        "title": input_data.title,
        "description": input_data.description,
        "status": input_data.status,
        "priority": input_data.priority,
        # Planning fields
        "acceptance_criteria": input_data.acceptance_criteria,
        "action_items": input_data.action_items,
        "expected_artifacts": input_data.expected_artifacts,
        "blocked_by": list(input_data.blocked_by),
        # Estimation fields
        "story_points": input_data.story_points,
        "estimate_hours": input_data.estimate_hours,
        # Additional fields
        "labels": input_data.labels,
        # Agent framework fields
        "tool_hints": input_data.tool_hints,
        "role_hint": input_data.role_hint,
        "execution_timeout_minutes": input_data.execution_timeout_minutes,
        "cost_budget_usd": input_data.cost_budget_usd,
    }

    # Add type-specific fields
    if input_data.owner is not None:
        metadata["assignee"] = input_data.owner

    if input_data.execution_phase and input_data.type in ["task", "bug"]:
        metadata["execution_phase"] = input_data.execution_phase

    # Add tool identifier
    metadata["x_tool_id"] = "CreateWorkItemTool"

    # Filter out None values
    final_metadata = {k: v for k, v in metadata.items() if v is not None}

    # Create the core input model
    core_input = CoreCreateMemoryBlockInput(
        type=input_data.type,
        text=input_data.description,
        metadata=final_metadata,
        tags=input_data.tags,
        source_file=input_data.source_file,
        state=input_data.state,
        visibility=input_data.visibility,
        confidence=input_data.confidence,
        created_by=input_data.created_by,
    )

    try:
        # Use the existing create_memory_block function
        result = create_memory_block(core_input, memory_bank)

        # Return enhanced output with work item type
        # Create a new output object instead of passing work_item_type as a parameter
        output = CreateWorkItemOutput(
            success=result.success,
            id=result.id,
            error=result.error,
            timestamp=result.timestamp,
            work_item_type=input_data.type,
        )
        return output
    except Exception as e:
        error_msg = f"Error in create_work_item wrapper: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return CreateWorkItemOutput(
            success=False, error=error_msg, timestamp=datetime.now(), work_item_type=input_data.type
        )


# Create the tool instance
create_work_item_tool = CogniTool(
    name="CreateWorkItem",
    description="Creates a new work item memory block (project, epic, task, or bug) with appropriate metadata structure.",
    input_model=CreateWorkItemInput,
    output_model=CreateWorkItemOutput,
    function=create_work_item,
    memory_linked=True,
)
