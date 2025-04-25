"""
Unit and integration tests for the StructuredMemoryBank class.
"""

import pytest
import os
from pathlib import Path
import time

# Target class
from experiments.src.memory_system.structured_memory_bank import StructuredMemoryBank

# Schemas needed for creating test blocks
from experiments.src.memory_system.schemas.memory_block import MemoryBlock, BlockLink, ConfidenceScore

# Helper for initializing test Dolt DB
from experiments.src.memory_system.initialize_dolt import initialize_dolt_db

# Helper for writing directly to Dolt for test setup
from experiments.src.memory_system.dolt_writer import write_memory_block_to_dolt

# Helper for reading directly from Dolt for verification
from experiments.src.memory_system.dolt_reader import read_memory_block

# --- Fixtures ---

@pytest.fixture(scope="module")
def test_dolt_db_path(tmp_path_factory) -> Path:
    """Creates a temporary directory for a test Dolt database."""
    db_path = tmp_path_factory.mktemp("test_dolt_db")
    assert initialize_dolt_db(str(db_path)), "Failed to initialize test Dolt DB"
    # TODO: Consider adding the node_schemas table here if needed for tests
    # TODO: Consider adding the block_links table here if not done by initialize_dolt_db
    return db_path

@pytest.fixture(scope="module")
def test_chroma_path(tmp_path_factory) -> Path:
    """Creates a temporary directory for test ChromaDB storage."""
    return tmp_path_factory.mktemp("test_chroma_storage")

@pytest.fixture(scope="module")
def memory_bank_instance(test_dolt_db_path: Path, test_chroma_path: Path) -> StructuredMemoryBank:
    """Provides an initialized StructuredMemoryBank instance for testing."""
    collection_name = "test_collection"
    # Ensure Chroma path exists (LlamaMemory init might do this, but being explicit)
    os.makedirs(test_chroma_path, exist_ok=True)
    
    bank = StructuredMemoryBank(
        dolt_db_path=str(test_dolt_db_path),
        chroma_path=str(test_chroma_path),
        chroma_collection=collection_name
    )
    assert bank.llama_memory.is_ready(), "LlamaMemory did not initialize correctly in fixture"
    # TODO: Add basic schema definition to node_schemas if needed for create tests
    # Example: register_schema(str(test_dolt_db_path), 'test_type', 1, {'title':'Test Schema'})
    return bank

@pytest.fixture
def sample_memory_block() -> MemoryBlock:
    """Provides a sample MemoryBlock for testing."""
    return MemoryBlock(
        id="test-block-001",
        type="knowledge",
        text="This is a test memory block.",
        tags=["test", "fixture"],
        metadata={"source": "pytest"},
        links=[BlockLink(to_id="related-block-002", relation="related_to")],
        confidence=ConfidenceScore(human=0.9)
    )

# --- Test Class ---

