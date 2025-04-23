import pytest
import uuid
import tempfile
import shutil
from datetime import datetime
from typing import List

from experiments.src.memory_system.llama_memory import LlamaMemory
from experiments.src.memory_system.schemas.memory_block import MemoryBlock
from experiments.src.memory_system.llamaindex_adapters import memory_block_to_node
from llama_index.core.schema import NodeWithScore


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
            created_at=datetime.now(),
            updated_at=datetime.now()
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
        # We'll rely on basic functionality to check this is working
        query_response = llama_memory.query("Python programming")
        assert query_response is not None
    
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
        updated_block.text = "Python is a popular programming language used extensively in data science, web development, and artificial intelligence applications."
        updated_block.tags.append("data-science")
        updated_block.metadata["focus"] = "data science"
        
        # Update the block in the index
        llama_memory.update_block(updated_block)
        
        # Query for the updated content
        updated_query = "Python for data science"
        updated_results = llama_memory.query_vector_store(updated_query, top_k=1)
        
        # Verify we get the updated block with a good score
        assert len(updated_results) > 0, "Should retrieve the updated block"
        assert updated_results[0].node.id_ == updated_block.id
        assert updated_results[0].score > 0.5, "Score should be good for a relevant query to updated content"
        
        # Check if the text in the node reflects the update
        node_text = updated_results[0].node.text
        assert "data science" in node_text.lower(), "Updated content should be reflected in the node text"
    
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