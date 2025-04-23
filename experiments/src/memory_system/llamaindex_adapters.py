from experiments.src.memory_system.schemas.memory_block import MemoryBlock
from llama_index.core.schema import TextNode
from typing import Dict, Any
import json # For serializing complex metadata


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
            metadata["metadata_json"] = json.dumps(block.metadata)
        except TypeError as e:
            print(f"Warning: Could not serialize metadata for block {block.id}: {e}")
            # Decide on fallback: store partial, store as string repr, or omit
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

    # Note: block.links are intentionally *not* added to metadata here.
    # They will be converted to NodeRelationship objects in Task 2.3.

    # --- Construct enriched text for semantic search --- 
    title = block.metadata.get('title', 'Untitled') # Get title from metadata or default
    tags_str = ", ".join(block.tags) if block.tags else "None"
    enriched_text_parts = [
        f"Title: {title}",
        f"Type: {block.type}",
        f"Tags: {tags_str}",
        "---",
        block.text # Original content
    ]
    enriched_text = "\n".join(enriched_text_parts)

    # --- Add enriched components to metadata (User Suggestion) ---
    metadata["enriched_title"] = title
    metadata["enriched_tags"] = tags_str

    # --- Create the TextNode --- 
    node = TextNode(
        text=enriched_text, # Use the enriched text
        id_=block.id, # Map MemoryBlock.id to TextNode.id_
        metadata=metadata # Assign the populated metadata
    )

    # TODO: Add relationship mapping (Task 2.3)

    return node

# Future tasks might add more conversion functions here, e.g., node_to_memory_block 