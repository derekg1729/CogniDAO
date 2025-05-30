"""
UpdateMemoryBlockTool: Agent-facing tool for updating memory blocks with patch support.

This tool provides a unified interface for agents to update memory blocks using
various patch types (text diffs, JSON patches) or direct field updates, with
comprehensive validation and concurrency safety.
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from ...schemas.common import BlockLink, BlockIdType
from ..base.cogni_tool import CogniTool
from ..memory_core.update_memory_block_core import update_memory_block_core
from ..memory_core.update_memory_block_models import (
    UpdateMemoryBlockInput,
    PatchType,
    UpdateErrorCode,
)
from ...structured_memory_bank import StructuredMemoryBank

# Setup logging
logger = logging.getLogger(__name__)


class UpdateMemoryBlockToolInput(BaseModel):
    """Simplified input model for agent-facing memory block updates."""

    # Required fields
    block_id: BlockIdType = Field(..., description="ID of the memory block to update")

    # Concurrency control
    previous_block_version: Optional[int] = Field(
        None,
        description="Expected current version for optimistic locking (prevents concurrent updates)",
    )

    # Direct field updates
    text: Optional[str] = Field(None, description="New text content for the block")
    state: Optional[str] = Field(None, description="New state: draft, published, or archived")
    visibility: Optional[str] = Field(
        None, description="New visibility: internal, public, or restricted"
    )
    tags: Optional[List[str]] = Field(None, description="Tags to set or merge with existing tags")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata fields to update")
    links: Optional[List[BlockLink]] = Field(None, description="Block links to set or merge")

    # Patch-based updates
    text_patch: Optional[str] = Field(
        None, description="Unified diff patch to apply to text content"
    )
    structured_patch: Optional[Union[str, List[Dict[str, Any]]]] = Field(
        None, description="JSON Patch (RFC-6902) operations for structured updates"
    )
    patch_type: Optional[PatchType] = Field(
        None, description="Type of patch being applied (unified_diff or json_patch)"
    )

    # Merge behavior
    merge_tags: bool = Field(
        True, description="Whether to merge with existing tags (true) or replace them (false)"
    )
    merge_metadata: bool = Field(
        True, description="Whether to merge with existing metadata (true) or replace it (false)"
    )
    merge_links: bool = Field(
        True, description="Whether to merge with existing links (true) or replace them (false)"
    )

    # Agent context
    author: str = Field("agent", description="Identifier for who is making the update")
    agent_id: str = Field("cogni_agent", description="Agent identifier for tracking")
    change_note: Optional[str] = Field(
        None, description="Optional note explaining the reason for this update"
    )


class UpdateMemoryBlockToolOutput(BaseModel):
    """Output model for memory block update results."""

    success: bool = Field(..., description="Whether the update was successful")
    id: Optional[BlockIdType] = Field(None, description="ID of the updated block")
    error: Optional[str] = Field(None, description="Error message if update failed")
    error_code: Optional[UpdateErrorCode] = Field(None, description="Structured error code")

    # Version tracking
    previous_version: Optional[int] = Field(None, description="Version before the update")
    new_version: Optional[int] = Field(None, description="Version after the update")

    # Metadata
    timestamp: datetime = Field(..., description="When the update was processed")
    processing_time_ms: Optional[float] = Field(None, description="Processing time in milliseconds")

    # Summary of changes
    fields_updated: List[str] = Field(
        default_factory=list, description="List of fields that were modified"
    )
    text_changed: bool = Field(False, description="Whether the text content was modified")


def update_memory_block_tool(
    input_data: UpdateMemoryBlockToolInput,
    memory_bank: StructuredMemoryBank,
) -> UpdateMemoryBlockToolOutput:
    """
    Agent-facing wrapper for updating memory blocks.

    This tool provides a user-friendly interface for agents to update memory blocks
    using various update methods including direct field updates, text patches,
    and JSON patches, with comprehensive validation and error handling.

    Args:
        input_data: Update parameters including block ID, update content, and options
        memory_bank: Memory bank interface for persistence

    Returns:
        UpdateMemoryBlockToolOutput with success status and details
    """
    start_time = datetime.now()

    try:
        # Convert UpdateMemoryBlockToolInput to UpdateMemoryBlockInput for core function
        core_input = UpdateMemoryBlockInput(
            block_id=input_data.block_id,
            text=input_data.text,
            state=input_data.state,
            visibility=input_data.visibility,
            tags=input_data.tags,
            metadata=input_data.metadata,
            source_file=input_data.source_file,
            confidence=input_data.confidence,
            previous_block_version=input_data.previous_block_version,
            text_patch=input_data.text_patch,
            structured_patch=input_data.structured_patch,
            patch_type=input_data.patch_type,
            merge_metadata=input_data.merge_metadata,
            merge_tags=input_data.merge_tags,
            author=input_data.author,
            change_note=input_data.change_note,
        )

        # Call the core update function
        core_result = update_memory_block_core(core_input, memory_bank)

        # Convert core result to tool output
        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        # Extract fields from diff_summary if available
        fields_updated = []
        text_changed = False
        if core_result.diff_summary:
            fields_updated = core_result.diff_summary.fields_updated
            text_changed = core_result.diff_summary.text_changed

        return UpdateMemoryBlockToolOutput(
            success=core_result.success,
            id=core_result.id,
            error=core_result.error,
            error_code=core_result.error_code,
            previous_version=core_result.previous_version,
            new_version=core_result.new_version,
            timestamp=core_result.timestamp,
            processing_time_ms=processing_time,
            fields_updated=fields_updated,
            text_changed=text_changed,
        )

    except Exception as e:
        logger.exception("Error in update_memory_block wrapper: %s", str(e))
        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        return UpdateMemoryBlockToolOutput(
            success=False,
            error=f"Error in update_memory_block wrapper: {str(e)}",
            timestamp=datetime.now(),
            processing_time_ms=processing_time,
            fields_updated=[],
            text_changed=False,
        )


# Create the CogniTool instance
update_memory_block_tool_instance = CogniTool(
    name="UpdateMemoryBlock",
    description="Update memory blocks with text, metadata, links, and patch support",
    input_model=UpdateMemoryBlockToolInput,
    output_model=UpdateMemoryBlockToolOutput,
    function=update_memory_block_tool,
    memory_linked=True,
)
