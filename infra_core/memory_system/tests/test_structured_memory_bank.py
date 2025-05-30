"""
Unit and integration tests for the StructuredMemoryBank class.
"""

import pytest
import os
from pathlib import Path
import time
import datetime
from unittest.mock import patch, MagicMock
import sys
from pydantic import ValidationError

# Import all required modules
from infra_core.memory_system.structured_memory_bank import (
    StructuredMemoryBank,
    diff_memory_blocks,
)
from infra_core.memory_system.schemas.memory_block import (
    MemoryBlock,
    ConfidenceScore,
)
from infra_core.memory_system.schemas.common import BlockLink
from infra_core.memory_system.initialize_dolt import initialize_dolt_db
from infra_core.memory_system.dolt_writer import write_memory_block_to_dolt
from infra_core.memory_system.dolt_reader import read_memory_block

# Add the project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Mock data paths
MOCK_DOLT_PATH = "/mock/dolt/path"
MOCK_CHROMA_PATH = "/mock/chroma/path"
MOCK_COLLECTION = "mock_collection"

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
        chroma_collection=collection_name,
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
        confidence=ConfidenceScore(human=0.9),
    )


@pytest.fixture
def mock_llama_memory():
    """Create a mock LlamaMemory instance."""
    with patch("infra_core.memory_system.structured_memory_bank.LlamaMemory") as mock_llama:
        mock_instance = mock_llama.return_value
        mock_instance.is_ready.return_value = True
        mock_instance.add_block.return_value = None  # No return value
        mock_instance.chroma_path = MOCK_CHROMA_PATH
        yield mock_instance


@pytest.fixture
def mock_dolt_writer():
    """Mock the dolt_writer functions."""
    # Create a mock Dolt repository
    mock_repo = MagicMock()
    mock_repo.sql.return_value = {"rows": []}  # Default empty result for SQL queries

    # Create patches for all necessary functions
    with (
        patch("infra_core.memory_system.structured_memory_bank.Dolt", return_value=mock_repo),
        patch(
            "infra_core.memory_system.structured_memory_bank.write_memory_block_to_dolt"
        ) as mock_write,
        patch(
            "infra_core.memory_system.structured_memory_bank.commit_working_changes"
        ) as mock_commit,
        patch(
            "infra_core.memory_system.structured_memory_bank.discard_working_changes"
        ) as mock_discard,
    ):
        # Configure the mocks
        mock_write.return_value = (True, None)  # Success, no hash (will be set by commit)
        mock_commit.return_value = (True, "mock_commit_hash")  # Success with hash
        mock_discard.return_value = True  # Success

        yield mock_write


@pytest.fixture
def mock_dolt_reader():
    """Mock the dolt_reader functions."""
    with patch("infra_core.memory_system.structured_memory_bank.read_memory_block") as mock_read:
        mock_read.return_value = None  # Default to no block found
        yield mock_read


@pytest.fixture
def mock_schema_manager():
    """Mock the dolt_schema_manager functions."""
    with patch("infra_core.memory_system.structured_memory_bank.get_schema") as mock_get_schema:
        # Default to returning None (no schema found)
        mock_get_schema.return_value = None
        yield mock_get_schema


@pytest.fixture
def memory_bank(mock_llama_memory, mock_dolt_writer, mock_dolt_reader, mock_schema_manager):
    """Create a StructuredMemoryBank instance with mocked dependencies."""
    # Create a mock Dolt repository
    mock_repo = MagicMock()
    mock_repo.init.return_value = None
    mock_repo.add.return_value = None
    mock_repo.commit.return_value = None
    mock_repo.checkout.return_value = None

    # Patch the Dolt class to return our mock repository
    with patch("infra_core.memory_system.structured_memory_bank.Dolt", return_value=mock_repo):
        bank = StructuredMemoryBank(
            dolt_db_path=MOCK_DOLT_PATH,
            chroma_path=MOCK_CHROMA_PATH,
            chroma_collection=MOCK_COLLECTION,
        )
        yield bank


# --- Test Class ---


