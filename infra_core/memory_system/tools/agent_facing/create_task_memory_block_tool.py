"""
CreateTaskMemoryBlockTool: Agent-facing tool for creating 'task' type memory blocks.

This tool provides a simplified interface for agents to create task blocks,
ensuring correct type, metadata structure, and schema validation.
"""

from typing import Optional, List, Literal, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, model_validator
import logging

from ...schemas.common import BlockLink
from ...schemas.memory_block import ConfidenceScore
from ...schemas.metadata.common.executable import (
    PriorityLiteral,
    WorkStatusLiteral,
    ExecutionPhaseLiteral,
    BlockIdType,
)
from ..base.cogni_tool import CogniTool
from ..memory_core.create_memory_block_tool import (
    create_memory_block,
    CreateMemoryBlockInput as CoreCreateMemoryBlockInput,
    CreateMemoryBlockOutput as CoreCreateMemoryBlockOutput,
)

# Setup logging
logger = logging.getLogger(__name__)


class CreateTaskMemoryBlockInput(BaseModel):
    """Input model for creating a 'task' type memory block."""

    # Core task fields
    title: str = Field(..., description="Short, descriptive title of the task.")
    description: str = Field(..., description="Detailed description of what the task involves.")
    assignee: Optional[str] = Field(
        None, description="User ID of the person assigned to this task."
    )

    # Status and planning fields
    status: WorkStatusLiteral = Field(
        "backlog", description="Current status of the task in workflow."
    )
    priority: Optional[PriorityLiteral] = Field(
        None, description="Priority level of the task (P0 highest, P5 lowest)"
    )
    execution_phase: Optional[ExecutionPhaseLiteral] = Field(
        None, description="Current phase of execution when status is 'in_progress'."
    )

    # Time tracking fields
    story_points: Optional[float] = Field(None, description="Story points assigned to this task.")
    estimate_hours: Optional[float] = Field(
        None, description="Estimated hours to complete this task."
    )
    start_date: Optional[datetime] = Field(None, description="When work on this task began.")
    due_date: Optional[datetime] = Field(None, description="Deadline for completing this task.")

    # ExecutableMetadata planning fields
    action_items: List[str] = Field(
        default_factory=list, description="Specific actions needed to complete this task."
    )
    acceptance_criteria: List[str] = Field(
        ..., description="Criteria that must be met for this task to be considered complete."
    )
    expected_artifacts: List[str] = Field(
        default_factory=list, description="Expected deliverables or artifacts to be produced."
    )
    blocked_by: List[BlockIdType] = Field(
        default_factory=list,
        description="IDs of items that must be completed before this one can start.",
    )

    # Agent framework fields
    tool_hints: List[str] = Field(
        default_factory=list, description="Suggested tools to use for executing this task."
    )
    role_hint: Optional[str] = Field(
        None, description="Suggested agent role (e.g., 'developer', 'researcher')."
    )
    execution_timeout_minutes: Optional[int] = Field(
        None, description="Maximum time allowed for execution in minutes."
    )
    cost_budget_usd: Optional[float] = Field(
        None, description="Maximum budget allowed for execution in USD."
    )

    # Labels and additional metadata
    labels: List[str] = Field(
        default_factory=list, description="Labels for categorizing this task."
    )
    confidence_score: Optional[ConfidenceScore] = Field(
        None, description="Confidence scores for this task."
    )

    # Optional phase and implementation details
    phase: Optional[str] = Field(None, description="Project phase this task belongs to.")
    implementation_details: Optional[Dict[str, Any]] = Field(
        None, description="Technical details for implementation (files, endpoints, etc.)"
    )

    # Additional fields from CoreCreateMemoryBlockInput
    source_file: Optional[str] = Field(None, description="Optional source file or markdown name.")
    tags: List[str] = Field(
        default_factory=list, max_length=20, description="Optional tags for filtering."
    )
    state: Optional[Literal["draft", "published", "archived"]] = Field(
        "draft", description="Initial state of the block."
    )
    visibility: Optional[Literal["internal", "public", "restricted"]] = Field(
        "internal", description="Visibility level of the block."
    )
    created_by: Optional[str] = Field(
        "agent", description="Identifier for creator (agent name or user ID)."
    )
    links: Optional[List[BlockLink]] = Field(
        default_factory=list, description="Optional links to other blocks."
    )

    @model_validator(mode="after")
    def validate_execution_phase(self) -> "CreateTaskMemoryBlockInput":
        """Validate that execution_phase is only set when status is 'in_progress'."""
        if self.execution_phase is not None and self.status != "in_progress":
            raise ValueError("execution_phase can only be set when status is 'in_progress'")
        return self


