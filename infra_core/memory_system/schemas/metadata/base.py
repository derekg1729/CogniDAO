"""
Base class for all MemoryBlock metadata schemas.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class BaseMetadata(BaseModel):
    """
    System-level metadata included in all MemoryBlocks under the `metadata` field.

    All fields are prefixed with `x_` to distinguish system fields from user-defined metadata.
    """

    x_timestamp: datetime = Field(
        default_factory=datetime.now, description="Timestamp when the block was generated (UTC)."
    )
    x_agent_id: str = Field(..., description="Agent or user that created this memory block.")
    x_tool_id: Optional[str] = Field(
        None, description="Tool or agent subcomponent responsible for this block, if any."
    )
    x_parent_block_id: Optional[str] = Field(
        None, description="ID of the parent block, e.g., a task or source interaction."
    )
    x_session_id: Optional[str] = Field(
        None, description="Optional session ID grouping related blocks (e.g., chat context)."
    )

    class Config:
        # Prevent users from adding undefined fields
        extra = "forbid"
