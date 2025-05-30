"""
Task metadata schema for MemoryBlocks of type "task".
"""

from typing import List, Optional, Dict, Any, ClassVar, Set
from datetime import datetime
from pydantic import Field

# Import ExecutableMetadata
from .common.executable import ExecutableMetadata, PriorityLiteral
from ..registry import register_metadata
from ..common import ConfidenceScore


class TaskMetadata(ExecutableMetadata):
    """
    Metadata schema for MemoryBlocks of type "task".
    Based on the link-first relationship approach where BlockLink is the source of truth for relationships.

    Tasks can have the following relationships via BlockLinks:
    - subtask_of: Points to a parent task or project that this task is part of
    - depends_on: Points to another task that must be completed before this one can start
    - belongs_to_epic: Points to an epic that this task is part of
    - blocks: Points to another task that cannot proceed until this one is complete
    - is_blocked_by: Points to another task that is blocking this one
    - has_bug: Points to a bug that is related to this task

    Tasks inherit from ExecutableMetadata and support agent execution with:
    - Planning fields (tool_hints, action_items, acceptance_criteria, expected_artifacts)
    - Agent framework fields (execution_timeout_minutes, cost_budget_usd, role_hint)
    - Completion fields (deliverables, validation_report)
    """

    # Define allowed status values for Tasks
    ALLOWED_STATUS: ClassVar[Set[str]] = {
        "backlog",
        "ready",
        "in_progress",
        "review",
        "blocked",
        "done",
    }

    priority: Optional[PriorityLiteral] = Field(
        None, description="Priority level of the task (P0 highest, P5 lowest)"
    )
    story_points: Optional[float] = Field(None, description="Story points assigned to this task")
    estimate_hours: Optional[float] = Field(
        None, description="Estimated hours to complete this task"
    )
    start_date: Optional[datetime] = Field(None, description="When work on this task began")
    due_date: Optional[datetime] = Field(None, description="Deadline for completing this task")
    labels: List[str] = Field(default_factory=list, description="Labels for categorizing this task")
    confidence_score: Optional[ConfidenceScore] = Field(
        None, description="Confidence scores for this task"
    )
    # Retain additional fields for backward compatibility
    phase: Optional[str] = Field(None, description="Project phase this task belongs to")
    implementation_details: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Technical details for implementation (files, endpoints, etc.)",
    )
    current_status: Optional[str] = Field(
        None, description="Detailed description of current implementation state"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "x_timestamp": "2024-04-30T11:30:00Z",
                    "x_agent_id": "user_5678",
                    "status": "in_progress",
                    "assignee": "user_1234",
                    "title": "Implement BlockLink Validation",
                    "description": "Create validation logic for BlockLinks to prevent circular dependencies",
                    "priority": "P2",
                    "story_points": 3.0,
                    "estimate_hours": 6.0,
                    "start_date": "2024-04-20T00:00:00Z",
                    "due_date": "2024-05-05T00:00:00Z",
                    "labels": ["link-manager", "validation", "technical-debt"],
                    "phase": "Implementation",
                    "implementation_details": {
                        "target_file": "infra_core/memory_system/link_manager.py"
                    },
                    "action_items": [
                        "Create validation rules",
                        "Write unit tests",
                        "Integrate with LinkManager",
                    ],
                    "acceptance_criteria": [
                        "All validation rules pass",
                        "Circular dependencies are prevented",
                    ],
                }
            ]
        }
    }


# Register this metadata model with the registry
register_metadata("task", TaskMetadata)
