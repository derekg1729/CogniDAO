"""
Tests for the CogniMemoryClient component.
"""

import os
import tempfile
import shutil
import pytest


# Placeholder for actual imports once modules are created
# from infra_core.memory.schema import MemoryBlock, MemoryQuery, MemoryQueryResult
# from infra_core.memory.storage import ChromaStorage, ArchiveStorage
# from infra_core.memory.query import MemoryQuery as MemoryQueryInterface
# from infra_core.memory.memory_tool import memory_tool


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
        # Will be replaced with actual MemoryBlock objects once schema is implemented
        # return [
        #     MemoryBlock(
        #         id="client-test-1",
        #         text="Memory client test block #thought",
        #         tags=["#thought"],
        #         source_file="client_test.md",
        #     ),
        #     MemoryBlock(
        #         id="client-test-2",
        #         text="Another memory client test #broadcast",
        #         tags=["#broadcast"],
        #         source_file="client_test.md",
        #     )
        # ]
        # Mock version until schema is implemented
        return [
            {
                "id": "client-test-1",
                "text": "Memory client test block #thought",
                "tags": ["#thought"],
                "source_file": "client_test.md",
            },
            {
                "id": "client-test-2",
                "text": "Another memory client test #broadcast",
                "tags": ["#broadcast"],
                "source_file": "client_test.md",
            }
        ]

    def test_client_initialization(self, test_directories):
        """Test client initialization."""
        # Verify test data is correct before skipping
        assert os.path.exists(test_directories["chroma"])
        assert os.path.exists(test_directories["archive"])
        
        # Skip test until client is implemented
        pytest.skip("CogniMemoryClient not yet implemented")
        
        # Code to uncomment when client is implemented:
        # client = CogniMemoryClient(
        #     chroma_path=test_directories["chroma"],
        #     archive_path=test_directories["archive"]
        # )
        # 
        # # Verify client is initialized correctly
        # assert client.chroma_storage is not None
        # assert client.archive_storage is not None
        # assert isinstance(client.query_interface, MemoryQueryInterface)

    def test_save_blocks(self, test_directories, mock_memory_blocks):
        """Test saving blocks through the client."""
        # Verify test data is correct before skipping
        assert len(mock_memory_blocks) == 2
        
        # Skip test until client is implemented
        pytest.skip("CogniMemoryClient not yet implemented")
        
        # Code to uncomment when client is implemented:
        # with patch("infra_core.memory.embedder.OpenAIEmbedder") as mock_embedder:
        #     # Configure mock embedder
        #     embedder_instance = MagicMock()
        #     mock_embedder.return_value = embedder_instance
        #     embedder_instance.embed_blocks.return_value = mock_memory_blocks
        #     
        #     # Create client with mocked components
        #     client = CogniMemoryClient(
        #         chroma_path=test_directories["chroma"],
        #         archive_path=test_directories["archive"]
        #     )
        #     
        #     # Replace storage components with mocks
        #     client.chroma_storage = MagicMock()
        #     
        #     # Test saving blocks
        #     client.save_blocks(mock_memory_blocks)
        #     
        #     # Verify blocks were embedded and saved
        #     embedder_instance.embed_blocks.assert_called_once()
        #     client.chroma_storage.add_blocks.assert_called_once()

    def test_query(self, test_directories):
        """Test querying through the client."""
        # Skip test until client is implemented
        pytest.skip("CogniMemoryClient not yet implemented")
        
        # Code to uncomment when client is implemented:
        # # Create mock query result
        # mock_result = MemoryQueryResult(
        #     query="test query",
        #     blocks=[
        #         MemoryBlock(
        #             id="query-test-1",
        #             text="Query test result",
        #             tags=["#thought"],
        #             source_file="query_test.md"
        #         )
        #     ],
        #     distances=[0.1]
        # )
        # 
        # # Create client with mocked components
        # client = CogniMemoryClient(
        #     chroma_path=test_directories["chroma"],
        #     archive_path=test_directories["archive"]
        # )
        # 
        # # Replace query interface with mock
        # client.query_interface = MagicMock()
        # client.query_interface.search.return_value = mock_result
        # 
        # # Test query
        # result = client.query("test query", n_results=1)
        # 
        # # Verify query was made correctly
        # client.query_interface.search.assert_called_once()
        # args, kwargs = client.query_interface.search.call_args
        # assert kwargs["query_text"] == "test query"
        # assert kwargs["n_results"] == 1
        # 
        # # Verify result
        # assert result == mock_result
        # assert len(result.blocks) == 1
        # assert result.blocks[0].text == "Query test result"

    def test_archive_blocks(self, test_directories, mock_memory_blocks):
        """Test archiving blocks through the client."""
        # Skip test until client is implemented
        pytest.skip("CogniMemoryClient not yet implemented")
        
        # Code to uncomment when client is implemented:
        # # Create client with mocked components
        # client = CogniMemoryClient(
        #     chroma_path=test_directories["chroma"],
        #     archive_path=test_directories["archive"]
        # )
        # 
        # # Replace storage components with mocks
        # client.archive_storage = MagicMock()
        # 
        # # Test archiving blocks
        # client.archive_blocks(mock_memory_blocks)
        # 
        # # Verify blocks were archived
        # client.archive_storage.archive_blocks.assert_called_once_with(mock_memory_blocks)

    def test_memory_tool_integration(self, test_directories):
        """Test the memory_tool integration."""
        # Skip test until memory_tool is implemented
        pytest.skip("memory_tool not yet implemented")
        
        # Code to uncomment when memory_tool is implemented:
        # with patch("infra_core.memory.query.search_memory") as mock_search:
        #     # Configure mock response
        #     mock_search.return_value = [
        #         {
        #             "id": "tool-test-1",
        #             "text": "Memory tool test result",
        #             "tags": ["#thought"],
        #             "source_file": "tool_test.md"
        #         }
        #     ]
        #     
        #     # Call memory tool
        #     result = memory_tool(
        #         input_text="tool test",
        #         n_results=1,
        #         chroma_path=test_directories["chroma"]
        #     )
        #     
        #     # Verify search was called correctly
        #     mock_search.assert_called_once()
        #     assert mock_search.call_args[1]["query"] == "tool test"
        #     assert mock_search.call_args[1]["n_results"] == 1
        #     
        #     # Verify result structure
        #     assert isinstance(result, dict)
        #     assert "query" in result
        #     assert "results" in result
        #     assert "result_count" in result
        #     assert result["query"] == "tool test"
        #     assert len(result["results"]) == 1
        #     assert result["result_count"] == 1

    def test_schema_validation(self):
        """Test schema validation through Pydantic models."""
        # Skip test until schema is implemented
        pytest.skip("Schema not yet implemented")
        
        # Code to uncomment when schema is implemented:
        # try:
        #     # Valid block should work
        #     valid_block = MemoryBlock(
        #         text="Valid block",
        #         tags=["#thought"],
        #         source_file="test.md"
        #     )
        #     
        #     # This should work and produce valid JSON
        #     valid_json = valid_block.json()
        #     assert isinstance(valid_json, str)
        #     
        #     # Test with missing required field
        #     # Pydantic should raise a validation error for missing 'text'
        #     try:
        #         invalid_block = MemoryBlock(
        #             tags=["#thought"],
        #             source_file="test.md"
        #         )
        #         assert False, "Should have raised validation error"
        #     except Exception:
        #         # Expected to fail validation
        #         pass
        # except Exception as e:
        #     assert False, f"Schema validation test failed: {e}" 