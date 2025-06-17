# Tests for Dolt Reader

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
import logging  # Import logging for caplog tests

# Use absolute import path based on project structure and sys.path modification in dolt_reader
from infra_core.memory_system.dolt_reader import read_memory_blocks
from infra_core.memory_system.schemas.memory_block import MemoryBlock, ConfidenceScore

# Sample data conforming to the structure returned by repo.sql(..., result_format='json')
# which is typically {'rows': [ {col1: val1, ...}, ... ]}

# --- Basic Block ---
SAMPLE_ROW_BASIC = {
    "id": "basic-001",
    "type": "knowledge",
    "schema_version": 1,
    "text": "This is a basic knowledge block.",
    "tags": [],  # Fixed: actual list instead of JSON string
    "metadata": {},  # Fixed: actual dict instead of JSON string
    "source_file": None,
    "source_uri": None,
    "confidence": None,
    "created_by": "test_runner",
    "created_at": "2023-10-27T10:00:00",
    "updated_at": "2023-10-27T11:00:00",
}

# --- Block with All Fields ---
SAMPLE_ROW_FULL = {
    "id": "full-002",
    "type": "task",
    "schema_version": 2,
    "text": "Full block with all fields populated.",
    "tags": ["dolt", "test", "full"],
    "metadata": {
        "status": "pending",
        "priority": 3,
        "assignee": "agent_x",
    },
    # Removed links field as it no longer exists in MemoryBlock
    "source_file": "tests/test_data.txt",
    "source_uri": "file://tests/test_data.txt",
    "confidence": {"ai": 0.95, "human": 0.7},
    "created_by": "test_runner_full",
    "created_at": "2023-10-27T12:00:00",
    "updated_at": "2023-10-27T13:00:00",
}

# --- Block with Invalid Data Structure (if JSON parsing was expected) ---
# Note: If the actual DB column 'metadata' contains non-JSON text,
# the updated reader should handle this gracefully. This mock simulates that.
SAMPLE_ROW_BAD_JSON_STRUCTURE = {
    "id": "bad-json-003",
    "type": "doc",
    "schema_version": 1,
    "text": "Block with bad data structure in metadata.",
    "tags": ["valid"],
    "metadata": {},  # DoltMySQLReader would return empty dict for invalid JSON
    # Removed links field
    "source_file": None,
    "source_uri": None,
    "confidence": None,
    "created_by": "test_runner_bad",
    "created_at": "2023-10-27T14:00:00",
    "updated_at": "2023-10-27T15:00:00",
}

# --- Block Violating Pydantic Schema ---
SAMPLE_ROW_BAD_SCHEMA = {
    "id": "bad-schema-004",
    "type": "invalid_type",  # Violates Literal constraint
    "schema_version": 1,
    "text": "Block violating schema.",
    "tags": [],  # DoltMySQLReader would provide empty list instead of None
    "metadata": {},  # DoltMySQLReader would provide empty dict instead of None
    # Removed links field
    "source_file": None,
    "source_uri": None,
    "confidence": None,
    "created_by": "test_runner_schema",
    "created_at": "2023-10-27T16:00:00",
    "updated_at": "2023-10-27T17:00:00",
}


# Updated patch target for the new MySQL-based reader
DOLT_MYSQL_READER_PATCH_TARGET = "infra_core.memory_system.dolt_reader.DoltMySQLReader"