class TestStructuredMemoryBank:
    def test_initialization(self, memory_bank_instance: StructuredMemoryBank):
        """Tests if the StructuredMemoryBank initializes correctly."""
        assert memory_bank_instance is not None
        assert memory_bank_instance.dolt_db_path is not None
        assert memory_bank_instance.llama_memory is not None
        assert memory_bank_instance.llama_memory.is_ready()

    def test_create_memory_block(
        self, memory_bank_instance: StructuredMemoryBank, sample_memory_block: MemoryBlock
    ):
        """Tests the create_memory_block method."""
        # pytest.skip("create_memory_block not yet fully implemented")
        success = memory_bank_instance.create_memory_block(sample_memory_block)
        assert success, "create_memory_block returned False"

        # Verify block exists in Dolt
        read_back_block = read_memory_block(
            memory_bank_instance.dolt_db_path, sample_memory_block.id
        )
        assert read_back_block is not None, "Block not found in Dolt after creation"
        assert read_back_block.id == sample_memory_block.id
        assert read_back_block.text == sample_memory_block.text

        # Verify block exists in LlamaIndex (basic check: query for it)
        # Allow some time for indexing to potentially complete if it were async (though it seems sync now)
        time.sleep(0.5)
        try:
            query_results = memory_bank_instance.llama_memory.query_vector_store(
                sample_memory_block.text, top_k=1
            )
            assert len(query_results) > 0, (
                "Block not found in LlamaIndex vector store after creation"
            )
            # Note: LlamaIndex might modify the ID slightly or store it differently.
            # A more robust check might involve searching metadata if the ID isn't directly queryable.
            assert query_results[0].node.id_ == sample_memory_block.id, (
                "Found node ID does not match created block ID"
            )
        except Exception as e:
            pytest.fail(f"Querying LlamaIndex after create failed: {e}")

        # TODO: Verify links are handled correctly in Dolt block_links table (once implemented)
        # TODO: Verify graph relationships exist in LlamaIndex graph store

    def test_get_memory_block(
        self, memory_bank_instance: StructuredMemoryBank, sample_memory_block: MemoryBlock
    ):
        """Tests retrieving a memory block after writing it directly."""
        # --- Test Setup: Write the block directly to Dolt ---
        # We use auto_commit=True here because we're not testing the bank's create method yet.
        write_success, commit_hash = write_memory_block_to_dolt(
            block=sample_memory_block, db_path=memory_bank_instance.dolt_db_path, auto_commit=True
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
        # Note: Links are now managed separately via LinkManager and block_links table,
        # not as inline properties of MemoryBlock objects.
        # assert retrieved_block.links == sample_memory_block.links  # Removed - links no longer part of MemoryBlock

    def test_get_non_existent_block(self, memory_bank_instance: StructuredMemoryBank):
        """Tests retrieving a block that doesn't exist."""
        # No setup needed, just try to retrieve
        retrieved_block = memory_bank_instance.get_memory_block("non-existent-id")
        assert retrieved_block is None

    def test_update_memory_block(
        self, memory_bank_instance: StructuredMemoryBank, sample_memory_block: MemoryBlock
    ):
        """Tests updating a memory block."""
        # pytest.skip("update_memory_block not yet implemented")

        # --- Setup: Create the initial block ---
        write_success, initial_commit = write_memory_block_to_dolt(
            block=sample_memory_block, db_path=memory_bank_instance.dolt_db_path, auto_commit=True
        )
        assert write_success and initial_commit, "Setup failed: Could not write initial block"
        # Also index it initially to simulate real state
        memory_bank_instance.llama_memory.add_block(sample_memory_block)
        time.sleep(0.5)  # Give indexing a moment

        # --- Perform Update ---
        # Create an updated version of the block
        updated_block = MemoryBlock(
            id=sample_memory_block.id,
            type=sample_memory_block.type,
            text="This is the updated text.",
            tags=["updated", "test"],
            metadata={"source": "pytest", "update_run": True},
            created_at=sample_memory_block.created_at,
            updated_at=datetime.datetime.now(),
        )

        update_success = memory_bank_instance.update_memory_block(updated_block)
        assert update_success, "update_memory_block returned False"

        # --- Verify Dolt Update ---
        read_back_block = read_memory_block(
            memory_bank_instance.dolt_db_path, sample_memory_block.id
        )
        assert read_back_block is not None, "Block not found in Dolt after update"
        assert read_back_block.text == updated_block.text
        assert read_back_block.tags == updated_block.tags
        assert read_back_block.metadata == updated_block.metadata
        # Check that updated_at timestamp has changed (is later than original)
        assert read_back_block.updated_at > sample_memory_block.updated_at, (
            "updated_at timestamp was not updated"
        )

        # --- Verify LlamaIndex Update ---
        time.sleep(0.5)  # Give indexing update a moment
        try:
            # Query for the *updated* text
            query_results = memory_bank_instance.llama_memory.query_vector_store(
                updated_block.text, top_k=1
            )
            assert len(query_results) > 0, "Updated block not found in LlamaIndex vector store"
            assert query_results[0].node.id_ == sample_memory_block.id, (
                "Found node ID does not match updated block ID"
            )

            # Query for the *old* text - should ideally not return the same block with high confidence
            old_query_results = memory_bank_instance.llama_memory.query_vector_store(
                sample_memory_block.text, top_k=1
            )
            if len(old_query_results) > 0:
                assert (
                    old_query_results[0].node.id_ != sample_memory_block.id
                    or old_query_results[0].score < 0.8
                ), "Old text still strongly matches the updated block in LlamaIndex"
        except Exception as e:
            pytest.fail(f"Querying LlamaIndex after update failed: {e}")

        # TODO: Verify link updates in Dolt/LlamaIndex if links were part of update_data

    def test_delete_memory_block(
        self, memory_bank_instance: StructuredMemoryBank, sample_memory_block: MemoryBlock
    ):
        """Tests deleting a memory block."""
        # pytest.skip("delete_memory_block not yet implemented")

        # --- Setup: Create the initial block ---
        write_success, initial_commit = write_memory_block_to_dolt(
            block=sample_memory_block, db_path=memory_bank_instance.dolt_db_path, auto_commit=True
        )
        assert write_success and initial_commit, (
            "Setup failed: Could not write initial block for delete test"
        )
        # Also index it initially
        memory_bank_instance.llama_memory.add_block(sample_memory_block)
        time.sleep(0.5)  # Give indexing a moment

        # --- Perform Delete ---
        delete_success = memory_bank_instance.delete_memory_block(sample_memory_block.id)
        assert delete_success, "delete_memory_block returned False"

        # --- Verify Dolt Deletion ---
        read_back_block = read_memory_block(
            memory_bank_instance.dolt_db_path, sample_memory_block.id
        )
        assert read_back_block is None, "Block still found in Dolt after deletion"

        # --- Verify LlamaIndex Deletion ---
        time.sleep(0.5)  # Give index update a moment
        try:
            # Query for the deleted text - should not be found
            query_results = memory_bank_instance.llama_memory.query_vector_store(
                sample_memory_block.text, top_k=1
            )
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
            id="query-block-1",
            type="knowledge",
            text="The quick brown fox jumps over the lazy dog.",
            tags=["animal", "quick"],
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        )
        block2_data = MemoryBlock(
            id="query-block-2",
            type="knowledge",
            text="Semantic search finds related concepts.",
            tags=["search", "concepts"],
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        )
        block3_data = MemoryBlock(
            id="query-block-3",
            type="task",
            text="Implement the semantic query functionality.",
            tags=["task", "query"],
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        )
        # Add a block specifically for the unrelated query test
        unrelated_block = MemoryBlock(
            id="query-block-animal",
            type="knowledge",
            text="Foxes have bushy tails and are quick animals that hunt at night.",
            tags=["animal", "fox"],
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        )

        create_success1 = memory_bank_instance.create_memory_block(block1_data)
        create_success2 = memory_bank_instance.create_memory_block(block2_data)
        create_success3 = memory_bank_instance.create_memory_block(block3_data)
        create_success4 = memory_bank_instance.create_memory_block(unrelated_block)
        assert create_success1 and create_success2 and create_success3 and create_success4, (
            "Failed to create blocks for semantic query test"
        )
        time.sleep(1)  # Give indexing a bit more time after creates

        # --- Perform Query ---
        query_text = "finding information using meaning"
        results = memory_bank_instance.query_semantic(query_text, top_k=2)

        # --- Verify Results ---
        assert results is not None, "query_semantic returned None"
        assert len(results) > 0, "Semantic query did not return any results"

        # Check if the most relevant block (likely block2) is returned
        # Note: Exact relevance/order depends heavily on the embedding model used by LlamaIndex
        assert any(block.id == "query-block-2" for block in results), (
            "Expected block 2 (related concepts) not found in results"
        )

        # Check if the first result is likely block 2 (stronger assertion)
        if results:
            assert results[0].id == "query-block-2", (
                f"Expected block 2 to be the most relevant result, but got {results[0].id}"
            )

        # --- Test with a query focused on a different topic (animals) ---
        animal_query = "foxes and animals with bushy tails"
        animal_results = memory_bank_instance.query_semantic(animal_query, top_k=1)

        assert animal_results is not None, "animal query returned None"
        assert len(animal_results) > 0, "animal query did not return any results"

        # The fox/animal block should be the top result for the animal query
        assert animal_results[0].id == "query-block-animal", (
            f"Expected animal block to be the most relevant result for animal query, but got {animal_results[0].id}"
        )

    def test_get_blocks_by_tags(self, memory_bank_instance: StructuredMemoryBank):
        """Tests retrieving blocks by tags."""
        # pytest.skip("get_blocks_by_tags not yet implemented")

        # --- Setup: Create blocks with specific tags ---
        block_a = MemoryBlock(
            id="tag-block-a",
            type="knowledge",
            text="Block with tag alpha",
            tags=["alpha"],
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        )
        block_b = MemoryBlock(
            id="tag-block-b",
            type="knowledge",
            text="Block with tag beta",
            tags=["beta"],
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        )
        block_ab = MemoryBlock(
            id="tag-block-ab",
            type="knowledge",
            text="Block with tags alpha and beta",
            tags=["alpha", "beta"],
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        )
        block_c = MemoryBlock(
            id="tag-block-c",
            type="task",
            text="Block with no relevant tags",
            tags=["gamma"],
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
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
        assert len(results_all_alpha) == 2  # block_a and block_ab
        assert {b.id for b in results_all_alpha} == {"tag-block-a", "tag-block-ab"}

        results_all_beta = memory_bank_instance.get_blocks_by_tags(["beta"], match_all=True)
        assert len(results_all_beta) == 2  # block_b and block_ab
        assert {b.id for b in results_all_beta} == {"tag-block-b", "tag-block-ab"}

        results_all_ab = memory_bank_instance.get_blocks_by_tags(["alpha", "beta"], match_all=True)
        assert len(results_all_ab) == 1
        assert results_all_ab[0].id == "tag-block-ab"

        results_all_ag = memory_bank_instance.get_blocks_by_tags(["alpha", "gamma"], match_all=True)
        assert len(results_all_ag) == 0

        results_all_none = memory_bank_instance.get_blocks_by_tags(["delta"], match_all=True)
        assert len(results_all_none) == 0

    @pytest.mark.skip(
        "Test relies on deprecated inline links architecture - links now managed via LinkManager"
    )
    def test_get_forward_links(
        self, memory_bank_instance: StructuredMemoryBank, sample_memory_block: MemoryBlock
    ):
        """Tests retrieving forward links."""
        # First create the target block
        target_block = MemoryBlock(
            id="related-block-002",
            type="knowledge",
            text="This is a target block for forward link testing.",
            tags=["test", "target"],
        )
        target_success = memory_bank_instance.create_memory_block(target_block)
        assert target_success, "Failed to create target block for forward link test"

        # Now create a block with links
        success = memory_bank_instance.create_memory_block(sample_memory_block)
        assert success, "Failed to create block with links for test"

        # Now test the forward link functionality
        links = memory_bank_instance.get_forward_links(sample_memory_block.id)
        assert len(links) == 1, f"Expected 1 link, got {len(links)}"
        assert links[0].to_id == "related-block-002", (
            f"Expected link to 'related-block-002', got '{links[0].to_id}'"
        )
        assert links[0].relation == "related_to", (
            f"Expected relation 'related_to', got '{links[0].relation}'"
        )

    @pytest.mark.skip(
        "Test relies on deprecated inline links architecture - links now managed via LinkManager"
    )
    def test_get_backlinks(
        self, memory_bank_instance: StructuredMemoryBank, sample_memory_block: MemoryBlock
    ):
        """Tests retrieving backlinks."""
        # First create a block that will be the target of a link
        target_block = MemoryBlock(
            id="related-block-002",
            type="knowledge",
            text="This is a target block for backlink testing.",
            tags=["test", "target"],
            links=[],  # No links in the target block
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
                assert link.relation == "related_to", (
                    f"Expected relation 'related_to', got '{link.relation}'"
                )
                break

        assert found_backlink, (
            f"Did not find expected backlink from {source_block.id} to 'related-block-002'"
        )

        # Test filtering by relation
        filtered_backlinks = memory_bank_instance.get_backlinks(
            "related-block-002", relation="related_to"
        )
        assert len(filtered_backlinks) >= 1, (
            "Expected at least 1 backlink when filtering by 'related_to'"
        )

    def test_create_memory_block_basic(self, memory_bank, mock_dolt_writer, mock_llama_memory):
        """Test basic memory block creation functionality."""
        # Create a simple test block
        test_block = MemoryBlock(id="test-block-1", type="knowledge", text="This is a test block.")

        # TODO: Add basic schema definition to node_schemas if needed for create tests

        # Execute the create operation
        result = memory_bank.create_memory_block(test_block)

        # Verify the result and interactions
        assert result is True
        mock_dolt_writer.assert_called_once()
        mock_llama_memory.add_block.assert_called_once_with(test_block)

    def test_create_memory_block_with_schema_version_lookup(
        self, memory_bank, mock_dolt_writer, mock_llama_memory, mock_schema_manager
    ):
        """Test that create_memory_block fetches and sets schema_version when missing."""
        # Configure mock to return a schema with version
        mock_schema = {"x_schema_version": 2, "title": "Knowledge", "type": "object"}
        mock_schema_manager.return_value = mock_schema

        # Create a test block without schema_version
        test_block = MemoryBlock(
            id="test-block-schema",
            type="knowledge",
            text="This is a test block for schema versioning.",
        )
        assert test_block.schema_version is None

        # Execute the create operation
        result = memory_bank.create_memory_block(test_block)

        # Verify schema version was set
        assert result is True
        assert test_block.schema_version == 2

        # Check if the mock was called at all
        assert mock_schema_manager.call_count == 1
        # Get the actual arguments the mock was called with
        args, kwargs = mock_schema_manager.call_args
        # Check that the function was called with the right parameters, regardless of how they were passed
        assert MOCK_DOLT_PATH in args or kwargs.get("db_path") == MOCK_DOLT_PATH
        assert "knowledge" in args or kwargs.get("node_type") == "knowledge"

        mock_dolt_writer.assert_called_once()
        mock_llama_memory.add_block.assert_called_once_with(test_block)

    def test_create_memory_block_missing_schema(
        self, memory_bank, mock_dolt_writer, mock_llama_memory, mock_schema_manager
    ):
        """Test that create_memory_block works even when no schema is found."""
        # Configure mock to return None (no schema found)
        mock_schema_manager.return_value = None

        # Create a test block without schema_version
        test_block = MemoryBlock(
            id="test-block-no-schema",
            type="knowledge",
            text="This is a test block with no available schema.",
        )
        assert test_block.schema_version is None

        # Execute the create operation
        result = memory_bank.create_memory_block(test_block)

        # Verify operation succeeded but schema_version remained None
        assert result is True
        assert test_block.schema_version is None

        # Check if the mock was called at all
        assert mock_schema_manager.call_count == 1
        # Get the actual arguments the mock was called with
        args, kwargs = mock_schema_manager.call_args
        # Check that the function was called with the right parameters, regardless of how they were passed
        assert MOCK_DOLT_PATH in args or kwargs.get("db_path") == MOCK_DOLT_PATH
        assert "knowledge" in args or kwargs.get("node_type") == "knowledge"

        mock_dolt_writer.assert_called_once()
        mock_llama_memory.add_block.assert_called_once_with(test_block)

    def test_create_memory_block_preserves_existing_schema_version(
        self, memory_bank, mock_dolt_writer, mock_llama_memory, mock_schema_manager
    ):
        """Test that create_memory_block doesn't change schema_version if already set."""
        # Configure mock to return a schema with different version
        mock_schema = {"x_schema_version": 3, "title": "Knowledge", "type": "object"}
        mock_schema_manager.return_value = mock_schema

        # Create a test block with schema_version already set
        test_block = MemoryBlock(
            id="test-block-existing-schema",
            type="knowledge",
            text="This is a test block with pre-set schema version.",
            schema_version=1,
        )

        # Execute the create operation
        result = memory_bank.create_memory_block(test_block)

        # Verify schema version was not changed
        assert result is True
        assert test_block.schema_version == 1  # Should remain 1, not changed to 3
        # Schema lookup shouldn't be called since version is already set
        mock_schema_manager.assert_not_called()
        mock_dolt_writer.assert_called_once()
        mock_llama_memory.add_block.assert_called_once_with(test_block)

    def test_create_memory_block_validation_fails(
        self, memory_bank, mock_dolt_writer, mock_llama_memory
    ):
        """Tests that create_memory_block fails when given an invalid block."""
        # Create a valid block first
        block = MemoryBlock(
            id="test-invalid-block", type="knowledge", text="This should fail validation"
        )

        # Setup a patched version of model_validate that raises ValidationError
        original_model_validate = MemoryBlock.model_validate

        def mock_model_validate(obj, *args, **kwargs):
            if hasattr(obj, "id") and obj.id == "test-invalid-block":
                # For this specific test block, raise a validation error
                # Use the lower-level PydanticCustomError directly
                raise ValidationError.from_exception_data(
                    title="validation-error",
                    line_errors=[
                        {
                            "type": "string_type",
                            "loc": ("id",),
                            "msg": "Mock validation error for testing",
                            "input": "test-invalid-block",
                            "ctx": {"error": "mocked validation failure"},
                        }
                    ],
                )
            # For any other object, use the original method
            return original_model_validate(obj, *args, **kwargs)

        # Apply the patch
        with patch.object(MemoryBlock, "model_validate", side_effect=mock_model_validate):
            # The validation should fail during create_memory_block
            result = memory_bank.create_memory_block(block)

            # Assert the operation failed
            assert result is False, "create_memory_block should return False for invalid blocks"

            # Verify no Dolt write was attempted
            mock_dolt_writer.assert_not_called()

            # Verify no LlamaIndex add was attempted
            mock_llama_memory.add_block.assert_not_called()

    def test_update_memory_block_validation_fails(
        self, memory_bank, mock_dolt_writer, mock_llama_memory, mock_dolt_reader
    ):
        """Tests that update_memory_block fails when given invalid update data."""
        # Set up mock reader to return a valid block
        valid_block = MemoryBlock(
            id="test-block-to-update",
            type="knowledge",
            text="Original text",
            tags=["original", "tags"],
        )
        mock_dolt_reader.return_value = valid_block

        # Set up a deeper mock to intercept model_validate to trigger validation error
        with patch(
            "infra_core.memory_system.structured_memory_bank.MemoryBlock.model_validate"
        ) as mock_validate:
            mock_validate.side_effect = ValidationError.from_exception_data(
                title="MemoryBlock",
                line_errors=[
                    {
                        "type": "list_type",
                        "loc": ("tags",),
                        "msg": "Input should be a valid list",
                        "input": "invalid-tags-format",
                    }
                ],
            )

            # Create a valid block first
            valid_block = MemoryBlock(
                id="test-block-to-update",
                type="knowledge",
                text="Original text",
                tags=["original", "tags"],
            )

            # The validation should fail when model_validate is called
            result = memory_bank.update_memory_block(valid_block)

            # Assert the operation failed
            assert result is False, (
                "update_memory_block should return False for invalid update data"
            )

            # Verify model_validate was called
            mock_validate.assert_called_once()

            # Verify no Dolt write was attempted
            mock_dolt_writer.assert_not_called()

            # Verify no LlamaIndex update was attempted
            mock_llama_memory.update_block.assert_not_called()

    def test_diff_memory_blocks(self):
        """Tests the diff_memory_blocks helper function."""
        # Create two blocks with some differences
        block1 = MemoryBlock(
            id="diff-test-block",
            type="knowledge",
            text="Original text",
            tags=["tag1", "tag2"],
            metadata={"key1": "value1", "key2": "value2"},
        )

        block2 = MemoryBlock(
            id="diff-test-block",  # Same ID
            type="knowledge",  # Same type
            text="Updated text",  # Different text
            tags=["tag1", "tag3"],  # Modified tags
            metadata={"key1": "value1", "key2": "modified"},  # Modified metadata
        )

        # Generate diff
        changes = diff_memory_blocks(block1, block2)

        # Verify changes were detected correctly
        assert "text" in changes, "Text change not detected"
        assert changes["text"] == ("Original text", "Updated text")

        assert "tags" in changes, "Tags change not detected"
        assert set(changes["tags"][0]) == {"tag1", "tag2"}
        assert set(changes["tags"][1]) == {"tag1", "tag3"}

        assert "metadata" in changes, "Metadata change not detected"
        assert changes["metadata"][0]["key2"] == "value2"
        assert changes["metadata"][1]["key2"] == "modified"

        # Verify unchanged fields are not in the diff
        assert "id" not in changes, "ID should not be in diff since it didn't change"
        assert "type" not in changes, "Type should not be in diff since it didn't change"
        assert "updated_at" not in changes, "updated_at should be excluded from diff"

        # Test with identical blocks
        changes_identical = diff_memory_blocks(block1, block1)
        assert not changes_identical, "No changes should be detected between identical blocks"

    def test_block_proofs(self, memory_bank_instance: StructuredMemoryBank):
        """Tests that block proofs are correctly recorded for CRUD operations."""
        # Generate a unique block ID for this test
        test_id = f"proof-test-block-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Create a test block
        test_block = MemoryBlock(
            id=test_id,
            type="knowledge",
            text="Initial text for proof testing",
            tags=["proof", "test"],
        )

        # 1. Test create operation
        create_success = memory_bank_instance.create_memory_block(test_block)
        assert create_success, "Failed to create test block for proof testing"

        # Check that a proof was recorded for the create operation
        create_proofs = memory_bank_instance.get_block_proofs(test_id)
        assert len(create_proofs) >= 1, "No proof record found after create operation"
        assert create_proofs[0]["operation"] == "create", (
            "First proof should be a 'create' operation"
        )
        assert create_proofs[0]["commit_hash"], "Commit hash should not be empty"

        # 2. Test update operation
        # Create an updated version of the block
        updated_block = MemoryBlock(
            id=test_id,
            type="knowledge",
            text="Updated text for proof testing",
            tags=["proof", "test", "updated"],
        )

        update_success = memory_bank_instance.update_memory_block(updated_block)
        assert update_success, "Failed to update test block for proof testing"

        # Check that a proof was recorded for the update operation
        update_proofs = memory_bank_instance.get_block_proofs(test_id)
        assert len(update_proofs) >= 2, "Should have at least 2 proof records after update"
        assert update_proofs[0]["operation"] == "update", (
            "Most recent proof should be an 'update' operation"
        )
        assert update_proofs[0]["commit_hash"], "Commit hash should not be empty"
        assert update_proofs[0]["commit_hash"] != update_proofs[1]["commit_hash"], (
            "Update commit hash should differ from create hash"
        )

        # 3. Test delete operation
        delete_success = memory_bank_instance.delete_memory_block(test_id)
        assert delete_success, "Failed to delete test block for proof testing"

        # Check that a proof was recorded for the delete operation
        delete_proofs = memory_bank_instance.get_block_proofs(test_id)
        assert len(delete_proofs) >= 3, "Should have at least 3 proof records after delete"
        assert delete_proofs[0]["operation"] == "delete", (
            "Most recent proof should be a 'delete' operation"
        )
        assert delete_proofs[0]["commit_hash"], "Commit hash should not be empty"
        assert delete_proofs[0]["commit_hash"] != delete_proofs[1]["commit_hash"], (
            "Delete commit hash should differ from update hash"
        )

        # Verify full history is preserved in chronological order (newest first)
        assert delete_proofs[2]["operation"] == "create", (
            "Oldest proof should be 'create' operation"
        )
        assert delete_proofs[1]["operation"] == "update", (
            "Middle proof should be 'update' operation"
        )
        assert delete_proofs[0]["operation"] == "delete", (
            "Newest proof should be 'delete' operation"
        )

    def test_commit_message_basic(self, memory_bank_instance: StructuredMemoryBank):
        """Tests that the default format still produces '{OPERATION}: {block_id} - {summary}' when no extra info is provided."""

        # Test with default summary
        message = memory_bank_instance.format_commit_message("create", "test-block-001")
        assert message == "CREATE: test-block-001 - No significant changes"

        # Test with custom summary
        message = memory_bank_instance.format_commit_message(
            "update", "test-block-001", "Changed text field"
        )
        assert message == "UPDATE: test-block-001 - Changed text field"

        # Test explicitly passing None for extra_info
        message = memory_bank_instance.format_commit_message(
            "delete", "test-block-001", "Block deleted", None
        )
        assert message == "DELETE: test-block-001 - Block deleted"

    def test_commit_message_with_extra_info(self, memory_bank_instance: StructuredMemoryBank):
        """Tests that extra_info appends neatly to the commit string."""

        # Test with extra_info
        message = memory_bank_instance.format_commit_message(
            operation="create",
            block_id="test-block-001",
            change_summary="New block",
            extra_info="actor=user-123",
        )
        assert message == "CREATE: test-block-001 - New block [actor=user-123]"

        # Test with extra_info but default summary
        message = memory_bank_instance.format_commit_message(
            operation="update", block_id="test-block-001", extra_info="session=abc123"
        )
        assert message == "UPDATE: test-block-001 - No significant changes [session=abc123]"

    def test_repo_connection_reuse(self):
        """Tests that StructuredMemoryBank reuses the same Dolt repository connection."""
        with (
            patch("infra_core.memory_system.structured_memory_bank.Dolt") as mock_dolt,
            patch("infra_core.memory_system.structured_memory_bank.LlamaMemory") as mock_llama,
        ):
            # Setup mock Dolt to return a mock repo
            mock_repo = mock_dolt.return_value
            mock_repo.sql.return_value = {"rows": []}

            # Setup mock LlamaMemory
            mock_llama_instance = mock_llama.return_value
            mock_llama_instance.is_ready.return_value = True

            # Create a memory bank instance
            bank = StructuredMemoryBank(
                dolt_db_path=MOCK_DOLT_PATH,
                chroma_path=MOCK_CHROMA_PATH,
                chroma_collection=MOCK_COLLECTION,
            )

            # Verify Dolt was called only once during initialization
            mock_dolt.assert_called_once_with(MOCK_DOLT_PATH)

            # Reset the mock to clear initialization call
            mock_dolt.reset_mock()

            # Call multiple methods that use Dolt
            bank.get_block_proofs("test-id")
            bank.get_forward_links("test-id")
            bank.get_backlinks("test-id")

            # Verify Dolt constructor was not called again
            mock_dolt.assert_not_called()

            # Verify the same repo instance was used for all method calls
            assert mock_repo.sql.call_count >= 3, (
                "Expected at least 3 SQL calls on the same repo instance"
            )

    def test_atomic_operations_llama_failure(self):
        """Tests that Dolt changes are rolled back when LlamaIndex operations fail."""
        # Setup mock objects
        with (
            patch("infra_core.memory_system.structured_memory_bank.Dolt"),
            patch("infra_core.memory_system.structured_memory_bank.LlamaMemory") as mock_llama,
            patch(
                "infra_core.memory_system.structured_memory_bank.write_memory_block_to_dolt",
                return_value=(True, None),
            ) as mock_write,
            patch(
                "infra_core.memory_system.structured_memory_bank.discard_working_changes",
                return_value=True,
            ) as mock_discard,
        ):
            # Setup mock LlamaMemory to fail on add_block
            mock_llama_instance = mock_llama.return_value
            mock_llama_instance.is_ready.return_value = True
            mock_llama_instance.add_block.side_effect = RuntimeError("Simulated LlamaIndex failure")

            # Create a memory bank instance
            bank = StructuredMemoryBank(
                dolt_db_path=MOCK_DOLT_PATH,
                chroma_path=MOCK_CHROMA_PATH,
                chroma_collection=MOCK_COLLECTION,
            )

            # Create a test memory block
            test_block = MemoryBlock(
                id="test-block-001", type="knowledge", text="This is a test memory block."
            )

            # Try to create the block (should fail due to LlamaIndex error)
            success = bank.create_memory_block(test_block)

            # Verify operations
            assert not success, "create_memory_block should return False when LlamaIndex fails"
            mock_write.assert_called_once()  # Write was attempted
            mock_llama_instance.add_block.assert_called_once()  # LlamaIndex add was attempted
            mock_discard.assert_called_once()  # Rollback was attempted

    def test_atomic_operations_commit_failure(self):
        """Tests that consistency is maintained when Dolt commit fails after successful LlamaIndex operation."""
        # Setup mock objects
        with (
            patch("infra_core.memory_system.structured_memory_bank.Dolt"),
            patch("infra_core.memory_system.structured_memory_bank.LlamaMemory") as mock_llama,
            patch(
                "infra_core.memory_system.structured_memory_bank.write_memory_block_to_dolt",
                return_value=(True, None),
            ) as mock_write,
            patch(
                "infra_core.memory_system.structured_memory_bank.commit_working_changes",
                return_value=(False, None),
            ) as mock_commit,
            patch(
                "infra_core.memory_system.structured_memory_bank.discard_working_changes",
                return_value=True,
            ) as mock_discard,
        ):
            # Setup mock LlamaMemory to succeed
            mock_llama_instance = mock_llama.return_value
            mock_llama_instance.is_ready.return_value = True

            # Create a memory bank instance
            bank = StructuredMemoryBank(
                dolt_db_path=MOCK_DOLT_PATH,
                chroma_path=MOCK_CHROMA_PATH,
                chroma_collection=MOCK_COLLECTION,
            )

            # Create a test memory block
            test_block = MemoryBlock(
                id="test-block-001", type="knowledge", text="This is a test memory block."
            )

            # Try to create the block (should fail due to commit error)
            success = bank.create_memory_block(test_block)

            # Verify operations
            assert not success, "create_memory_block should return False when commit fails"
            mock_write.assert_called_once()  # Write was attempted
            mock_llama_instance.add_block.assert_called_once()  # LlamaIndex add was attempted
            mock_commit.assert_called_once()  # Commit was attempted
            mock_discard.assert_called_once()  # Rollback was attempted

    def test_atomic_operations_rollback_failure(self):
        """Tests that memory bank is marked as inconsistent when rollback fails."""
        # Setup mock objects
        with (
            patch("infra_core.memory_system.structured_memory_bank.Dolt"),
            patch("infra_core.memory_system.structured_memory_bank.LlamaMemory") as mock_llama,
            patch(
                "infra_core.memory_system.structured_memory_bank.write_memory_block_to_dolt",
                return_value=(True, None),
            ) as mock_write,
            patch(
                "infra_core.memory_system.structured_memory_bank.discard_working_changes",
                side_effect=RuntimeError("Simulated rollback failure"),
            ) as mock_discard,
        ):
            # Setup mock LlamaMemory to fail on add_block
            mock_llama_instance = mock_llama.return_value
            mock_llama_instance.is_ready.return_value = True
            mock_llama_instance.add_block.side_effect = RuntimeError("Simulated LlamaIndex failure")

            # Create a memory bank instance
            bank = StructuredMemoryBank(
                dolt_db_path=MOCK_DOLT_PATH,
                chroma_path=MOCK_CHROMA_PATH,
                chroma_collection=MOCK_COLLECTION,
            )

            # Create a test memory block
            test_block = MemoryBlock(
                id="test-block-001", type="knowledge", text="This is a test memory block."
            )

            # Try to create the block (should fail with both LlamaIndex and rollback errors)
            success = bank.create_memory_block(test_block)

            # Verify operations
            assert not success, "create_memory_block should return False when operations fail"
            mock_write.assert_called_once()  # Write was attempted
            mock_llama_instance.add_block.assert_called_once()  # LlamaIndex add was attempted
            mock_discard.assert_called_once()  # Rollback was attempted
            assert not bank.is_consistent, (
                "Memory bank should be marked as inconsistent when rollback fails"
            )
