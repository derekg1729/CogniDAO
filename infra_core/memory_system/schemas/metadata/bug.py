"""
Bug metadata schema definition.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import field_validator

from infra_core.memory_system.schemas.metadata.base import BaseMetadata
from ..registry import register_metadata


class BugStatus(str, Enum):
    """Valid status values for a Bug."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    RESOLVED = "resolved"
    CLOSED = "closed"
    WONT_FIX = "wont_fix"
    DUPLICATE = "duplicate"
    CANNOT_REPRODUCE = "cannot_reproduce"


class BugPriority(str, Enum):
    """Valid priority values for a Bug."""

    P0 = "P0"  # Critical
    P1 = "P1"  # High
    P2 = "P2"  # Medium
    P3 = "P3"  # Low
    P4 = "P4"  # Very low
    P5 = "P5"  # Trivial


class BugSeverity(str, Enum):
    """Valid severity levels for a Bug."""

    CRITICAL = "critical"  # System crash, data loss
    MAJOR = "major"  # Major functionality impacted
    MODERATE = "moderate"  # Partial functionality impacted
    MINOR = "minor"  # Minor impact, workaround exists
    TRIVIAL = "trivial"  # Cosmetic issues


class BugMetadata(BaseMetadata):
    """
    Bug metadata schema.

    A Bug represents an issue, defect, or unexpected behavior in software
    that needs to be addressed.
    """

    # Required fields
    reporter: str
    title: str
    description: str

    # Optional fields
    status: str = BugStatus.OPEN.value
    assignee: Optional[str] = None
    priority: Optional[str] = None
    severity: Optional[str] = None
    version_found: Optional[str] = None
    version_fixed: Optional[str] = None
    steps_to_reproduce: Optional[str] = None
    due_date: Optional[datetime] = None
    labels: Optional[List[str]] = None
    confidence_score: Optional[Dict[str, float]] = None

    @field_validator("status")
    def validate_status(cls, v):
        """Validate that the status is one of the allowed values."""
        if v not in [status.value for status in BugStatus]:
            raise ValueError(
                f"Invalid status: {v}. Must be one of: {[status.value for status in BugStatus]}"
            )
        return v

    @field_validator("priority")
    def validate_priority(cls, v):
        """Validate that the priority is one of the allowed values."""
        if v is not None and v not in [priority.value for priority in BugPriority]:
            raise ValueError(
                f"Invalid priority: {v}. Must be one of: {[priority.value for priority in BugPriority]}"
            )
        return v

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
                    "status": "open",
                    "assignee": "user_5678",
                    "priority": "P1",
                    "severity": "major",
                    "version_found": "1.5.2",
                    "steps_to_reproduce": "1. Create a memory block > 10MB\n2. Process it with process_block()\n3. Observe corruption in output",
                    "due_date": "2024-05-15T00:00:00Z",
                    "labels": ["memory", "data-integrity", "high-priority"],
                    "confidence_score": {"human": 0.95, "ai": 0.85},
                }
            ]
        }
    }


# Register this metadata model with the registry
register_metadata("bug", BugMetadata)
