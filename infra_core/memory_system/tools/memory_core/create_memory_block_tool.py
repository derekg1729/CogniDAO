"""
CreateMemoryBlockTool: Tool for creating new memory blocks with validation and persistence.

This tool handles the creation of new memory blocks, including:
- Input validation against Pydantic schemas
- Automatic ID and timestamp generation
- Persistence to Dolt database
- Indexing in LlamaMemory
"""

from typing import Optional, Dict, Any, Literal, List
from datetime import datetime
from pydantic import BaseModel, Field, ValidationError, field_validator
import logging

from ...schemas.memory_block import MemoryBlock, ConfidenceScore
from ...schemas.common import BlockLink
from ...schemas.registry import validate_metadata, get_available_node_types
from ...structured_memory_bank import StructuredMemoryBank
from ..base.cogni_tool import CogniTool

# Setup logging
logger = logging.getLogger(__name__)


class CreateMemoryBlockInput(BaseModel):
    """Input model for creating a new memory block."""

    type: str = Field(
        ..., description="Type of memory block to create (must be registered in schema registry)"
    )
    text: str = Field(..., description="Primary content of the memory block")
    state: Optional[Literal["draft", "published", "archived"]] = Field(
        "draft", description="Initial state of the block"
    )
    visibility: Optional[Literal["internal", "public", "restricted"]] = Field(
        "internal", description="Visibility level of the block"
    )
    tags: list[str] = Field(
        default_factory=list, max_length=20, description="Optional tags for filtering and metadata"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Type-specific metadata for the block"
    )
    source_file: Optional[str] = Field(None, description="Optional source file or markdown name")
    confidence: Optional[ConfidenceScore] = Field(
        None, description="Optional confidence scores for the block"
    )
    created_by: Optional[str] = Field(
        "agent",  # Default created_by to 'agent'
        description="Optional identifier for creator (agent name or user ID)",
    )
    links: Optional[List[BlockLink]] = Field(
        default_factory=list, description="Optional list of links to other blocks"
    )

    @field_validator("type")
    def check_type_is_registered(cls, v):
        """Validate that the provided block type is registered in the schema registry."""
        registered_types = get_available_node_types()
        if v not in registered_types:
            raise ValueError(f"Invalid block type '{v}'. Must be one of: {registered_types}")
        return v


class CreateMemoryBlockOutput(BaseModel):
    """Output model for memory block creation results."""

    success: bool = Field(..., description="Whether the creation was successful")
    id: Optional[str] = Field(None, description="ID of the created block if successful")
    error: Optional[str] = Field(None, description="Error message if creation failed")
    timestamp: datetime = Field(
        ..., description="Timestamp of the block creation (from block.created_at)"
    )


def create_memory_block(
    input_data: CreateMemoryBlockInput, memory_bank: StructuredMemoryBank
) -> CreateMemoryBlockOutput:
    """
    Create a new memory block with validation and persistence.

    Args:
        input_data: Input data for creating the block
        memory_bank: StructuredMemoryBank instance for persistence

    Returns:
        CreateMemoryBlockOutput containing creation status, ID, error message, and timestamp
    """
    # Capture timestamp for potential error reporting
    now = datetime.now()

    try:
        # Inject system metadata fields FIRST if they are not already present
        # Ensure metadata exists and is a dict
        if not isinstance(input_data.metadata, dict):
            input_data.metadata = {}

        if "x_timestamp" not in input_data.metadata:
            input_data.metadata["x_timestamp"] = now  # Use the consistent timestamp
        if "x_agent_id" not in input_data.metadata:
            # Fallback to created_by field from input if x_agent_id is missing
            input_data.metadata["x_agent_id"] = input_data.created_by

        # Metadata validation now returns error string or None
        metadata_error = validate_metadata(input_data.type, input_data.metadata)
        if metadata_error:
            return CreateMemoryBlockOutput(
                success=False,
                error=metadata_error,  # Use the detailed error from validate_metadata
                timestamp=now,  # Use consistent timestamp for failed attempt
            )

        # Get latest schema version for the block type
        schema_version = memory_bank.get_latest_schema_version(input_data.type)
        if schema_version is None:
            # This case should ideally be prevented by the input validator for 'type',
            # but handle defensively.
            error_msg = (
                f"Schema definition missing or lookup failed for registered type: {input_data.type}"
            )
            logger.error(error_msg)  # Log this potentially inconsistent state
            return CreateMemoryBlockOutput(
                success=False,
                error=error_msg,
                timestamp=now,  # Use consistent timestamp
            )

        # Create the memory block
        block = MemoryBlock(
            type=input_data.type,
            text=input_data.text,
            state=input_data.state,
            visibility=input_data.visibility,
            tags=input_data.tags,
            metadata=input_data.metadata,
            source_file=input_data.source_file,
            confidence=input_data.confidence,
            links=input_data.links,
            created_by=input_data.created_by,  # Default is now handled by input model
            schema_version=schema_version,
        )

        # Persist to Dolt and index in LlamaMemory
        success = memory_bank.create_memory_block(block)

        if success:
            # Return block.created_at for consistency
            return CreateMemoryBlockOutput(success=True, id=block.id, timestamp=block.created_at)
        else:
            # Persistence failure should be logged by memory_bank.create_memory_block
            return CreateMemoryBlockOutput(
                success=False, error="Failed to persist memory block", timestamp=now
            )

    except ValidationError as ve:
        # Catch potential Pydantic validation errors during input parsing or MemoryBlock creation
        error_details = str(ve)
        logger.error(
            f"Pydantic validation error during memory block creation process: {error_details}"
        )
        return CreateMemoryBlockOutput(
            success=False,
            error=f"Input or internal validation failed: {error_details}",
            timestamp=now,
        )
    except Exception as e:
        # Catch unexpected errors
        logger.exception(
            f"Unexpected error creating memory block: {str(e)}"
        )  # Use logger.exception for stack trace
        return CreateMemoryBlockOutput(
            success=False, error=f"Unexpected creation failed: {str(e)}", timestamp=now
        )


# Create the tool instance
create_memory_block_tool = CogniTool(
    name="CreateMemoryBlock",
    description="Creates a new memory block with validation and persistence to Dolt and LlamaMemory",
    input_model=CreateMemoryBlockInput,
    output_model=CreateMemoryBlockOutput,
    function=create_memory_block,
    memory_linked=True,
)