class CreateTaskMemoryBlockOutput(CoreCreateMemoryBlockOutput):
    """Output model for creating a 'task' memory block. Inherits from core output."""

    pass


def create_task_memory_block(
    input_data: CreateTaskMemoryBlockInput, memory_bank
) -> CreateTaskMemoryBlockOutput:
    """
    Create a 'task' type memory block with structured metadata.
    """
    logger.debug(f"Attempting to create 'task' memory block with title: {input_data.title}")

    # Prepare metadata for the 'task' block
    task_specific_metadata = {
        # Required fields
        "title": input_data.title,
        "description": input_data.description,
        # Task-specific optional fields
        "assignee": input_data.assignee,
        "status": input_data.status,
        "priority": input_data.priority,
        "execution_phase": input_data.execution_phase,
        "story_points": input_data.story_points,
        "estimate_hours": input_data.estimate_hours,
        "start_date": input_data.start_date,
        "due_date": input_data.due_date,
        "labels": input_data.labels,
        "confidence_score": input_data.confidence_score,
        "phase": input_data.phase,
        "implementation_details": input_data.implementation_details,
        # ExecutableMetadata planning fields
        "action_items": input_data.action_items,
        "acceptance_criteria": input_data.acceptance_criteria,
        "expected_artifacts": input_data.expected_artifacts,
        "blocked_by": list(input_data.blocked_by),
        # Agent framework fields
        "tool_hints": input_data.tool_hints,
        "role_hint": input_data.role_hint,
        "execution_timeout_minutes": input_data.execution_timeout_minutes,
        "cost_budget_usd": input_data.cost_budget_usd,
        # Mark as completed=False by default
        "completed": False,
    }

    # Filter out None values from task_specific_metadata to keep it clean
    final_metadata = {k: v for k, v in task_specific_metadata.items() if v is not None}

    # Add x_tool_id to identify this agent-facing tool
    final_metadata["x_tool_id"] = "CreateTaskMemoryBlockTool"

    # Create the core input model
    core_input = CoreCreateMemoryBlockInput(
        type="task",  # Automatically set type to "task"
        text=input_data.description,  # Use description as the main text content
        metadata=final_metadata,
        source_file=input_data.source_file,
        tags=input_data.tags,
        state=input_data.state,
        visibility=input_data.visibility,
        confidence=input_data.confidence_score,
        created_by=input_data.created_by,
        links=input_data.links,
    )

    try:
        result = create_memory_block(core_input, memory_bank)
        # The result is already CoreCreateMemoryBlockOutput, which CreateTaskMemoryBlockOutput inherits from
        return CreateTaskMemoryBlockOutput(**result.model_dump())
    except Exception as e:
        error_msg = f"Error in create_task_memory_block wrapper: {str(e)}"
        logger.error(error_msg, exc_info=True)
        # Ensure a consistent error response structure
        return CreateTaskMemoryBlockOutput(
            success=False,
            error=error_msg,
            timestamp=datetime.now(),  # Core tool's error response also includes timestamp
        )


# Create the tool instance
create_task_memory_block_tool = CogniTool(
    name="CreateTaskMemoryBlock",
    description="Creates a new 'task' type memory block with agent execution metadata, enabling task planning and tracking.",
    input_model=CreateTaskMemoryBlockInput,
    output_model=CreateTaskMemoryBlockOutput,
    function=create_task_memory_block,
    memory_linked=True,
)
