"""
Metadata schema for log type MemoryBlocks.
Used to store atomic agent log entries linked to other blocks like tasks.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from ..registry import register_metadata


class LogMetadata(BaseModel):
    """
    Metadata schema for log type MemoryBlocks.
    Used to store atomic agent log entries linked to other blocks like tasks.
    """

    timestamp: datetime = Field(..., description="Timestamp of when the log was recorded")
    agent: str = Field(..., description="Name of the agent that generated the log")
    tool: Optional[str] = Field(
        default=None, description="Name of the tool invoked (if applicable)"
    )
    input: Optional[str] = Field(
        default=None, description="Stringified input (if any) used by the tool or agent"
    )
    output: Optional[str] = Field(
        default=None, description="Stringified output/result of the operation"
    )
    parent_block: Optional[str] = Field(
        default=None, description="ID of the parent MemoryBlock (usually a task or interaction)"
    )
    session_id: Optional[str] = Field(None, description="Optional session ID for tracking")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "timestamp": "2024-03-20T10:30:00Z",
                    "agent": "task_agent",
                    "tool": "codebase_search",
                    "input": "Find implementation of schema versioning",
                    "output": "Found in memory_block_schema_versioning_system.json",
                    "parent_block": "task-3.4.2",
                }
            ]
        }
    }


# Register the metadata model
register_metadata("log", LogMetadata)
