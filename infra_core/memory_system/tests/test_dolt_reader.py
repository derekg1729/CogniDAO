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
    "metadata": '{"key": "value", invalid}',  # Invalid JSON string to test error handling
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
    "tags": None,
    "metadata": None,
    # Removed links field
    "source_file": None,
    "source_uri": None,
    "confidence": None,
    "created_by": "test_runner_schema",
    "created_at": "2023-10-27T16:00:00",
    "updated_at": "2023-10-27T17:00:00",
}


# Patch the Dolt class within the module where it's used (dolt_reader)
DOLT_PATCH_TARGET = "infra_core.memory_system.dolt_reader.Dolt"


class TestDoltReader:
    @patch(DOLT_PATCH_TARGET)
    def test_read_basic_block(self, MockDolt):
        """Test reading a single block with basic fields."""
        # Configure mock Dolt instance and its sql method for Property-Schema Split
        mock_repo = MagicMock()

        # First call: memory_blocks table returns the block data
        # Second call: block_properties table returns empty list (no properties for basic test)
        mock_repo.sql.side_effect = [
            {"rows": [SAMPLE_ROW_BASIC]},  # memory_blocks query
            {"rows": []},  # block_properties query (empty for basic test)
        ]
        MockDolt.return_value = mock_repo

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
        assert block.metadata == {}  # Empty because no properties returned
        assert block.confidence is None
        assert isinstance(block.created_at, datetime)
        assert isinstance(block.updated_at, datetime)

        # Verify Dolt connection and 2 SQL queries (Property-Schema Split)
        assert MockDolt.call_count == 2  # Two Dolt instances created
        assert mock_repo.sql.call_count == 2  # Two SQL calls made

        # Check first query (memory_blocks)
        first_call_args, first_call_kwargs = mock_repo.sql.call_args_list[0]
        assert "query" in first_call_kwargs
        sql_query = first_call_kwargs["query"].upper()
        assert "SELECT" in sql_query
        assert "FROM MEMORY_BLOCKS" in sql_query
        assert "AS OF 'MAIN'" in sql_query  # Check default branch
        assert first_call_kwargs["result_format"] == "json"

        # Check second query (block_properties)
        second_call_args, second_call_kwargs = mock_repo.sql.call_args_list[1]
        assert "query" in second_call_kwargs
        sql_query2 = second_call_kwargs["query"].upper()
        assert "SELECT" in sql_query2
        assert "FROM BLOCK_PROPERTIES" in sql_query2
        assert "AS OF 'MAIN'" in sql_query2
        assert "WHERE BLOCK_ID = 'BASIC-001'" in sql_query2
        assert second_call_kwargs["result_format"] == "json"

    @patch(DOLT_PATCH_TARGET)
    def test_read_block_with_all_fields(self, MockDolt):
        """Test reading a block with all fields populated correctly."""
        # Create mock property data that will compose to the expected metadata
        mock_properties = [
            {
                "block_id": "full-002",
                "property_name": "status",
                "property_type": "text",
                "property_value_text": "pending",
                "property_value_number": None,
                "property_value_json": None,
                "is_computed": False,
                "created_at": "2023-10-27T12:00:00",
                "updated_at": "2023-10-27T12:00:00",
            },
            {
                "block_id": "full-002",
                "property_name": "priority",
                "property_type": "number",
                "property_value_text": None,
                "property_value_number": 3.0,
                "property_value_json": None,
                "is_computed": False,
                "created_at": "2023-10-27T12:00:00",
                "updated_at": "2023-10-27T12:00:00",
            },
            {
                "block_id": "full-002",
                "property_name": "assignee",
                "property_type": "text",
                "property_value_text": "agent_x",
                "property_value_number": None,
                "property_value_json": None,
                "is_computed": False,
                "created_at": "2023-10-27T12:00:00",
                "updated_at": "2023-10-27T12:00:00",
            },
        ]

        mock_repo = MagicMock()
        mock_repo.sql.side_effect = [
            {"rows": [SAMPLE_ROW_FULL]},  # memory_blocks query
            {"rows": mock_properties},  # block_properties query with the metadata
        ]
        MockDolt.return_value = mock_repo

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

    @patch(DOLT_PATCH_TARGET)
    def test_read_multiple_blocks(self, MockDolt):
        """Test reading multiple blocks."""
        # Create mock property data for the full block only (basic block has no properties)
        mock_properties_full = [
            {
                "block_id": "full-002",
                "property_name": "status",
                "property_type": "text",
                "property_value_text": "pending",
                "property_value_number": None,
                "property_value_json": None,
                "is_computed": False,
                "created_at": "2023-10-27T12:00:00",
                "updated_at": "2023-10-27T12:00:00",
            },
            {
                "block_id": "full-002",
                "property_name": "priority",
                "property_type": "number",
                "property_value_text": None,
                "property_value_number": 3.0,
                "property_value_json": None,
                "is_computed": False,
                "created_at": "2023-10-27T12:00:00",
                "updated_at": "2023-10-27T12:00:00",
            },
            {
                "block_id": "full-002",
                "property_name": "assignee",
                "property_type": "text",
                "property_value_text": "agent_x",
                "property_value_number": None,
                "property_value_json": None,
                "is_computed": False,
                "created_at": "2023-10-27T12:00:00",
                "updated_at": "2023-10-27T12:00:00",
            },
        ]

        mock_repo = MagicMock()
        # 3 calls: 1 memory_blocks + 2 block_properties (one per block)
        mock_repo.sql.side_effect = [
            {"rows": [SAMPLE_ROW_BASIC, SAMPLE_ROW_FULL]},  # memory_blocks query
            {"rows": []},  # block_properties query for basic-001 (empty)
            {"rows": mock_properties_full},  # block_properties query for full-002
        ]
        MockDolt.return_value = mock_repo

        db_path = "/fake/path"
        blocks = read_memory_blocks(db_path)

        assert len(blocks) == 2
        assert blocks[0].id == "basic-001"
        assert blocks[1].id == "full-002"

    @patch(DOLT_PATCH_TARGET)
    def test_read_with_json_decode_error(self, MockDolt, caplog):
        """Test that blocks with invalid metadata in old format are handled gracefully."""
        mock_repo = MagicMock()
        # Property-Schema Split: Need side_effect for multiple calls
        mock_repo.sql.side_effect = [
            {"rows": [SAMPLE_ROW_BASIC, SAMPLE_ROW_BAD_JSON_STRUCTURE]},  # memory_blocks query
            {"rows": []},  # block_properties query for basic-001 (empty)
            {"rows": []},  # block_properties query for bad-json-003 (empty)
        ]
        MockDolt.return_value = mock_repo

        db_path = "/fake/path"
        blocks = read_memory_blocks(db_path)

        # Both blocks should be returned since the Property-Schema Split ignores the old metadata field.
        # Invalid JSON in the legacy metadata field doesn't cause validation errors anymore.
        assert len(blocks) == 2
        assert blocks[0].id == "basic-001"
        assert blocks[1].id == "bad-json-003"
        assert blocks[1].metadata == {}  # Empty metadata since properties table is empty

    @patch(DOLT_PATCH_TARGET)
    def test_read_with_pydantic_validation_error(self, MockDolt, caplog):
        """Test handling of Pydantic validation errors for other fields (e.g., type)."""
        mock_repo = MagicMock()
        # Return one good row and one that violates schema (invalid type)
        mock_repo.sql.return_value = {"rows": [SAMPLE_ROW_BASIC, SAMPLE_ROW_BAD_SCHEMA]}
        MockDolt.return_value = mock_repo

        db_path = "/fake/path"
        with caplog.at_level(logging.ERROR):
            blocks = read_memory_blocks(db_path)

        # Should only return the valid block
        assert len(blocks) == 1
        assert blocks[0].id == "basic-001"

        # Check for the Pydantic validation error in logs
        assert "Pydantic validation failed" in caplog.text
        assert "invalid_type" in caplog.text  # Mention the invalid value
        assert "bad-schema-004" in caplog.text  # Mention the block ID

    @patch(DOLT_PATCH_TARGET)
    def test_read_empty_table(self, MockDolt):
        """Test reading from an empty table."""
        mock_repo = MagicMock()
        mock_repo.sql.return_value = {"rows": []}  # Simulate empty result set
        MockDolt.return_value = mock_repo

        db_path = "/fake/path"
        blocks = read_memory_blocks(db_path)

        assert len(blocks) == 0
        assert blocks == []
        mock_repo.sql.assert_called_once()

    @patch(DOLT_PATCH_TARGET)
    def test_read_query_specific_branch(self, MockDolt):
        """Test querying a specific branch."""
        mock_repo = MagicMock()
        # Property-Schema Split: Need side_effect for multiple calls
        mock_repo.sql.side_effect = [
            {"rows": [SAMPLE_ROW_BASIC]},  # memory_blocks query
            {"rows": []},  # block_properties query (empty)
        ]
        MockDolt.return_value = mock_repo

        db_path = "/fake/path"
        branch_name = "dev_branch"
        blocks = read_memory_blocks(db_path, branch=branch_name)

        assert len(blocks) == 1
        # Property-Schema Split: Expect 2 SQL calls now
        assert mock_repo.sql.call_count == 2

        # Check that both queries use the specified branch
        first_call_args, first_call_kwargs = mock_repo.sql.call_args_list[0]
        assert f"AS OF '{branch_name}'" in first_call_kwargs["query"]

        second_call_args, second_call_kwargs = mock_repo.sql.call_args_list[1]
        assert f"AS OF '{branch_name}'" in second_call_kwargs["query"]

    @patch(DOLT_PATCH_TARGET)
    def test_read_dolt_connection_error(self, MockDolt, caplog):
        """Test handling of errors during Dolt connection."""
        # Configure MockDolt constructor to raise an error
        MockDolt.side_effect = FileNotFoundError("Dolt repo not found at path")

        db_path = "/non/existent/path"
        with caplog.at_level(logging.ERROR):
            # Catch the specific exception we expect to be re-raised
            with pytest.raises(FileNotFoundError):
                read_memory_blocks(db_path)

        # Check for error log message
        assert f"Dolt database path not found: {db_path}" in caplog.text

    @patch(DOLT_PATCH_TARGET)
    def test_read_dolt_sql_error(self, MockDolt, caplog):
        """Test handling of errors during SQL execution."""
        mock_repo = MagicMock()
        # Configure the sql method to raise an exception
        mock_repo.sql.side_effect = Exception("SQL execution failed")
        MockDolt.return_value = mock_repo

        db_path = "/fake/path"
        with caplog.at_level(logging.ERROR):
            blocks = read_memory_blocks(db_path)

        # Function should return an empty list on SQL error
        assert blocks == []

        # Check for error log message
        assert "Failed to read from Dolt DB" in caplog.text
        assert "SQL execution failed" in caplog.text
