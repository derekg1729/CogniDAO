"""
Project metadata schema for MemoryBlocks of type "project".
"""

from typing import List, Optional, Dict, Union
from datetime import datetime
from pydantic import Field

# Import BaseMetadata
from .base import BaseMetadata
from ..registry import register_metadata
from ..common import ConfidenceScore


class ProjectMetadata(BaseMetadata):
    """
    Metadata schema for MemoryBlocks of type "project".
    Based on the link-first relationship approach where BlockLink is the source of truth for relationships.

    Projects can have the following relationships via BlockLinks:
    - child_of: Points to a parent project that this project is part of
    - parent_of: Points to a child project that is part of this project
    - belongs_to_epic: Points to an epic that this project is part of
    - epic_contains: Points to an epic that is related to this project (if project contains epics)
    - has_bug: Points to a bug that is related to this project
    """

    status: str = Field(
        "backlog",
        description="Current status of the project",
        pattern="^(backlog|in_progress|blocked|done)$",
    )
    owner: str = Field(..., description="User ID of the project owner/lead")
    name: str = Field(..., description="Short, descriptive name of the project")
    description: str = Field(
        ..., description="Detailed description of the project purpose and goals"
    )
    priority: Optional[str] = Field(
        None,
        description="Priority level of the project (P0 highest, P3 lowest)",
        pattern="^(P0|P1|P2|P3)$",
    )
    start_date: Optional[datetime] = Field(None, description="When work on this project began")
    target_date: Optional[datetime] = Field(
        None, description="Target completion date for the project"
    )
    progress_percent: Optional[float] = Field(
        None, ge=0, le=100, description="Percentage completion of the project (0-100)"
    )
    tags: List[str] = Field(
        default_factory=list, description="Tags/labels for categorizing this project"
    )
    confidence_score: Optional[ConfidenceScore] = Field(
        None, description="Confidence scores for this project"
    )
    phase: Optional[str] = Field(
        None,
        description="Current phase of the project (e.g., 'Phase 1: Schema + Rapid Indexing Loop')",
    )
    implementation_flow: Optional[List[str]] = Field(
        default_factory=list, description="List of tasks or phases in the implementation flow"
    )
    success_criteria: Optional[List[Dict[str, Union[str, List[str]]]]] = Field(
        default_factory=list, description="List of measurable outcomes that define project success"
    )
    completed: bool = Field(False, description="Whether the project is marked as complete")
    design_decisions: Optional[Dict[str, str]] = Field(
        default_factory=dict, description="Key design decisions and rationales for the project"
    )
    references: Optional[Dict[str, str]] = Field(
        default_factory=dict, description="References to related documentation or resources"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "x_timestamp": "2024-04-30T10:00:00Z",
                    "x_agent_id": "user_1234",
                    "status": "in_progress",
                    "owner": "user_1234",
                    "name": "Memory System Block Links",
                    "description": "Implement link-first relationship approach for memory blocks",
                    "priority": "P1",
                    "start_date": "2024-04-15T00:00:00Z",
                    "target_date": "2024-05-30T00:00:00Z",
                    "progress_percent": 40.0,
                    "tags": ["memory-system", "links", "infrastructure"],
                    "phase": "Phase 1: Schema Enhancement",
                    "implementation_flow": ["task-3.1", "task-3.2"],
                    "success_criteria": [
                        {"phase_1": ["BlockLink as source of truth for relationships"]}
                    ],
                    "completed": False,
                }
            ]
        }
    }


# Register this metadata model with the registry
register_metadata("project", ProjectMetadata)
