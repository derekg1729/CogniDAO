"""
Tests to document and verify the vector-only behavior of save_blocks() and query() methods.

These tests demonstrate that these methods operate exclusively on the vector database
and do not perform any file I/O operations on markdown files.
"""

import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from legacy_logseq.memory.memory_client import CogniMemoryClient
from legacy_logseq.memory.schema import MemoryBlock


@pytest.fixture
def test_directories():
    """Create temporary directories for testing."""
    with tempfile.TemporaryDirectory() as chroma_dir, tempfile.TemporaryDirectory() as archive_dir:
        yield {"chroma": chroma_dir, "archive": archive_dir}


@pytest.fixture
def mock_memory_blocks():
    """Create test memory blocks."""
    return [
        MemoryBlock(
            id="vector-test-1",
            text="This is a vector test block",
            tags=["#thought"],
            source_file="test_file.md",
        ),
        MemoryBlock(
            id="vector-test-2",
            text="This is another vector test block",
            tags=["#broadcast"],
            source_file="test_file.md",
        ),
    ]


class TestVectorOnlyBehavior:
    """Tests to document and verify vector-only behavior."""

    @patch("chromadb.PersistentClient")
    def test_save_blocks_does_not_affect_files(
        self, mock_chroma_client, test_directories, mock_memory_blocks
    ):
        """
        Test that save_blocks() only saves to the vector database and does not modify any files.

        This test demonstrates that save_blocks() is a vector-only operation that:
        1. Stores data in ChromaDB for semantic search
        2. Does not write to or modify any markdown files
        3. Is not directly visible to users without querying
        """
        # Configure mock
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_chroma_client.return_value = mock_client
        mock_client.get_collection.side_effect = ValueError("Collection not found")
        mock_client.create_collection.return_value = mock_collection

        # Create client
        client = CogniMemoryClient(
            chroma_path=test_directories["chroma"], archive_path=test_directories["archive"]
        )

        # Replace storage components with mocks
        client.storage.chroma.client = mock_client
        client.storage.chroma.collection = mock_collection

        # Create a test markdown file
        test_file_path = os.path.join(test_directories["chroma"], "test_file.md")
        original_content = "# Test File\n\nThis is original content."
        with open(test_file_path, "w", encoding="utf-8") as f:
            f.write(original_content)

        # Save blocks
        client.save_blocks(mock_memory_blocks)

        # Verify blocks were saved to ChromaDB
        mock_collection.add.assert_called_once()
        args, kwargs = mock_collection.add.call_args
        assert len(kwargs["ids"]) == 2

        # Verify the markdown file was NOT modified
        with open(test_file_path, "r", encoding="utf-8") as f:
            content_after_save = f.read()

        assert content_after_save == original_content, (
            "File content should remain unchanged after save_blocks() operation"
        )

    @patch("chromadb.PersistentClient")
    def test_query_does_not_scan_files(self, mock_chroma_client, test_directories):
        """
        Test that query() only searches the vector database and does not scan any files.

        This test demonstrates that query() is a vector-only operation that:
        1. Searches through vectors stored in ChromaDB
        2. Does not read or scan any markdown files
        3. Results depend solely on what has been previously embedded
        """
        # Configure mock
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_chroma_client.return_value = mock_client
        mock_client.get_collection.side_effect = ValueError("Collection not found")
        mock_client.create_collection.return_value = mock_collection

        # Configure mock query response
        mock_query_response = {
            "ids": [["vector-test-1"]],
            "documents": [["This is a vector test block"]],
            "metadatas": [[{"tags": "#thought", "source": "test_file.md"}]],
            "distances": [[0.1]],
        }
        mock_collection.query.return_value = mock_query_response

        # Create client
        client = CogniMemoryClient(
            chroma_path=test_directories["chroma"], archive_path=test_directories["archive"]
        )

        # Replace storage components with mocks
        client.storage.chroma.client = mock_client
        client.storage.chroma.collection = mock_collection

        # Create a test markdown file that ChromaDB doesn't know about
        new_file_path = os.path.join(test_directories["chroma"], "new_file.md")
        with open(new_file_path, "w", encoding="utf-8") as f:
            f.write(
                "# New File\n\n- This is a new thought block #thought\n- This would match our query"
            )

        # Test query
        result = client.query("test query", n_results=5)

        # Verify query was made against ChromaDB only
        mock_collection.query.assert_called_once()

        # Verify the new file was not scanned (only getting mocked results)
        assert len(result.blocks) == 1
        assert result.blocks[0].text == "This is a vector test block"
        assert "new_file.md" not in [block.source_file for block in result.blocks]

    def test_vector_operations_vs_file_operations(self, test_directories):
        """
        Demonstrate the separation between vector operations and file operations.

        This test shows the clear distinction between:
        1. Vector-based operations (save_blocks, query) that operate on ChromaDB
        2. File-based operations (scan_logseq, get_page, write_page) that operate on markdown files
        """
        # Create client with real storage for demonstration
        client = CogniMemoryClient(
            chroma_path=test_directories["chroma"], archive_path=test_directories["archive"]
        )

        # Create a test file
        test_dir = os.path.join(test_directories["chroma"], "logseq")
        os.makedirs(test_dir, exist_ok=True)
        test_file_path = os.path.join(test_dir, "test_file.md")

        # Write content to the file using write_page (file operation)
        file_content = """# Test File
        
- This is a thought block #thought
- This is a broadcast block #broadcast
"""
        client.write_page(test_file_path, file_content)

        # Check that the file exists and contains the content
        assert os.path.exists(test_file_path)
        with open(test_file_path, "r", encoding="utf-8") as f:
            assert f.read() == file_content

        # Scan logseq directory for blocks (file operation)
        blocks = client.scan_logseq(test_dir)

        # Check that blocks were found in the file
        assert len(blocks) >= 2
        assert any("#thought" in block.tags for block in blocks)

        # At this point, blocks are found in files but NOT in the vector database
        # Verify this by querying (vector operation)
        query_result = client.query("thought", n_results=5)

        # The query should return no results because we haven't saved blocks to the vector database
        assert len(query_result.blocks) == 0

        # Now save blocks to vector database (vector operation)
        client.save_blocks(blocks)

        # Query again to verify blocks are now in the vector database
        query_result = client.query("thought", n_results=5)

        # Now the query should return results
        assert len(query_result.blocks) > 0

        # Modify the file content (doesn't affect vector database)
        modified_content = """# Modified Test File
        
- This is a modified thought block #thought
- This is a new block #new
"""
        client.write_page(test_file_path, modified_content)

        # Query again - results should still reflect the original content
        query_result = client.query("thought", n_results=5)
        assert len(query_result.blocks) > 0

        # None of the results should contain "modified" since the vector DB hasn't been updated
        assert all("modified" not in block.text.lower() for block in query_result.blocks)

        # This test demonstrates that:
        # 1. File operations (write_page, scan_logseq) affect/read files but not the vector database
        # 2. Vector operations (save_blocks, query) operate on the vector database but not files
        # 3. Changes to files don't automatically update the vector database
        # 4. To keep the vector database in sync with files, you need to explicitly index or save blocks
