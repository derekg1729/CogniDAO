"""
GetActiveWorkItemsTool: Agent-facing tool for retrieving work items that are currently active.

This tool provides a focused interface for agents to retrieve work items (tasks, projects,
epics, bugs) that are currently in progress with optional priority and type filtering.
"""

from typing import Optional, List, Literal
from datetime import datetime
import logging

from pydantic import BaseModel, Field

from ..memory_core.get_memory_block_core import (
    get_memory_block_core,
    GetMemoryBlockInput as CoreGetMemoryBlockInput,
)
from infra_core.memory_system.schemas.memory_block import MemoryBlock
from ..base.cogni_tool import CogniTool

# Setup logging
logger = logging.getLogger(__name__)

# Type literals for input validation
WorkItemTypeLiteral = Literal["task", "project", "epic", "bug"]
PriorityLiteral = Literal["P0", "P1", "P2", "P3", "P4", "P5"]


class GetActiveWorkItemsInput(BaseModel):
    """Input model for retrieving active work items."""

    priority_filter: Optional[PriorityLiteral] = Field(
        None, description="Optional filter by priority level (P0 highest, P5 lowest)"
    )
    work_item_type_filter: Optional[WorkItemTypeLiteral] = Field(
        None, description="Optional filter by work item type"
    )
    limit: Optional[int] = Field(
        None, description="Maximum number of results to return", ge=1, le=100
    )
    namespace_id: str = Field("cogni-project-management", description="Namespace ID")


class GetActiveWorkItemsOutput(BaseModel):
    """Output model for the get active work items operation."""

    success: bool = Field(..., description="Whether the operation was successful.")
    work_items: List[MemoryBlock] = Field(
        default_factory=list,
        description="The retrieved active work items, sorted by priority then creation date.",
    )
    total_count: int = Field(0, description="Total number of active work items found")
    current_branch: Optional[str] = Field(None, description="Current Dolt branch")
    error: Optional[str] = Field(None, description="Error message if operation failed.")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Timestamp of when the operation was performed."
    )


def _sort_work_items_by_priority(work_items: List[MemoryBlock]) -> List[MemoryBlock]:
    """
    Sort work items by priority (P0 highest) then by creation date (newest first).

    Args:
        work_items: List of work item memory blocks

    Returns:
        Sorted list of work items
    """
    # Priority order mapping (P0 = highest priority = 0, P5 = lowest priority = 5)
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4, "P5": 5}

    def sort_key(item: MemoryBlock):
        # Get priority, default to P5 (lowest) if not set
        priority = item.metadata.get("priority", "P5")
        priority_rank = priority_order.get(priority, 5)

        # Use created_at for secondary sort (newest first)
        created_at = item.created_at if item.created_at else datetime.min

        return (priority_rank, -created_at.timestamp())

    return sorted(work_items, key=sort_key)


def get_active_work_items(
    input_data: GetActiveWorkItemsInput, memory_bank
) -> GetActiveWorkItemsOutput:
    """
    Retrieve work items that are currently active (status='in_progress') with optional filtering.

    Args:
        input_data: GetActiveWorkItemsInput containing the filtering parameters
        memory_bank: An instance of StructuredMemoryBank

    Returns:
        GetActiveWorkItemsOutput with the retrieved active work items
    """
    logger.debug(f"Agent-facing get_active_work_items called with input: {input_data}")

    try:
        # Build metadata filters - always filter by status='in_progress'
        metadata_filters = {"status": "in_progress"}

        # Add priority filter if specified
        if input_data.priority_filter:
            metadata_filters["priority"] = input_data.priority_filter

        # Build core input for filtering work item types
        core_input_params = {
            "namespace_id": input_data.namespace_id,
            "metadata_filters": metadata_filters,
            "limit": input_data.limit,
            "branch": memory_bank.dolt_writer.active_branch,  # Use current active branch
        }

        # Add work item type filter if specified
        if input_data.work_item_type_filter:
            core_input_params["type_filter"] = input_data.work_item_type_filter
        else:
            # If no specific type requested, we need to filter for work item types only
            # We'll get all blocks with status='in_progress' and filter by type afterward
            pass

        # Create core input for GetMemoryBlock
        core_input = CoreGetMemoryBlockInput(**core_input_params)

        # Call the core function
        core_result = get_memory_block_core(core_input, memory_bank)

        if not core_result.success:
            return GetActiveWorkItemsOutput(
                success=False,
                error=core_result.error,
                current_branch=core_result.current_branch,
                timestamp=datetime.now(),
            )

        # Filter for work item types if no specific type was requested
        work_items = core_result.blocks
        if not input_data.work_item_type_filter:
            work_item_types = {"task", "project", "epic", "bug"}
            work_items = [block for block in work_items if block.type in work_item_types]

        # Sort by priority then creation date
        sorted_work_items = _sort_work_items_by_priority(work_items)

        logger.debug(f"Successfully retrieved {len(sorted_work_items)} active work items")

        return GetActiveWorkItemsOutput(
            success=True,
            work_items=sorted_work_items,
            total_count=len(sorted_work_items),
            current_branch=core_result.current_branch,
            timestamp=datetime.now(),
        )

    except Exception as e:
        error_msg = f"Agent-facing get_active_work_items failed: {str(e)}"
        logger.error(error_msg, exc_info=True)

        # Try to get current branch even in error case
        try:
            current_branch = memory_bank.dolt_writer.active_branch
        except Exception:
            current_branch = "unknown"

        return GetActiveWorkItemsOutput(
            success=False, error=error_msg, current_branch=current_branch, timestamp=datetime.now()
        )


# Create the tool instance
get_active_work_items_tool = CogniTool(
    name="GetActiveWorkItems",
    description="Get work items that are currently active (status='in_progress') with optional filtering",
    input_model=GetActiveWorkItemsInput,
    output_model=GetActiveWorkItemsOutput,
    function=get_active_work_items,
    memory_linked=True,
)
