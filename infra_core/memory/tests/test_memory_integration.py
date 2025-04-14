"""
Integration tests for the Cogni Memory Architecture components.

These tests verify that the different components of the memory system 
(storage, indexing, querying, archiving) work together correctly.
"""

import os
import tempfile
import shutil
import pytest
import json
import uuid
from datetime import datetime
from pathlib import Path

import chromadb
from infra_core.memory.memory_client import CogniMemoryClient
from infra_core.memory.memory_tool import memory_tool
from infra_core.memory.schema import MemoryBlock
from infra_core.memory.storage import ChromaStorage, ArchiveStorage, CombinedStorage


class TestStorage(ChromaStorage):
    """Test-specific extension of ChromaStorage that creates a collection if it doesn't exist."""
    
    def __init__(self, vector_db_dir: str, collection_name: str = "cogni-memory"):
        """Initialize with collection creation if needed."""
        # Create directory if it doesn't exist
        os.makedirs(vector_db_dir, exist_ok=True)
        
        # Store configuration
        self.vector_db_dir = vector_db_dir
        self.collection_name = collection_name
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=vector_db_dir,
            settings=chromadb.Settings(
                anonymized_telemetry=False,
                allow_reset=True,
                chroma_server_ssl_enabled=False,
            ),
        )
        
        # Try to get collection first, create if it doesn't exist
        try:
            self.collection = self.client.get_collection(name=self.collection_name)
        except Exception:
            # Create collection if it doesn't exist
            self.collection = self.client.create_collection(name=self.collection_name)


