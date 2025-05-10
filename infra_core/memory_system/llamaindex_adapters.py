from infra_core.memory_system.schemas.memory_block import MemoryBlock
from llama_index.core.schema import TextNode, NodeRelationship, RelatedNodeInfo
from typing import Dict, Any
import json  # For serializing complex metadata
import logging
from datetime import datetime  # Import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define mapping from MemoryBlock relation types to LlamaIndex NodeRelationship enums
# This mapping determines how MemoryBlock.links are translated to LlamaIndex relationships
RELATION_TO_NODE_RELATIONSHIP = {
    # When a block has "subtask_of" links, it means it has children (subtasks)
    "subtask_of": NodeRelationship.CHILD,
    # When a block has "child_of" links, it means it has parents
    "child_of": NodeRelationship.PARENT,
    # When a block "depends_on" another, use PREVIOUS to avoid conflict with SOURCE
    "depends_on": NodeRelationship.PREVIOUS,
    # For "related_to" and generic relationships, use NEXT as a general connection
    "related_to": NodeRelationship.NEXT,
    # For "mentions" links, use NEXT relationship (closest match)
    "mentions": NodeRelationship.NEXT,
}


# Helper function to convert datetime objects in nested structures
def convert_datetimes_to_isoformat(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: convert_datetimes_to_isoformat(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetimes_to_isoformat(elem) for elem in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def memory_block_to_node(block: MemoryBlock) -> TextNode:
    """Converts a MemoryBlock Pydantic object into a LlamaIndex TextNode.

    Args:
        block: The MemoryBlock object to convert.

    Returns:
        A LlamaIndex TextNode representing the MemoryBlock.
    """
    # Initialize metadata dictionary
    metadata: Dict[str, Any] = {}

    # --- Map MemoryBlock fields to metadata ---
    # Simple fields
    metadata["type"] = block.type

    # Directly promote 'title' from block.metadata
    # This makes it top-level accessible in the LlamaIndex Node's metadata
    if block.metadata and "title" in block.metadata:
        metadata["title"] = block.metadata["title"]

    if block.tags:
        metadata["tags"] = ",".join(block.tags)  # Join tags into a comma-separated string
    if block.source_file:
        metadata["source_file"] = block.source_file
    if block.source_uri:
        metadata["source_uri"] = block.source_uri
    if block.created_by:
        metadata["created_by"] = block.created_by

    # Nested/Complex fields
    # Store nested metadata as a JSON string for potential filtering/retrieval
    if block.metadata:
        try:
            # Create a copy to avoid modifying the original if serializing the rest
            metadata_to_serialize = block.metadata.copy()
            # Optionally, if you want metadata_json to not duplicate the promoted title:
            # metadata_to_serialize.pop("title", None)

            serializable_metadata = convert_datetimes_to_isoformat(metadata_to_serialize)
            metadata["metadata_json"] = json.dumps(serializable_metadata)
        except TypeError as e:
            logger.warning(f"Could not serialize metadata for block {block.id}: {e}")
            # Decide on fallback: store partial, store as string repr, or omit
            # Fallback to repr if deep conversion and serialization still fail
            metadata["metadata_json"] = repr(block.metadata)

    # Flatten confidence scores
    if block.confidence:
        if block.confidence.human is not None:
            metadata["confidence_human"] = block.confidence.human
        if block.confidence.ai is not None:
            metadata["confidence_ai"] = block.confidence.ai

    # Convert datetimes to ISO format strings
    if block.created_at:
        metadata["created_at"] = block.created_at.isoformat()
    if block.updated_at:
        metadata["updated_at"] = block.updated_at.isoformat()

    # Add schema version if available (from Task 2.0 changes)
    if block.schema_version is not None:
        metadata["schema_version"] = block.schema_version

    # --- Construct enriched text for semantic search ---
    title = block.metadata.get("title", "Untitled")  # Get title from metadata or default
    tags_str = ", ".join(block.tags) if block.tags else "None"
    enriched_text_parts = [
        f"Title: {title}",
        f"Type: {block.type}",
        f"Tags: {tags_str}",
        "---",
        block.text,  # Original content
    ]
    enriched_text = "\n".join(enriched_text_parts)

    # --- Add enriched components to metadata (User Suggestion) ---
    metadata["enriched_title"] = title
    metadata["enriched_tags"] = tags_str

    # --- Create the TextNode ---
    node = TextNode(
        text=enriched_text,  # Use the enriched text
        id_=block.id,  # Map MemoryBlock.id to TextNode.id_
        metadata=metadata,  # Assign the populated metadata
    )

    # --- Handle relationships (Task 2.3) ---
    if block.links:
        # Initialize relationships dictionary if needed
        if not hasattr(node, "relationships") or node.relationships is None:
            node.relationships = {}

        # Process each link and convert to appropriate NodeRelationship
        for link in block.links:
            # Map the relation string to NodeRelationship enum
            if link.relation in RELATION_TO_NODE_RELATIONSHIP:
                node_relationship = RELATION_TO_NODE_RELATIONSHIP[link.relation]

                # Create RelatedNodeInfo with original relation in metadata
                related_node_info = RelatedNodeInfo(
                    node_id=link.to_id, metadata={"original_relation": link.relation}
                )

                # Add to the appropriate list in relationships dictionary
                if node_relationship not in node.relationships:
                    node.relationships[node_relationship] = []

                node.relationships[node_relationship].append(related_node_info)
                logger.debug(
                    f"Added relationship from {block.id} to {link.to_id}: '{link.relation}' → {node_relationship}"
                )
            else:
                # Handle unknown relation type - could default to NEXT or log a warning
                logger.warning(
                    f"Unknown relation type '{link.relation}' from {block.id} to {link.to_id}. Defaulting to NEXT."
                )

                # Default to NEXT for unknown types
                if NodeRelationship.NEXT not in node.relationships:
                    node.relationships[NodeRelationship.NEXT] = []

                node.relationships[NodeRelationship.NEXT].append(
                    RelatedNodeInfo(
                        node_id=link.to_id,
                        metadata={"original_relation": link.relation, "unknown_type": True},
                    )
                )

    return node


# Future tasks might add more conversion functions here, e.g., node_to_memory_block
