"""
QueryMemoryBlocksTool: Tool for querying memory blocks using semantic search with filters.

This tool enables semantic search of memory blocks with support for:
- Semantic search via LlamaIndex
- Filtering by type, tags, and metadata
- Configurable result limit
"""

from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from ...schemas.memory_block import MemoryBlock
from ...structured_memory_bank import StructuredMemoryBank
from ..base.cogni_tool import CogniTool

# Setup logging
logger = logging.getLogger(__name__)


class QueryMemoryBlocksInput(BaseModel):
    """Input model for querying memory blocks."""

    query_text: str = Field(..., description="Text to search for semantically")
    type_filter: Optional[Literal["knowledge", "task", "project", "doc", "interaction"]] = Field(
        None, description="Optional filter by block type"
    )
    tag_filters: Optional[List[str]] = Field(None, description="Optional list of tags to filter by")
    top_k: Optional[int] = Field(5, description="Maximum number of results to return", ge=1, le=20)
    metadata_filters: Optional[Dict[str, Any]] = Field(
        None, description="Optional metadata key-value pairs to filter by"
    )


class QueryMemoryBlocksOutput(BaseModel):
    """Output model for memory block query results."""

    success: bool = Field(..., description="Whether the query was successful")
    blocks: List[MemoryBlock] = Field(
        default_factory=list, description="List of matching memory blocks"
    )
    error: Optional[str] = Field(None, description="Error message if query failed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of the query")


def query_memory_blocks_core(
    input_data: QueryMemoryBlocksInput, memory_bank: StructuredMemoryBank
) -> QueryMemoryBlocksOutput:
    """
    Query memory blocks using semantic search with optional filters.

    Args:
        input_data: Input data for the query
        memory_bank: StructuredMemoryBank instance for querying

    Returns:
        QueryMemoryBlocksOutput containing query status, matching blocks, error message, and timestamp
    """
    try:
        # Perform semantic search
        blocks = memory_bank.query_semantic(
            query_text=input_data.query_text, top_k=input_data.top_k
        )

        # Ensure all blocks are MemoryBlock objects
        blocks = [b if isinstance(b, MemoryBlock) else MemoryBlock(**b) for b in blocks]

        # Apply type filter if specified
        if input_data.type_filter:
            blocks = [b for b in blocks if b.type == input_data.type_filter]

        # Apply tag filters if specified
        if input_data.tag_filters:
            blocks = [b for b in blocks if all(tag in b.tags for tag in input_data.tag_filters)]

        # Apply metadata filters if specified
        if input_data.metadata_filters:
            blocks = [
                b
                for b in blocks
                if all(b.metadata.get(k) == v for k, v in input_data.metadata_filters.items())
            ]

        return QueryMemoryBlocksOutput(success=True, blocks=blocks, timestamp=datetime.now())

    except Exception as e:
        logger.error(f"Error querying memory blocks: {str(e)}")
        return QueryMemoryBlocksOutput(
            success=False, blocks=[], error=str(e), timestamp=datetime.now()
        )


# Create the tool instance
query_memory_blocks_tool = CogniTool(
    name="QueryMemoryBlocks",
    description="Query memory blocks using semantic search with optional filters",
    input_model=QueryMemoryBlocksInput,
    output_model=QueryMemoryBlocksOutput,
    function=query_memory_blocks_core,
    memory_linked=True,
)