class TestMemoryIntegration:
    """Integration tests for the memory architecture components."""
    
    @pytest.fixture
    def test_environment(self):
        """Set up a complete test environment for integration testing."""
        # Create temporary directories
        test_root = tempfile.mkdtemp()
        logseq_dir = os.path.join(test_root, "logseq")
        output_dir = os.path.join(test_root, "cogni-memory")
        
        os.makedirs(logseq_dir)
        
        try:
            # Create test Logseq files with a mix of tagged and untagged content
            with open(os.path.join(logseq_dir, "journal.md"), "w") as f:
                f.write("- First test thought #thought\n")
                f.write("- This is an important announcement #broadcast #approved\n")
                f.write("- Just a regular block without tags\n")
                f.write("- Another thought to consider #thought\n")
                f.write("- Critical update notification #broadcast\n")
            
            with open(os.path.join(logseq_dir, "notes.md"), "w") as f:
                f.write("- Some notes about the project\n")
                f.write("- Important concept to remember #thought\n")
                f.write("- Announcement for team members #broadcast\n")
            
            yield {
                "root": test_root,
                "logseq_dir": logseq_dir,
                "output_dir": output_dir
            }
        finally:
            shutil.rmtree(test_root)
    
    def test_simple_chromadb(self, test_environment):
        """Test basic ChromaDB functionality directly to verify it works."""
        # Create directory for ChromaDB
        chroma_path = os.path.join(test_environment["output_dir"], "simple_chroma")
        os.makedirs(chroma_path, exist_ok=True)
        
        # Create client and collection
        client = chromadb.PersistentClient(path=chroma_path)
        collection = client.create_collection("test-collection")
        
        # Add test document with tags
        test_id = "test1"
        test_text = "This is a test document with a thought tag"
        test_tags = "#thought, #test"
        
        collection.add(
            ids=[test_id],
            documents=[test_text],
            metadatas=[{"tags": test_tags, "source": "test.md"}],
            embeddings=[[0.1] * 384]  # Mock embedding
        )
        
        # Query and verify
        results = collection.query(
            query_embeddings=[[0.1] * 384],
            n_results=1
        )
        
        # Check results
        assert len(results["ids"][0]) == 1
        assert results["ids"][0][0] == test_id
        assert results["documents"][0][0] == test_text
        assert results["metadatas"][0][0]["tags"] == test_tags
    
    def test_complete_memory_pipeline(self, test_environment):
        """
        Test the complete memory pipeline from parsing to embedding to querying.
        
        This tests integration between:
        1. Data extraction and formatting
        2. Storage components (ChromaDB and Archive)
        3. Memory client operations
        4. Memory tool interface
        """
        # Create required directories
        chroma_path = os.path.join(test_environment["output_dir"], "chroma")
        archive_path = os.path.join(test_environment["output_dir"], "archive")
        os.makedirs(chroma_path, exist_ok=True)
        os.makedirs(archive_path, exist_ok=True)
        os.makedirs(os.path.join(archive_path, "blocks"), exist_ok=True)
        os.makedirs(os.path.join(archive_path, "index"), exist_ok=True)
        
        # Step 1: Create storage components directly
        collection_name = "cogni-memory"
        chroma_storage = TestStorage(chroma_path, collection_name)
        archive_storage = ArchiveStorage(archive_path)
        combined_storage = CombinedStorage(
            vector_db_dir=chroma_path,
            archive_dir=archive_path
        )
        
        # Replace with our test components
        combined_storage.chroma = chroma_storage
        combined_storage.archive = archive_storage
        
        # Step 2: Create memory client with our storage
        memory_client = CogniMemoryClient(
            chroma_path=chroma_path,
            archive_path=archive_path,
            collection_name=collection_name
        )
        
        # Override storage components
        memory_client.storage = combined_storage
        memory_client.chroma_storage = chroma_storage
        memory_client.archive_storage = archive_storage
        
        # Step 3: Extract test data from Logseq files
        test_blocks = []
        journal_path = os.path.join(test_environment["logseq_dir"], "journal.md")
        notes_path = os.path.join(test_environment["logseq_dir"], "notes.md")
        
        # Read files and extract tagged blocks
        target_tags = {"#thought", "#broadcast", "#approved"}
        
        with open(journal_path, "r") as f:
            lines = f.readlines()
            for line in lines:
                # Extract tags
                tags = {tag for tag in line.split() if tag.startswith("#")}
                if tags & target_tags:  # If there's an overlap with target tags
                    # Create block
                    block_id = str(uuid.uuid4())
                    test_blocks.append({
                        "id": block_id,
                        "text": line.strip(),
                        "tags": list(tags),
                        "source_file": os.path.basename(journal_path)
                    })
        
        with open(notes_path, "r") as f:
            lines = f.readlines()
            for line in lines:
                # Extract tags
                tags = {tag for tag in line.split() if tag.startswith("#")}
                if tags & target_tags:
                    # Create block
                    block_id = str(uuid.uuid4())
                    test_blocks.append({
                        "id": block_id,
                        "text": line.strip(),
                        "tags": list(tags),
                        "source_file": os.path.basename(notes_path)
                    })
        
        # Step 4: Create memory blocks
        memory_blocks = []
        for block in test_blocks:
            # Create MemoryBlock with specific tags
            memory_block = MemoryBlock(
                id=block["id"],
                text=block["text"],
                tags=block["tags"],
                source_file=block["source_file"],
                embedding=[0.1] * 384,  # Mock embedding
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            memory_blocks.append(memory_block)
        
        # Step 5: Save blocks directly to ChromaDB using our storage
        for block in memory_blocks:
            # Convert tags list to a string for ChromaDB metadata
            tags_str = ", ".join(block.tags)
            
            # Add to ChromaDB directly
            chroma_storage.collection.add(
                ids=[block.id],
                documents=[block.text],
                metadatas=[{"tags": tags_str, "source": block.source_file}],
                embeddings=[block.embedding]
            )
        
        # Step 6: Query for thought-tagged content
        thought_results = memory_client.query("thought", n_results=10)
        
        # Debug: Print the tags in the results
        print("\nThought query results:")
        for i, block in enumerate(thought_results.blocks):
            print(f"Block {i}: {block.text}")
            print(f"Tags: {block.tags}")
        
        # Verify thought results
        assert len(thought_results.blocks) >= 3, f"Expected >=3 thought blocks, got {len(thought_results.blocks)}"
        
        # Count how many blocks have the #thought tag
        thought_count = sum(1 for block in thought_results.blocks if "#thought" in block.tags)
        assert thought_count >= 3, f"Expected >=3 blocks with #thought tag, got {thought_count}"
        
        # Step 7: Add a new memory block
        new_block = {
            "text": "New memory created during testing #thought",
            "tags": ["#thought"],
            "source_file": "test_generated.md"
        }
        memory_client.save_blocks([new_block])
        
        # Step 8: Archive a block
        first_block_id = memory_blocks[0].id
        memory_client.archive_blocks([first_block_id])
        
        # Step 9: Verify archive contains the block
        archive_files = list(Path(archive_path, "blocks").glob("*.json"))
        assert len(archive_files) >= 1
        
        with open(archive_files[0], "r") as f:
            archived_data = json.load(f)
            print(f"Archived data: {archived_data}")
        
        # Step 10: Test memory tool integration
        tool_results = memory_tool(
            input_text="test",
            n_results=2,
            chroma_path=chroma_path
        )
        
        # Verify tool results
        assert len(tool_results["results"]) > 0
        
        # Step 11: Test index_from_logseq integration
        # Create a new collection for testing index_from_logseq
        index_collection_name = "index-test-collection"
        index_chroma_path = os.path.join(test_environment["output_dir"], "index-chroma")
        index_archive_path = os.path.join(test_environment["output_dir"], "index-archive")
        
        os.makedirs(index_chroma_path, exist_ok=True)
        os.makedirs(index_archive_path, exist_ok=True)
        os.makedirs(os.path.join(index_archive_path, "blocks"), exist_ok=True)
        os.makedirs(os.path.join(index_archive_path, "index"), exist_ok=True)
        
        # Create a new client for indexing
        index_client = CogniMemoryClient(
            chroma_path=index_chroma_path,
            archive_path=index_archive_path,
            collection_name=index_collection_name
        )
        
        # Create a mock embedding function that returns consistent dimension
        from unittest.mock import patch
        
        # Get the dimensions from the collection - it should be 384 from our test setup
        dimension = 384
        
        # Define a mock function that returns the right dimension
        def mock_embedding_function(texts):
            return [[0.1] * dimension for _ in range(len(texts))]
        
        # Patch the init_embedding_function method to return our mock
        with patch("infra_core.memory.memory_indexer.init_embedding_function", 
                  return_value=mock_embedding_function):
            
            # Run the indexing
            num_indexed = index_client.index_from_logseq(
                logseq_dir=test_environment["logseq_dir"],
                tag_filter="#thought",
                embed_model="mock",
                verbose=True
            )
            
            # Verify correct number of blocks were indexed
            assert num_indexed == 3, f"Expected 3 blocks with #thought tag, got {num_indexed}"
            
            # Test querying with the same mock
            with patch("infra_core.memory.memory_indexer.init_embedding_function", 
                      return_value=mock_embedding_function):
                
                # Query for thought content
                index_results = index_client.query("test query", n_results=10)
                
                # Verify results
                assert len(index_results.blocks) > 0, "No results returned from index query"
                
                # Verify all results have the #thought tag
                for block in index_results.blocks:
                    assert "#thought" in block.tags, f"Block missing #thought tag, has {block.tags}"
                    print(f"Index result: {block.text}")
        
        # Test completed successfully
    
    def test_verify_test_data(self, test_environment):
        """Verify test data was created correctly."""
        # This test ensures our fixture is working correctly
        journal_path = os.path.join(test_environment["logseq_dir"], "journal.md")
        notes_path = os.path.join(test_environment["logseq_dir"], "notes.md")
        
        assert os.path.exists(journal_path)
        assert os.path.exists(notes_path)
        
        # Count tagged blocks
        thought_count = 0
        broadcast_count = 0
        
        with open(journal_path, "r") as f:
            content = f.read()
            thought_count += content.count("#thought")
            broadcast_count += content.count("#broadcast")
        
        with open(notes_path, "r") as f:
            content = f.read()
            thought_count += content.count("#thought")
            broadcast_count += content.count("#broadcast")
        
        # Verify we have the expected number of tagged blocks
        assert thought_count == 3
        assert broadcast_count == 3
        
    def test_index_from_logseq_e2e(self, test_environment):
        """
        End-to-end test for the index_from_logseq method.
        
        Tests that the method can:
        1. Correctly scan and parse Logseq files
        2. Index blocks with appropriate tags
        3. Create proper embeddings
        4. Allow querying the indexed content
        5. Apply tag filtering correctly
        """
        # Create required directories
        chroma_path = os.path.join(test_environment["output_dir"], "index_chroma")
        archive_path = os.path.join(test_environment["output_dir"], "index_archive")
        os.makedirs(chroma_path, exist_ok=True)
        os.makedirs(archive_path, exist_ok=True)
        os.makedirs(os.path.join(archive_path, "blocks"), exist_ok=True)
        os.makedirs(os.path.join(archive_path, "index"), exist_ok=True)
        
        # Create memory client
        memory_client = CogniMemoryClient(
            chroma_path=chroma_path,
            archive_path=archive_path,
            collection_name="cogni-memory-e2e"
        )
        
        # Mock embeddings for testing
        from unittest.mock import MagicMock
        mock_embedder = MagicMock()
        mock_embedder.return_value = [[0.1] * 384 for _ in range(10)]
        
        # Index from Logseq with tag filter for #thought
        with pytest.MonkeyPatch().context() as mp:
            # Patch the embedding function to return mock embeddings
            mp.setattr("infra_core.memory.memory_indexer.init_embedding_function", lambda model_name: mock_embedder)
            
            # Run indexing with tag filter
            num_indexed = memory_client.index_from_logseq(
                logseq_dir=test_environment["logseq_dir"],
                tag_filter="#thought",
                embed_model="mock",
                verbose=True
            )
        
        # Verify the right number of blocks were indexed
        assert num_indexed == 3, f"Expected 3 #thought blocks to be indexed, got {num_indexed}"
        
        # Query for thought content
        with pytest.MonkeyPatch().context() as mp:
            # For query we need to mock the embedding function again
            mp.setattr("infra_core.memory.memory_indexer.init_embedding_function", lambda model_name: mock_embedder)
            
            # Query for thought-related content
            thought_results = memory_client.query("thought concept", n_results=10)
        
        # Verify we got results matching our indexed content
        assert len(thought_results.blocks) > 0, "No results returned from query"
        
        # All results should have #thought tag
        for block in thought_results.blocks:
            assert "#thought" in block.tags, f"Block has tags {block.tags} but missing #thought tag"
        
        # Now try indexing with a different tag filter
        chroma_path2 = os.path.join(test_environment["output_dir"], "index_chroma2")
        archive_path2 = os.path.join(test_environment["output_dir"], "index_archive2")
        os.makedirs(chroma_path2, exist_ok=True)
        os.makedirs(archive_path2, exist_ok=True)
        os.makedirs(os.path.join(archive_path2, "blocks"), exist_ok=True)
        os.makedirs(os.path.join(archive_path2, "index"), exist_ok=True)
        
        # Create a new client
        memory_client2 = CogniMemoryClient(
            chroma_path=chroma_path2,
            archive_path=archive_path2,
            collection_name="cogni-memory-e2e2"
        )
        
        # Index with broadcast tag filter
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("infra_core.memory.memory_indexer.init_embedding_function", lambda model_name: mock_embedder)
            
            num_indexed2 = memory_client2.index_from_logseq(
                logseq_dir=test_environment["logseq_dir"],
                tag_filter="#broadcast",
                embed_model="mock",
                verbose=True
            )
        
        # Verify the right number of blocks were indexed
        assert num_indexed2 == 3, f"Expected 3 #broadcast blocks to be indexed, got {num_indexed2}"
        
        # Query for broadcast content
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("infra_core.memory.memory_indexer.init_embedding_function", lambda model_name: mock_embedder)
            
            broadcast_results = memory_client2.query("announcement", n_results=10)
        
        # Verify we got results matching our indexed content
        assert len(broadcast_results.blocks) > 0, "No results returned from query"
        
        # All results should have #broadcast tag
        for block in broadcast_results.blocks:
            assert "#broadcast" in block.tags, f"Block has tags {block.tags} but missing #broadcast tag" 