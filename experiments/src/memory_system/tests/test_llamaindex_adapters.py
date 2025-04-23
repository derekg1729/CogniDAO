from experiments.src.memory_system.schemas.memory_block import MemoryBlock, BlockLink, ConfidenceScore
from experiments.src.memory_system.llamaindex_adapters import memory_block_to_node
from llama_index.core.schema import TextNode, NodeRelationship
from datetime import datetime
import json
import pytest

# TODO: Implement tests for memory_block_to_node conversion

# @pytest.mark.skip(reason="Conversion function not yet implemented") # Un-skip this test
def test_memory_block_to_node_basic():
    """Test basic conversion of a memory block to a node."""
    block = MemoryBlock(
        id="test_id_123",
        type="knowledge",
        text="Test block content.",
        tags=["test", "block"]
    )
    
    node = memory_block_to_node(block)
    
    assert isinstance(node, TextNode)
    assert node.id_ == "test_id_123"
    assert "Test block content." in node.text
    assert "Type: knowledge" in node.text

# @pytest.mark.skip(reason="Metadata conversion not yet implemented") # Un-skip this test
def test_memory_block_to_node_metadata_and_enrichment():
    """Test conversion of various metadata fields and text enrichment."""
    now = datetime.now()
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
        "tags": "tag1,test",  # Note: Implementation joins with comma, no space
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
    metadata_copy.pop("created_at")
    metadata_copy.pop("updated_at")
    
    assert metadata_copy == expected_metadata_static

# Add more tests as needed, e.g., for handling missing optional fields 

class TestMemoryBlockToNode:
    """Tests for the memory_block_to_node function."""
    
    @pytest.fixture
    def sample_memory_block(self):
        """Create a sample MemoryBlock for testing."""
        return MemoryBlock(
            id="test-block-1",
            type="knowledge",
            text="This is a test memory block.",
            tags=["test", "memory"],
            metadata={"title": "Test Block"}
        )
    
    @pytest.fixture
    def sample_memory_block_with_links(self):
        """Create a sample MemoryBlock with links for testing relationship conversion."""
        block = MemoryBlock(
            id="main-block",
            type="task",
            text="Implement task relationship handling.",
            tags=["task", "relationship"],
            metadata={"title": "Main Task"},
        )
        
        # Add various types of links
        block.links = [
            BlockLink(to_id="subtask-1", relation="subtask_of"),
            BlockLink(to_id="related-doc", relation="related_to"),
            BlockLink(to_id="parent-project", relation="child_of"),
            BlockLink(to_id="dependent-task", relation="depends_on"),
            BlockLink(to_id="reference-doc", relation="mentions"),
        ]
        
        return block
    
    def test_basic_conversion(self, sample_memory_block):
        """Test basic conversion without links."""
        node = memory_block_to_node(sample_memory_block)
        
        # Verify basic properties were copied
        assert node.id_ == sample_memory_block.id
        assert sample_memory_block.text in node.text
        assert node.metadata["type"] == sample_memory_block.type
        # The actual implementation joins tags with comma but no space
        assert node.metadata["tags"] == "test,memory"
        
    def test_relationships_conversion(self, sample_memory_block_with_links):
        """Test that links are properly converted to TextNode relationships."""
        node = memory_block_to_node(sample_memory_block_with_links)
        
        # Verify node has relationships
        assert hasattr(node, "relationships")
        assert node.relationships is not None
        
        # Check relationships dictionary contains expected entries
        relationships = node.relationships
        
        # Verify relationship mapping works correctly
        # "subtask_of" should map to CHILD (the node has children)
        assert NodeRelationship.CHILD in relationships
        subtask_relations = relationships[NodeRelationship.CHILD]
        assert any(rel.node_id == "subtask-1" for rel in subtask_relations)
        
        # "child_of" should map to PARENT (the node has parents)
        assert NodeRelationship.PARENT in relationships
        parent_relations = relationships[NodeRelationship.PARENT]
        assert any(rel.node_id == "parent-project" for rel in parent_relations)
        
        # "related_to" should map to NEXT
        assert NodeRelationship.NEXT in relationships
        next_relations = relationships[NodeRelationship.NEXT]
        assert any(rel.node_id == "related-doc" for rel in next_relations)
        
        # Check that original relation type is stored in metadata
        for rel_type, nodes in relationships.items():
            for node_info in nodes:
                assert "original_relation" in node_info.metadata
        
        # Check specific mapping (example)
        child_relations = relationships[NodeRelationship.CHILD]
        subtask_relation = next((r for r in child_relations if r.node_id == "subtask-1"), None)
        assert subtask_relation is not None
        assert subtask_relation.metadata["original_relation"] == "subtask_of"
        
    def test_multiple_same_relationship_type(self):
        """Test handling multiple links with the same relationship type."""
        block = MemoryBlock(
            id="parent-block",
            type="project",
            text="Project with multiple subtasks.",
            metadata={"title": "Project"},
            links=[
                BlockLink(to_id="subtask-1", relation="subtask_of"),
                BlockLink(to_id="subtask-2", relation="subtask_of"),
                BlockLink(to_id="subtask-3", relation="subtask_of"),
            ]
        )
        
        node = memory_block_to_node(block)
        
        # Verify all subtasks are added as CHILD relationships
        assert NodeRelationship.CHILD in node.relationships
        child_relations = node.relationships[NodeRelationship.CHILD]
        assert len(child_relations) == 3
        
        # Verify all subtask IDs are in the relationships
        subtask_ids = [rel.node_id for rel in child_relations]
        assert "subtask-1" in subtask_ids
        assert "subtask-2" in subtask_ids
        assert "subtask-3" in subtask_ids 