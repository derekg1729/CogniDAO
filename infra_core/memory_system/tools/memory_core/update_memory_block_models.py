"""
UpdateMemoryBlockModels: Pydantic models and enums for memory block updates.

This module contains all input/output models, error codes, and validation logic
for the UpdateMemoryBlockCore tool, extracted for better maintainability.
"""

from typing import Optional, Dict, Any, Literal, List, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator
import json

from ...schemas.memory_block import ConfidenceScore
from ...schemas.common import BlockLink


class UpdateErrorCode(str, Enum):
    """Error codes for programmatic handling of update failures."""

    BLOCK_NOT_FOUND = "BLOCK_NOT_FOUND"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PATCH_PARSE_ERROR = "PATCH_PARSE_ERROR"
    PATCH_APPLY_ERROR = "PATCH_APPLY_ERROR"
    PATCH_SIZE_LIMIT_ERROR = "PATCH_SIZE_LIMIT_ERROR"
    LINK_VALIDATION_ERROR = "LINK_VALIDATION_ERROR"
    PERSISTENCE_FAILURE = "PERSISTENCE_FAILURE"
    RE_INDEX_FAILURE = "RE_INDEX_FAILURE"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class PatchType(str, Enum):
    """Types of patches that can be applied."""

    UNIFIED_DIFF = "unified_diff"
    JSON_PATCH = "json_patch"


class DiffSummary(BaseModel):
    """Summary of changes made during the update."""

    fields_updated: List[str] = Field(..., description="List of fields that were modified")
    text_changed: bool = Field(..., description="Whether the text content was modified")
    metadata_changed: bool = Field(..., description="Whether metadata was modified")
    tags_changed: bool = Field(..., description="Whether tags were modified")
    links_changed: bool = Field(..., description="Whether links were modified")
    patch_stats: Optional[Dict[str, Any]] = Field(
        None, description="Statistics about patches applied"
    )


class UpdateMemoryBlockInput(BaseModel):
    """Enhanced input model for updating an existing memory block."""

    # Required fields
    block_id: str = Field(..., description="ID of the memory block to update")

    # Concurrency control field (canonical)
    previous_block_version: Optional[int] = Field(
        None, description="Expected current block version for optimistic locking"
    )

    # Patch support fields - either patches OR full values, not both
    text_patch: Optional[str] = Field(None, description="Unified diff patch for text content")
    structured_patch: Optional[Union[str, List[Dict[str, Any]]]] = Field(
        None, description="JSON Patch (RFC-6902) operations for structured fields"
    )
    patch_type: Optional[PatchType] = Field(None, description="Type of patch format being used")

    # Traditional full replacement fields (mutually exclusive with patches)
    text: Optional[str] = Field(None, description="New content for the memory block")
    state: Optional[Literal["draft", "published", "archived"]] = Field(
        None, description="New state of the block"
    )
    visibility: Optional[Literal["internal", "public", "restricted"]] = Field(
        None, description="New visibility level of the block"
    )
    tags: Optional[List[str]] = Field(
        None, max_length=20, description="New tags for filtering and metadata"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="New or updated type-specific metadata"
    )
    source_file: Optional[str] = Field(None, description="New source file reference")
    confidence: Optional[ConfidenceScore] = Field(
        None, description="New confidence scores for the block"
    )
    links: Optional[List[BlockLink]] = Field(None, description="New list of links to other blocks")

    # Control behavior
    merge_metadata: bool = Field(
        True, description="If True, merge new metadata with existing. If False, replace entirely."
    )
    merge_tags: bool = Field(
        True, description="If True, merge new tags with existing. If False, replace entirely."
    )

    # Metadata for tracking and logging
    author: Optional[str] = Field(None, description="User or agent making the update")
    agent_id: Optional[str] = Field(None, description="ID of the agent performing the update")
    session_id: Optional[str] = Field(None, description="Session ID for request tracking")
    change_note: Optional[str] = Field(None, description="Brief description of the change")

    @validator("patch_type")
    def validate_patch_type_with_content(cls, v, values):
        """Ensure patch_type is specified when patches are provided."""
        text_patch = values.get("text_patch")
        structured_patch = values.get("structured_patch")

        if (text_patch or structured_patch) and not v:
            raise ValueError("patch_type must be specified when providing patches")

        if v and not (text_patch or structured_patch):
            raise ValueError("patch_type specified but no patches provided")

        return v

    @validator("structured_patch")
    def validate_structured_patch_format(cls, v, values):
        """Validate structured patch format based on patch_type."""
        if not v:
            return v

        patch_type = values.get("patch_type")

        if patch_type == PatchType.JSON_PATCH:
            # Should be a JSON Patch RFC-6902 string or list of operations
            if isinstance(v, str):
                try:
                    operations = json.loads(v)
                    if not isinstance(operations, list):
                        raise ValueError("JSON Patch must be a list of operations")
                except json.JSONDecodeError:
                    raise ValueError("Invalid JSON in structured_patch")
            elif isinstance(v, list):
                # Validate it's a proper list of operations
                for op in v:
                    if not isinstance(op, dict) or "op" not in op:
                        raise ValueError("Invalid JSON Patch operation format")
            else:
                raise ValueError("JSON Patch must be string or list")

        return v


class UpdateMemoryBlockOutput(BaseModel):
    """Enhanced output model for memory block update results."""

    success: bool = Field(..., description="Whether the update was successful")
    id: Optional[str] = Field(None, description="ID of the updated block if successful")
    error: Optional[str] = Field(None, description="Human-readable error message if update failed")
    error_code: Optional[UpdateErrorCode] = Field(
        None, description="Machine-readable error code for programmatic handling"
    )
    timestamp: datetime = Field(..., description="Timestamp when the update was performed")
    diff_summary: Optional[DiffSummary] = Field(
        None, description="Summary of changes made during the update"
    )

    # Version tracking
    previous_version: Optional[int] = Field(None, description="Version of the block before update")
    new_version: Optional[int] = Field(None, description="Version of the block after update")

    # Performance metrics
    processing_time_ms: Optional[float] = Field(
        None, description="Time taken to process the update in milliseconds"
    )
