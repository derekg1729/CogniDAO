"""
Project metadata schema for MemoryBlocks of type "project".
"""

from typing import List, Optional, Dict, Union, Literal
from datetime import datetime
from pydantic import BaseModel, Field

from ..registry import register_metadata

class ProjectMetadata(BaseModel):
    """
    Metadata schema for MemoryBlocks of type "project".
    Based on the structure of project files in experiments/docs/roadmap/project-*.json.
    """
    status: Literal["planning", "in-progress", "completed", "archived"] = Field(
        "planning", 
        description="Current status of the project"
    )
    epic: Optional[str] = Field(
        None, 
        description="Reference to an epic or larger initiative this project belongs to"
    )
    name: str = Field(
        ..., 
        description="Short, descriptive name of the project"
    )
    description: str = Field(
        ..., 
        description="Detailed description of the project purpose and goals"
    )
    phase: Optional[str] = Field(
        None, 
        description="Current phase of the project (e.g., '🧱 Phase 1: Schema + Rapid Indexing Loop')"
    )
    implementation_flow: Optional[List[str]] = Field(
        default_factory=list, 
        description="List of tasks or phases in the implementation flow"
    )
    success_criteria: Optional[List[Dict[str, Union[str, List[str]]]]] = Field(
        default_factory=list, 
        description="List of measurable outcomes that define project success"
    )
    completed: bool = Field(
        False, 
        description="Whether the project is marked as complete"
    )
    deadline: Optional[datetime] = Field(
        None, 
        description="Target completion date for the project"
    )
    design_decisions: Optional[Dict[str, str]] = Field(
        default_factory=dict, 
        description="Key design decisions and rationales for the project"
    )
    references: Optional[Dict[str, str]] = Field(
        default_factory=dict, 
        description="References to related documentation or resources"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "planning",
                    "epic": "Epic_Presence_and_Control_Loops",
                    "name": "CogniMemorySystem-POC",
                    "description": "Proof-of-concept for a composable memory system",
                    "phase": "Phase 1: Schema",
                    "implementation_flow": ["task-1.1", "task-1.2"],
                    "success_criteria": [
                        {"phase_1": ["Demonstrate storing a MemoryBlock in Dolt."]}
                    ],
                    "completed": False,
                    "deadline": "2023-12-31T23:59:59",
                    "design_decisions": {"dolt_llamaindex_sync": "Writes to Dolt will trigger updates"}
                }
            ]
        }
    }

# Register this metadata model with the registry
register_metadata("project", ProjectMetadata) 