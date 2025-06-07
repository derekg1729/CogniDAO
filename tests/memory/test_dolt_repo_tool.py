"""
Tests for the dolt_commit tool.

This module tests the dolt_commit tool's functionality for manually
committing working set changes to Dolt when auto_commit=False.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from infra_core.memory_system.tools.agent_facing.dolt_repo_tool import (
    dolt_repo_tool,
    DoltCommitInput,
)
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

# Mock data paths
MOCK_CHROMA_PATH = "/mock/chroma/path"
MOCK_COLLECTION = "mock_collection"


@pytest.fixture
def mock_memory_bank():
    """Create a mock StructuredMemoryBank with mocked DoltMySQLWriter."""
    with (
        patch("infra_core.memory_system.structured_memory_bank.LlamaMemory"),
        patch(
            "infra_core.memory_system.structured_memory_bank.DoltMySQLWriter"
        ) as mock_writer_class,
        patch("infra_core.memory_system.structured_memory_bank.DoltMySQLReader"),
    ):
        # Create mock writer instance
        mock_writer = MagicMock()
        mock_writer_class.return_value = mock_writer

        # Create mock config
        mock_config = DoltConnectionConfig(
            host="localhost", port=3306, user="root", password="", database="test_db"
        )

        # Create memory bank instance
        memory_bank = StructuredMemoryBank(
            chroma_path=MOCK_CHROMA_PATH,
            chroma_collection=MOCK_COLLECTION,
            dolt_connection_config=mock_config,
            auto_commit=False,  # Default to False for commit tool testing
        )

        yield memory_bank, mock_writer


class TestDoltRepoTool:
    """Test class for dolt_commit tool functionality."""

    def test_successful_commit_with_default_tables(self, mock_memory_bank):
        """Test successful commit operation with default tables."""
        memory_bank, mock_writer = mock_memory_bank

        # Mock successful commit
        expected_hash = "abc123def456"
        mock_writer.commit_changes.return_value = (True, expected_hash)

        # Prepare input
        input_data = DoltCommitInput(commit_message="Test commit message")

        # Execute tool
        result = dolt_repo_tool(input_data, memory_bank)

        # Verify results
        assert result.success is True
        assert result.commit_hash == expected_hash
        assert "Successfully committed changes" in result.message
        assert result.tables_committed == ["memory_blocks", "block_properties", "block_links"]
        assert result.error is None
        assert isinstance(result.timestamp, datetime)

        # Verify mock calls
        mock_writer.commit_changes.assert_called_once_with(
            commit_msg="Test commit message",
            tables=["memory_blocks", "block_properties", "block_links"],
        )

    def test_successful_commit_with_custom_tables(self, mock_memory_bank):
        """Test successful commit operation with custom table list."""
        memory_bank, mock_writer = mock_memory_bank

        # Mock successful commit
        expected_hash = "custom123hash"
        mock_writer.commit_changes.return_value = (True, expected_hash)

        # Prepare input with custom tables
        custom_tables = ["memory_blocks", "block_links"]
        input_data = DoltCommitInput(commit_message="Custom table commit", tables=custom_tables)

        # Execute tool
        result = dolt_repo_tool(input_data, memory_bank)

        # Verify results
        assert result.success is True
        assert result.commit_hash == expected_hash
        assert result.tables_committed == custom_tables

        # Verify mock calls
        mock_writer.commit_changes.assert_called_once_with(
            commit_msg="Custom table commit", tables=custom_tables
        )

    def test_successful_commit_with_author(self, mock_memory_bank):
        """Test successful commit operation with author attribution."""
        memory_bank, mock_writer = mock_memory_bank

        # Mock successful commit
        expected_hash = "author123hash"
        mock_writer.commit_changes.return_value = (True, expected_hash)

        # Prepare input with author
        input_data = DoltCommitInput(commit_message="Feature implementation", author="TestAgent")

        # Execute tool
        result = dolt_repo_tool(input_data, memory_bank)

        # Verify results
        assert result.success is True
        assert result.commit_hash == expected_hash

        # Verify commit message includes author
        expected_commit_msg = "Feature implementation\n\nAuthor: TestAgent"
        mock_writer.commit_changes.assert_called_once_with(
            commit_msg=expected_commit_msg,
            tables=["memory_blocks", "block_properties", "block_links"],
        )

    def test_failed_commit_operation(self, mock_memory_bank):
        """Test failed commit operation."""
        memory_bank, mock_writer = mock_memory_bank

        # Mock failed commit
        mock_writer.commit_changes.return_value = (False, None)

        # Prepare input
        input_data = DoltCommitInput(commit_message="This commit will fail")

        # Execute tool
        result = dolt_repo_tool(input_data, memory_bank)

        # Verify results
        assert result.success is False
        assert result.commit_hash is None
        assert "Dolt commit operation failed" in result.message
        assert result.error == "Dolt commit operation failed - no commit hash returned"
        assert result.tables_committed == ["memory_blocks", "block_properties", "block_links"]

    def test_commit_with_exception(self, mock_memory_bank):
        """Test commit operation when an exception occurs."""
        memory_bank, mock_writer = mock_memory_bank

        # Mock exception during commit
        mock_writer.commit_changes.side_effect = Exception("Database connection failed")

        # Prepare input
        input_data = DoltCommitInput(commit_message="This will cause an exception")

        # Execute tool
        result = dolt_repo_tool(input_data, memory_bank)

        # Verify results
        assert result.success is False
        assert result.commit_hash is None
        assert "Commit failed: Database connection failed" in result.message
        assert "Exception during dolt_commit" in result.error
        assert result.tables_committed is None

    def test_input_validation_empty_message(self):
        """Test input validation with empty commit message."""
        with pytest.raises(ValueError):
            DoltCommitInput(commit_message="")

    def test_input_validation_long_message(self):
        """Test input validation with overly long commit message."""
        long_message = "x" * 501  # Exceeds max_length of 500
        with pytest.raises(ValueError):
            DoltCommitInput(commit_message=long_message)

    def test_input_validation_long_author(self):
        """Test input validation with overly long author name."""
        long_author = "x" * 101  # Exceeds max_length of 100
        with pytest.raises(ValueError):
            DoltCommitInput(commit_message="Valid message", author=long_author)

    def test_input_validation_valid_max_lengths(self):
        """Test input validation with maximum allowed lengths."""
        # Test maximum valid lengths
        max_message = "x" * 500
        max_author = "x" * 100

        # Should not raise an exception
        input_data = DoltCommitInput(
            commit_message=max_message, author=max_author, tables=["memory_blocks"]
        )

        assert input_data.commit_message == max_message
        assert input_data.author == max_author
        assert input_data.tables == ["memory_blocks"]

    def test_output_model_serialization(self, mock_memory_bank):
        """Test that DoltCommitOutput can be properly serialized."""
        memory_bank, mock_writer = mock_memory_bank

        # Mock successful commit
        mock_writer.commit_changes.return_value = (True, "test_hash_123")

        # Prepare input
        input_data = DoltCommitInput(
            commit_message="Serialization test", tables=["memory_blocks"], author="TestAgent"
        )

        # Execute tool
        result = dolt_repo_tool(input_data, memory_bank)

        # Test serialization
        serialized = result.model_dump(mode="json")

        # Verify all fields are present and properly typed
        assert isinstance(serialized["success"], bool)
        assert isinstance(serialized["commit_hash"], str)
        assert isinstance(serialized["message"], str)
        assert isinstance(serialized["tables_committed"], list)
        assert serialized["error"] is None
        assert isinstance(serialized["timestamp"], str)  # datetime becomes string in JSON

    def test_empty_tables_list_uses_defaults(self, mock_memory_bank):
        """Test that an empty tables list uses default tables."""
        memory_bank, mock_writer = mock_memory_bank

        # Mock successful commit
        mock_writer.commit_changes.return_value = (True, "empty_list_hash")

        # Prepare input with empty tables list
        input_data = DoltCommitInput(
            commit_message="Empty tables test",
            tables=[],  # Empty list should use defaults
        )

        # Execute tool
        result = dolt_repo_tool(input_data, memory_bank)

        # Verify results - empty list should be passed through, not replaced with defaults
        assert result.success is True
        assert result.tables_committed == []

        # Verify mock calls - empty list should be passed to commit_changes
        mock_writer.commit_changes.assert_called_once_with(
            commit_msg="Empty tables test", tables=[]
        )
