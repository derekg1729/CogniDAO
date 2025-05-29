"""
ExecutableMetadata mixin for agent-executable memory blocks.

This mixin adds fields related to planning, execution, and validation
that are shared across Task, Bug, Project, and Epic metadata models.
"""

from typing import List, Optional, Literal, ClassVar, Set
from pydantic import Field, validator, model_validator

from ..base_user import BaseUserMetadata
from .validation import ValidationReport
from ....schemas.common import BlockIdType

# Status and phase literals for executable memory blocks
WorkStatusLiteral = Literal[
    "backlog",  # Not yet started, in the queue
    "ready",  # Ready to be worked on
    "in_progress",  # Currently being worked on
    "review",  # Under review
    "merged",  # Code or content has been merged
    "validated",  # Has been validated against criteria
    "released",  # Released to production or published
    "done",  # Complete and no further action needed
    "archived",  # No longer active but preserved for reference
]

ExecutionPhaseLiteral = Literal[
    "designing",  # Planning or designing the solution
    "implementing",  # Actively implementing the solution
    "testing",  # Testing the implementation
    "debugging",  # Fixing issues found in testing
    "documenting",  # Creating or updating documentation
    "awaiting_review",  # Implementation complete, waiting for review
]

# Priority literal for consistent priorities across models
PriorityLiteral = Literal["P0", "P1", "P2", "P3", "P4", "P5"]


class ExecutableMetadata(BaseUserMetadata):
    """
    Mixin class for metadata models that represent executable work items.

    Extends BaseMetadata with fields for agent execution, including planning fields
    (pre-execution), agent framework compatibility fields, and completion fields
    (post-execution).

    This mixin should be inherited by Task, Bug, Project, and Epic metadata models.
    """

    # Status mapping with allowed values for each subclass type
    # This will be overridden by each subclass
    ALLOWED_STATUS: ClassVar[Set[str]] = {
        "backlog",
        "ready",
        "in_progress",
        "review",
        "merged",
        "validated",
        "released",
        "done",
        "archived",
        "blocked",
    }

    # Common fields for all executable metadata
    status: WorkStatusLiteral = Field("backlog", description="Top-level workflow state")
    assignee: Optional[str] = Field(None, description="Assignee or owner of this work item")

    # Planning fields (pre-execution)
    tool_hints: List[str] = Field(
        default_factory=list, description="Suggested tools to use for executing this item"
    )
    action_items: List[str] = Field(
        default_factory=list, description="Specific actions needed to complete this item"
    )
    acceptance_criteria: List[str] = Field(
        default_factory=list,
        description="Criteria that must be met for this item to be considered complete",
    )
    expected_artifacts: List[str] = Field(
        default_factory=list, description="Expected deliverables or artifacts to be produced"
    )
    blocked_by: List[BlockIdType] = Field(
        default_factory=list,
        description="IDs of items that must be completed before this one can start (UUID format)",
    )
    priority_score: Optional[float] = Field(
        None, description="Numeric priority score (higher = more important)", ge=0
    )
    reviewer: Optional[str] = Field(
        None, description="ID of user or agent responsible for reviewing this item"
    )

    # Agent framework compatibility fields
    execution_timeout_minutes: Optional[int] = Field(
        None, description="Maximum time allowed for execution in minutes", ge=0
    )
    cost_budget_usd: Optional[float] = Field(
        None, description="Maximum budget allowed for execution in USD", ge=0
    )
    role_hint: Optional[str] = Field(
        None, description="Suggested agent role (e.g., 'developer', 'researcher')"
    )

    # Execution phase tracking
    execution_phase: Optional[ExecutionPhaseLiteral] = Field(
        None, description="Current phase of execution when status is 'in_progress'"
    )

    # Completion fields (post-execution)
    deliverables: List[str] = Field(
        default_factory=list, description="Actual artifacts or file paths produced during execution"
    )
    validation_report: Optional[ValidationReport] = Field(
        None, description="Validation results for all acceptance criteria"
    )

    @validator("acceptance_criteria")
    def validate_acceptance_criteria(cls, v):
        """Ensure at least one acceptance criterion is provided."""
        if not v:
            raise ValueError("At least one acceptance criterion is required")
        return v

    @model_validator(mode="after")
    def _validate_status_and_execution(self):
        """
        Validates:
        1. Status is in the allowed set for this class type
        2. Execution phase is only set when status is 'in_progress'
        3. Validation report is provided when status is 'done'
        """
        # Check if status is in the allowed set for this type
        if self.status not in self.ALLOWED_STATUS:
            allowed_str = ", ".join(f"'{s}'" for s in sorted(self.ALLOWED_STATUS))
            raise ValueError(
                f"Status '{self.status}' not allowed for {self.__class__.__name__}. "
                f"Allowed values: {allowed_str}"
            )

        # Check execution phase is only set when status is 'in_progress'
        if self.execution_phase is not None and self.status != "in_progress":
            raise ValueError("execution_phase can only be set when status is 'in_progress'")

        # Check for validation report when status is 'done' or 'released'
        if self.status in ["done", "released"] and self.validation_report is None:
            raise ValueError("A validation report is required when status is 'done' or 'released'")

        # Ensure all validation results pass if provided
        if self.validation_report is not None:
            # Ensure all results are passing
            failing_results = [r for r in self.validation_report.results if r.status == "fail"]
            if failing_results:
                failing_criteria = [r.criterion for r in failing_results]
                raise ValueError(
                    f"Validation failed for the following criteria: {', '.join(failing_criteria)}"
                )

        return self
