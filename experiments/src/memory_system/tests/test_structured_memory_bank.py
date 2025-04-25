"""
Unit and integration tests for the StructuredMemoryBank class.
"""

import pytest
import os
from pathlib import Path
import time
import datetime

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
        # pytest.skip("delete_memory_block not yet implemented")
        
        # --- Setup: Create the initial block --- 
        write_success, initial_commit = write_memory_block_to_dolt(
            block=sample_memory_block,
            db_path=memory_bank_instance.dolt_db_path,
            auto_commit=True
        )
        assert write_success and initial_commit, "Setup failed: Could not write initial block for delete test"
        # Also index it initially
        memory_bank_instance.llama_memory.add_block(sample_memory_block)
        time.sleep(0.5) # Give indexing a moment
        
        # --- Perform Delete --- 
        delete_success = memory_bank_instance.delete_memory_block(sample_memory_block.id)
        assert delete_success, "delete_memory_block returned False"

        # --- Verify Dolt Deletion --- 
        read_back_block = read_memory_block(memory_bank_instance.dolt_db_path, sample_memory_block.id)
        assert read_back_block is None, "Block still found in Dolt after deletion"

        # --- Verify LlamaIndex Deletion --- 
        time.sleep(0.5) # Give index update a moment
        try:
            # Query for the deleted text - should not be found
            query_results = memory_bank_instance.llama_memory.query_vector_store(sample_memory_block.text, top_k=1)
            found_deleted = False
            if len(query_results) > 0:
                # Check if the result found is actually the deleted block
                if query_results[0].node.id_ == sample_memory_block.id:
                    found_deleted = True
            assert not found_deleted, "Deleted block still found in LlamaIndex vector store"
            
            # Optional: Verify graph store removal if applicable/testable
            # backlinks = memory_bank_instance.llama_memory.get_backlinks(sample_memory_block.links[0].to_id)
            # assert sample_memory_block.id not in backlinks
            
        except Exception as e:
            pytest.fail(f"Querying LlamaIndex after delete failed: {e}")

    def test_query_semantic(self, memory_bank_instance: StructuredMemoryBank):
        """Tests semantic querying."""
        # pytest.skip("query_semantic depends on create or direct DB/index setup")
        
        # --- Setup: Create several distinct blocks ---
        block1_data = MemoryBlock(
            id="query-block-1", type="knowledge", text="The quick brown fox jumps over the lazy dog.", 
            tags=["animal", "quick"], created_at=datetime.datetime.now(), updated_at=datetime.datetime.now()
        )
        block2_data = MemoryBlock(
            id="query-block-2", type="knowledge", text="Semantic search finds related concepts.", 
            tags=["search", "concepts"], created_at=datetime.datetime.now(), updated_at=datetime.datetime.now()
        )
        block3_data = MemoryBlock(
            id="query-block-3", type="task", text="Implement the semantic query functionality.", 
            tags=["task", "query"], created_at=datetime.datetime.now(), updated_at=datetime.datetime.now()
        )
        
        create_success1 = memory_bank_instance.create_memory_block(block1_data)
        create_success2 = memory_bank_instance.create_memory_block(block2_data)
        create_success3 = memory_bank_instance.create_memory_block(block3_data)
        assert create_success1 and create_success2 and create_success3, "Failed to create blocks for semantic query test"
        time.sleep(1) # Give indexing a bit more time after creates
        
        # --- Perform Query --- 
        query_text = "finding information using meaning"
        results = memory_bank_instance.query_semantic(query_text, top_k=2)
        
        # --- Verify Results --- 
        assert results is not None, "query_semantic returned None"
        assert len(results) > 0, "Semantic query did not return any results"
        
        # Check if the most relevant block (likely block2) is returned
        # Note: Exact relevance/order depends heavily on the embedding model used by LlamaIndex
        assert any(block.id == "query-block-2" for block in results), "Expected block 2 (related concepts) not found in results"
        
        # Check if the first result is likely block 2 (stronger assertion)
        if results:
             assert results[0].id == "query-block-2", f"Expected block 2 to be the most relevant result, but got {results[0].id}"
        
        # Query for something completely different
        unrelated_results = memory_bank_instance.query_semantic("unrelated pizza topic", top_k=1)
        assert unrelated_results is not None
        # Check that the specific relevant block (block 2) was NOT returned for the unrelated query
        assert not any(block.id == "query-block-2" for block in unrelated_results), \
            "Unrelated query unexpectedly returned the block related to semantic search"

    def test_get_blocks_by_tags(self, memory_bank_instance: StructuredMemoryBank):
        """Tests retrieving blocks by tags."""
        # pytest.skip("get_blocks_by_tags not yet implemented")

        # --- Setup: Create blocks with specific tags ---
        block_a = MemoryBlock(
            id="tag-block-a", type="knowledge", text="Block with tag alpha", tags=["alpha"], 
            created_at=datetime.datetime.now(), updated_at=datetime.datetime.now()
        )
        block_b = MemoryBlock(
            id="tag-block-b", type="knowledge", text="Block with tag beta", tags=["beta"], 
            created_at=datetime.datetime.now(), updated_at=datetime.datetime.now()
        )
        block_ab = MemoryBlock(
            id="tag-block-ab", type="knowledge", text="Block with tags alpha and beta", tags=["alpha", "beta"], 
            created_at=datetime.datetime.now(), updated_at=datetime.datetime.now()
        )
        block_c = MemoryBlock(
            id="tag-block-c", type="task", text="Block with no relevant tags", tags=["gamma"], 
            created_at=datetime.datetime.now(), updated_at=datetime.datetime.now()
        )

        # Write directly for setup simplicity
        write_memory_block_to_dolt(block_a, memory_bank_instance.dolt_db_path, auto_commit=True)
        write_memory_block_to_dolt(block_b, memory_bank_instance.dolt_db_path, auto_commit=True)
        write_memory_block_to_dolt(block_ab, memory_bank_instance.dolt_db_path, auto_commit=True)
        write_memory_block_to_dolt(block_c, memory_bank_instance.dolt_db_path, auto_commit=True)

        # --- Test Match Any (OR) --- 
        results_any_alpha = memory_bank_instance.get_blocks_by_tags(["alpha"], match_all=False)
        assert len(results_any_alpha) == 2
        assert {b.id for b in results_any_alpha} == {"tag-block-a", "tag-block-ab"}

        results_any_beta = memory_bank_instance.get_blocks_by_tags(["beta"], match_all=False)
        assert len(results_any_beta) == 2
        assert {b.id for b in results_any_beta} == {"tag-block-b", "tag-block-ab"}

        results_any_ab = memory_bank_instance.get_blocks_by_tags(["alpha", "beta"], match_all=False)
        assert len(results_any_ab) == 3
        assert {b.id for b in results_any_ab} == {"tag-block-a", "tag-block-b", "tag-block-ab"}
        
        results_any_gamma = memory_bank_instance.get_blocks_by_tags(["gamma"], match_all=False)
        assert len(results_any_gamma) == 1
        assert results_any_gamma[0].id == "tag-block-c"
        
        results_any_none = memory_bank_instance.get_blocks_by_tags(["delta"], match_all=False)
        assert len(results_any_none) == 0

        # --- Test Match All (AND) ---
        results_all_alpha = memory_bank_instance.get_blocks_by_tags(["alpha"], match_all=True)
        assert len(results_all_alpha) == 2 # block_a and block_ab
        assert {b.id for b in results_all_alpha} == {"tag-block-a", "tag-block-ab"}
        
        results_all_beta = memory_bank_instance.get_blocks_by_tags(["beta"], match_all=True)
        assert len(results_all_beta) == 2 # block_b and block_ab
        assert {b.id for b in results_all_beta} == {"tag-block-b", "tag-block-ab"}

        results_all_ab = memory_bank_instance.get_blocks_by_tags(["alpha", "beta"], match_all=True)
        assert len(results_all_ab) == 1
        assert results_all_ab[0].id == "tag-block-ab"
        
        results_all_ag = memory_bank_instance.get_blocks_by_tags(["alpha", "gamma"], match_all=True)
        assert len(results_all_ag) == 0
        
        results_all_none = memory_bank_instance.get_blocks_by_tags(["delta"], match_all=True)
        assert len(results_all_none) == 0

    def test_get_forward_links(self, memory_bank_instance: StructuredMemoryBank, sample_memory_block: MemoryBlock):
        """Tests retrieving forward links."""
        # First create the target block
        target_block = MemoryBlock(
            id="related-block-002",
            type="knowledge",
            text="This is a target block for forward link testing.",
            tags=["test", "target"]
        )
        target_success = memory_bank_instance.create_memory_block(target_block)
        assert target_success, "Failed to create target block for forward link test"
        
        # Now create a block with links
        success = memory_bank_instance.create_memory_block(sample_memory_block)
        assert success, "Failed to create block with links for test"
        
        # Now test the forward link functionality
        links = memory_bank_instance.get_forward_links(sample_memory_block.id)
        assert len(links) == 1, f"Expected 1 link, got {len(links)}"
        assert links[0].to_id == "related-block-002", f"Expected link to 'related-block-002', got '{links[0].to_id}'"
        assert links[0].relation == "related_to", f"Expected relation 'related_to', got '{links[0].relation}'"

    def test_get_backlinks(self, memory_bank_instance: StructuredMemoryBank, sample_memory_block: MemoryBlock):
        """Tests retrieving backlinks."""
        # First create a block that will be the target of a link
        target_block = MemoryBlock(
            id="related-block-002",
            type="knowledge",
            text="This is a target block for backlink testing.",
            tags=["test", "target"],
            links=[]  # No links in the target block
        )
        success = memory_bank_instance.create_memory_block(target_block)
        assert success, "Failed to create target block for backlink test"
        
        # Create a block that links to the target
        source_block = sample_memory_block  # Already has a link to "related-block-002"
        success = memory_bank_instance.create_memory_block(source_block)
        assert success, "Failed to create source block with link for backlink test"
        
        # Now test the backlink functionality
        backlinks = memory_bank_instance.get_backlinks("related-block-002")
        assert len(backlinks) >= 1, f"Expected at least 1 backlink, got {len(backlinks)}"
        
        # Find the backlink from our test block
        found_backlink = False
        for link in backlinks:
            if link.to_id == source_block.id:
                found_backlink = True
                assert link.relation == "related_to", f"Expected relation 'related_to', got '{link.relation}'"
                break
        
        assert found_backlink, f"Did not find expected backlink from {source_block.id} to 'related-block-002'"
        
        # Test filtering by relation
        filtered_backlinks = memory_bank_instance.get_backlinks("related-block-002", relation="related_to")
        assert len(filtered_backlinks) >= 1, "Expected at least 1 backlink when filtering by 'related_to'" 