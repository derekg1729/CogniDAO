"""
GlobalSemanticSearchTool: Cross-namespace semantic search tool.

This tool provides semantic search across all namespaces by default, solving the
namespace blindness issue where agents can't find relevant content because they're
limited to a single namespace context.

Key capabilities:
- Semantic search with **NO automatic namespace injection** (searches everywhere by default)
- Optional namespace filtering if agents want to limit scope
- Same semantic search capabilities as QueryMemoryBlocksSemantic but with global scope
- Backward compatible with existing QueryMemoryBlocksSemantic parameters
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


class GlobalSemanticSearchInput(BaseModel):
    """Input model for global semantic search."""

    query_text: str = Field(..., description="Text to search for semantically")
    type_filter: Optional[
        Literal["knowledge", "task", "project", "doc", "interaction", "log", "epic", "bug"]
    ] = Field(None, description="Optional filter by block type")
    namespace_filter: Optional[str] = Field(
        None, description="Optional filter by specific namespace (None = search all namespaces)"
    )
    tag_filters: Optional[List[str]] = Field(None, description="Optional list of tags to filter by")
    top_k: Optional[int] = Field(10, description="Maximum number of results to return", ge=1, le=50)
    metadata_filters: Optional[Dict[str, Any]] = Field(
        None, description="Optional metadata key-value pairs to filter by"
    )
    include_namespace_stats: bool = Field(
        True, description="Whether to include per-namespace result statistics"
    )


class NamespaceStats(BaseModel):
    """Statistics about results from a specific namespace."""

    namespace_id: str = Field(..., description="Namespace identifier")
    result_count: int = Field(..., description="Number of results from this namespace")
    avg_score: float = Field(..., description="Average relevance score for this namespace")
    top_types: List[str] = Field(
        default_factory=list, description="Most common block types in results"
    )


class GlobalSemanticSearchOutput(BaseModel):
    """Output model for global semantic search results."""

    success: bool = Field(..., description="Whether the search was successful")
    blocks: List[MemoryBlock] = Field(
        default_factory=list, description="List of matching memory blocks from all namespaces"
    )
    total_results: int = Field(0, description="Total number of results returned")
    namespaces_searched: List[str] = Field(
        default_factory=list, description="List of namespaces that contained results"
    )
    namespace_stats: List[NamespaceStats] = Field(
        default_factory=list, description="Per-namespace result statistics"
    )
    query_text: str = Field("", description="Original query text for reference")
    active_branch: str = Field(..., description="Branch used for the search")
    message: str = Field("", description="Human-readable result message")
    error: Optional[str] = Field(None, description="Error message if search failed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of the search")


def global_semantic_search_core(
    input_data: GlobalSemanticSearchInput, memory_bank: StructuredMemoryBank
) -> GlobalSemanticSearchOutput:
    """
    Perform semantic search across all namespaces by default.

    This function explicitly bypasses namespace injection to provide semantic search
    across the entire memory system, while still allowing optional namespace filtering.

    Args:
        input_data: Input parameters for the global semantic search
        memory_bank: StructuredMemoryBank instance for searching

    Returns:
        GlobalSemanticSearchOutput containing search results and statistics
    """
    try:
        logger.info(f"🔍 Starting global semantic search for: '{input_data.query_text}'")

        # Perform semantic search without namespace restrictions
        # The semantic search naturally queries across all data unless filtered
        all_blocks = memory_bank.query_semantic(
            query_text=input_data.query_text,
            top_k=input_data.top_k * 2,  # Get more results to allow for filtering
        )

        # Ensure all blocks are MemoryBlock objects
        all_blocks = [b if isinstance(b, MemoryBlock) else MemoryBlock(**b) for b in all_blocks]

        logger.info(f"Raw semantic search returned {len(all_blocks)} results")

        # Apply filters
        filtered_blocks = all_blocks

        # Apply type filter if specified
        if input_data.type_filter:
            filtered_blocks = [b for b in filtered_blocks if b.type == input_data.type_filter]
            logger.info(
                f"After type filter '{input_data.type_filter}': {len(filtered_blocks)} results"
            )

        # Apply namespace filter if specified (this allows intentional namespace limitation)
        if input_data.namespace_filter:
            filtered_blocks = [
                b for b in filtered_blocks if b.namespace_id == input_data.namespace_filter
            ]
            logger.info(
                f"After namespace filter '{input_data.namespace_filter}': {len(filtered_blocks)} results"
            )

        # Apply tag filters if specified
        if input_data.tag_filters:
            filtered_blocks = [
                b
                for b in filtered_blocks
                if all(tag in (b.tags or []) for tag in input_data.tag_filters)
            ]
            logger.info(
                f"After tag filters {input_data.tag_filters}: {len(filtered_blocks)} results"
            )

        # Apply metadata filters if specified
        if input_data.metadata_filters:
            filtered_blocks = [
                b
                for b in filtered_blocks
                if all(
                    (b.metadata or {}).get(k) == v for k, v in input_data.metadata_filters.items()
                )
            ]
            logger.info(f"After metadata filters: {len(filtered_blocks)} results")

        # Limit to requested top_k
        final_blocks = filtered_blocks[: input_data.top_k]

        # Collect namespace statistics
        namespaces_found = set()
        namespace_counts = {}
        namespace_types = {}

        for block in final_blocks:
            ns = block.namespace_id
            namespaces_found.add(ns)
            namespace_counts[ns] = namespace_counts.get(ns, 0) + 1

            if ns not in namespace_types:
                namespace_types[ns] = []
            namespace_types[ns].append(block.type)

        # Build namespace statistics if requested
        namespace_stats = []
        if input_data.include_namespace_stats:
            for ns in namespaces_found:
                # Calculate average score (simplified - would need actual relevance scores)
                avg_score = 0.8  # Placeholder since we don't have access to semantic scores

                # Get top types for this namespace
                types_in_ns = namespace_types[ns]
                type_counts = {}
                for t in types_in_ns:
                    type_counts[t] = type_counts.get(t, 0) + 1
                top_types = sorted(type_counts.keys(), key=lambda x: type_counts[x], reverse=True)[
                    :3
                ]

                stats = NamespaceStats(
                    namespace_id=ns,
                    result_count=namespace_counts[ns],
                    avg_score=avg_score,
                    top_types=top_types,
                )
                namespace_stats.append(stats)

        # Build result message
        if input_data.namespace_filter:
            message = (
                f"Found {len(final_blocks)} results in namespace '{input_data.namespace_filter}'"
            )
        else:
            message = f"Found {len(final_blocks)} results across {len(namespaces_found)} namespaces"
            if len(namespaces_found) > 1:
                ns_list = list(namespaces_found)[:3]  # Show first 3
                if len(namespaces_found) > 3:
                    ns_list.append("...")
                message += f" ({', '.join(ns_list)})"

        logger.info(f"✅ Global semantic search complete: {message}")

        return GlobalSemanticSearchOutput(
            success=True,
            blocks=final_blocks,
            total_results=len(final_blocks),
            namespaces_searched=list(namespaces_found),
            namespace_stats=namespace_stats,
            query_text=input_data.query_text,
            active_branch=memory_bank.branch,
            message=message,
            timestamp=datetime.now(),
        )

    except Exception as e:
        error_msg = f"Global semantic search failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return GlobalSemanticSearchOutput(
            success=False,
            blocks=[],
            total_results=0,
            namespaces_searched=[],
            namespace_stats=[],
            query_text=input_data.query_text,
            active_branch=memory_bank.branch,
            message="Search failed",
            error=error_msg,
            timestamp=datetime.now(),
        )


# Create the tool instance
global_semantic_search_tool = CogniTool(
    name="GlobalSemanticSearch",
    description="Semantic search across all namespaces by default, with optional namespace filtering",
    input_model=GlobalSemanticSearchInput,
    output_model=GlobalSemanticSearchOutput,
    function=global_semantic_search_core,
    memory_linked=True,
)