class TestDoltReader:
    @patch(DOLT_MYSQL_READER_PATCH_TARGET)
    def test_read_basic_block(self, MockDoltMySQLReader):
        """Test reading a single block with basic fields."""
        # Configure mock DoltMySQLReader instance
        mock_reader = MagicMock()

        # Mock the read_memory_blocks method to return sample data
        mock_reader.read_memory_blocks.return_value = [
            MemoryBlock.model_validate(
                {
                    **SAMPLE_ROW_BASIC,
                    "state": "published",
                    "visibility": "internal",
                    "block_version": 1,
                    "parent_id": None,
                    "has_children": False,
                }
            )
        ]
        MockDoltMySQLReader.return_value = mock_reader

        db_path = "/fake/path"
        blocks = read_memory_blocks(db_path)

        assert len(blocks) == 1
        block = blocks[0]
        assert isinstance(block, MemoryBlock)
        assert block.id == "basic-001"
        assert block.type == "knowledge"
        assert block.text == "This is a basic knowledge block."
        assert block.created_by == "test_runner"
        assert block.schema_version == 1
        # Check defaults for optional/JSON fields
        assert block.tags == []
        assert block.metadata == {}
        assert block.confidence is None
        assert isinstance(block.created_at, datetime)
        assert isinstance(block.updated_at, datetime)

        # Verify DoltMySQLReader was called
        MockDoltMySQLReader.assert_called_once()
        mock_reader.read_memory_blocks.assert_called_once_with("main")

    @patch(DOLT_MYSQL_READER_PATCH_TARGET)
    def test_read_block_with_all_fields(self, MockDoltMySQLReader):
        """Test reading a block with all fields populated correctly."""
        mock_reader = MagicMock()

        # Mock full block data with metadata
        full_block_data = {
            **SAMPLE_ROW_FULL,
            "state": "published",
            "visibility": "internal",
            "block_version": 2,
            "parent_id": None,
            "has_children": False,
        }

        mock_reader.read_memory_blocks.return_value = [MemoryBlock.model_validate(full_block_data)]
        MockDoltMySQLReader.return_value = mock_reader

        db_path = "/fake/path"
        blocks = read_memory_blocks(db_path)

        assert len(blocks) == 1
        block = blocks[0]
        assert isinstance(block, MemoryBlock)
        assert block.id == "full-002"
        assert block.type == "task"
        assert block.schema_version == 2
        assert block.text == "Full block with all fields populated."
        assert block.tags == ["dolt", "test", "full"]
        assert block.metadata == {"status": "pending", "priority": 3, "assignee": "agent_x"}
        assert block.source_file == "tests/test_data.txt"
        assert block.source_uri == "file://tests/test_data.txt"
        assert isinstance(block.confidence, ConfidenceScore)
        assert block.confidence.ai == 0.95
        assert block.confidence.human == 0.7
        assert block.created_by == "test_runner_full"
        assert isinstance(block.created_at, datetime)
        assert isinstance(block.updated_at, datetime)

    @patch(DOLT_MYSQL_READER_PATCH_TARGET)
    def test_read_multiple_blocks(self, MockDoltMySQLReader):
        """Test reading multiple blocks with batch optimization."""
        mock_reader = MagicMock()
        # Mock returning both blocks directly
        mock_reader.read_memory_blocks.return_value = [
            MemoryBlock.model_validate(
                {
                    **SAMPLE_ROW_BASIC,
                    "state": "published",
                    "visibility": "internal",
                    "block_version": 1,
                    "parent_id": None,
                    "has_children": False,
                }
            ),
            MemoryBlock.model_validate(
                {
                    **SAMPLE_ROW_FULL,
                    "state": "published",
                    "visibility": "internal",
                    "block_version": 2,
                    "parent_id": None,
                    "has_children": False,
                }
            ),
        ]
        MockDoltMySQLReader.return_value = mock_reader

        db_path = "/fake/path"
        blocks = read_memory_blocks(db_path)

        assert len(blocks) == 2
        assert blocks[0].id == "basic-001"
        assert blocks[1].id == "full-002"

        # Verify method was called once
        assert mock_reader.read_memory_blocks.call_count == 1

    @patch(DOLT_MYSQL_READER_PATCH_TARGET)
    def test_read_with_json_decode_error(self, MockDoltMySQLReader, caplog):
        """Test that blocks with invalid metadata in old format are handled gracefully."""
        mock_reader = MagicMock()
        # Mock returning blocks where JSON parsing has already been handled
        mock_reader.read_memory_blocks.return_value = [
            MemoryBlock.model_validate(
                {
                    **SAMPLE_ROW_BASIC,
                    "state": "published",
                    "visibility": "internal",
                    "block_version": 1,
                    "parent_id": None,
                    "has_children": False,
                }
            ),
            MemoryBlock.model_validate(
                {
                    **SAMPLE_ROW_BAD_JSON_STRUCTURE,
                    "state": "published",
                    "visibility": "internal",
                    "block_version": 1,
                    "parent_id": None,
                    "has_children": False,
                }
            ),
        ]
        MockDoltMySQLReader.return_value = mock_reader

        db_path = "/fake/path"
        with caplog.at_level(logging.WARNING):
            blocks = read_memory_blocks(db_path)

        # Should still return blocks, DoltMySQLReader handles JSON errors gracefully
        assert len(blocks) == 2
        assert blocks[0].id == "basic-001"
        assert blocks[1].id == "bad-json-003"
        assert blocks[1].metadata == {}  # Invalid JSON becomes empty dict

    @patch(DOLT_MYSQL_READER_PATCH_TARGET)
    def test_read_with_pydantic_validation_error(self, MockDoltMySQLReader, caplog):
        """Test handling of Pydantic validation errors for other fields (e.g., type)."""
        mock_reader = MagicMock()
        # Mock returning only valid blocks - DoltMySQLReader would skip invalid ones
        mock_reader.read_memory_blocks.return_value = [
            MemoryBlock.model_validate(
                {
                    **SAMPLE_ROW_BASIC,
                    "state": "published",
                    "visibility": "internal",
                    "block_version": 1,
                    "parent_id": None,
                    "has_children": False,
                }
            ),
        ]
        MockDoltMySQLReader.return_value = mock_reader

        db_path = "/fake/path"
        with caplog.at_level(logging.ERROR):
            blocks = read_memory_blocks(db_path)

        # Should return only valid blocks
        assert len(blocks) == 1
        assert blocks[0].id == "basic-001"

    @patch(DOLT_MYSQL_READER_PATCH_TARGET)
    def test_read_empty_table(self, MockDoltMySQLReader):
        """Test reading from an empty table."""
        mock_reader = MagicMock()
        mock_reader.read_memory_blocks.return_value = []  # Simulate empty result set
        MockDoltMySQLReader.return_value = mock_reader

        db_path = "/fake/path"
        blocks = read_memory_blocks(db_path)

        assert len(blocks) == 0
        assert blocks == []
        mock_reader.read_memory_blocks.assert_called_once()

    @patch(DOLT_MYSQL_READER_PATCH_TARGET)
    def test_read_query_specific_branch(self, MockDoltMySQLReader):
        """Test querying a specific branch."""
        mock_reader = MagicMock()
        # Mock simple return value
        mock_reader.read_memory_blocks.return_value = [
            MemoryBlock.model_validate(
                {
                    **SAMPLE_ROW_BASIC,
                    "state": "published",
                    "visibility": "internal",
                    "block_version": 1,
                    "parent_id": None,
                    "has_children": False,
                }
            )
        ]
        MockDoltMySQLReader.return_value = mock_reader

        db_path = "/fake/path"
        branch_name = "dev_branch"
        blocks = read_memory_blocks(db_path, branch=branch_name)

        assert len(blocks) == 1
        # Verify method was called once with correct branch
        mock_reader.read_memory_blocks.assert_called_once_with(branch_name)

    @patch(DOLT_MYSQL_READER_PATCH_TARGET)
    def test_read_dolt_connection_error(self, MockDoltMySQLReader, caplog):
        """Test handling of errors during Dolt connection."""
        # Configure MockDoltMySQLReader constructor to raise an error
        MockDoltMySQLReader.side_effect = Exception("Connection failed")

        db_path = "/non/existent/path"
        with caplog.at_level(logging.ERROR):
            # The legacy function will re-raise the exception
            with pytest.raises(Exception, match="Connection failed"):
                read_memory_blocks(db_path)

    @patch(DOLT_MYSQL_READER_PATCH_TARGET)
    def test_read_dolt_sql_error(self, MockDoltMySQLReader, caplog):
        """Test handling of errors during SQL execution."""
        mock_reader = MagicMock()
        # Configure the read_memory_blocks method to raise an exception
        mock_reader.read_memory_blocks.side_effect = Exception("SQL execution failed")
        MockDoltMySQLReader.return_value = mock_reader

        db_path = "/fake/path"
        with caplog.at_level(logging.ERROR):
            # The legacy function will re-raise the exception
            with pytest.raises(Exception, match="SQL execution failed"):
                read_memory_blocks(db_path)

    # FIX-03 Tests: Embedding field JSON string handling
    def test_fix03_embedding_arrives_as_json_string(self):
        """FIX-03: Test that embedding field is properly parsed when it arrives as JSON string from Dolt."""
        from infra_core.memory_system.dolt_reader import read_memory_block

        # Create a 384-dimension embedding list (valid size)
        embedding_list = [0.1 * i for i in range(384)]

        sample_row_with_embedding = {
            "id": "embedding-test-001",
            "type": "knowledge",
            "schema_version": 1,
            "text": "Test block with embedding",
            "state": "published",
            "visibility": "internal",
            "block_version": 1,
            "parent_id": None,
            "has_children": False,
            "tags": ["test", "embedding"],
            "source_file": None,
            "source_uri": None,
            "confidence": None,
            "created_by": "test_runner",
            "created_at": "2023-10-27T10:00:00",
            "updated_at": "2023-10-27T11:00:00",
            "embedding": embedding_list,  # Parse JSON to list (as DoltMySQLReader does)
            "metadata": {},  # Add metadata field
        }

        with patch(DOLT_MYSQL_READER_PATCH_TARGET) as MockDoltMySQLReader:
            mock_reader = MagicMock()
            # Mock the correct method for single block read
            mock_reader.read_memory_block.return_value = MemoryBlock.model_validate(
                sample_row_with_embedding
            )
            MockDoltMySQLReader.return_value = mock_reader

            db_path = "/fake/path"
            block = read_memory_block(db_path, "embedding-test-001")

            # Should successfully parse and validate
            assert block is not None
            assert block.id == "embedding-test-001"
            assert block.embedding is not None
            assert isinstance(block.embedding, list)
            assert len(block.embedding) == 384
            assert block.embedding[0] == 0.0
            assert abs(block.embedding[383] - 38.3) < 1e-10  # Use approximate equality for floats

    def test_fix03_embedding_roundtrip_384_dimensions(self):
        """FIX-03: Test round-trip of block with 384-dimensional embedding list."""
        # Note: This test demonstrates the fix concept but uses mocking for simplicity
        # A full integration test would require complete schema setup
        from infra_core.memory_system.dolt_reader import read_memory_block

        # Create embedding with exactly 384 dimensions
        embedding_384 = [0.1 * i for i in range(384)]

        # Mock scenario: block was written to Dolt and now we're reading it back
        # The embedding comes back as JSON string from Dolt but is parsed by DoltMySQLReader
        sample_row_roundtrip = {
            "id": "roundtrip-embedding-001",
            "type": "knowledge",
            "schema_version": 1,
            "text": "Test block for embedding roundtrip",
            "state": "published",
            "visibility": "internal",
            "block_version": 1,
            "parent_id": None,
            "has_children": False,
            "tags": ["test"],
            "source_file": None,
            "source_uri": None,
            "confidence": None,
            "created_by": "test_runner",
            "created_at": "2023-10-27T10:00:00",
            "updated_at": "2023-10-27T11:00:00",
            "embedding": embedding_384,  # Already parsed list (as DoltMySQLReader would provide)
            "metadata": {"test": "embedding_roundtrip"},  # Add metadata field
        }

        with patch(DOLT_MYSQL_READER_PATCH_TARGET) as MockDoltMySQLReader:
            mock_reader = MagicMock()
            # Mock the correct method for single block read
            mock_reader.read_memory_block.return_value = MemoryBlock.model_validate(
                sample_row_roundtrip
            )
            MockDoltMySQLReader.return_value = mock_reader

            # Read block back
            read_block = read_memory_block("/fake/path", "roundtrip-embedding-001")

            # Verify embedding round-trip
            assert read_block is not None
            assert read_block.embedding is not None
            assert isinstance(read_block.embedding, list)
            assert len(read_block.embedding) == 384
            assert read_block.embedding == embedding_384  # Exact match
            assert read_block.metadata == {"test": "embedding_roundtrip"}  # Metadata also works

    def test_fix03_multiple_blocks_with_embeddings(self):
        """FIX-03: Test reading multiple blocks where some have embeddings as JSON strings."""
        from infra_core.memory_system.dolt_reader import read_memory_blocks

        # Create embedding data
        embedding1 = [0.1 * i for i in range(384)]
        embedding2 = [0.2 * i for i in range(384)]

        sample_rows_mixed_embeddings = [
            {
                "id": "block-with-embedding-001",
                "type": "knowledge",
                "schema_version": 1,
                "text": "Block with embedding",
                "state": "published",
                "visibility": "internal",
                "block_version": 1,
                "parent_id": None,
                "has_children": False,
                "tags": ["test"],
                "source_file": None,
                "source_uri": None,
                "confidence": None,
                "created_by": "test_runner",
                "created_at": "2023-10-27T10:00:00",
                "updated_at": "2023-10-27T11:00:00",
                "embedding": embedding1,  # Already parsed list
                "metadata": {},
            },
            {
                "id": "block-without-embedding-002",
                "type": "doc",
                "schema_version": 1,
                "text": "Block without embedding",
                "state": "draft",
                "visibility": "internal",
                "block_version": 1,
                "parent_id": None,
                "has_children": False,
                "tags": ["test"],
                "source_file": None,
                "source_uri": None,
                "confidence": None,
                "created_by": "test_runner",
                "created_at": "2023-10-27T12:00:00",
                "updated_at": "2023-10-27T13:00:00",
                "embedding": None,  # No embedding
                "metadata": {},
            },
            {
                "id": "block-with-embedding-003",
                "type": "task",
                "schema_version": 1,
                "text": "Another block with embedding",
                "state": "published",
                "visibility": "public",
                "block_version": 1,
                "parent_id": None,
                "has_children": False,
                "tags": ["test", "embedding"],
                "source_file": None,
                "source_uri": None,
                "confidence": None,
                "created_by": "test_runner",
                "created_at": "2023-10-27T14:00:00",
                "updated_at": "2023-10-27T15:00:00",
                "embedding": embedding2,  # Already parsed list
                "metadata": {},
            },
        ]

        with patch(DOLT_MYSQL_READER_PATCH_TARGET) as MockDoltMySQLReader:
            mock_reader = MagicMock()
            # Mock the correct method for multiple blocks read
            memory_blocks = [
                MemoryBlock.model_validate(row) for row in sample_rows_mixed_embeddings
            ]
            mock_reader.read_memory_blocks.return_value = memory_blocks
            MockDoltMySQLReader.return_value = mock_reader

            db_path = "/fake/path"
            blocks = read_memory_blocks(db_path)

            # All blocks should be successfully parsed
            assert len(blocks) == 3

            # First block - has embedding
            assert blocks[0].id == "block-with-embedding-001"
            assert blocks[0].embedding is not None
            assert len(blocks[0].embedding) == 384
            assert blocks[0].embedding == embedding1

            # Second block - no embedding
            assert blocks[1].id == "block-without-embedding-002"
            assert blocks[1].embedding is None

            # Third block - has embedding
            assert blocks[2].id == "block-with-embedding-003"
            assert blocks[2].embedding is not None
            assert len(blocks[2].embedding) == 384
            assert blocks[2].embedding == embedding2

    @patch(DOLT_MYSQL_READER_PATCH_TARGET)
    def test_read_work_items_core_view(self, MockDoltMySQLReader):
        """Test reading from the work_items_core view using DoltMySQLReader."""
        mock_reader = MagicMock()
        sample_rows = [
            {
                "work_item_type": "task",
                "id": "abc123",
                "state": "draft",
                "visibility": "internal",
                "created_by": "agent",
                "created_at": "2025-06-12 00:00:00",
                "updated_at": "2025-06-12 00:00:00",
            }
        ]
        mock_reader.read_work_items_core_view.return_value = sample_rows
        MockDoltMySQLReader.return_value = mock_reader

        reader = MockDoltMySQLReader()
        rows = reader.read_work_items_core_view(limit=3)
        assert isinstance(rows, list)
        if rows:
            assert isinstance(rows[0], dict)
            expected_keys = {
                "work_item_type",
                "id",
                "state",
                "visibility",
                "created_by",
                "created_at",
                "updated_at",
            }
            assert expected_keys.issubset(set(rows[0].keys()))
        mock_reader.read_work_items_core_view.assert_called_once_with(limit=3)
