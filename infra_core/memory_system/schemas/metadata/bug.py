"""
Bug metadata schema for MemoryBlocks of type "bug".
"""

from typing import List, Optional, Dict, ClassVar, Set
from datetime import datetime
from enum import Enum
from pydantic import field_validator, Field

# Import ExecutableMetadata
from .common.executable import ExecutableMetadata, PriorityLiteral
from ..registry import register_metadata


class BugSeverity(str, Enum):
    """Valid severity levels for a Bug."""

    CRITICAL = "critical"  # System crash, data loss
    MAJOR = "major"  # Major functionality impacted
    MODERATE = "moderate"  # Partial functionality impacted
    MINOR = "minor"  # Minor impact, workaround exists
    TRIVIAL = "trivial"  # Cosmetic issues


class BugMetadata(ExecutableMetadata):
    """
    Bug metadata schema.

    A Bug represents an issue, defect, or unexpected behavior in software
    that needs to be addressed.

    Bugs inherit from ExecutableMetadata and support agent execution with:
    - Planning fields (tool_hints, action_items, acceptance_criteria, expected_artifacts)
    - Agent framework fields (execution_timeout_minutes, cost_budget_usd, role_hint)
    - Completion fields (deliverables, validation_report)

    Bugs can have relationships via BlockLinks:
    - bug_affects: Points to a component, project, or system affected by this bug
    - is_blocked_by: Points to another task or bug that is blocking this one
    - blocks: Points to another task or bug that is blocked by this one
    """

    # Define allowed status values for Bugs
    ALLOWED_STATUS: ClassVar[Set[str]] = {
        "backlog",
        "ready",
        "in_progress",
        "blocked",
        "done",
        "released",
    }

    # Required fields
    # reporter: str # Remove
    # title: str # Remove
    # description: str # Remove

    # Optional fields
    priority: Optional[PriorityLiteral] = None
    severity: Optional[str] = None
    version_found: Optional[str] = None
    version_fixed: Optional[str] = None
    steps_to_reproduce: Optional[str] = None
    due_date: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list, description="Tags for categorizing this bug")
    confidence_score: Optional[Dict[str, float]] = None

    # Bug-specific detail fields
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None
    environment: Optional[str] = None
    logs_link: Optional[str] = None
    repro_steps: Optional[List[str]] = None

    @field_validator("severity")
    def validate_severity(cls, v):
        """Validate that the severity is one of the allowed values."""
        if v is not None and v not in [severity.value for severity in BugSeverity]:
            raise ValueError(
                f"Invalid severity: {v}. Must be one of: {[severity.value for severity in BugSeverity]}"
            )
        return v

    @field_validator("confidence_score")
    def validate_confidence_score(cls, v):
        """Validate that confidence score values are between 0 and 1."""
        if v is not None:
            for source, score in v.items():
                if not 0 <= score <= 1:
                    raise ValueError(
                        f"Confidence score for {source} must be between 0 and 1, got {score}"
                    )
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "x_timestamp": "2024-04-30T14:25:00Z",
                    "x_agent_id": "user_1234",
                    "reporter": "user_1234",
                    "title": "Memory corruption when processing large blocks",
                    "description": "When processing memory blocks larger than 10MB, data corruption occurs.",
                    "status": "in_progress",
                    "assignee": "user_5678",
                    "priority": "P1",
                    "severity": "major",
                    "version_found": "1.5.2",
                    "steps_to_reproduce": "1. Create a memory block > 10MB\n2. Process it with process_block()\n3. Observe corruption in output",
                    "due_date": "2024-05-15T00:00:00Z",
                    "tags": ["memory", "data-integrity", "high-priority"],
                    "confidence_score": {"human": 0.95, "ai": 0.85},
                    "expected_behavior": "Data should be processed correctly without corruption",
                    "actual_behavior": "Processed data is corrupted with random values",
                    "environment": "Production server running v1.5.2",
                    "acceptance_criteria": ["No data corruption occurs with 20MB blocks"],
                }
            ]
        }
    }


# Register this metadata model with the registry
register_metadata("bug", BugMetadata)
