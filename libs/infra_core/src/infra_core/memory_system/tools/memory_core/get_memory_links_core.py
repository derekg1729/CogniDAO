"""
GetMemoryLinksCore: Core tool for retrieving memory links by filtering.

This tool provides interfaces for:
- All links retrieval with optional filtering by relation type
- Filtered link retrieval with limit support
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from infra_core.memory_system.schemas.common import BlockLink
from infra_core.memory_system.link_manager import LinkQuery

# Setup logging
logger = logging.getLogger(__name__)


class GetMemoryLinksInput(BaseModel):
    """Input model for retrieving memory links with filtering."""

    # Link filtering parameters
    relation_filter: Optional[str] = Field(
        None, description="Optional filter by relation type (e.g., 'depends_on', 'subtask_of')"
    )
    limit: Optional[int] = Field(
        100, description="Maximum number of results to return", ge=1, le=1000
    )
    cursor: Optional[str] = Field(
        None, description="Optional pagination cursor for retrieving next batch"
    )


class GetMemoryLinksOutput(BaseModel):
    """Output model for the get memory links operation."""

    success: bool = Field(..., description="Whether the operation was successful.")
    links: List[BlockLink] = Field(
        default_factory=list,
        description="The retrieved memory links.",
    )
    next_cursor: Optional[str] = Field(
        None, description="Cursor for retrieving next batch if more results exist."
    )
    error: Optional[str] = Field(None, description="Error message if operation failed.")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Timestamp of when the operation was performed."
    )


def get_memory_links_core(input_data: GetMemoryLinksInput, memory_bank) -> GetMemoryLinksOutput:
    """
    Retrieve memory links with optional filtering.

    Args:
        input_data: GetMemoryLinksInput containing filtering parameters
        memory_bank: An instance of StructuredMemoryBank

    Returns:
        GetMemoryLinksOutput with the retrieved links or error information
    """
    logger.debug(
        f"Attempting to retrieve memory links with filters: relation={input_data.relation_filter}, limit={input_data.limit}"
    )

    try:
        # Check that memory bank has a link_manager
        if not hasattr(memory_bank, "link_manager"):
            error_msg = "Memory bank does not have a link_manager"
            logger.error(error_msg)
            return GetMemoryLinksOutput(success=False, error=error_msg, timestamp=datetime.now())

        link_manager = memory_bank.link_manager

        # Build query with provided filters
        query = LinkQuery()
        if input_data.relation_filter:
            query = query.relation(input_data.relation_filter)
        if input_data.limit:
            query = query.limit(input_data.limit)
        if input_data.cursor:
            query = query.cursor(input_data.cursor)

        # Get links using our new get_all_links method
        result = link_manager.get_all_links(query=query)

        logger.debug(f"Successfully retrieved {len(result.links)} memory links")
        return GetMemoryLinksOutput(
            success=True,
            links=result.links,
            next_cursor=result.next_cursor,
            timestamp=datetime.now(),
        )

    except Exception as e:
        error_msg = f"Error retrieving memory links: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return GetMemoryLinksOutput(success=False, error=error_msg, timestamp=datetime.now())
