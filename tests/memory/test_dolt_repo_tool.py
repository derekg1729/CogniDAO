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
    dolt_branch_tool,
    DoltBranchInput,
    DoltListBranchesInput,
    dolt_list_branches_tool,
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
        """Test that an empty tables list is passed through as-is (not replaced with defaults)."""
        memory_bank, mock_writer = mock_memory_bank

        # Mock successful commit
        mock_writer.commit_changes.return_value = (True, "empty_list_hash")

        # Prepare input with empty tables list
        input_data = DoltCommitInput(
            commit_message="Empty tables test",
            tables=[],  # Empty list should be passed through as-is
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


class TestDoltBranchTool:
    """Test class for dolt_branch tool functionality."""

    def test_successful_branch_creation_basic(self, mock_memory_bank):
        """Test successful branch creation with basic parameters."""
        memory_bank, mock_writer = mock_memory_bank

        # Mock successful branch creation
        mock_writer.create_branch.return_value = (
            True,
            "Branch 'feature-branch' created successfully",
        )

        # Prepare input
        input_data = DoltBranchInput(branch_name="feature-branch")

        # Execute tool
        result = dolt_branch_tool(input_data, memory_bank)

        # Verify results
        assert result.success is True
        assert result.branch_name == "feature-branch"
        assert "Branch 'feature-branch' created successfully" in result.message
        assert result.start_point is None
        assert result.force is False
        assert result.error is None
        assert isinstance(result.timestamp, datetime)

        # Verify mock calls
        mock_writer.create_branch.assert_called_once_with(
            branch_name="feature-branch",
            start_point=None,
            force=False,
        )

    def test_successful_branch_creation_with_start_point(self, mock_memory_bank):
        """Test successful branch creation with start point."""
        memory_bank, mock_writer = mock_memory_bank

        # Mock successful branch creation
        mock_writer.create_branch.return_value = (
            True,
            "Branch 'feature-from-main' created from 'main'",
        )

        # Prepare input with start point
        input_data = DoltBranchInput(branch_name="feature-from-main", start_point="main")

        # Execute tool
        result = dolt_branch_tool(input_data, memory_bank)

        # Verify results
        assert result.success is True
        assert result.branch_name == "feature-from-main"
        assert result.start_point == "main"
        assert result.force is False

        # Verify mock calls
        mock_writer.create_branch.assert_called_once_with(
            branch_name="feature-from-main",
            start_point="main",
            force=False,
        )

    def test_successful_branch_creation_with_force(self, mock_memory_bank):
        """Test successful branch creation with force flag."""
        memory_bank, mock_writer = mock_memory_bank

        # Mock successful branch creation
        mock_writer.create_branch.return_value = (True, "Branch 'existing-branch' force created")

        # Prepare input with force
        input_data = DoltBranchInput(branch_name="existing-branch", force=True)

        # Execute tool
        result = dolt_branch_tool(input_data, memory_bank)

        # Verify results
        assert result.success is True
        assert result.force is True

        # Verify mock calls
        mock_writer.create_branch.assert_called_once_with(
            branch_name="existing-branch",
            start_point=None,
            force=True,
        )

    def test_failed_branch_creation(self, mock_memory_bank):
        """Test failed branch creation operation."""
        memory_bank, mock_writer = mock_memory_bank

        # Mock failed branch creation
        mock_writer.create_branch.return_value = (False, "Branch already exists")

        # Prepare input
        input_data = DoltBranchInput(branch_name="duplicate-branch")

        # Execute tool
        result = dolt_branch_tool(input_data, memory_bank)

        # Verify results
        assert result.success is False
        assert result.branch_name == "duplicate-branch"
        assert "Branch creation failed" in result.message
        assert result.error == "Branch already exists"

    def test_branch_creation_with_exception(self, mock_memory_bank):
        """Test branch creation when an exception occurs."""
        memory_bank, mock_writer = mock_memory_bank

        # Mock exception during branch creation
        mock_writer.create_branch.side_effect = Exception("Database connection failed")

        # Prepare input
        input_data = DoltBranchInput(branch_name="exception-branch")

        # Execute tool
        result = dolt_branch_tool(input_data, memory_bank)

        # Verify results
        assert result.success is False
        assert result.branch_name == "exception-branch"
        assert "Branch creation failed due to exception" in result.message
        assert "Exception during branch creation" in result.error

    def test_branch_input_validation_empty_name(self):
        """Test input validation with empty branch name."""
        with pytest.raises(ValueError):
            DoltBranchInput(branch_name="")

    def test_branch_input_validation_long_name(self):
        """Test input validation with overly long branch name."""
        long_name = "x" * 101  # Exceeds max_length of 100
        with pytest.raises(ValueError):
            DoltBranchInput(branch_name=long_name)

    def test_branch_input_validation_valid_max_lengths(self):
        """Test input validation with maximum allowed lengths."""
        # Test maximum valid lengths
        max_name = "x" * 100
        max_start_point = "x" * 100

        # Should not raise an exception
        input_data = DoltBranchInput(
            branch_name=max_name,
            start_point=max_start_point,
            force=True,
        )

        assert input_data.branch_name == max_name
        assert input_data.start_point == max_start_point
        assert input_data.force is True


class TestDoltListBranchesTool:
    """Test class for dolt_list_branches tool functionality."""

    def test_successful_branch_listing(self, mock_memory_bank):
        """Test successful branch listing operation."""
        memory_bank, mock_writer = mock_memory_bank

        # Mock branch listing result
        mock_branches_data = [
            {
                "name": "main",
                "hash": "abc123",
                "latest_committer": "root",
                "latest_committer_email": "root@example.com",
                "latest_commit_date": datetime(2025, 6, 7, 12, 0, 0),
                "latest_commit_message": "Initial commit",
                "remote": "origin",
                "branch": "main",
                "dirty": 0,
            },
            {
                "name": "feature/test",
                "hash": "def456",
                "latest_committer": "developer",
                "latest_committer_email": "dev@example.com",
                "latest_commit_date": datetime(2025, 6, 7, 13, 0, 0),
                "latest_commit_message": "Feature work",
                "remote": "",
                "branch": "",
                "dirty": 1,
            },
        ]

        # Mock current branch query
        mock_writer._execute_query.side_effect = [
            [{"branch": "main"}],  # Current branch query
            mock_branches_data,  # Branches query
        ]

        # Prepare input
        input_data = DoltListBranchesInput()

        # Execute tool
        result = dolt_list_branches_tool(input_data, memory_bank)

        # Verify results
        assert result.success is True
        assert result.current_branch == "main"
        assert len(result.branches) == 2
        assert result.branches[0].name == "main"
        assert result.branches[0].dirty is False  # 0 becomes False
        assert result.branches[1].name == "feature/test"
        assert result.branches[1].dirty is True  # 1 becomes True
        assert "Found 2 branches" in result.message
        assert result.error is None

        # Verify mock calls
        assert mock_writer._execute_query.call_count == 2

    def test_failed_branch_listing(self, mock_memory_bank):
        """Test failed branch listing operation."""
        memory_bank, mock_writer = mock_memory_bank

        # Mock exception during branch listing
        mock_writer._execute_query.side_effect = Exception("Database connection failed")

        # Prepare input
        input_data = DoltListBranchesInput()

        # Execute tool
        result = dolt_list_branches_tool(input_data, memory_bank)

        # Verify results
        assert result.success is False
        assert result.current_branch == "unknown"
        assert len(result.branches) == 0
        assert "Failed to list branches" in result.message
        assert "Exception during branch listing" in result.error

    def test_empty_branch_listing(self, mock_memory_bank):
        """Test branch listing with no branches."""
        memory_bank, mock_writer = mock_memory_bank

        # Mock empty branch listing result
        mock_writer._execute_query.side_effect = [
            [{"branch": "main"}],  # Current branch query
            [],  # Empty branches query
        ]

        # Prepare input
        input_data = DoltListBranchesInput()

        # Execute tool
        result = dolt_list_branches_tool(input_data, memory_bank)

        # Verify results
        assert result.success is True
        assert result.current_branch == "main"
        assert len(result.branches) == 0
        assert "Found 0 branches" in result.message
        assert result.error is None
