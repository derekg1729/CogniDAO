"""
CreateMemoryBlockTool: Tool for creating new memory blocks with validation and persistence.

This tool handles the creation of new memory blocks, including:
- Input validation against Pydantic schemas
- Automatic ID and timestamp generation
- Persistence to Dolt database
- Indexing in LlamaMemory
"""

from typing import Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from ..schemas.memory_block import MemoryBlock, ConfidenceScore
from ..structured_memory_bank import StructuredMemoryBank
from .cogni_tool import CogniTool

# Setup logging
logger = logging.getLogger(__name__)


class CreateMemoryBlockInput(BaseModel):
    """Input model for creating a new memory block."""

    type: Literal["knowledge", "task", "project", "doc", "interaction"] = Field(
        ..., description="Type of memory block to create"
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
        None, description="Optional identifier for creator (agent name or user ID)"
    )


class CreateMemoryBlockOutput(BaseModel):
    """Output model for memory block creation results."""

    success: bool = Field(..., description="Whether the creation was successful")
    id: Optional[str] = Field(None, description="ID of the created block if successful")
    error: Optional[str] = Field(None, description="Error message if creation failed")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Timestamp of the creation attempt"
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
        CreateMemoryBlockOutput with creation status
    """
    try:
        # Get latest schema version for the block type
        schema_version = memory_bank.get_latest_schema_version(input_data.type)
        if schema_version is None:
            return CreateMemoryBlockOutput(
                success=False, error=f"No schema version found for type: {input_data.type}"
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
            created_by=input_data.created_by,
            schema_version=schema_version,
        )

        # Persist to Dolt and index in LlamaMemory
        success = memory_bank.create_memory_block(block)

        if success:
            return CreateMemoryBlockOutput(success=True, id=block.id)
        else:
            return CreateMemoryBlockOutput(success=False, error="Failed to persist memory block")

    except Exception as e:
        logger.error(f"Error creating memory block: {str(e)}")
        return CreateMemoryBlockOutput(success=False, error=f"Creation failed: {str(e)}")


# Create the tool instance
create_memory_block_tool = CogniTool(
    name="CreateMemoryBlock",
    description="Creates a new memory block with validation and persistence to Dolt and LlamaMemory",
    input_model=CreateMemoryBlockInput,
    output_model=CreateMemoryBlockOutput,
    function=create_memory_block,
    memory_linked=True,
)
