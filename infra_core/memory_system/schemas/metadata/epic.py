"""
Epic metadata schema definition.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import field_validator, model_validator

from infra_core.memory_system.schemas.metadata.base import BaseMetadata
from ..registry import register_metadata


class EpicStatus(str, Enum):
    """Valid status values for an Epic."""

    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class EpicPriority(str, Enum):
    """Valid priority values for an Epic."""

    P0 = "P0"  # Most critical
    P1 = "P1"  # Very important
    P2 = "P2"  # Important
    P3 = "P3"  # Normal
    P4 = "P4"  # Low
    P5 = "P5"  # Very low


class EpicMetadata(BaseMetadata):
    """
    Epic metadata schema.

    An Epic represents a large body of work that can be broken down into multiple projects,
    tasks, or stories. It typically represents a significant business initiative or a major
    feature set.
    """

    # Required fields
    owner: str
    name: str
    description: str

    # Optional fields
    status: str = EpicStatus.PLANNING.value
    start_date: Optional[datetime] = None
    target_date: Optional[datetime] = None
    priority: Optional[str] = None
    progress_percent: Optional[float] = None
    tags: Optional[List[str]] = None
    completed: bool = False

    @field_validator("status")
    def validate_status(cls, v):
        """Validate that the status is one of the allowed values."""
        if v not in [status.value for status in EpicStatus]:
            raise ValueError(
                f"Invalid status: {v}. Must be one of: {[status.value for status in EpicStatus]}"
            )
        return v

    @field_validator("priority")
    def validate_priority(cls, v):
        """Validate that the priority is one of the allowed values."""
        if v is not None and v not in [priority.value for priority in EpicPriority]:
            raise ValueError(
                f"Invalid priority: {v}. Must be one of: {[priority.value for priority in EpicPriority]}"
            )
        return v

    @field_validator("progress_percent")
    def validate_progress_percent(cls, v):
        """Validate that the progress percentage is between 0 and 100."""
        if v is not None and (v < 0 or v > 100):
            raise ValueError(f"Invalid progress percentage: {v}. Must be between 0 and 100.")
        return v

    @model_validator(mode="after")
    def check_completed_status(self):
        """Ensure that if completed is True, status is set to COMPLETED."""
        if self.completed and self.status != EpicStatus.COMPLETED.value:
            self.status = EpicStatus.COMPLETED.value
        elif self.status == EpicStatus.COMPLETED.value and not self.completed:
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
                }
            ]
        }
    }


# Register this metadata model with the registry
register_metadata("epic", EpicMetadata)
