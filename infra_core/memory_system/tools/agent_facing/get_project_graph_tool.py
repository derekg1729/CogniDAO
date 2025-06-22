"""
GetProjectGraphTool: Hierarchical project data retrieval tool.

This tool solves the multiple-query problem by fetching a project (or any block)
with its complete linked hierarchy in one shot, returning nested JSON structure
with children, parents, and dependency relations.

Key capabilities:
- Uses link table joins to fetch children/parent/dependency relations recursively
- Includes minimal metadata for each node (title, status, priority) for LLM summarization
- Optional server-side LLM summary generation
- Configurable depth limit and cycle protection

TODO replace with NetworkX backend graph implementaion
"""

from typing import Optional, List, Dict, Set
from datetime import datetime
from pydantic import BaseModel, Field
import logging
from collections import defaultdict, deque

from ...schemas.memory_block import MemoryBlock
from ...structured_memory_bank import StructuredMemoryBank
from ..base.cogni_tool import CogniTool

# Setup logging
logger = logging.getLogger(__name__)


class GraphNode(BaseModel):
    """A node in the project graph with block data and relationships."""

    # Core block data
    block_id: str = Field(..., description="Unique block identifier")
    title: str = Field("", description="Block title")
    type: str = Field(..., description="Block type (project, epic, task, etc.)")
    status: Optional[str] = Field(None, description="Current status")
    priority: Optional[str] = Field(None, description="Priority level")
    namespace_id: str = Field(..., description="Namespace identifier")

    # Relationship data
    children: List["GraphNode"] = Field(default_factory=list, description="Child nodes")
    dependencies: List["GraphNode"] = Field(
        default_factory=list, description="Nodes this depends on"
    )
    dependents: List["GraphNode"] = Field(
        default_factory=list, description="Nodes that depend on this"
    )

    # Metadata
    depth: int = Field(0, description="Depth level in the graph")
    relationship_type: Optional[str] = Field(None, description="Type of relationship to parent")


class GetProjectGraphInput(BaseModel):
    """Input model for project graph retrieval."""

    root_block_id: str = Field(..., description="ID of the root block to build graph from")
    max_depth: int = Field(3, description="Maximum depth to traverse", ge=1, le=10)
    include_dependencies: bool = Field(
        True, description="Whether to include dependency relationships"
    )
    include_reverse_dependencies: bool = Field(
        False, description="Whether to include reverse dependencies (what depends on this)"
    )
    relation_filters: Optional[List[str]] = Field(
        None, description="Only include specific relation types"
    )
    summarize: bool = Field(False, description="Generate an LLM summary of the project graph")
    namespace_scope: Optional[str] = Field(
        None, description="Limit graph traversal to specific namespace (None = cross-namespace)"
    )


class GetProjectGraphOutput(BaseModel):
    """Output model for project graph results."""

    success: bool = Field(..., description="Whether the graph retrieval was successful")
    root_node: Optional[GraphNode] = Field(None, description="Root node of the project graph")
    total_nodes: int = Field(0, description="Total number of nodes in the graph")
    max_depth_reached: int = Field(0, description="Maximum depth actually reached")
    cycles_detected: List[str] = Field(
        default_factory=list, description="Block IDs where cycles were detected and broken"
    )
    summary: Optional[str] = Field(None, description="LLM-generated summary of the project graph")
    active_branch: str = Field(..., description="Branch used for the query")
    message: str = Field("", description="Human-readable result message")
    error: Optional[str] = Field(None, description="Error message if retrieval failed")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Timestamp of the retrieval"
    )


