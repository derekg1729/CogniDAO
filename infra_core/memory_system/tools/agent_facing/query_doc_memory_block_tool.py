"""
QueryDocMemoryBlockTool: Agent-facing tool for querying 'doc' type memory blocks.

This tool provides a simplified interface for agents to search for documentation blocks,
with automatic type filtering and options to filter by document-specific metadata.
"""

from typing import Dict, Any, Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from ..base.cogni_tool import CogniTool
from ..memory_core.query_memory_blocks_tool import (
    query_memory_blocks_core,
    QueryMemoryBlocksInput as CoreQueryMemoryBlocksInput,
    QueryMemoryBlocksOutput as CoreQueryMemoryBlocksOutput,
)

# Setup logging
logger = logging.getLogger(__name__)


class QueryDocMemoryBlockInput(BaseModel):
    """Input model for querying 'doc' type memory blocks."""

    query_text: str = Field(..., description="Text to search for semantically within documents.")

    # Document-specific metadata filters
    title_filter: Optional[str] = Field(
        None, description="Filter by exact document title (if specified in metadata)."
    )
    audience_filter: Optional[str] = Field(None, description="Filter by intended audience.")
    section_filter: Optional[str] = Field(None, description="Filter by document section.")
    doc_version_filter: Optional[str] = Field(
        None, description="Filter by document version (metadata field 'version')."
    )
    doc_format_filter: Optional[Literal["markdown", "html", "text", "code"]] = Field(
        None, description="Filter by document format (metadata field 'format')."
    )
    completed_filter: Optional[bool] = Field(None, description="Filter by completion status.")

    # Common query filters
    tag_filters: Optional[List[str]] = Field(None, description="List of tags to filter by.")
    top_k: Optional[int] = Field(5, description="Maximum number of results to return.", ge=1, le=20)


class QueryDocMemoryBlockOutput(CoreQueryMemoryBlocksOutput):
    """Output model for querying 'doc' memory blocks. Inherits from core output."""

    pass


def query_doc_memory_block(
    input_data: QueryDocMemoryBlockInput, memory_bank
) -> QueryDocMemoryBlockOutput:
    """
    Query 'doc' type memory blocks with structured metadata filters.
    """
    logger.debug(f"Attempting to query 'doc' memory blocks with query: '{input_data.query_text}'")

    # Prepare metadata filters for the core query tool
    metadata_filters: Dict[str, Any] = {}
    if input_data.title_filter:
        metadata_filters["title"] = input_data.title_filter
    if input_data.audience_filter:
        metadata_filters["audience"] = input_data.audience_filter
    if input_data.section_filter:
        metadata_filters["section"] = input_data.section_filter
    if input_data.doc_version_filter:
        metadata_filters["version"] = (
            input_data.doc_version_filter
        )  # Mapped from doc_version_filter
    if input_data.doc_format_filter:
        metadata_filters["format"] = input_data.doc_format_filter  # Mapped from doc_format_filter
    if input_data.completed_filter is not None:  # Check for None because bool can be False
        metadata_filters["completed"] = input_data.completed_filter

    # Add x_tool_id to any metadata filters if we want to ensure it came from a specific tool (optional here)
    # For querying, usually we don't filter by x_tool_id unless specifically needed.

    core_input = CoreQueryMemoryBlocksInput(
        query_text=input_data.query_text,
        type_filter="doc",  # Automatically filter by type "doc"
        tag_filters=input_data.tag_filters,
        top_k=input_data.top_k,
        metadata_filters=metadata_filters if metadata_filters else None,  # Pass None if empty
    )

    try:
        result = query_memory_blocks_core(core_input, memory_bank)
        # The result is already CoreQueryMemoryBlocksOutput, which QueryDocMemoryBlockOutput inherits from
        return QueryDocMemoryBlockOutput(**result.model_dump())
    except Exception as e:
        error_msg = f"Error in query_doc_memory_block wrapper: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return QueryDocMemoryBlockOutput(
            success=False, blocks=[], error=error_msg, timestamp=datetime.now()
        )


# Create the tool instance
query_doc_memory_block_tool = CogniTool(
    name="QueryDocMemoryBlock",
    description="Queries 'doc' type memory blocks with semantic search and specific document metadata filters.",
    input_model=QueryDocMemoryBlockInput,
    output_model=QueryDocMemoryBlockOutput,
    function=query_doc_memory_block,
    memory_linked=True,
)
