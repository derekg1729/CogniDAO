"""
Tests for the CogniMemoryClient component.
"""

import os
import tempfile
import shutil
import pytest
from unittest.mock import patch, MagicMock

from infra_core.memory.schema import MemoryBlock, QueryResult
from infra_core.memory.memory_client import CogniMemoryClient
from infra_core.memory.memory_tool import memory_tool


class TestCogniMemoryClient:
    """Tests for the CogniMemoryClient class."""

    @pytest.fixture
    def test_directories(self):
        """Create temporary directories for testing."""
        chroma_dir = tempfile.mkdtemp()
        archive_dir = tempfile.mkdtemp()
        try:
            yield {"chroma": chroma_dir, "archive": archive_dir}
        finally:
            shutil.rmtree(chroma_dir)
            shutil.rmtree(archive_dir)

    @pytest.fixture
    def mock_memory_blocks(self):
        """Create mock memory blocks for testing."""
        return [
            MemoryBlock(
                id="client-test-1",
                text="Memory client test block #thought",
                tags=["#thought"],
                source_file="client_test.md",
            ),
            MemoryBlock(
                id="client-test-2",
                text="Another memory client test #broadcast",
                tags=["#broadcast"],
                source_file="client_test.md",
            )
        ]

    @patch("chromadb.PersistentClient")
    def test_client_initialization(self, mock_chroma_client, test_directories):
        """Test client initialization."""
        # Verify test data is correct
        assert os.path.exists(test_directories["chroma"])
        assert os.path.exists(test_directories["archive"])
        
        # Configure mock
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_chroma_client.return_value = mock_client
        mock_client.get_collection.side_effect = ValueError("Collection not found")
        mock_client.create_collection.return_value = mock_collection
        
        # Test client initialization
        client = CogniMemoryClient(
            chroma_path=test_directories["chroma"],
            archive_path=test_directories["archive"]
        )
        
        # Verify client is initialized correctly
        assert client.storage is not None
        assert client.chroma_path == test_directories["chroma"]
        assert client.archive_path == test_directories["archive"]

    @patch("chromadb.PersistentClient")
    def test_save_blocks(self, mock_chroma_client, test_directories, mock_memory_blocks):
        """Test saving blocks through the client."""
        # Verify test data is correct
        assert len(mock_memory_blocks) == 2
        
        # Configure mock
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_chroma_client.return_value = mock_client
        mock_client.get_collection.side_effect = ValueError("Collection not found")
        mock_client.create_collection.return_value = mock_collection
        
        # Create client
        client = CogniMemoryClient(
            chroma_path=test_directories["chroma"],
            archive_path=test_directories["archive"]
        )
        
        # Replace storage components with mocks
        client.storage.chroma.client = mock_client
        client.storage.chroma.collection = mock_collection
        
        # Test saving blocks
        client.save_blocks(mock_memory_blocks)
        
        # Verify blocks were saved
        mock_collection.add.assert_called_once()
        args, kwargs = mock_collection.add.call_args
        assert len(kwargs["ids"]) == 2
        assert kwargs["ids"] == ["client-test-1", "client-test-2"]

    @patch("chromadb.PersistentClient")
    def test_query(self, mock_chroma_client, test_directories):
        """Test querying through the client."""
        # Configure mock
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_chroma_client.return_value = mock_client
        mock_client.get_collection.side_effect = ValueError("Collection not found")
        mock_client.create_collection.return_value = mock_collection
        
        # Configure mock query response
        mock_query_response = {
            "ids": [["query-test-1"]],
            "documents": [["Query test result"]],
            "metadatas": [[{"tags": "#thought", "source": "query_test.md"}]],
            "distances": [[0.1]]
        }
        mock_collection.query.return_value = mock_query_response
        
        # Create client
        client = CogniMemoryClient(
            chroma_path=test_directories["chroma"],
            archive_path=test_directories["archive"]
        )
        
        # Replace storage components with mocks
        client.storage.chroma.client = mock_client
        client.storage.chroma.collection = mock_collection
        
        # Test query
        result = client.query("test query", n_results=1)
        
        # Verify query was made correctly
        mock_collection.query.assert_called_once()
        args, kwargs = mock_collection.query.call_args
        assert kwargs["query_texts"] == ["test query"]
        assert kwargs["n_results"] == 1
        
        # Verify result
        assert isinstance(result, QueryResult)
        assert result.query_text == "test query"
        assert len(result.blocks) == 1
        assert result.blocks[0].text == "Query test result"
        assert result.blocks[0].tags == ["#thought"]
        assert result.blocks[0].source_file == "query_test.md"

    @patch("chromadb.PersistentClient")
    def test_archive_blocks(self, mock_chroma_client, test_directories):
        """Test archiving blocks through the client."""
        # Configure mock
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_chroma_client.return_value = mock_client
        mock_client.get_collection.side_effect = ValueError("Collection not found")
        mock_client.create_collection.return_value = mock_collection
        
        # Configure mock get response for retrieve before archive
        mock_get_response = {
            "ids": ["archive-test-1", "archive-test-2"],
            "documents": ["Archive test block 1", "Archive test block 2"],
            "metadatas": [
                {"tags": "#thought", "source": "archive_test.md"},
                {"tags": "#broadcast", "source": "archive_test.md"}
            ]
        }
        mock_collection.get.return_value = mock_get_response
        
        # Create client
        client = CogniMemoryClient(
            chroma_path=test_directories["chroma"],
            archive_path=test_directories["archive"]
        )
        
        # Replace storage components with mocks
        client.storage.chroma.client = mock_client
        client.storage.chroma.collection = mock_collection
        client.storage.archive = MagicMock()
        
        # Test archiving blocks
        block_ids = ["archive-test-1", "archive-test-2"]
        client.archive_blocks(block_ids)
        
        # Verify blocks were archived
        client.storage.archive.archive_blocks.assert_called_once()
        mock_collection.delete.assert_called_once_with(ids=block_ids)

    @patch("infra_core.memory.memory_tool.CogniMemoryClient")
    def test_memory_tool_integration(self, mock_memory_client, test_directories):
        """Test the memory_tool integration."""
        # Configure mocks
        client_instance = MagicMock()
        mock_memory_client.return_value = client_instance
        
        # Configure mock query response
        query_result = QueryResult(
            query_text="tool test",
            blocks=[
                MemoryBlock(
                    id="tool-test-1",
                    text="Memory tool test result",
                    tags=["#thought"],
                    source_file="tool_test.md"
                )
            ],
            total_results=1
        )
        client_instance.query.return_value = query_result
        
        # Call memory tool
        result = memory_tool(
            input_text="tool test",
            n_results=1,
            chroma_path=test_directories["chroma"],
            archive_path=test_directories["archive"]
        )
        
        # Verify client was initialized correctly
        mock_memory_client.assert_called_once_with(
            chroma_path=test_directories["chroma"],
            archive_path=test_directories["archive"],
            collection_name="cogni-memory"
        )
        
        # Verify query was called correctly
        client_instance.query.assert_called_once_with(
            query_text="tool test",
            n_results=1,
            include_archived=False,
            filter_tags=None
        )
        
        # Verify result structure
        assert isinstance(result, dict)
        assert "query" in result
        assert "results" in result
        assert "result_count" in result
        assert result["query"] == "tool test"
        assert len(result["results"]) == 1
        assert result["result_count"] == 1

    def test_schema_validation(self):
        """Test schema validation through Pydantic models."""
        # Test with valid block
        valid_block = MemoryBlock(
            text="Valid block",
            tags=["#thought"],
            source_file="test.md"
        )
        
        # This should work and produce valid JSON
        valid_json = valid_block.model_dump_json()
        assert isinstance(valid_json, str)
        
        # Test with missing required field
        # Pydantic should raise a validation error for missing 'text'
        with pytest.raises(Exception):
            # Creating a block without the required 'text' field should raise an exception
            MemoryBlock(
                tags=["#thought"],
                source_file="test.md"
            ) 