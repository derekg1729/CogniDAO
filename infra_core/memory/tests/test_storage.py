"""
Tests for the storage components (ChromaDB and Archive).
"""

import os
import json
import shutil
import tempfile
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock


from infra_core.memory.storage import ChromaStorage, ArchiveStorage
from infra_core.memory.schema import MemoryBlock


class TestChromaStorage:
    """Tests for the ChromaDB storage component."""

    @pytest.fixture
    def test_chroma_dir(self):
        """Create a temporary directory for ChromaDB."""
        temp_dir = tempfile.mkdtemp()
        try:
            yield temp_dir
        finally:
            shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_memory_blocks(self):
        """Create mock memory blocks for testing."""
        return [
            MemoryBlock(
                id="test-1",
                text="Test block with #thought tag",
                tags=["#thought"],
                source_file="test1.md",
                embedding=[0.1] * 1536
            ),
            MemoryBlock(
                id="test-2",
                text="Test block with #broadcast and #approved tags",
                tags=["#broadcast", "#approved"],
                source_file="test2.md",
                embedding=[0.2] * 1536
            )
        ]

    @patch("chromadb.PersistentClient")
    def test_chroma_initialization(self, mock_chroma_client, test_chroma_dir):
        """Test ChromaDB storage initialization."""
        # Verify test data is correct
        assert os.path.exists(test_chroma_dir)
        
        # Configure mock
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_chroma_client.return_value = mock_client
        
        # Handle collection creation
        mock_client.get_collection.side_effect = ValueError("Collection not found")
        mock_client.create_collection.return_value = mock_collection
        
        storage = ChromaStorage(test_chroma_dir)
        storage.client = mock_client
        storage.collection = mock_collection
        
        # Verify storage is initialized correctly
        assert storage.persist_directory == Path(test_chroma_dir)
        assert storage.collection_name == "cogni-memory"
        
        # Verify collection exists
        assert storage.collection is not None

    @patch("chromadb.PersistentClient")
    def test_add_blocks(self, mock_chroma_client, test_chroma_dir, mock_memory_blocks):
        """Test adding blocks to ChromaDB."""
        # Verify test data is correct
        assert len(mock_memory_blocks) == 2
        
        # Configure mock
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_chroma_client.return_value = mock_client
        mock_client.get_collection.side_effect = ValueError("Collection not found")
        mock_client.create_collection.return_value = mock_collection
        
        # Initialize storage and add blocks
        storage = ChromaStorage(test_chroma_dir)
        storage.client = mock_client
        storage.collection = mock_collection
        storage.add_blocks(mock_memory_blocks)
        
        # Verify blocks were added
        mock_collection.add.assert_called_once()
        args, kwargs = mock_collection.add.call_args
        
        # Verify correct data was passed
        assert len(kwargs["ids"]) == 2
        assert kwargs["ids"] == ["test-1", "test-2"]
        assert len(kwargs["embeddings"]) == 2
        assert len(kwargs["documents"]) == 2
        assert len(kwargs["metadatas"]) == 2

    @patch("chromadb.PersistentClient")
    def test_query(self, mock_chroma_client, test_chroma_dir):
        """Test querying blocks from ChromaDB."""
        # Configure mock
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_chroma_client.return_value = mock_client
        mock_client.get_collection.return_value = mock_collection
        
        # Configure mock query response
        mock_query_response = {
            "ids": [["test-1"]],
            "documents": [["Test block with #thought tag"]],
            "metadatas": [[{"tags": "#thought", "source": "test1.md"}]],
            "distances": [[0.1]]
        }
        mock_collection.query.return_value = mock_query_response
        
        # Initialize storage and query
        storage = ChromaStorage(test_chroma_dir)
        storage.client = mock_client
        storage.collection = mock_collection
        results = storage.query("thought", n_results=1)
        
        # Verify query was made correctly
        mock_collection.query.assert_called_once()
        args, kwargs = mock_collection.query.call_args
        assert kwargs["query_texts"] == ["thought"]
        assert kwargs["n_results"] == 1
        
        # Verify results
        assert results["ids"] == [["test-1"]]
        assert results["documents"] == [["Test block with #thought tag"]]


