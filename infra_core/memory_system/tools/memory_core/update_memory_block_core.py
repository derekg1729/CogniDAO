"""
UpdateMemoryBlockCore: Core tool for updating existing memory blocks with validation.

This tool handles updating existing memory blocks, including:
- Input validation against current block state
- Metadata validation against schema registry
- Atomic persistence to Dolt database and LlamaIndex
- Comprehensive error handling and logging
"""

from typing import Optional, Dict, Any, Literal, List
from datetime import datetime
from pydantic import BaseModel, Field, ValidationError
import logging

from ...schemas.memory_block import MemoryBlock, ConfidenceScore
from ...schemas.common import BlockLink
from ...schemas.registry import validate_metadata
from ...structured_memory_bank import StructuredMemoryBank

# Setup logging
logger = logging.getLogger(__name__)


class UpdateMemoryBlockInput(BaseModel):
    """Input model for updating an existing memory block."""

    block_id: str = Field(..., description="ID of the memory block to update")
    
    # Optional fields that can be updated (None means "don't change")
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
    links: Optional[List[BlockLink]] = Field(
        None, description="New list of links to other blocks"
    )
    
    # Control behavior
    merge_metadata: bool = Field(
        True, description="If True, merge new metadata with existing. If False, replace entirely."
    )
    merge_tags: bool = Field(
        True, description="If True, merge new tags with existing. If False, replace entirely."
    )


class UpdateMemoryBlockOutput(BaseModel):
    """Output model for memory block update results."""

    success: bool = Field(..., description="Whether the update was successful")
    id: Optional[str] = Field(None, description="ID of the updated block if successful")
    error: Optional[str] = Field(None, description="Error message if update failed")
    timestamp: datetime = Field(
        ..., description="Timestamp when the update was performed"
    )
    updated_fields: List[str] = Field(
        default_factory=list, description="List of fields that were actually updated"
    )


def update_memory_block_core(
    input_data: UpdateMemoryBlockInput, memory_bank: StructuredMemoryBank
) -> UpdateMemoryBlockOutput:
    """
    Update an existing memory block with validation and atomic persistence.

    Args:
        input_data: Input data for updating the block
        memory_bank: StructuredMemoryBank instance for persistence

    Returns:
        UpdateMemoryBlockOutput containing update status, ID, error message, and timestamp
    """
    now = datetime.now()
    logger.debug(f"Attempting to update memory block: {input_data.block_id}")

    try:
        # 1. Retrieve existing block
        existing_block = memory_bank.get_memory_block(input_data.block_id)
        if not existing_block:
            error_msg = f"Memory block with ID '{input_data.block_id}' not found"
            logger.warning(error_msg)
            return UpdateMemoryBlockOutput(
                success=False, error=error_msg, timestamp=now, updated_fields=[]
            )

        # 2. Create updated block with merged/replaced fields
        updated_fields = []
        updated_block_data = existing_block.model_dump()

        # Update scalar fields if provided
        if input_data.text is not None:
            updated_block_data["text"] = input_data.text
            updated_fields.append("text")
        
        if input_data.state is not None:
            updated_block_data["state"] = input_data.state
            updated_fields.append("state")
            
        if input_data.visibility is not None:
            updated_block_data["visibility"] = input_data.visibility
            updated_fields.append("visibility")
            
        if input_data.source_file is not None:
            updated_block_data["source_file"] = input_data.source_file
            updated_fields.append("source_file")
            
        if input_data.confidence is not None:
            updated_block_data["confidence"] = input_data.confidence
            updated_fields.append("confidence")

        # Handle tags merging/replacement
        if input_data.tags is not None:
            if input_data.merge_tags and existing_block.tags:
                # Merge and deduplicate
                merged_tags = list(set(existing_block.tags + input_data.tags))
                updated_block_data["tags"] = merged_tags
            else:
                updated_block_data["tags"] = input_data.tags
            updated_fields.append("tags")

        # Handle metadata merging/replacement  
        if input_data.metadata is not None:
            if input_data.merge_metadata and existing_block.metadata:
                # Merge dictionaries, new values overwrite existing
                merged_metadata = {**existing_block.metadata, **input_data.metadata}
                updated_block_data["metadata"] = merged_metadata
            else:
                updated_block_data["metadata"] = input_data.metadata
            updated_fields.append("metadata")

        # Handle links replacement
        if input_data.links is not None:
            updated_block_data["links"] = input_data.links
            updated_fields.append("links")

        # Always update the updated_at timestamp
        updated_block_data["updated_at"] = now
        updated_fields.append("updated_at")

        # 3. Validate metadata if it was updated
        if "metadata" in updated_fields:
            metadata_error = validate_metadata(existing_block.type, updated_block_data["metadata"])
            if metadata_error:
                return UpdateMemoryBlockOutput(
                    success=False, error=metadata_error, timestamp=now, updated_fields=[]
                )

        # 4. Create new MemoryBlock instance for validation
        try:
            updated_block = MemoryBlock(**updated_block_data)
        except ValidationError as ve:
            field_errors = [
                f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in ve.errors()
            ]
            error_details = "\n- ".join(field_errors)
            logger.error(f"Validation failed for updated block {input_data.block_id}:\n- {error_details}")
            return UpdateMemoryBlockOutput(
                success=False, 
                error=f"Updated block validation failed: {error_details}", 
                timestamp=now, 
                updated_fields=[]
            )

        # 5. Persist using memory bank's atomic update
        success = memory_bank.update_memory_block(updated_block)
        
        if success:
            logger.info(f"Successfully updated memory block: {input_data.block_id}")
            return UpdateMemoryBlockOutput(
                success=True, 
                id=updated_block.id, 
                timestamp=updated_block.updated_at,
                updated_fields=updated_fields
            )
        else:
            error_msg = "Failed to persist updated memory block"
            logger.error(error_msg)
            return UpdateMemoryBlockOutput(
                success=False, error=error_msg, timestamp=now, updated_fields=[]
            )

    except Exception as e:
        error_msg = f"Unexpected error updating memory block: {str(e)}"
        logger.exception(error_msg)
        return UpdateMemoryBlockOutput(
            success=False, error=error_msg, timestamp=now, updated_fields=[]
        )