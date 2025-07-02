"""
DeleteMemoryBlockModels: Pydantic models and enums for memory block deletion.

This module contains all input/output models, error codes, and validation logic
for the DeleteMemoryBlockCore tool, following the established pattern.
"""

from typing import Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

from ...schemas.common import BlockIdType


class DeleteErrorCode(str, Enum):
    """Error codes for programmatic handling of deletion failures."""

    BLOCK_NOT_FOUND = "BLOCK_NOT_FOUND"
    DEPENDENCIES_EXIST = "DEPENDENCIES_EXIST"
    DELETION_FAILED = "DELETION_FAILED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class DeleteMemoryBlockInput(BaseModel):
    """Input model for deleting an existing memory block."""

    # Required fields
    block_id: BlockIdType = Field(..., description="ID of the memory block to delete")

    # Control behavior
    validate_dependencies: bool = Field(
        True,
        description="If True, check for dependent blocks and fail if any exist. If False, force deletion.",
    )

    # Metadata for tracking and logging
    author: Optional[str] = Field("agent", description="User or agent performing the deletion")
    agent_id: Optional[str] = Field(
        "cogni_agent", description="ID of the agent performing the deletion"
    )
    session_id: Optional[str] = Field(None, description="Session ID for request tracking")
    change_note: Optional[str] = Field(
        None, description="Brief description of why the block is being deleted"
    )


class DeleteMemoryBlockOutput(BaseModel):
    """Output model for memory block deletion results."""

    success: bool = Field(..., description="Whether the deletion was successful")
    id: Optional[BlockIdType] = Field(None, description="ID of the deleted block if successful")
    error: Optional[str] = Field(
        None, description="Human-readable error message if deletion failed"
    )
    error_code: Optional[DeleteErrorCode] = Field(
        None, description="Machine-readable error code for programmatic handling"
    )
    timestamp: datetime = Field(..., description="Timestamp when the deletion was performed")

    # Metadata about the deleted block
    deleted_block_type: Optional[str] = Field(None, description="Type of the deleted block")
    deleted_block_version: Optional[int] = Field(None, description="Version of the deleted block")

    # Performance metrics
    processing_time_ms: Optional[float] = Field(
        None, description="Time taken to process the deletion in milliseconds"
    )