class TestArchiveStorage:
    """Tests for the Archive storage component."""

    @pytest.fixture
    def test_archive_dir(self):
        """Create a temporary directory for archive storage."""
        temp_dir = tempfile.mkdtemp()
        try:
            # Create directory structure
            os.makedirs(os.path.join(temp_dir, "blocks"))
            os.makedirs(os.path.join(temp_dir, "index"))
            yield temp_dir
        finally:
            shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_memory_blocks(self):
        """Create mock memory blocks for testing."""
        return [
            MemoryBlock(
                id="archive-1",
                text="Archive test block with #thought tag",
                tags=["#thought"],
                source_file="archive1.md",
                embedding=[0.3] * 1536
            )
        ]

    def test_archive_initialization(self, test_archive_dir):
        """Test archive storage initialization."""
        # Verify test data is correct
        assert os.path.exists(os.path.join(test_archive_dir, "blocks"))
        assert os.path.exists(os.path.join(test_archive_dir, "index"))
        
        archive = ArchiveStorage(test_archive_dir)
        
        # Verify storage is initialized correctly
        assert archive.archive_directory == Path(test_archive_dir)
        assert os.path.exists(os.path.join(test_archive_dir, "blocks"))
        assert os.path.exists(os.path.join(test_archive_dir, "index"))

    def test_archive_blocks(self, test_archive_dir, mock_memory_blocks):
        """Test archiving blocks to cold storage."""
        # Verify test data is correct
        assert len(mock_memory_blocks) == 1
        
        archive = ArchiveStorage(test_archive_dir)
        
        # Archive blocks
        archive.archive_blocks(mock_memory_blocks)
        
        # Verify block files were created
        block_path = os.path.join(test_archive_dir, "blocks", "archive-1.json")
        assert os.path.exists(block_path)
        
        # Verify block content
        with open(block_path, "r") as f:
            data = json.load(f)
            assert data["id"] == "archive-1"
            assert data["text"] == "Archive test block with #thought tag"
            assert "#thought" in data["tags"]
            assert "embedding" not in data  # Should exclude embedding to save space

    def test_update_index(self, test_archive_dir, mock_memory_blocks):
        """Test updating the archive index."""
        # First archive some blocks
        archive = ArchiveStorage(test_archive_dir)
        archive.archive_blocks(mock_memory_blocks)
        
        # Then update the index
        archive._update_index()
        
        # Verify index files were created
        latest_path = os.path.join(test_archive_dir, "index", "latest.json")
        assert os.path.exists(latest_path)
        
        # Check index content
        with open(latest_path, "r") as f:
            index = json.load(f)
            assert "metadata" in index
            assert "version" in index["metadata"]
            assert "updated_at" in index["metadata"]
            assert "blocks" in index
            assert "archive-1" in index["blocks"]
            
            # Verify block entry
            block_entry = index["blocks"]["archive-1"]
            assert block_entry["text"] == "Archive test block with #thought tag"
            assert "#thought" in block_entry["tags"]

    def test_retrieve_block(self, test_archive_dir, mock_memory_blocks):
        """Test retrieving a block from the archive."""
        # First archive a block
        archive = ArchiveStorage(test_archive_dir)
        archive.archive_blocks(mock_memory_blocks)
        
        # Then retrieve it
        retrieved = archive.retrieve_block("archive-1")
        
        # Verify retrieval
        assert retrieved is not None
        assert retrieved["id"] == "archive-1"
        assert retrieved["text"] == "Archive test block with #thought tag"
        assert "#thought" in retrieved["tags"]
        
        # Test retrieving non-existent block
        not_found = archive.retrieve_block("non-existent")
        assert not_found is None
        
    def test_archive_workflow(self, test_archive_dir, mock_memory_blocks):
        """Test archiving and retrieval workflow."""
        # Setup storage
        archive = ArchiveStorage(test_archive_dir)
        
        # Archive blocks
        archive.archive_blocks(mock_memory_blocks)
        
        # Verify index was created
        index_files = list(Path(test_archive_dir).joinpath("index").glob("*.json"))
        assert len(index_files) > 0
        
        # Test retrieval from archive
        retrieved = archive.retrieve_block(mock_memory_blocks[0].id)
        assert retrieved is not None
        assert retrieved["text"] == mock_memory_blocks[0].text
        assert "source_uri" in retrieved

    def test_index_structure(self, test_archive_dir, mock_memory_blocks):
        """Verify index file structure and contents."""
        archive = ArchiveStorage(test_archive_dir)
        
        # Archive blocks to create initial index
        archive.archive_blocks(mock_memory_blocks)
        
        # Trigger index creation
        archive._update_index()
        
        # Load latest index
        with open(Path(test_archive_dir).joinpath("index", "latest.json"), "r") as f:
            index = json.load(f)
        
        # Check structure
        assert "metadata" in index
        assert "version" in index["metadata"]
        assert "updated_at" in index["metadata"]
        assert "block_count" in index["metadata"]
        assert "blocks" in index
        
        # Verify block entries
        for block_id, block_data in index["blocks"].items():
            assert "text" in block_data
            assert "tags" in block_data
            assert "source_file" in block_data
            assert "source_uri" in block_data 