"""
Metadata schema for log type MemoryBlocks.
Used to store atomic agent log entries linked to other blocks like tasks.
"""

from typing import Optional, Dict
from pydantic import Field

# Import the base class
from .base import BaseMetadata

# Import for registration
from ..registry import register_metadata


# Inherit from BaseMetadata
class LogMetadata(BaseMetadata):
    """
    Metadata schema for log type MemoryBlocks.
    Inherits common fields (x_timestamp, x_agent_id, x_tool_id, x_parent_block_id, x_session_id) from BaseMetadata.
    """

    # Keep specific fields, renamed for clarity
    input_text: Optional[str] = Field(
        default=None, description="Stringified input (if any) used by the tool or agent"
    )
    output_text: Optional[str] = Field(
        default=None, description="Stringified output/result of the operation"
    )
    # Add fields previously stored as unstructured metadata
    model: Optional[str] = Field(None, description="Optional model name/version used")
    token_count: Optional[Dict[str, int]] = Field(
        None, description="Optional token counts (e.g., prompt, completion)"
    )
    latency_ms: Optional[float] = Field(
        None, description="Optional end-to-end latency in milliseconds"
    )
    # session_id is now inherited from BaseMetadata as x_session_id

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    # Use x_ prefixed fields from BaseMetadata
                    "x_timestamp": "2024-03-20T10:30:00Z",
                    "x_agent_id": "task_agent_xyz",
                    "x_tool_id": "codebase_search",
                    "x_parent_block_id": "task-3.4.2",
                    "x_session_id": "session_12345",
                    # Fields specific to LogMetadata
                    "input_text": "Find implementation of schema versioning",
                    "output_text": "Found in memory_block_schema_versioning_system.json",
                }
            ]
        }
    }


# Register the metadata model
register_metadata("log", LogMetadata)
