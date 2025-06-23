"""
GetProjectGraphTool: Hierarchical project data retrieval tool.

⚠️ **DEPRECATED - DO NOT USE** ⚠️
This tool is broken and incorrectly reports zero links for projects that have many links.
The link traversal logic is fundamentally flawed and needs a complete rewrite.

TODO: Complete rewrite with proper link traversal or remove entirely
TODO: Replace with NetworkX backend graph implementation

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

from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel, Field
import logging
from collections import defaultdict

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
    ⚠️ **DEPRECATED - BROKEN IMPLEMENTATION** ⚠️

    This implementation is fundamentally flawed and incorrectly reports zero links
    for projects that have many links. DO NOT USE.

    Returns an error immediately to prevent incorrect results.
    """
    logger.error("❌ GetProjectGraph tool is deprecated and broken - refusing to execute")

    return GetProjectGraphOutput(
        success=False,
        total_nodes=0,
        max_depth_reached=0,
        cycles_detected=[],
        active_branch=memory_bank.branch,
        message="Tool is deprecated and broken",
        error="GetProjectGraph tool is deprecated due to broken link traversal logic. Use GetLinkedBlocks or direct link queries instead.",
        timestamp=datetime.now(),
    )


# COMMENTED OUT - BROKEN IMPLEMENTATION
"""
def get_project_graph_core(
    input_data: GetProjectGraphInput, memory_bank: StructuredMemoryBank
) -> GetProjectGraphOutput:
    \"\"\"
    Core implementation for retrieving project graphs with hierarchical relationships.

    Builds a complete project graph by traversing block relationships through
    the block_links table, respecting depth limits and relationship filters.
    \"\"\"
    logger.info(
        f"🔍 Building project graph for {input_data.root_block_id}, "
        f"max_depth={input_data.max_depth}, "
        f"include_deps={input_data.include_dependencies}, "
        f"include_reverse_deps={input_data.include_reverse_dependencies}"
    )

    try:
        # Initialize tracking structures
        graph_nodes: Dict[str, GraphNode] = {}
        visited: Set[str] = set()
        cycles_detected: List[str] = []
        max_depth_reached = 0

        # BFS traversal queue: (block_id, depth, parent_id, relationship_type)
        traversal_queue: Deque[Tuple[str, int, Optional[str], Optional[str]]] = deque()
        traversal_queue.append((input_data.root_block_id, 0, None, None))

        # Block cache to avoid repeated database calls
        block_cache: Dict[str, MemoryBlock] = {}

        # BFS traversal to discover all connected blocks
        while traversal_queue:
            current_id, depth, parent_id, rel_type = traversal_queue.popleft()

            # Update max depth tracking
            max_depth_reached = max(max_depth_reached, depth)

            # Skip if already visited (cycle detection)
            if current_id in visited:
                if current_id not in cycles_detected:
                    cycles_detected.append(current_id)
                    logger.debug(f"Cycle detected at block {current_id}, depth {depth}")
                continue

            visited.add(current_id)

            # Fetch block data if not cached
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
                # Get outgoing links using dolt_reader
                forward_links = memory_bank.dolt_reader.read_forward_links(
                    block_id=current_id,
                    relation=None,  # We'll filter by relation_filters later if needed
                    branch=memory_bank.branch,
                )

                # Process outgoing links (children and dependencies)
                for link in forward_links:
                    # Apply relation filter if specified
                    if (
                        input_data.relation_filters
                        and link["relation"] not in input_data.relation_filters
                    ):
                        continue

                    target_id = link["to_block_id"]
                    relation = link["relation"]

                    # Add to traversal queue
                    traversal_queue.append((target_id, depth + 1, current_id, relation))

                # Process incoming links if reverse dependencies requested
                if input_data.include_reverse_dependencies:
                    backlinks = memory_bank.dolt_reader.read_backlinks(
                        block_id=current_id,
                        relation=None,  # We'll filter by relation_filters later if needed
                        branch=memory_bank.branch,
                    )
                    
                    for link in backlinks:
                        # Apply relation filter if specified
                        if (
                            input_data.relation_filters
                            and link["relation"] not in input_data.relation_filters
                        ):
                            continue

                        source_id = link["from_block_id"]
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

        # Build proper parent-child hierarchy from all discovered nodes
        if len(graph_nodes) > 1:
            # Get all links between our discovered nodes for hierarchy building
            for node_id in graph_nodes.keys():
                # Get forward links for this node
                forward_links = memory_bank.dolt_reader.read_forward_links(
                    block_id=node_id,
                    relation=None,
                    branch=memory_bank.branch,
                )

                # Process links between discovered nodes only
                for link in forward_links:
                    source_id = link["from_block_id"]
                    target_id = link["to_block_id"]
                    relation = link["relation"]

                    source_node = graph_nodes.get(source_id)
                    target_node = graph_nodes.get(target_id)

                    # Only process links between nodes we've discovered
                    if not source_node or not target_node:
                        continue

                    # Handle parent-child relationships
                    parent_child_relations = ["child_of", "subtask_of", "epic_of", "part_of"]
                    dependency_relations = ["depends_on", "blocks", "requires"]

                    if relation in parent_child_relations:
                        # source is child of target
                        if source_node not in target_node.children:
                            target_node.children.append(source_node)

                    # Handle dependencies
                    elif relation in dependency_relations and input_data.include_dependencies:
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
"""


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
    description="⚠️ DEPRECATED - DO NOT USE - Broken link traversal tool that reports incorrect results",
    input_model=GetProjectGraphInput,
    output_model=GetProjectGraphOutput,
    function=get_project_graph_core,
    memory_linked=True,
)
