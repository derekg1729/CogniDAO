"""
CreateProjectMemoryBlockTool: Agent-facing tool for creating 'project' type memory blocks.

This tool provides a simplified interface for agents to create project blocks,
ensuring correct type, metadata structure, and schema validation.
"""

from typing import Optional, List, Literal, Dict, Union
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from ...schemas.common import BlockLink, BlockIdType
from ...schemas.memory_block import ConfidenceScore
from ...schemas.metadata.common.executable import (
    PriorityLiteral,
    WorkStatusLiteral,
)
from ..base.cogni_tool import CogniTool
from ..memory_core.create_memory_block_tool import (
    create_memory_block,
    CreateMemoryBlockInput as CoreCreateMemoryBlockInput,
    CreateMemoryBlockOutput as CoreCreateMemoryBlockOutput,
)

# Setup logging
logger = logging.getLogger(__name__)


class CreateProjectMemoryBlockInput(BaseModel):
    """Input model for creating a 'project' type memory block."""

    # Core project fields
    name: str = Field(..., description="Short, descriptive name of the project.")
    description: str = Field(
        ..., description="Detailed description of the project purpose and goals."
    )
    owner: str = Field(..., description="User ID of the project owner/lead.")

    # Status and planning fields
    status: WorkStatusLiteral = Field(
        "backlog", description="Current status of the project in workflow."
    )
    priority: Optional[PriorityLiteral] = Field(
        None, description="Priority level of the project (P0 highest, P5 lowest)"
    )

    # Time tracking fields
    start_date: Optional[datetime] = Field(None, description="When work on this project began.")
    target_date: Optional[datetime] = Field(
        None, description="Target completion date for the project."
    )
    progress_percent: Optional[float] = Field(
        None, ge=0, le=100, description="Percentage completion of the project (0-100)."
    )

    # ExecutableMetadata planning fields
    action_items: List[str] = Field(
        default_factory=list, description="Specific actions needed to complete this project."
    )
    acceptance_criteria: List[str] = Field(
        ...,
        min_length=1,
        description="Criteria that must be met for this project to be considered complete.",
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
        default_factory=list, description="Suggested tools to use for executing this project."
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

    # Project-specific fields
    tags: List[str] = Field(
        default_factory=list, description="Tags/labels for categorizing this project."
    )
    confidence_score: Optional[ConfidenceScore] = Field(
        None, description="Confidence scores for this project."
    )
    phase: Optional[str] = Field(
        None,
        description="Current phase of the project (e.g., 'Phase 1: Schema + Rapid Indexing Loop').",
    )
    implementation_flow: Optional[List[str]] = Field(
        default_factory=list, description="List of tasks or phases in the implementation flow."
    )
    success_criteria: Optional[List[Dict[str, Union[str, List[str]]]]] = Field(
        default_factory=list, description="List of measurable outcomes that define project success."
    )
    design_decisions: Optional[Dict[str, str]] = Field(
        None, description="Key design decisions and rationales for the project."
    )
    references: Optional[Dict[str, str]] = Field(
        None, description="References to related documentation or resources."
    )

    # Additional fields from CoreCreateMemoryBlockInput
    source_file: Optional[str] = Field(None, description="Optional source file or markdown name.")
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


class CreateProjectMemoryBlockOutput(CoreCreateMemoryBlockOutput):
    """Output model for creating a 'project' memory block. Inherits from core output."""

    pass


def create_project_memory_block(
    input_data: CreateProjectMemoryBlockInput, memory_bank
) -> CreateProjectMemoryBlockOutput:
    """
    Create a 'project' type memory block with structured metadata.
    """
    logger.debug(f"Attempting to create 'project' memory block with name: {input_data.name}")

    # Prepare metadata for the 'project' block
    project_specific_metadata = {
        # Required fields
        "name": input_data.name,
        "description": input_data.description,
        "owner": input_data.owner,
        # Project-specific optional fields
        "status": input_data.status,
        "priority": input_data.priority,
        "start_date": input_data.start_date,
        "target_date": input_data.target_date,
        "progress_percent": input_data.progress_percent,
        "tags": input_data.tags,
        "confidence_score": input_data.confidence_score,
        "phase": input_data.phase,
        "implementation_flow": input_data.implementation_flow,
        "success_criteria": input_data.success_criteria,
        "design_decisions": input_data.design_decisions,
        "references": input_data.references,
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

    # Filter out None values from project_specific_metadata to keep it clean
    final_metadata = {k: v for k, v in project_specific_metadata.items() if v is not None}

    # Add x_tool_id to identify this agent-facing tool
    final_metadata["x_tool_id"] = "CreateProjectMemoryBlockTool"

    # Create the core input model
    core_input = CoreCreateMemoryBlockInput(
        type="project",  # Automatically set type to "project"
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
        # The result is already CoreCreateMemoryBlockOutput, which CreateProjectMemoryBlockOutput inherits from
        return CreateProjectMemoryBlockOutput(**result.model_dump())
    except Exception as e:
        error_msg = f"Error in create_project_memory_block wrapper: {str(e)}"
        logger.error(error_msg, exc_info=True)
        # Ensure a consistent error response structure
        return CreateProjectMemoryBlockOutput(
            success=False,
            error=error_msg,
            timestamp=datetime.now(),  # Core tool's error response also includes timestamp
        )


# Create the tool instance
create_project_memory_block_tool = CogniTool(
    name="CreateProjectMemoryBlock",
    description="Creates a new 'project' type memory block with agent execution metadata, enabling project planning and tracking.",
    input_model=CreateProjectMemoryBlockInput,
    output_model=CreateProjectMemoryBlockOutput,
    function=create_project_memory_block,
    memory_linked=True,
)
