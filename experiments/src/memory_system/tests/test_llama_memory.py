import pytest
import uuid
import tempfile
import shutil
from typing import List

from experiments.src.memory_system.llama_memory import LlamaMemory
from experiments.src.memory_system.schemas.memory_block import MemoryBlock, BlockLink
from experiments.src.memory_system.llamaindex_adapters import memory_block_to_node
from llama_index.core.schema import NodeWithScore
from llama_index.core.schema import NodeRelationship


class TestLlamaMemory:
    """Tests for the LlamaMemory class."""
    
    @pytest.fixture
    def temp_chroma_dir(self):
        """Create a temporary directory for ChromaDB during tests."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Clean up after tests
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def llama_memory(self, temp_chroma_dir):
        """Create a LlamaMemory instance with a temp ChromaDB directory."""
        collection_name = f"test_collection_{uuid.uuid4().hex[:8]}"
        memory = LlamaMemory(
            chroma_path=temp_chroma_dir,
            collection_name=collection_name
        )
        return memory
    
    @pytest.fixture
    def sample_memory_block(self):
        """Create a sample MemoryBlock for testing."""
        return MemoryBlock(
            id=str(uuid.uuid4()),
            type="knowledge",
            text="Python is a high-level programming language with a philosophy emphasizing code readability. It supports multiple programming paradigms, including structured, object-oriented, and functional programming.",
            tags=["programming", "python", "language"],
            metadata={
                "title": "Python Programming Language",
                "difficulty": "beginner",
                "version": "3.10"
            },
            created_by="test_user",
        )
    
    def test_init(self, llama_memory):
        """Test initialization of LlamaMemory."""
        assert llama_memory is not None
        assert llama_memory.is_ready()  # Proper boolean check without == True
    
    def test_add_block(self, llama_memory, sample_memory_block):
        """Test adding a MemoryBlock to the index."""
        # Add the block
        llama_memory.add_block(sample_memory_block)
        
        # Verify it was added by querying for it
        # Use vector store query for more direct verification
        query_results = llama_memory.query_vector_store("Python programming", top_k=1)
        assert query_results is not None
        assert len(query_results) > 0
        assert query_results[0].node.id_ == sample_memory_block.id
    
    def test_query_vector_store(self, llama_memory, sample_memory_block):
        """Test semantic search against the vector store."""
        # Add the memory block (using memory_block_to_node)
        node = memory_block_to_node(sample_memory_block)
        llama_memory.index.insert_nodes([node])
        
        # Test relevant query
        query_text = "Tell me about Python programming"
        results: List[NodeWithScore] = llama_memory.query_vector_store(query_text, top_k=3)
        
        # Verify results
        assert len(results) > 0, "Should retrieve at least one result for a relevant query"
        
        # Check if the correct node was retrieved with a reasonable score
        found = False
        min_score = 0.5  # Reasonable threshold for semantic similarity
        
        for result in results:
            if result.node.id_ == sample_memory_block.id:
                found = True
                assert result.score > min_score, f"Score ({result.score}) should be above threshold ({min_score})"
                break
        
        assert found, f"The original block ID ({sample_memory_block.id}) should be in the results"
    
    def test_query_vector_store_irrelevant(self, llama_memory, sample_memory_block):
        """Test querying with irrelevant text does not return the indexed block."""
        # Add the memory block (using memory_block_to_node)
        node = memory_block_to_node(sample_memory_block)
        llama_memory.index.insert_nodes([node])
        
        # Test irrelevant query
        query_text = "Recipe for chocolate chip cookies with walnuts"
        results: List[NodeWithScore] = llama_memory.query_vector_store(query_text, top_k=3)
        
        # If we get results (which might happen with small collections), the score should be low
        for result in results:
            if result.node.id_ == sample_memory_block.id:
                # The score should be relatively low for an irrelevant query
                # Using 0.55 as the threshold based on observed behavior
                assert result.score < 0.55, f"Score for irrelevant query should be low, but got {result.score}"
    
    def test_update_block(self, llama_memory, sample_memory_block):
        """Test updating a memory block."""
        # First add the block
        llama_memory.add_block(sample_memory_block)
        
        # Query for it to get baseline results
        original_query = "Python programming language"
        original_results = llama_memory.query_vector_store(original_query, top_k=1)
        assert len(original_results) > 0, "Should have found the original block"
        assert original_results[0].node.id_ == sample_memory_block.id
        
        # Update the block with new content
        updated_block = sample_memory_block.model_copy(deep=True)
        updated_text = "Python is a popular programming language used extensively in data science, web development, and artificial intelligence applications."
        updated_block.text = updated_text
        updated_block.tags.append("data-science")
        updated_block.metadata["focus"] = "data science"
        updated_block.metadata["title"] = "Python for Data Science"
        
        # Update the block in the index
        llama_memory.update_block(updated_block)
        
        # Allow some time for indexing if necessary (though Chroma might be fast)
        import time
        time.sleep(0.5) 

        # Query for the updated content
        updated_query = "Python for data science"
        updated_results = llama_memory.query_vector_store(updated_query, top_k=1)
        
        # Verify we get the updated block with a good score
        assert len(updated_results) > 0, f"Should retrieve the updated block for query '{updated_query}'"
        assert updated_results[0].node.id_ == updated_block.id, "Retrieved node ID should match the updated block ID"
        
        # Check if the text in the node reflects the update
        # The adapter enriches the text, so we check for the original text within node.text
        node_text = updated_results[0].node.text
        assert updated_text in node_text, "Updated content should be reflected in the node text"
        assert "Title: Python for Data Science" in node_text, "Updated title should be in enriched text"
    
    def test_add_multiple_blocks_and_query(self, llama_memory):
        """Test adding multiple blocks and retrieving the most relevant one."""
        # Create several blocks with different topics
        python_block = MemoryBlock(
            id=str(uuid.uuid4()),
            type="knowledge",
            text="Python is a high-level programming language known for its readability and versatility.",
            tags=["programming", "python"],
            metadata={"title": "Python Programming"}
        )
        
        javascript_block = MemoryBlock(
            id=str(uuid.uuid4()),
            type="knowledge",
            text="JavaScript is a scripting language used to create dynamic web content.",
            tags=["programming", "javascript"],
            metadata={"title": "JavaScript Programming"}
        )
        
        gardening_block = MemoryBlock(
            id=str(uuid.uuid4()),
            type="knowledge",
            text="Gardening involves growing and caring for plants in a designated space.",
            tags=["hobby", "gardening"],
            metadata={"title": "Introduction to Gardening"}
        )
        
        # Add all blocks
        for block in [python_block, javascript_block, gardening_block]:
            node = memory_block_to_node(block)
            llama_memory.index.insert_nodes([node])
        
        # Query specifically for Python
        results = llama_memory.query_vector_store("Python programming syntax", top_k=3)
        
        # Check if Python block is ranked higher than others
        python_rank = None
        # We track gardening_rank but not javascript_rank since we're only comparing Python vs Gardening
        gardening_rank = None
        
        for i, result in enumerate(results):
            if result.node.id_ == python_block.id:
                python_rank = i
            elif result.node.id_ == gardening_block.id:
                gardening_rank = i
        
        # Python should be found and ranked higher than gardening
        assert python_rank is not None, "Python block should be in results"
        
        # If gardening is in results, Python should be ranked higher
        if gardening_rank is not None:
            assert python_rank < gardening_rank, "Python should rank higher than gardening for a Python query"

    # --- New tests for Graph Store Integration (Task 2.4) ---

    def test_graph_relationships(self, llama_memory):
        """Test adding blocks with links and verifying graph store relationships."""
        # 1. Create blocks with links
        block_a_id = f"block-a-{uuid.uuid4()}"
        block_b_id = f"block-b-{uuid.uuid4()}"
        block_c_id = f"block-c-{uuid.uuid4()}"

        block_a = MemoryBlock(
            id=block_a_id,
            type="task",
            text="Task A: Needs subtask B and related doc C",
            links=[
                BlockLink(to_id=block_b_id, relation="subtask_of"), # A has child B
                BlockLink(to_id=block_c_id, relation="related_to")  # A is related to C
            ]
        )
        block_b = MemoryBlock(
            id=block_b_id,
            type="task",
            text="Subtask B",
            links=[BlockLink(to_id=block_a_id, relation="child_of")] # B is child of A
        )
        block_c = MemoryBlock(
            id=block_c_id,
            type="doc",
            text="Related Document C",
            # No outgoing links from C in this test
        )

        # 2. Add blocks to memory
        llama_memory.add_block(block_a)
        llama_memory.add_block(block_b)
        llama_memory.add_block(block_c)

        # 3. Verify relationships using graph_store.get_rel_map()
        # Allow time for potential async operations if any (though SimpleGraphStore is sync)
        import time
        time.sleep(0.1) 
        
        # SimpleGraphStore.get_rel_map() returns Dict[str, List[List[str]]]
        # Key: subject_id, Value: List of triplets involving that subject [subj, rel, obj]
        graph_map_dict = llama_memory.graph_store.get_rel_map()
        assert isinstance(graph_map_dict, dict)
        
        # Define expected triplets
        expected_triplet_a_b = [block_a_id, NodeRelationship.CHILD.name, block_b_id]
        expected_triplet_a_c = [block_a_id, NodeRelationship.NEXT.name, block_c_id]
        expected_triplet_b_a = [block_b_id, NodeRelationship.PARENT.name, block_a_id]

        # Check A's relationships
        assert block_a_id in graph_map_dict, f"Block A ({block_a_id}) should be a key in the graph map"
        triplets_involving_a = graph_map_dict.get(block_a_id, [])
        assert expected_triplet_a_b in triplets_involving_a, f"Missing triplet originating from A: {expected_triplet_a_b}"
        assert expected_triplet_a_c in triplets_involving_a, f"Missing triplet originating from A: {expected_triplet_a_c}"
        # Also check for incoming relationship listed under A's key
        assert expected_triplet_b_a in triplets_involving_a, f"Missing triplet pointing to A: {expected_triplet_b_a}"

        # Check B's relationships
        assert block_b_id in graph_map_dict, f"Block B ({block_b_id}) should be a key in the graph map"
        triplets_involving_b = graph_map_dict.get(block_b_id, [])
        assert expected_triplet_b_a in triplets_involving_b, f"Missing triplet originating from B: {expected_triplet_b_a}"
        # Also check for incoming relationship listed under B's key
        assert expected_triplet_a_b in triplets_involving_b, f"Missing triplet pointing to B: {expected_triplet_a_b}"

        # Check C has no outgoing relations and only one incoming relation listed
        assert block_c_id not in graph_map_dict, f"Block C ({block_c_id}) should NOT be a key (no outgoing relations)"
        # Check that C doesn't appear as a subject in any triplet lists associated with other keys
        all_triplets_flat = [triplet for subj_triplets in graph_map_dict.values() for triplet in subj_triplets]
        assert not any(t[0] == block_c_id for t in all_triplets_flat), f"Block C ({block_c_id}) should not be a subject in any triplet"
        

        # 4. Verify relationships using get_backlinks (Remains the same)
        backlinks_to_b = llama_memory.get_backlinks(block_b_id)
        assert block_a_id in backlinks_to_b, "Block A should be listed as a backlink to B"

        backlinks_to_c = llama_memory.get_backlinks(block_c_id)
        assert block_a_id in backlinks_to_c, "Block A should be listed as a backlink to C (via NEXT relation)"
        
        backlinks_to_a = llama_memory.get_backlinks(block_a_id)
        assert block_b_id in backlinks_to_a, "Block B should be listed as a backlink to A (via PARENT relation)"

    # TODO: Add test_graph_link_to_nonexistent
    # TODO: Add test_graph_update_relationships (if update logic differs significantly) 