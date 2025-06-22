"""
GlobalMemoryInventoryTool: Cross-namespace discovery tool for memory block inventory.

This tool solves namespace blindness by providing agents with a fast way to discover
what data exists across all namespaces and branches without being limited by
automatic namespace injection.

Key capabilities:
- Cross-namespace, cross-branch scan with **NO automatic namespace injection**
- Lightweight aggregate query (SELECT namespace_id, type, COUNT(*), MAX(updated_at) GROUP BY ...)
- Gives agents an index to plan follow-up calls
- Optional filtering by branch, updated_since, tag, metadata_contains
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from ...structured_memory_bank import StructuredMemoryBank
from ..base.cogni_tool import CogniTool

# Setup logging
logger = logging.getLogger(__name__)


class InventoryBucket(BaseModel):
    """A single inventory bucket representing aggregated block data."""

    namespace_id: str = Field(..., description="Namespace identifier")
    block_type: str = Field(..., description="Type of memory block")
    count: int = Field(..., description="Number of blocks in this bucket")
    last_updated: Optional[datetime] = Field(
        None, description="Most recent update timestamp in this bucket"
    )
    sample_titles: List[str] = Field(
        default_factory=list, description="Sample titles from this bucket (max 3)"
    )


class GlobalMemoryInventoryInput(BaseModel):
    """Input model for global memory inventory."""

    branch_filter: Optional[str] = Field(None, description="Optional filter by specific branch")
    updated_since: Optional[datetime] = Field(
        None, description="Only include buckets with updates since this timestamp"
    )
    tag_contains: Optional[str] = Field(
        None, description="Only include buckets where blocks contain this tag"
    )
    metadata_contains_key: Optional[str] = Field(
        None, description="Only include buckets where blocks have this metadata key"
    )
    include_sample_titles: bool = Field(
        True, description="Whether to include sample titles for each bucket"
    )
    max_buckets: int = Field(100, description="Maximum number of buckets to return", ge=1, le=500)


class GlobalMemoryInventoryOutput(BaseModel):
    """Output model for global memory inventory results."""

    success: bool = Field(..., description="Whether the inventory was successful")
    buckets: List[InventoryBucket] = Field(
        default_factory=list, description="Inventory buckets grouped by namespace and type"
    )
    total_namespaces: int = Field(0, description="Total number of namespaces found")
    total_blocks: int = Field(0, description="Total number of blocks across all buckets")
    active_branch: str = Field(..., description="Branch used for the inventory")
    message: str = Field("", description="Human-readable summary message")
    error: Optional[str] = Field(None, description="Error message if inventory failed")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Timestamp of the inventory"
    )


def global_memory_inventory_core(
    input_data: GlobalMemoryInventoryInput, memory_bank: StructuredMemoryBank
) -> GlobalMemoryInventoryOutput:
    """
    Generate a cross-namespace inventory of memory blocks with aggregate statistics.

    This function explicitly bypasses namespace injection to provide full visibility
    across all namespaces and branches.

    Args:
        input_data: Input parameters for the inventory
        memory_bank: StructuredMemoryBank instance for querying

    Returns:
        GlobalMemoryInventoryOutput containing inventory buckets and statistics
    """
    try:
        logger.info("🔍 Starting global memory inventory (bypassing namespace injection)")

        # Build the base query with explicit cross-namespace scope
        base_query = """
        SELECT 
            namespace_id,
            type,
            COUNT(*) as count,
            MAX(updated_at) as last_updated
        FROM memory_blocks
        WHERE 1=1
        """

        params = []

        # Apply optional filters
        if input_data.updated_since:
            base_query += " AND updated_at >= %s"
            params.append(input_data.updated_since)

        if input_data.tag_contains:
            base_query += " AND JSON_CONTAINS(tags, %s)"
            params.append(f'"{input_data.tag_contains}"')

        if input_data.metadata_contains_key:
            base_query += " AND JSON_EXTRACT(metadata, %s) IS NOT NULL"
            params.append(f"$.{input_data.metadata_contains_key}")

        # Group by namespace and type
        base_query += """
        GROUP BY namespace_id, type
        ORDER BY namespace_id, count DESC
        LIMIT %s
        """
        params.append(input_data.max_buckets)

        # Execute the aggregation query
        logger.info(f"Executing inventory query: {base_query}")
        logger.info(f"Query parameters: {params}")

        # Use the memory bank's reader properly with the correct method
        results = memory_bank.dolt_reader._execute_query(base_query, tuple(params))

        # Build inventory buckets
        buckets = []
        total_blocks = 0
        namespaces_seen = set()

        # Collect all namespace+type combinations for batch sample fetching
        bucket_specs = []
        for row in results:
            namespace_id = row["namespace_id"]
            block_type = row["type"]
            count = row["count"]
            last_updated = row["last_updated"]

            namespaces_seen.add(namespace_id)
            total_blocks += count

            bucket_specs.append(
                {
                    "namespace_id": namespace_id,
                    "block_type": block_type,
                    "count": count,
                    "last_updated": last_updated,
                }
            )

        # Batch fetch sample titles if requested
        sample_titles_map = {}
        if input_data.include_sample_titles and bucket_specs:
            # Instead of complex VALUES clause, use multiple OR conditions
            # This is simpler and avoids SQL injection issues

            for spec in bucket_specs:
                namespace_id = spec["namespace_id"]
                block_type = spec["block_type"]

                # Simple query for each namespace+type combination
                sample_query = """
                SELECT title 
                FROM memory_blocks 
                WHERE namespace_id = %s AND type = %s AND title IS NOT NULL
                ORDER BY updated_at DESC 
                LIMIT 3
                """

                sample_results = memory_bank.dolt_reader._execute_query(
                    sample_query, (namespace_id, block_type)
                )

                # Store samples for this bucket
                key = (namespace_id, block_type)
                sample_titles_map[key] = [row["title"] for row in sample_results if row["title"]]

        # Build final buckets with cached sample titles
        for spec in bucket_specs:
            sample_titles = sample_titles_map.get((spec["namespace_id"], spec["block_type"]), [])

            bucket = InventoryBucket(
                namespace_id=spec["namespace_id"],
                block_type=spec["block_type"],
                count=spec["count"],
                last_updated=spec["last_updated"],
                sample_titles=sample_titles,
            )
            buckets.append(bucket)

        # Generate summary message
        message = f"Found {len(buckets)} inventory buckets across {len(namespaces_seen)} namespaces containing {total_blocks} total blocks"
        if input_data.updated_since:
            message += f" (updated since {input_data.updated_since})"

        logger.info(f"✅ Global inventory complete: {message}")

        return GlobalMemoryInventoryOutput(
            success=True,
            buckets=buckets,
            total_namespaces=len(namespaces_seen),
            total_blocks=total_blocks,
            active_branch=memory_bank.branch,
            message=message,
            timestamp=datetime.now(),
        )

    except Exception as e:
        error_msg = f"Global memory inventory failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return GlobalMemoryInventoryOutput(
            success=False,
            buckets=[],
            total_namespaces=0,
            total_blocks=0,
            active_branch=memory_bank.branch,
            message="Inventory failed",
            error=error_msg,
            timestamp=datetime.now(),
        )


# Create the tool instance
global_memory_inventory_tool = CogniTool(
    name="GlobalMemoryInventory",
    description="Fast cross-namespace discovery of memory block inventory with aggregate statistics",
    input_model=GlobalMemoryInventoryInput,
    output_model=GlobalMemoryInventoryOutput,
    function=global_memory_inventory_core,
    memory_linked=True,
)
