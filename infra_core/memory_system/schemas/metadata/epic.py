"""
Epic metadata schema for MemoryBlocks of type "epic".
"""

from typing import List, Optional, ClassVar, Set
from datetime import datetime
from pydantic import field_validator, model_validator

# Import ExecutableMetadata
from .common.executable import ExecutableMetadata, PriorityLiteral
from ..registry import register_metadata


class EpicMetadata(ExecutableMetadata):
    """
    Epic metadata schema.

    An Epic represents a large body of work that can be broken down into multiple projects,
    tasks, or stories. It typically represents a significant business initiative or a major
    feature set.

    Epics inherit from ExecutableMetadata and support agent execution with:
    - Planning fields (tool_hints, action_items, acceptance_criteria, expected_artifacts)
    - Agent framework fields (execution_timeout_minutes, cost_budget_usd, role_hint)
    - Completion fields (deliverables, validation_report)

    Epics can have relationships via BlockLinks:
    - parent_of: Points to projects that are part of this epic
    - epic_contains: Points to tasks that are part of this epic
    - has_bug: Points to bugs that affect this epic
    """

    # Define allowed status values for Epics
    ALLOWED_STATUS: ClassVar[Set[str]] = {
        "backlog",
        "ready",
        "in_progress",
        "review",
        "blocked",
        "done",
        "archived",
    }

    # Required fields
    # owner: str
    # name: str
    # description: str

    # Optional fields
    start_date: Optional[datetime] = None
    target_date: Optional[datetime] = None
    priority: Optional[PriorityLiteral] = None
    progress_percent: Optional[float] = None
    tags: Optional[List[str]] = None
    completed: bool = False

    @field_validator("progress_percent")
    def validate_progress_percent(cls, v):
        """Validate that the progress percentage is between 0 and 100."""
        if v is not None and (v < 0 or v > 100):
            raise ValueError(f"Invalid progress percentage: {v}. Must be between 0 and 100.")
        return v

    @model_validator(mode="after")
    def check_completed_status(self):
        """Ensure that if completed is True, status is set to done."""
        if self.completed and self.status != "done":
            self.status = "done"
        elif self.status == "done" and not self.completed:
            self.completed = True
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "x_timestamp": "2024-04-30T10:00:00Z",
                    "x_agent_id": "user_1234",
                    "status": "in_progress",
                    "owner": "user_1234",
                    "name": "Memory System Overhaul",
                    "description": "Comprehensive updates to improve memory system reliability and capabilities",
                    "start_date": "2024-04-01T00:00:00Z",
                    "target_date": "2024-06-30T00:00:00Z",
                    "priority": "P1",
                    "progress_percent": 35.0,
                    "tags": ["memory", "reliability", "infrastructure"],
                    "completed": False,
                    "acceptance_criteria": [
                        "All memory system components pass integration tests",
                        "Performance benchmarks show 50% improvement",
                    ],
                }
            ]
        }
    }


# Register this metadata model with the registry
register_metadata("epic", EpicMetadata)