class TestStructuredMemoryBank:

    def test_initialization(self, memory_bank_instance: StructuredMemoryBank):
        """Tests if the StructuredMemoryBank initializes correctly."""
        assert memory_bank_instance is not None
        assert memory_bank_instance.dolt_db_path is not None
        assert memory_bank_instance.llama_memory is not None
        assert memory_bank_instance.llama_memory.is_ready()

    def test_create_memory_block(self, memory_bank_instance: StructuredMemoryBank, sample_memory_block: MemoryBlock):
        """Tests the create_memory_block method."""
        # pytest.skip("create_memory_block not yet fully implemented")
        success = memory_bank_instance.create_memory_block(sample_memory_block)
        assert success, "create_memory_block returned False"
        
        # Verify block exists in Dolt
        read_back_block = read_memory_block(memory_bank_instance.dolt_db_path, sample_memory_block.id)
        assert read_back_block is not None, "Block not found in Dolt after creation"
        assert read_back_block.id == sample_memory_block.id
        assert read_back_block.text == sample_memory_block.text

        # Verify block exists in LlamaIndex (basic check: query for it)
        # Allow some time for indexing to potentially complete if it were async (though it seems sync now)
        time.sleep(0.5) 
        try:
            query_results = memory_bank_instance.llama_memory.query_vector_store(sample_memory_block.text, top_k=1)
            assert len(query_results) > 0, "Block not found in LlamaIndex vector store after creation"
            # Note: LlamaIndex might modify the ID slightly or store it differently.
            # A more robust check might involve searching metadata if the ID isn't directly queryable.
            assert query_results[0].node.id_ == sample_memory_block.id, "Found node ID does not match created block ID"
        except Exception as e:
            pytest.fail(f"Querying LlamaIndex after create failed: {e}")

        # TODO: Verify links are handled correctly in Dolt block_links table (once implemented)
        # TODO: Verify graph relationships exist in LlamaIndex graph store

    def test_get_memory_block(self, memory_bank_instance: StructuredMemoryBank, sample_memory_block: MemoryBlock):
        """Tests retrieving a memory block after writing it directly."""
        # --- Test Setup: Write the block directly to Dolt --- 
        # We use auto_commit=True here because we're not testing the bank's create method yet.
        write_success, commit_hash = write_memory_block_to_dolt(
            block=sample_memory_block, 
            db_path=memory_bank_instance.dolt_db_path,
            auto_commit=True
        )
        assert write_success, "Failed to write sample block directly to Dolt for test setup"
        assert commit_hash is not None, "Failed to get commit hash after writing sample block"
        # --- End Test Setup ---
        
        retrieved_block = memory_bank_instance.get_memory_block(sample_memory_block.id)
        
        assert retrieved_block is not None, f"Failed to retrieve block {sample_memory_block.id}"
        assert retrieved_block.id == sample_memory_block.id
        assert retrieved_block.text == sample_memory_block.text
        assert retrieved_block.tags == sample_memory_block.tags
        # Pydantic models handle nested validation, so comparing directly should work if data is the same
        assert retrieved_block.metadata == sample_memory_block.metadata
        assert retrieved_block.confidence == sample_memory_block.confidence
        # Note: read_memory_block currently reads the `links` column from the main table.
        # If `write_memory_block_to_dolt` populates that correctly, this assertion should pass.
        # If we switch to reading links *only* from the `block_links` table in get_memory_block,
        # this test setup would need to also write to `block_links`.
        assert retrieved_block.links == sample_memory_block.links

    def test_get_non_existent_block(self, memory_bank_instance: StructuredMemoryBank):
        """Tests retrieving a block that doesn't exist."""
        # No setup needed, just try to retrieve
        retrieved_block = memory_bank_instance.get_memory_block("non-existent-id")
        assert retrieved_block is None

    def test_update_memory_block(self, memory_bank_instance: StructuredMemoryBank, sample_memory_block: MemoryBlock):
        """Tests updating a memory block."""
        # pytest.skip("update_memory_block not yet implemented")
        
        # --- Setup: Create the initial block --- 
        write_success, initial_commit = write_memory_block_to_dolt(
            block=sample_memory_block,
            db_path=memory_bank_instance.dolt_db_path,
            auto_commit=True
        )
        assert write_success and initial_commit, "Setup failed: Could not write initial block"
        # Also index it initially to simulate real state
        memory_bank_instance.llama_memory.add_block(sample_memory_block)
        time.sleep(0.5) # Give indexing a moment
        
        # --- Perform Update --- 
        update_data = {
            "text": "This is the updated text.", 
            "tags": ["updated", "test"],
            "metadata": {"source": "pytest", "update_run": True}
        }
        update_success = memory_bank_instance.update_memory_block(sample_memory_block.id, update_data)
        assert update_success, "update_memory_block returned False"

        # --- Verify Dolt Update --- 
        read_back_block = read_memory_block(memory_bank_instance.dolt_db_path, sample_memory_block.id)
        assert read_back_block is not None, "Block not found in Dolt after update"
        assert read_back_block.text == update_data["text"]
        assert read_back_block.tags == update_data["tags"]
        assert read_back_block.metadata == update_data["metadata"]
        # Check that updated_at timestamp has changed (is later than original)
        assert read_back_block.updated_at > sample_memory_block.updated_at, "updated_at timestamp was not updated"

        # --- Verify LlamaIndex Update --- 
        time.sleep(0.5) # Give indexing update a moment
        try:
            # Query for the *updated* text
            query_results = memory_bank_instance.llama_memory.query_vector_store(update_data["text"], top_k=1)
            assert len(query_results) > 0, "Updated block not found in LlamaIndex vector store"
            assert query_results[0].node.id_ == sample_memory_block.id, "Found node ID does not match updated block ID"
            
            # Query for the *old* text - should ideally not return the same block with high confidence
            old_query_results = memory_bank_instance.llama_memory.query_vector_store(sample_memory_block.text, top_k=1)
            if len(old_query_results) > 0:
                 assert old_query_results[0].node.id_ != sample_memory_block.id or old_query_results[0].score < 0.8, \
                     "Old text still strongly matches the updated block in LlamaIndex"
        except Exception as e:
            pytest.fail(f"Querying LlamaIndex after update failed: {e}")
        
        # TODO: Verify link updates in Dolt/LlamaIndex if links were part of update_data

    def test_delete_memory_block(self, memory_bank_instance: StructuredMemoryBank, sample_memory_block: MemoryBlock):
        """Tests deleting a memory block."""
        pytest.skip("delete_memory_block not yet implemented")
        # # Pre-requisite: Create the block
        # success = memory_bank_instance.delete_memory_block(sample_memory_block.id)
        # assert success
        # # TODO: Verify block is gone from Dolt and LlamaIndex

    def test_query_semantic(self, memory_bank_instance: StructuredMemoryBank):
        """Tests semantic querying."""
        pytest.skip("query_semantic depends on create or direct DB/index setup")
        # # Pre-requisite: Create several blocks with distinct text
        # results = memory_bank_instance.query_semantic("query related to test block text", top_k=1)
        # assert len(results) >= 1
        # assert results[0].id == "test-block-001" # Assuming test-block-001 is most relevant

    def test_get_blocks_by_tags(self, memory_bank_instance: StructuredMemoryBank):
        """Tests retrieving blocks by tags."""
        pytest.skip("get_blocks_by_tags not yet implemented")
        # # Pre-requisite: Create blocks with specific tags
        # results = memory_bank_instance.get_blocks_by_tags(["test"])
        # assert len(results) >= 1
        # # TODO: Add more specific tag tests (match_all=False, multiple tags)

    def test_get_forward_links(self, memory_bank_instance: StructuredMemoryBank, sample_memory_block: MemoryBlock):
        """Tests retrieving forward links."""
        pytest.skip("get_forward_links depends on create or direct DB setup")
        # # Pre-requisite: Create the block with links
        # links = memory_bank_instance.get_forward_links(sample_memory_block.id)
        # assert len(links) == 1
        # assert links[0].to_id == "related-block-002"
        # assert links[0].relation == "related_to"

    def test_get_backlinks(self, memory_bank_instance: StructuredMemoryBank, sample_memory_block: MemoryBlock):
        """Tests retrieving backlinks."""
        pytest.skip("get_backlinks depends on create or direct DB setup")
        # # Pre-requisite: Create sample_memory_block AND a block that links TO it
        # backlinks = memory_bank_instance.get_backlinks("related-block-002") # Find links pointing to this ID
        # assert len(backlinks) >= 1
        # assert backlinks[0].from_id == sample_memory_block.id # Assuming sample_memory_block links to it 