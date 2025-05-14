"""
CreateBugMemoryBlockTool: Agent-facing tool for creating 'bug' type memory blocks.

This tool provides a simplified interface for agents to create bug blocks,
ensuring correct type, metadata structure, and schema validation.
"""

from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator
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


class BugSeverity(str, Enum):
    """Valid severity levels for a Bug."""

    CRITICAL = "critical"  # System crash, data loss
    MAJOR = "major"  # Major functionality impacted
    MODERATE = "moderate"  # Partial functionality impacted
    MINOR = "minor"  # Minor impact, workaround exists
    TRIVIAL = "trivial"  # Cosmetic issues


class CreateBugMemoryBlockInput(BaseModel):
    """Input model for creating a 'bug' type memory block."""

    # Core bug fields
    title: str = Field(..., description="Short, descriptive title of the bug.")
    description: str = Field(..., description="Detailed description of the bug issue.")
    reporter: str = Field(..., description="User ID of the person who reported this bug.")

    # Assignment and status fields
    assignee: Optional[str] = Field(
        None, description="User ID of the person assigned to fix this bug."
    )
    status: WorkStatusLiteral = Field(
        "backlog", description="Current status of the bug in workflow."
    )
    priority: Optional[PriorityLiteral] = Field(
        None, description="Priority level of the bug (P0 highest, P5 lowest)"
    )
    severity: Optional[str] = Field(
        None, description="Severity level of the bug (critical, major, moderate, minor, trivial)."
    )

    # Version tracking fields
    version_found: Optional[str] = Field(None, description="Software version where bug was found.")
    version_fixed: Optional[str] = Field(None, description="Software version where bug was fixed.")
    due_date: Optional[datetime] = Field(None, description="Deadline for fixing this bug.")

    # ExecutableMetadata planning fields
    action_items: List[str] = Field(
        default_factory=list, description="Specific actions needed to fix this bug."
    )
    acceptance_criteria: List[str] = Field(
        ...,
        min_length=1,
        description="Criteria that must be met for this bug to be considered fixed.",
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
        default_factory=list, description="Suggested tools to use for fixing this bug."
    )
    role_hint: Optional[str] = Field(
        None, description="Suggested agent role (e.g., 'developer', 'tester')."
    )
    execution_timeout_minutes: Optional[int] = Field(
        None, description="Maximum time allowed for execution in minutes."
    )
    cost_budget_usd: Optional[float] = Field(
        None, description="Maximum budget allowed for execution in USD."
    )

    # Bug-specific detail fields
    steps_to_reproduce: Optional[str] = Field(
        None, description="Step-by-step instructions to reproduce the bug."
    )
    expected_behavior: Optional[str] = Field(
        None, description="Description of the expected correct behavior."
    )
    actual_behavior: Optional[str] = Field(
        None, description="Description of the actual incorrect behavior."
    )
    environment: Optional[str] = Field(
        None, description="Details about the environment where the bug occurs (OS, browser, etc.)."
    )
    logs_link: Optional[str] = Field(None, description="Link to relevant logs or error messages.")
    repro_steps: Optional[List[str]] = Field(
        None, description="Structured list of steps to reproduce the issue."
    )

    # Classification fields
    labels: List[str] = Field(default_factory=list, description="Labels for categorizing this bug.")
    confidence_score: Optional[ConfidenceScore] = Field(
        None, description="Confidence scores for this bug."
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

    @field_validator("severity")
    def validate_severity(cls, v):
        """Validate that the severity is one of the allowed values."""
        if v is not None and v not in [severity.value for severity in BugSeverity]:
            raise ValueError(
                f"Invalid severity: {v}. Must be one of: {[severity.value for severity in BugSeverity]}"
            )
        return v


class CreateBugMemoryBlockOutput(CoreCreateMemoryBlockOutput):
    """Output model for creating a 'bug' memory block. Inherits from core output."""

    pass


def create_bug_memory_block(
    input_data: CreateBugMemoryBlockInput, memory_bank
) -> CreateBugMemoryBlockOutput:
    """
    Create a 'bug' type memory block with structured metadata.
    """
    logger.debug(f"Attempting to create 'bug' memory block with title: {input_data.title}")

    # Prepare metadata for the 'bug' block
    bug_specific_metadata = {
        # Required fields
        "title": input_data.title,
        "description": input_data.description,
        "reporter": input_data.reporter,
        # Bug-specific optional fields
        "assignee": input_data.assignee,
        "status": input_data.status,
        "priority": input_data.priority,
        "severity": input_data.severity,
        "version_found": input_data.version_found,
        "version_fixed": input_data.version_fixed,
        "due_date": input_data.due_date,
        "steps_to_reproduce": input_data.steps_to_reproduce,
        "expected_behavior": input_data.expected_behavior,
        "actual_behavior": input_data.actual_behavior,
        "environment": input_data.environment,
        "logs_link": input_data.logs_link,
        "repro_steps": input_data.repro_steps,
        "labels": input_data.labels,
        "confidence_score": input_data.confidence_score,
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

    # Filter out None values from bug_specific_metadata to keep it clean
    final_metadata = {k: v for k, v in bug_specific_metadata.items() if v is not None}

    # Add x_tool_id to identify this agent-facing tool
    final_metadata["x_tool_id"] = "CreateBugMemoryBlockTool"

    # Create the core input model
    core_input = CoreCreateMemoryBlockInput(
        type="bug",  # Automatically set type to "bug"
        text=input_data.description,  # Use description as the main text content
        metadata=final_metadata,
        source_file=input_data.source_file,
        tags=input_data.labels,  # Use labels as tags for bugs
        state=input_data.state,
        visibility=input_data.visibility,
        confidence=input_data.confidence_score,
        created_by=input_data.created_by,
        links=input_data.links,
    )

    try:
        result = create_memory_block(core_input, memory_bank)
        # The result is already CoreCreateMemoryBlockOutput, which CreateBugMemoryBlockOutput inherits from
        return CreateBugMemoryBlockOutput(**result.model_dump())
    except Exception as e:
        error_msg = f"Error in create_bug_memory_block wrapper: {str(e)}"
        logger.error(error_msg, exc_info=True)
        # Ensure a consistent error response structure
        return CreateBugMemoryBlockOutput(
            success=False,
            error=error_msg,
            timestamp=datetime.now(),  # Core tool's error response also includes timestamp
        )


# Create the tool instance
create_bug_memory_block_tool = CogniTool(
    name="CreateBugMemoryBlock",
    description="Creates a new 'bug' type memory block with agent execution metadata, enabling bug tracking and resolution.",
    input_model=CreateBugMemoryBlockInput,
    output_model=CreateBugMemoryBlockOutput,
    function=create_bug_memory_block,
    memory_linked=True,
)
