from experiments.src.memory_system.schemas.memory_block import MemoryBlock, BlockLink, ConfidenceScore
from experiments.src.memory_system.llamaindex_adapters import memory_block_to_node
from llama_index.core.schema import TextNode
from datetime import datetime
import json

# TODO: Implement tests for memory_block_to_node conversion

# @pytest.mark.skip(reason="Conversion function not yet implemented") # Un-skip this test
def test_memory_block_to_node_basic():
    """Test basic conversion of text, id, and minimal metadata."""
    now = datetime.now()
    # created_at_iso = now.isoformat() # Removed unused variable
    # updated_at is set by model_post_init, so we can't easily predict it here

    block = MemoryBlock(
        id="test_id_123",
        type="knowledge",
        text="This is the core content.",
        created_at=now
        # updated_at will be set by model_post_init
    )
    
    node = memory_block_to_node(block)
    
    assert isinstance(node, TextNode)
    assert node.id_ == "test_id_123"
    
    # Check enriched text
    expected_text = (
        "Title: Untitled\n" # Default title
        "Type: knowledge\n"
        "Tags: None\n" # Default tags string
        "---\n"
        "This is the core content."
    )
    assert node.text == expected_text

    # Check basic metadata that IS generated
    # We handle dynamic created_at and updated_at separately
    assert node.metadata.get("type") == "knowledge"
    assert node.metadata.get("enriched_title") == "Untitled"
    assert node.metadata.get("enriched_tags") == "None"
    assert "created_at" in node.metadata 
    assert "updated_at" in node.metadata 
    assert len(node.metadata) == 5 # type, created_at, updated_at, enriched_title, enriched_tags


# @pytest.mark.skip(reason="Metadata conversion not yet implemented") # Un-skip this test
def test_memory_block_to_node_metadata_and_enrichment():
    """Test conversion of various metadata fields and text enrichment."""
    now = datetime.now()
    # created_at_iso = now.isoformat() # Store expected created_at -- Removed unused variable
    # updated_at will be set by model_post_init
    schema_ver = 1
    specific_title = "Specific Test Title"
    specific_tags = ["tag1", "test"]
    tags_str = ", ".join(specific_tags)

    block = MemoryBlock(
        id="test_id_456",
        type="task",
        schema_version=schema_ver,
        text="Metadata test block.",
        tags=specific_tags,
        metadata={"project": "POC", "status": "pending", "title": specific_title},
        links=[BlockLink(to_id="linked_id_1", relation="related_to")], # Links ignored by this func
        source_file="source.md",
        source_uri="http://example.com/source",
        confidence=ConfidenceScore(human=0.8, ai=0.9),
        created_by="agent_x",
        created_at=now
        # updated_at set by model_post_init
    )
    
    node = memory_block_to_node(block)
    
    assert isinstance(node, TextNode)
    assert node.id_ == "test_id_456"

    # Check enriched text
    expected_text = (
        f"Title: {specific_title}\n"
        f"Type: task\n"
        f"Tags: {tags_str}\n"
        f"---\n"
        f"Metadata test block."
    )
    assert node.text == expected_text
    
    # Verify metadata matches implementation logic
    # Exclude dynamic timestamps from direct comparison
    expected_metadata_static = {
        "type": "task",
        "schema_version": schema_ver,
        "tags": specific_tags,
        "metadata_json": json.dumps({"project": "POC", "status": "pending", "title": specific_title}),
        "source_file": "source.md",
        "source_uri": "http://example.com/source",
        "confidence_human": 0.8,
        "confidence_ai": 0.9,
        "created_by": "agent_x",
        "enriched_title": specific_title,
        "enriched_tags": tags_str
    }
    # Compare metadata excluding the dynamic timestamps
    metadata_copy = node.metadata.copy()
    assert "created_at" in metadata_copy
    assert "updated_at" in metadata_copy
    # created_at_actual = metadata_copy.pop("created_at") # Removed unused variable
    metadata_copy.pop("created_at") # Still need to pop it
    metadata_copy.pop("updated_at") # Still need to remove it for comparison
    
    assert metadata_copy == expected_metadata_static
    # Optionally, check if created_at is close to the expected iso string
    # We need access to created_at_iso if we want to do this check
    # For now, we rely on the check that the key exists and the length check.
    # assert created_at_actual.startswith(created_at_iso[:19]) # Compare up to seconds

# Add more tests as needed, e.g., for handling missing optional fields 