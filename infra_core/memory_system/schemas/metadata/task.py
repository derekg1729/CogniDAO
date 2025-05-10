"""
Task metadata schema for MemoryBlocks of type "task".
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import Field

# Import BaseMetadata
from .base import BaseMetadata
from ..registry import register_metadata


class TaskMetadata(BaseMetadata):
    """
    Metadata schema for MemoryBlocks of type "task".
    Based on the structure of task files in experiments/docs/roadmap/tasks/task-*.json.
    """

    status: Literal["todo", "in-progress", "completed", "blocked"] = Field(
        "todo", description="Current status of the task"
    )
    project: str = Field(..., description="The project this task belongs to")
    name: str = Field(..., description="Short, descriptive name of the task")
    description: str = Field(..., description="Detailed description of what the task involves")
    phase: Optional[str] = Field(None, description="Project phase this task belongs to")
    implementation_details: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Technical details for implementation (files, endpoints, etc.)",
    )
    action_items: Optional[List[str]] = Field(
        default_factory=list, description="Specific steps required to complete the task"
    )
    test_criteria: Optional[List[str]] = Field(
        default_factory=list, description="Criteria to verify the task is implemented correctly"
    )
    success_criteria: Optional[List[str]] = Field(
        default_factory=list, description="Criteria to verify the task meets its objectives"
    )
    completed: bool = Field(False, description="Whether the task is marked as complete")
    priority: Optional[int] = Field(
        None, ge=1, le=5, description="Priority level (1-5, where 1 is highest priority)"
    )
    assignee: Optional[str] = Field(None, description="Person or agent assigned to this task")
    current_status: Optional[str] = Field(
        None, description="Detailed description of current implementation state"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "todo",
                    "project": "CogniMemorySystem-POC",
                    "name": "Define and Register Block Type Schemas",
                    "description": "Create structured Pydantic sub-schemas",
                    "phase": "Phase 2: Full Indexing System",
                    "implementation_details": {
                        "target_file": "infra_core/memorysystem/schemas/memory_block.py"
                    },
                    "action_items": ["Define Pydantic models"],
                    "test_criteria": ["All models pass validation"],
                    "completed": False,
                    "priority": 1,
                    "assignee": "agent_1",
                }
            ]
        }
    }


# Register this metadata model with the registry
register_metadata("task", TaskMetadata)
