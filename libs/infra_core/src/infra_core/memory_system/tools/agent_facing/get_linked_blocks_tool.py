"""
GetLinkedBlocksTool: Agent-facing tool for retrieving linked blocks with full context.

This tool retrieves all blocks linked to a source block, providing both the
relationship information and the full block details in a single operation.
"""

from typing import Optional, List, Literal
from datetime import datetime
import logging

from pydantic import BaseModel, Field

from ..memory_core.get_memory_block_core import (
    get_memory_block_core,
    GetMemoryBlockInput as CoreGetMemoryBlockInput,
)
from infra_core.memory_system.schemas.common import BlockLink
from infra_core.memory_system.schemas.memory_block import MemoryBlock

# Setup logging
logger = logging.getLogger(__name__)


class LinkedBlockInfo(BaseModel):
    """Information about a linked block including relationship context."""

    block: MemoryBlock = Field(..., description="The full memory block details")
    relationship: BlockLink = Field(..., description="The link relationship information")
    direction: Literal["incoming", "outgoing"] = Field(
        ..., description="Direction of the relationship from source block"
    )
    relationship_description: str = Field(
        ..., description="Human-readable description of the relationship"
    )


class GetLinkedBlocksInput(BaseModel):
    """Input model for retrieving linked blocks."""

    source_block_id: str = Field(..., description="ID of the source block to find links for")
    relation_filter: Optional[str] = Field(
        None,
        description="Optional filter by specific relation type (e.g., 'subtask_of', 'depends_on')",
    )
    direction_filter: Optional[Literal["incoming", "outgoing", "both"]] = Field(
        "both", description="Filter by link direction relative to source block"
    )
    limit: Optional[int] = Field(
        50, description="Maximum number of linked blocks to return", ge=1, le=200
    )


class GetLinkedBlocksOutput(BaseModel):
    """Output model for the get linked blocks operation."""

    success: bool = Field(..., description="Whether the operation was successful")
    source_block_id: str = Field(..., description="ID of the source block queried")
    linked_blocks: List[LinkedBlockInfo] = Field(
        default_factory=list, description="List of linked blocks with relationship context"
    )
    total_count: int = Field(..., description="Total number of linked blocks found")
    error: Optional[str] = Field(None, description="Error message if operation failed")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Timestamp of when the operation was performed"
    )


def _generate_relationship_description(
    link: BlockLink, direction: str, source_block_id: str
) -> str:
    """Generate a human-readable description of the relationship."""

    if direction == "outgoing":
        # Source block -> target block
        descriptions = {
            "subtask_of": "This block is a subtask of the linked block",
            "depends_on": "This block depends on the linked block",
            "blocks": "This block blocks the linked block",
            "child_of": "This block is a child of the linked block",
            "belongs_to_epic": "This block belongs to the linked epic",
            "bug_affects": "This bug affects the linked block",
            "references": "This block references the linked block",
            "mentions": "This block mentions the linked block",
            "related_to": "This block is related to the linked block",
        }
        return descriptions.get(
            link.relation, f"This block has '{link.relation}' relationship with the linked block"
        )

    else:  # incoming
        # Target block -> source block
        descriptions = {
            "subtask_of": "The linked block is a subtask of this block",
            "depends_on": "The linked block depends on this block",
            "blocks": "The linked block blocks this block",
            "child_of": "The linked block is a child of this block",
            "belongs_to_epic": "The linked block belongs to this epic",
            "bug_affects": "The linked bug affects this block",
            "references": "The linked block references this block",
            "mentions": "The linked block mentions this block",
            "related_to": "The linked block is related to this block",
        }
        return descriptions.get(
            link.relation, f"The linked block has '{link.relation}' relationship with this block"
        )


def get_linked_blocks_tool(
    source_block_id: str,
    relation_filter: Optional[str] = None,
    direction_filter: Optional[str] = "both",
    limit: Optional[int] = 50,
    memory_bank=None,
    **kwargs,
) -> GetLinkedBlocksOutput:
    """
    Retrieve all blocks linked to a source block with full context.

    Args:
        source_block_id: ID of the source block to find links for
        relation_filter: Optional filter by specific relation type
        direction_filter: Filter by link direction ("incoming", "outgoing", "both")
        limit: Maximum number of linked blocks to return
        memory_bank: Memory bank instance
        **kwargs: Additional parameters

    Returns:
        GetLinkedBlocksOutput with linked blocks and relationship context
    """
    logger.debug(
        f"Getting linked blocks for source_block_id={source_block_id}, relation_filter={relation_filter}, direction_filter={direction_filter}"
    )

    try:
        # Validate input
        input_data = GetLinkedBlocksInput(
            source_block_id=source_block_id,
            relation_filter=relation_filter,
            direction_filter=direction_filter,
            limit=limit,
            **kwargs,
        )

        return get_linked_blocks(input_data, memory_bank)

    except Exception as e:
        error_msg = f"Input validation error: {str(e)}"
        logger.error(error_msg)
        return GetLinkedBlocksOutput(
            success=False,
            source_block_id=source_block_id,
            total_count=0,
            error=error_msg,
            timestamp=datetime.now(),
        )