def get_project_graph_core(
    input_data: GetProjectGraphInput, memory_bank: StructuredMemoryBank
) -> GetProjectGraphOutput:
    """
    Retrieve a project with its complete linked hierarchy in one operation.

    This function uses breadth-first traversal with cycle detection to build
    a comprehensive project graph including children, dependencies, and metadata.

    Args:
        input_data: Input parameters for the graph retrieval
        memory_bank: StructuredMemoryBank instance for querying

    Returns:
        GetProjectGraphOutput containing the project graph and statistics
    """
    try:
        logger.info(f"🏗️ Building project graph for block {input_data.root_block_id}")

        # Track visited nodes to prevent cycles
        visited_nodes: Set[str] = set()
        cycles_detected: List[str] = []

        # Cache for fetched blocks to avoid duplicate queries
        block_cache: Dict[str, MemoryBlock] = {}

        # Queue for breadth-first traversal: (block_id, depth, parent_id, relationship_type)
        traversal_queue = deque([(input_data.root_block_id, 0, None, None)])

        # Build the graph structure
        graph_nodes: Dict[str, GraphNode] = {}
        max_depth_reached = 0

        while traversal_queue and max_depth_reached < input_data.max_depth:
            current_id, depth, parent_id, rel_type = traversal_queue.popleft()

            # Skip if already visited (cycle detection)
            if current_id in visited_nodes:
                if current_id not in cycles_detected:
                    cycles_detected.append(current_id)
                    logger.warning(f"Cycle detected at block {current_id}, skipping")
                continue

            visited_nodes.add(current_id)
            max_depth_reached = max(max_depth_reached, depth)

            # Fetch the block if not in cache
            if current_id not in block_cache:
                block_result = memory_bank.get_memory_block(current_id)
                if not block_result:
                    logger.warning(f"Block {current_id} not found, skipping")
                    continue
                block_cache[current_id] = block_result

            block = block_cache[current_id]

            # Apply namespace scope filter if specified
            if input_data.namespace_scope and block.namespace_id != input_data.namespace_scope:
                logger.debug(
                    f"Skipping block {current_id} - outside namespace scope {input_data.namespace_scope}"
                )
                continue

            # Create graph node
            node = GraphNode(
                block_id=current_id,
                title=block.metadata.get(
                    "title", block.text[:50] + "..." if len(block.text) > 50 else block.text
                ),
                type=block.type,
                status=block.metadata.get("status"),
                priority=block.metadata.get("priority"),
                namespace_id=block.namespace_id,
                depth=depth,
                relationship_type=rel_type,
            )
            graph_nodes[current_id] = node

            # If we haven't reached max depth, find children and dependencies
            if depth < input_data.max_depth:
                # Get all links involving this block
                links_query = """
                SELECT source_block_id, target_block_id, relation
                FROM block_links 
                WHERE (source_block_id = %s OR target_block_id = %s)
                """

                query_params = [current_id, current_id]

                if input_data.relation_filters:
                    placeholders = ", ".join(["%s"] * len(input_data.relation_filters))
                    links_query += f" AND relation IN ({placeholders})"
                    query_params.extend(input_data.relation_filters)

                links = memory_bank.dolt_reader._execute_query(links_query, tuple(query_params))

                # Process outgoing links (children and dependencies)
                for link in links:
                    if link["source_block_id"] == current_id:
                        target_id = link["target_block_id"]
                        relation = link["relation"]

                        # Add to traversal queue
                        traversal_queue.append((target_id, depth + 1, current_id, relation))

                # Process incoming links if reverse dependencies requested
                if input_data.include_reverse_dependencies:
                    for link in links:
                        if link["target_block_id"] == current_id:
                            source_id = link["source_block_id"]
                            relation = f"reverse_{link['relation']}"

                            # Add to traversal queue
                            traversal_queue.append((source_id, depth + 1, current_id, relation))

        # Build the hierarchical structure
        root_node = graph_nodes.get(input_data.root_block_id)
        if not root_node:
            return GetProjectGraphOutput(
                success=False,
                total_nodes=0,
                max_depth_reached=0,
                active_branch=memory_bank.branch,
                message="Root block not found or inaccessible",
                error=f"Could not retrieve root block {input_data.root_block_id}",
                timestamp=datetime.now(),
            )

        # CRITICAL FIX: Build proper parent-child hierarchy from traversed links
        # Get all links between our discovered nodes for hierarchy building
        if len(graph_nodes) > 1:
            node_ids = list(graph_nodes.keys())
            placeholders = ", ".join(["%s"] * len(node_ids))
            hierarchy_query = f"""
            SELECT source_block_id, target_block_id, relation
            FROM block_links 
            WHERE source_block_id IN ({placeholders}) 
               AND target_block_id IN ({placeholders})
            """

            # Double the params for both IN clauses
            hierarchy_params = node_ids + node_ids
            hierarchy_links = memory_bank.dolt_reader._execute_query(
                hierarchy_query, tuple(hierarchy_params)
            )

            # Build parent-child relationships
            parent_child_relations = ["child_of", "subtask_of", "epic_of", "part_of"]
            dependency_relations = ["depends_on", "blocks", "requires"]

            for link in hierarchy_links:
                source_id = link["source_block_id"]
                target_id = link["target_block_id"]
                relation = link["relation"]

                source_node = graph_nodes.get(source_id)
                target_node = graph_nodes.get(target_id)

                if not source_node or not target_node:
                    continue

                # Handle parent-child relationships
                if relation in parent_child_relations:
                    # source is child of target
                    if target_node not in source_node.children:
                        target_node.children.append(source_node)

                # Handle dependencies
                elif relation in dependency_relations:
                    # source depends on target
                    if target_node not in source_node.dependencies:
                        source_node.dependencies.append(target_node)
                    if input_data.include_reverse_dependencies:
                        if source_node not in target_node.dependents:
                            target_node.dependents.append(source_node)

        # Sort children by priority and depth for consistent ordering
        for node in graph_nodes.values():
            node.children.sort(key=lambda x: (x.depth, x.priority or "ZZZ", x.title))
            node.dependencies.sort(key=lambda x: (x.priority or "ZZZ", x.title))
            node.dependents.sort(key=lambda x: (x.priority or "ZZZ", x.title))

        # Generate summary if requested
        summary = None
        if input_data.summarize:
            summary = _generate_project_summary(root_node, graph_nodes)

        # Build result message
        message = (
            f"Retrieved project graph with {len(graph_nodes)} nodes, max depth {max_depth_reached}"
        )
        if cycles_detected:
            message += f", {len(cycles_detected)} cycles detected and resolved"

        logger.info(f"✅ Project graph complete: {message}")

        return GetProjectGraphOutput(
            success=True,
            root_node=root_node,
            total_nodes=len(graph_nodes),
            max_depth_reached=max_depth_reached,
            cycles_detected=cycles_detected,
            summary=summary,
            active_branch=memory_bank.branch,
            message=message,
            timestamp=datetime.now(),
        )

    except Exception as e:
        error_msg = f"Project graph retrieval failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return GetProjectGraphOutput(
            success=False,
            total_nodes=0,
            max_depth_reached=0,
            cycles_detected=[],
            active_branch=memory_bank.branch,
            message="Graph retrieval failed",
            error=error_msg,
            timestamp=datetime.now(),
        )


def _generate_project_summary(root_node: GraphNode, all_nodes: Dict[str, GraphNode]) -> str:
    """Generate a concise LLM summary of the project graph."""
    # This is a placeholder - in practice you'd call an LLM service
    node_count = len(all_nodes)
    types_count = defaultdict(int)

    for node in all_nodes.values():
        types_count[node.type] += 1

    type_summary = ", ".join([f"{count} {type}s" for type, count in types_count.items()])

    return f"Project '{root_node.title}' contains {node_count} total items: {type_summary}. This is a hierarchical structure showing the complete project breakdown and dependencies."


# Create the tool instance
get_project_graph_tool = CogniTool(
    name="GetProjectGraph",
    description="Retrieve a project with its complete linked hierarchy in one operation",
    input_model=GetProjectGraphInput,
    output_model=GetProjectGraphOutput,
    function=get_project_graph_core,
    memory_linked=True,
)