def get_linked_blocks(input_data: GetLinkedBlocksInput, memory_bank) -> GetLinkedBlocksOutput:
    """
    Core function to retrieve linked blocks with full context.

    Args:
        input_data: GetLinkedBlocksInput containing the retrieval parameters
        memory_bank: An instance of StructuredMemoryBank

    Returns:
        GetLinkedBlocksOutput with linked blocks and relationship context
    """
    logger.debug(f"Getting linked blocks for: {input_data}")

    try:
        # Step 1: Verify source block exists
        source_check = get_memory_block_core(
            CoreGetMemoryBlockInput(block_ids=[input_data.source_block_id]), memory_bank
        )

        if not source_check.success or not source_check.blocks:
            return GetLinkedBlocksOutput(
                success=False,
                source_block_id=input_data.source_block_id,
                total_count=0,
                error=f"Source block {input_data.source_block_id} not found",
                timestamp=datetime.now(),
            )

        # Step 2: Get all links involving this block
        all_links = []

        # Get outgoing links (from source block)
        if input_data.direction_filter in ["outgoing", "both"]:
            # Use the link manager directly to get outgoing links
            if hasattr(memory_bank, "link_manager"):
                from infra_core.memory_system.link_manager import LinkQuery

                query = LinkQuery()
                if input_data.relation_filter:
                    query = query.relation(input_data.relation_filter)
                query = query.limit(input_data.limit or 50)

                outgoing_result = memory_bank.link_manager.links_from(
                    input_data.source_block_id, query
                )
                for link in outgoing_result.links:
                    all_links.append((link, "outgoing"))

        # Get incoming links (to source block)
        if input_data.direction_filter in ["incoming", "both"]:
            if hasattr(memory_bank, "link_manager"):
                from infra_core.memory_system.link_manager import LinkQuery

                query = LinkQuery()
                if input_data.relation_filter:
                    query = query.relation(input_data.relation_filter)
                query = query.limit(input_data.limit or 50)

                incoming_result = memory_bank.link_manager.links_to(
                    input_data.source_block_id, query
                )
                for link in incoming_result.links:
                    all_links.append((link, "incoming"))

        # Apply limit across all links
        if input_data.limit:
            all_links = all_links[: input_data.limit]

        # Step 3: Get block details for all linked blocks
        linked_block_ids = []
        for link, direction in all_links:
            if direction == "outgoing":
                linked_block_ids.append(link.to_id)
            else:  # incoming
                linked_block_ids.append(link.from_id)

        # Remove duplicates while preserving order
        seen = set()
        unique_linked_block_ids = []
        for block_id in linked_block_ids:
            if block_id not in seen:
                seen.add(block_id)
                unique_linked_block_ids.append(block_id)

        # Handle case where there are no linked blocks
        if not unique_linked_block_ids:
            logger.debug(f"No linked blocks found for {input_data.source_block_id}")
            return GetLinkedBlocksOutput(
                success=True,
                source_block_id=input_data.source_block_id,
                linked_blocks=[],
                total_count=0,
                timestamp=datetime.now(),
            )

        # Get block details
        blocks_result = get_memory_block_core(
            CoreGetMemoryBlockInput(block_ids=unique_linked_block_ids), memory_bank
        )

        if not blocks_result.success:
            return GetLinkedBlocksOutput(
                success=False,
                source_block_id=input_data.source_block_id,
                total_count=0,
                error=f"Failed to retrieve linked blocks: {blocks_result.error}",
                timestamp=datetime.now(),
            )

        # Create a lookup for blocks by ID
        blocks_by_id = {block.id: block for block in blocks_result.blocks}

        # Step 4: Combine links with block details
        linked_blocks = []
        for link, direction in all_links:
            linked_block_id = link.to_id if direction == "outgoing" else link.from_id

            if linked_block_id in blocks_by_id:
                block = blocks_by_id[linked_block_id]
                relationship_description = _generate_relationship_description(
                    link, direction, input_data.source_block_id
                )

                linked_block_info = LinkedBlockInfo(
                    block=block,
                    relationship=link,
                    direction=direction,
                    relationship_description=relationship_description,
                )
                linked_blocks.append(linked_block_info)

        logger.debug(
            f"Successfully retrieved {len(linked_blocks)} linked blocks for {input_data.source_block_id}"
        )

        return GetLinkedBlocksOutput(
            success=True,
            source_block_id=input_data.source_block_id,
            linked_blocks=linked_blocks,
            total_count=len(linked_blocks),
            timestamp=datetime.now(),
        )

    except Exception as e:
        error_msg = f"Error retrieving linked blocks: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return GetLinkedBlocksOutput(
            success=False,
            source_block_id=input_data.source_block_id,
            total_count=0,
            error=error_msg,
            timestamp=datetime.now(),
        )
