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
    dolt_add_tool,
    DoltAddInput,
    dolt_checkout_tool,
    DoltCheckoutInput,
    dolt_diff_tool,
    DoltDiffInput,
    dolt_reset_tool,
    DoltResetInput,
    dolt_merge_tool,
    DoltMergeInput,
)
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

# Mock data paths
MOCK_CHROMA_PATH = "/mock/chroma/path"
MOCK_COLLECTION = "mock_collection"


@pytest.fixture
def mock_memory_bank():
    """Create a mock StructuredMemoryBank with mocked DoltMySQLWriter and DoltMySQLReader."""
    with (
        patch("infra_core.memory_system.structured_memory_bank.LlamaMemory"),
        patch(
            "infra_core.memory_system.structured_memory_bank.DoltMySQLWriter"
        ) as mock_writer_class,
        patch(
            "infra_core.memory_system.structured_memory_bank.DoltMySQLReader"
        ) as mock_reader_class,
    ):
        # Create mock writer instance
        mock_writer = MagicMock()
        mock_writer_class.return_value = mock_writer

        # Create mock reader instance
        mock_reader = MagicMock()
        mock_reader_class.return_value = mock_reader

        # Set up persistent connection attributes for both reader and writer
        # These need to be consistent for the synchronization check to pass
        mock_reader._current_branch = "main"
        mock_reader._use_persistent = False
        mock_reader._persistent_connection = None

        mock_writer._current_branch = "main"
        mock_writer._use_persistent = False
        mock_writer._persistent_connection = None

        # Set up active_branch property to return string instead of MagicMock
        mock_writer.active_branch = "main"
        mock_reader.active_branch = "main"

        # Mock the use_persistent_connection method to update _current_branch
        def mock_reader_use_persistent(branch):
            mock_reader._current_branch = branch
            mock_reader._use_persistent = True

        def mock_writer_use_persistent(branch):
            mock_writer._current_branch = branch
            mock_writer._use_persistent = True

        mock_reader.use_persistent_connection = mock_reader_use_persistent
        mock_writer.use_persistent_connection = mock_writer_use_persistent

        # Mock the close_persistent_connection method
        def mock_reader_close_persistent():
            mock_reader._use_persistent = False
            mock_reader._persistent_connection = None

        def mock_writer_close_persistent():
            mock_writer._use_persistent = False
            mock_writer._persistent_connection = None

        mock_reader.close_persistent_connection = mock_reader_close_persistent
        mock_writer.close_persistent_connection = mock_writer_close_persistent

        # Mock _execute_query to return proper string values for branch queries
        mock_reader._execute_query.return_value = [{"branch": "main"}]
        mock_writer._execute_query.return_value = [{"branch": "main"}]

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

        yield memory_bank, mock_writer, mock_reader


class TestDoltRepoTool:
    """Test class for dolt_commit tool functionality."""

    def test_successful_commit_with_default_tables(self, mock_memory_bank):
        """Test successful commit operation with default tables."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

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
        assert result.tables_committed == [
            "memory_blocks",
            "block_properties",
            "block_links",
            "block_proofs",
        ]
        assert result.error is None
        assert isinstance(result.timestamp, datetime)

        # Verify mock calls
        mock_writer.commit_changes.assert_called_once_with(
            commit_msg="Test commit message",
            tables=["memory_blocks", "block_properties", "block_links", "block_proofs"],
        )

    def test_successful_commit_with_custom_tables(self, mock_memory_bank):
        """Test successful commit operation with custom table list."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

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
        memory_bank, mock_writer, mock_reader = mock_memory_bank

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
            tables=["memory_blocks", "block_properties", "block_links", "block_proofs"],
        )

    def test_failed_commit_operation(self, mock_memory_bank):
        """Test failed commit operation."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

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
        assert result.tables_committed == [
            "memory_blocks",
            "block_properties",
            "block_links",
            "block_proofs",
        ]

    def test_commit_with_exception(self, mock_memory_bank):
        """Test commit operation when an exception occurs."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

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
        memory_bank, mock_writer, mock_reader = mock_memory_bank

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
        memory_bank, mock_writer, mock_reader = mock_memory_bank

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
        memory_bank, mock_writer, mock_reader = mock_memory_bank

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
        memory_bank, mock_writer, mock_reader = mock_memory_bank

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
        memory_bank, mock_writer, mock_reader = mock_memory_bank

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
        memory_bank, mock_writer, mock_reader = mock_memory_bank

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
        memory_bank, mock_writer, mock_reader = mock_memory_bank

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
    """Test class for dolt_list_branches_tool functionality."""

    def test_successful_branch_listing(self, mock_memory_bank):
        """Test successful branch listing operation."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

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
        mock_reader.list_branches.return_value = (mock_branches_data, "main")

        # Prepare input
        input_data = DoltListBranchesInput()

        # Execute tool
        result = dolt_list_branches_tool(input_data, memory_bank)

        # Verify results
        assert result.success is True
        assert len(result.branches) == 2
        assert result.active_branch == "main"
        assert result.branches[0].name == "main"
        assert result.branches[1].hash == "def456"
        assert "Found 2 branches" in result.message
        assert result.error is None

    def test_failed_branch_listing(self, mock_memory_bank):
        """Test failed branch listing operation."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank
        mock_reader.list_branches.return_value = ([], "unknown")

        # Prepare input
        input_data = DoltListBranchesInput()

        # Execute tool
        result = dolt_list_branches_tool(input_data, memory_bank)

        # A failed listing from the writer should be handled gracefully by the tool
        assert result.success is True
        assert len(result.branches) == 0
        assert result.active_branch == "unknown"

    def test_empty_branch_listing(self, mock_memory_bank):
        """Test branch listing with no branches."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank
        mock_reader.list_branches.return_value = ([], "main")

        # Prepare input
        input_data = DoltListBranchesInput()

        # Execute tool
        result = dolt_list_branches_tool(input_data, memory_bank)

        # Verify results
        assert result.success is True
        assert len(result.branches) == 0
        assert result.active_branch == "main"
        assert "Found 0 branches" in result.message
        assert result.error is None

    def test_list_branches_with_exception(self, mock_memory_bank):
        """Test branch listing when an exception occurs."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank
        mock_reader.list_branches.side_effect = Exception("Connection timeout")

        result = dolt_list_branches_tool(DoltListBranchesInput(), memory_bank)

        assert result.success is False
        assert "Failed to list branches" in result.message
        assert "Exception during branch listing" in result.error
        assert "Connection timeout" in result.error


class TestDoltAddTool:
    """Test class for dolt_add_tool functionality."""

    def test_successful_add_all(self, mock_memory_bank):
        """Test successful add operation for all changes."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank
        mock_writer.add_to_staging.return_value = (True, "Successfully staged all changes")

        input_data = DoltAddInput()  # No tables specified
        result = dolt_add_tool(input_data, memory_bank)

        assert result.success is True
        assert "Successfully staged all changes" in result.message
        mock_writer.add_to_staging.assert_called_once_with(tables=None)

    def test_successful_add_specific_tables(self, mock_memory_bank):
        """Test successful add operation for a specific list of tables."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank
        mock_writer.add_to_staging.return_value = (True, "Successfully staged 2 tables")
        tables = ["table1", "table2"]

        input_data = DoltAddInput(tables=tables)
        result = dolt_add_tool(input_data, memory_bank)

        assert result.success is True
        assert "Successfully staged 2 tables" in result.message
        mock_writer.add_to_staging.assert_called_once_with(tables=tables)

    def test_failed_add(self, mock_memory_bank):
        """Test a failed add operation."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank
        mock_writer.add_to_staging.return_value = (False, "Staging failed")

        input_data = DoltAddInput()
        result = dolt_add_tool(input_data, memory_bank)

        assert result.success is False
        assert "ADD FAILED: Staging failed" in result.message
        assert "Staging failed" in result.error

    def test_add_with_exception(self, mock_memory_bank):
        """Test add operation when an exception occurs."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank
        mock_writer.add_to_staging.side_effect = Exception("Underlying SQL error")

        input_data = DoltAddInput()
        result = dolt_add_tool(input_data, memory_bank)

        assert result.success is False
        assert "ADD FAILED: Underlying SQL error" in result.message
        assert "Exception during ADD" in result.error


class TestDoltCheckoutTool:
    """Test class for dolt_checkout_tool functionality."""

    def test_successful_checkout(self, mock_memory_bank):
        """Test a successful branch checkout."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        input_data = DoltCheckoutInput(branch_name="feat/new-branch")
        result = dolt_checkout_tool(input_data, memory_bank)

        assert result.success is True
        assert (
            "Successfully checked out branch 'feat/new-branch' with coordinated persistent connections"
            in result.message
        )

        # Verify that both reader and writer are now on the target branch
        assert memory_bank.dolt_reader._current_branch == "feat/new-branch"
        assert memory_bank.dolt_writer._current_branch == "feat/new-branch"
        assert memory_bank.branch == "feat/new-branch"

    def test_successful_force_checkout(self, mock_memory_bank):
        """Test a successful force checkout."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        input_data = DoltCheckoutInput(branch_name="feat/new-branch", force=True)
        result = dolt_checkout_tool(input_data, memory_bank)

        assert result.success is True
        assert (
            "Successfully checked out branch 'feat/new-branch' with coordinated persistent connections"
            in result.message
        )

        # Verify that both reader and writer are now on the target branch
        assert memory_bank.dolt_reader._current_branch == "feat/new-branch"
        assert memory_bank.dolt_writer._current_branch == "feat/new-branch"
        assert memory_bank.branch == "feat/new-branch"

    def test_failed_checkout(self, mock_memory_bank):
        """Test a failed checkout operation."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Make the reader's use_persistent_connection method raise an exception
        def mock_reader_use_persistent_fail(branch):
            raise Exception("Branch not found")

        memory_bank.dolt_reader.use_persistent_connection = mock_reader_use_persistent_fail

        input_data = DoltCheckoutInput(branch_name="nonexistent-branch")
        result = dolt_checkout_tool(input_data, memory_bank)

        assert result.success is False
        assert "Checkout failed:" in result.message
        assert "Branch not found" in result.message

    def test_checkout_with_exception(self, mock_memory_bank):
        """Test checkout operation when an exception occurs."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Make the writer's use_persistent_connection method raise an exception
        def mock_writer_use_persistent_fail(branch):
            raise Exception("Connection error")

        memory_bank.dolt_writer.use_persistent_connection = mock_writer_use_persistent_fail

        input_data = DoltCheckoutInput(branch_name="any-branch")
        result = dolt_checkout_tool(input_data, memory_bank)

        assert result.success is False
        assert "Checkout failed:" in result.message
        assert "Connection error" in result.message


class TestDoltDiffTool:
    """Test class for dolt_diff_tool functionality."""

    def test_successful_diff_working(self, mock_memory_bank):
        """Test a successful diff for the working set."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        mock_diff_summary = [
            {
                "from_table_name": "test_table",
                "to_table_name": "test_table",
                "diff_type": "modified",
                "data_change": True,
                "schema_change": False,
            }
        ]
        mock_writer.get_diff_summary.return_value = mock_diff_summary

        mock_diff_details = [
            {
                "_table_name": "test_table",
                "diff_type": "modified",
                "from_id": "123",
                "to_id": "123",
                "from_name": "old_value",
                "to_name": "new_value",
            }
        ]
        mock_reader.get_diff_summary.return_value = mock_diff_summary
        mock_reader.get_diff_details.return_value = mock_diff_details

        input_data = DoltDiffInput(mode="working")
        result = dolt_diff_tool(input_data, memory_bank)

        assert result.success is True
        assert "Successfully retrieved diff" in result.message
        assert len(result.diff_summary) == 1
        assert result.diff_summary[0].to_table_name == "test_table"
        assert result.diff_summary[0].diff_type == "modified"
        assert len(result.diff_details) == 1
        assert result.diff_details[0]["_table_name"] == "test_table"
        assert result.diff_details[0]["diff_type"] == "modified"
        mock_reader.get_diff_summary.assert_called_once_with(
            from_revision="HEAD", to_revision="WORKING"
        )
        mock_reader.get_diff_details.assert_called_once_with(
            from_revision="HEAD", to_revision="WORKING"
        )

    def test_successful_diff_staged(self, mock_memory_bank):
        """Test a successful diff for the staged changes."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        mock_diff_summary = [
            {
                "from_table_name": None,
                "to_table_name": "new_table",
                "diff_type": "added",
                "data_change": True,
                "schema_change": True,
            }
        ]
        mock_writer.get_diff_summary.return_value = mock_diff_summary

        mock_diff_details = [
            {
                "_table_name": "new_table",
                "diff_type": "added",
                "from_id": None,
                "to_id": "456",
                "from_name": None,
                "to_name": "new_record",
            }
        ]
        mock_reader.get_diff_summary.return_value = mock_diff_summary
        mock_reader.get_diff_details.return_value = mock_diff_details

        input_data = DoltDiffInput(mode="staged")
        result = dolt_diff_tool(input_data, memory_bank)

        assert result.success is True
        assert "Successfully retrieved diff" in result.message
        assert len(result.diff_summary) == 1
        assert result.diff_summary[0].to_table_name == "new_table"
        assert result.diff_summary[0].diff_type == "added"
        assert len(result.diff_details) == 1
        assert result.diff_details[0]["_table_name"] == "new_table"
        assert result.diff_details[0]["diff_type"] == "added"
        mock_reader.get_diff_summary.assert_called_once_with(
            from_revision="HEAD", to_revision="STAGED"
        )
        mock_reader.get_diff_details.assert_called_once_with(
            from_revision="HEAD", to_revision="STAGED"
        )

    def test_successful_diff_custom_revisions(self, mock_memory_bank):
        """Test a successful diff with custom from and to revisions."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank
        mock_writer.get_diff_summary.return_value = []
        mock_reader.get_diff_summary.return_value = []
        mock_reader.get_diff_details.return_value = []

        input_data = DoltDiffInput(from_revision="main", to_revision="feature-branch")
        result = dolt_diff_tool(input_data, memory_bank)

        assert result.success is True
        assert "No changes found" in result.message
        assert len(result.diff_summary) == 0
        assert len(result.diff_details) == 0
        mock_reader.get_diff_summary.assert_called_once_with(
            from_revision="main", to_revision="feature-branch"
        )
        mock_reader.get_diff_details.assert_called_once_with(
            from_revision="main", to_revision="feature-branch"
        )

    def test_no_changes_found(self, mock_memory_bank):
        """Test the case where no diff summary is returned."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank
        mock_writer.get_diff_summary.return_value = []
        mock_reader.get_diff_summary.return_value = []
        mock_reader.get_diff_details.return_value = []

        input_data = DoltDiffInput(mode="working")
        result = dolt_diff_tool(input_data, memory_bank)

        assert result.success is True
        assert "No changes found" in result.message
        assert len(result.diff_summary) == 0
        assert len(result.diff_details) == 0

    def test_failed_diff_with_exception(self, mock_memory_bank):
        """Test the case where the reader raises an exception."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank
        mock_writer.get_diff_summary.side_effect = Exception("Dolt connection error")
        mock_reader.get_diff_summary.side_effect = Exception("Dolt connection error")

        input_data = DoltDiffInput(mode="working")
        result = dolt_diff_tool(input_data, memory_bank)

        assert result.success is False
        assert "An unexpected error occurred" in result.message
        assert "Dolt connection error" in result.error
        assert len(result.diff_summary) == 0
        assert len(result.diff_details) == 0

    def test_invalid_input_no_revisions(self, mock_memory_bank):
        """Test invalid input where no mode or revisions are provided."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # This combination is not valid anymore because mode has a default
        # Instead, we test the internal logic that requires both from and to revs
        input_data = DoltDiffInput(mode=None, from_revision="HEAD", to_revision=None)
        result = dolt_diff_tool(input_data, memory_bank)

        assert result.success is False
        assert "must be provided if not using a mode" in result.message
        assert "Invalid revision arguments" in result.error
        assert len(result.diff_details) == 0
        mock_reader.get_diff_summary.assert_not_called()
        mock_reader.get_diff_details.assert_not_called()


class TestDoltResetTool:
    """Test class for dolt_reset_tool functionality."""

    def test_successful_reset_all(self, mock_memory_bank):
        """Test successful reset operation for all tables."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock successful reset
        mock_writer.reset.return_value = (True, "Successfully performed hard reset on all changes")

        # Prepare input
        input_data = DoltResetInput()

        # Execute tool
        result = dolt_reset_tool(input_data, memory_bank)

        # Verify results
        assert result.success is True
        assert "Successfully performed hard reset on all changes" in result.message
        assert result.tables_reset is None
        assert result.error is None
        assert isinstance(result.timestamp, datetime)

        # Verify reset was called with correct parameters
        mock_writer.reset.assert_called_once_with(hard=True, tables=None)

    def test_successful_reset_specific_tables(self, mock_memory_bank):
        """Test successful reset operation for specific tables."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock successful reset
        specific_tables = ["memory_blocks", "block_links"]
        mock_writer.reset.return_value = (
            True,
            f"Successfully performed hard reset on {len(specific_tables)} table(s): {', '.join(specific_tables)}",
        )

        # Prepare input with specific tables
        input_data = DoltResetInput(tables=specific_tables)

        # Execute tool
        result = dolt_reset_tool(input_data, memory_bank)

        # Verify results
        assert result.success is True
        assert (
            "Successfully performed hard reset on 2 table(s): memory_blocks, block_links"
            in result.message
        )
        assert result.tables_reset == specific_tables
        assert result.error is None

        # Verify reset was called with correct parameters
        mock_writer.reset.assert_called_once_with(hard=True, tables=specific_tables)

    def test_failed_reset_operation(self, mock_memory_bank):
        """Test failed reset operation."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock failed reset
        mock_writer.reset.return_value = (False, "Failed to reset changes: Connection error")

        # Prepare input
        input_data = DoltResetInput()

        # Execute tool
        result = dolt_reset_tool(input_data, memory_bank)

        # Verify results
        assert result.success is False
        assert "Failed to reset changes: Connection error" in result.message
        assert "Failed to reset changes: Connection error" in result.error
        assert result.error_code == "RESET_FAILED"
        assert result.tables_reset is None

    def test_reset_with_exception(self, mock_memory_bank):
        """Test reset operation when an exception occurs."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock exception during reset
        mock_writer.reset.side_effect = Exception("Database connection error")

        # Prepare input
        input_data = DoltResetInput()

        # Execute tool
        result = dolt_reset_tool(input_data, memory_bank)

        # Verify results
        assert result.success is False
        assert "Exception during dolt_reset: Database connection error" in result.message
        assert "Exception during dolt_reset: Database connection error" in result.error
        assert result.error_code == "EXCEPTION"

    def test_reset_hard_flag_default(self, mock_memory_bank):
        """Test that hard flag defaults to True."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock successful reset
        mock_writer.reset.return_value = (True, "Successfully performed hard reset on all changes")

        # Prepare input without specifying hard flag
        input_data = DoltResetInput()

        # Verify default value
        assert input_data.hard is True

        # Execute tool
        result = dolt_reset_tool(input_data, memory_bank)

        # Verify success
        assert result.success is True

        # Verify hard=True was passed
        mock_writer.reset.assert_called_once_with(hard=True, tables=None)

    def test_reset_hard_flag_explicit(self, mock_memory_bank):
        """Test that hard flag can be set explicitly."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock successful reset
        mock_writer.reset.return_value = (True, "Successfully performed hard reset on all changes")

        # Prepare input with explicit hard flag
        input_data = DoltResetInput(hard=True)

        # Verify explicit value
        assert input_data.hard is True

        # Execute tool
        result = dolt_reset_tool(input_data, memory_bank)

        # Verify success
        assert result.success is True

        # Verify hard=True was passed
        mock_writer.reset.assert_called_once_with(hard=True, tables=None)

    def test_input_validation_empty_tables_list(self, mock_memory_bank):
        """Test that empty tables list is handled correctly."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock successful reset
        mock_writer.reset.return_value = (True, "Successfully performed hard reset on all changes")

        # Prepare input with empty tables list
        input_data = DoltResetInput(tables=[])

        # Execute tool
        result = dolt_reset_tool(input_data, memory_bank)

        # Verify results - empty list should be passed through
        assert result.success is True
        assert result.tables_reset == []

        # Verify reset was called with empty list
        mock_writer.reset.assert_called_once_with(hard=True, tables=[])

    def test_output_model_serialization(self, mock_memory_bank):
        """Test that the output model can be properly serialized."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock successful reset
        mock_writer.reset.return_value = (
            True,
            "Successfully performed hard reset on 1 table(s): test_table",
        )

        # Prepare input
        input_data = DoltResetInput(tables=["test_table"])

        # Execute tool
        result = dolt_reset_tool(input_data, memory_bank)

        # Test serialization
        serialized = result.model_dump(mode="json")

        # Verify serialized structure
        assert "success" in serialized
        assert "message" in serialized
        assert "active_branch" in serialized
        assert "tables_reset" in serialized
        assert "timestamp" in serialized
        assert serialized["success"] is True
        assert serialized["tables_reset"] == ["test_table"]


class TestDoltMergeTool:
    """Test class for dolt_merge_tool functionality."""

    def test_successful_regular_merge(self, mock_memory_bank):
        """Test successful regular merge operation."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock successful merge
        mock_writer.merge_branch.return_value = (True, "merge successful")

        # Prepare input for regular merge
        input_data = DoltMergeInput(
            source_branch="feature/test-branch",
            commit_message="Merge feature/test-branch into main",
        )

        # Execute tool
        result = dolt_merge_tool(input_data, memory_bank)

        # Verify results
        assert result.success is True
        assert result.source_branch == "feature/test-branch"
        assert result.target_branch == "main"  # Should use current branch
        assert result.squash is False
        assert result.no_ff is False
        assert result.fast_forward is False  # Default when not specified
        assert result.conflicts == 0
        assert result.merge_hash is None  # Tool doesn't extract hash from Dolt result
        assert "merge successful" in result.message
        assert result.error is None
        assert isinstance(result.timestamp, datetime)

        # Verify mock calls
        mock_writer.merge_branch.assert_called_once_with(
            source_branch="feature/test-branch",
            squash=False,
            no_ff=False,
            commit_message="Merge feature/test-branch into main",
        )

    def test_successful_squash_merge(self, mock_memory_bank):
        """Test successful squash merge operation."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock successful squash merge
        mock_writer.merge_branch.return_value = (True, "merge successful")

        # Prepare input for squash merge
        input_data = DoltMergeInput(
            source_branch="feature/cleanup",
            squash=True,
            commit_message="Squash merge feature/cleanup",
        )

        # Execute tool
        result = dolt_merge_tool(input_data, memory_bank)

        # Verify results
        assert result.success is True
        assert result.source_branch == "feature/cleanup"
        assert result.squash is True
        assert result.no_ff is False
        assert result.merge_hash is None
        assert "merge successful" in result.message

        # Verify mock calls
        mock_writer.merge_branch.assert_called_once_with(
            source_branch="feature/cleanup",
            squash=True,
            no_ff=False,
            commit_message="Squash merge feature/cleanup",
        )

    def test_successful_no_ff_merge(self, mock_memory_bank):
        """Test successful no-fast-forward merge operation."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock successful no-ff merge
        mock_writer.merge_branch.return_value = (True, "merge successful")

        # Prepare input for no-ff merge
        input_data = DoltMergeInput(
            source_branch="feature/important",
            no_ff=True,
            commit_message="No-FF merge feature/important",
        )

        # Execute tool
        result = dolt_merge_tool(input_data, memory_bank)

        # Verify results
        assert result.success is True
        assert result.source_branch == "feature/important"
        assert result.squash is False
        assert result.no_ff is True
        assert result.merge_hash is None

        # Verify mock calls
        mock_writer.merge_branch.assert_called_once_with(
            source_branch="feature/important",
            squash=False,
            no_ff=True,
            commit_message="No-FF merge feature/important",
        )

    def test_successful_squash_and_no_ff_merge(self, mock_memory_bank):
        """Test successful merge with both squash and no-ff flags."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock successful merge with both flags
        mock_writer.merge_branch.return_value = (True, "merge successful")

        # Prepare input with both squash and no_ff
        input_data = DoltMergeInput(
            source_branch="feature/complex",
            squash=True,
            no_ff=True,
            commit_message="Complex merge with squash and no-ff",
        )

        # Execute tool
        result = dolt_merge_tool(input_data, memory_bank)

        # Verify results
        assert result.success is True
        assert result.squash is True
        assert result.no_ff is True
        assert result.merge_hash is None

        # Verify mock calls
        mock_writer.merge_branch.assert_called_once_with(
            source_branch="feature/complex",
            squash=True,
            no_ff=True,
            commit_message="Complex merge with squash and no-ff",
        )

    def test_merge_with_default_commit_message(self, mock_memory_bank):
        """Test merge operation with auto-generated commit message."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock successful merge
        mock_writer.merge_branch.return_value = (True, "merge successful")

        # Prepare input without commit message
        input_data = DoltMergeInput(source_branch="feature/auto-message")

        # Execute tool
        result = dolt_merge_tool(input_data, memory_bank)

        # Verify results
        assert result.success is True

        # Verify mock calls - should pass None for commit_message when not provided
        mock_writer.merge_branch.assert_called_once_with(
            source_branch="feature/auto-message",
            squash=False,
            no_ff=False,
            commit_message=None,
        )

    def test_failed_merge_with_conflicts(self, mock_memory_bank):
        """Test failed merge operation due to conflicts."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock failed merge with conflict error
        conflict_error = "error: local changes would be stomped by merge:\n\tblock_proofs\n Please commit your changes before you merge."
        mock_writer.merge_branch.return_value = (False, conflict_error)

        # Prepare input
        input_data = DoltMergeInput(
            source_branch="feature/conflicting", commit_message="This merge will conflict"
        )

        # Execute tool
        result = dolt_merge_tool(input_data, memory_bank)

        # Verify results
        assert result.success is False
        assert result.source_branch == "feature/conflicting"
        assert result.merge_hash is None
        assert result.conflicts == 0  # Tool doesn't parse conflict count
        assert "Merge operation failed" in result.message
        assert conflict_error in result.error
        assert result.error_code is None

    def test_failed_merge_branch_not_found(self, mock_memory_bank):
        """Test failed merge operation when source branch doesn't exist."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock failed merge with branch not found error
        branch_error = "Branch 'nonexistent-branch' not found"
        mock_writer.merge_branch.return_value = (False, branch_error)

        # Prepare input with non-existent branch
        input_data = DoltMergeInput(
            source_branch="nonexistent-branch", commit_message="This branch doesn't exist"
        )

        # Execute tool
        result = dolt_merge_tool(input_data, memory_bank)

        # Verify results
        assert result.success is False
        assert result.source_branch == "nonexistent-branch"
        assert result.merge_hash is None
        assert "Merge operation failed" in result.message
        assert branch_error in result.error

    def test_merge_with_exception(self, mock_memory_bank):
        """Test merge operation when an exception occurs."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock exception during merge
        mock_writer.merge_branch.side_effect = Exception("Database connection failed")

        # Prepare input
        input_data = DoltMergeInput(
            source_branch="feature/exception-test", commit_message="This will cause an exception"
        )

        # Execute tool
        result = dolt_merge_tool(input_data, memory_bank)

        # Verify results
        assert result.success is False
        assert result.source_branch == "feature/exception-test"
        assert result.merge_hash is None
        assert "Merge failed: Database connection failed" in result.message
        assert "Exception during dolt_merge" in result.error

    def test_input_validation_empty_source_branch(self):
        """Test input validation with empty source branch name."""
        with pytest.raises(ValueError):
            DoltMergeInput(source_branch="")

    def test_input_validation_long_source_branch(self):
        """Test input validation with overly long source branch name."""
        long_branch = "x" * 101  # Exceeds max_length of 100
        with pytest.raises(ValueError):
            DoltMergeInput(source_branch=long_branch)

    def test_input_validation_long_commit_message(self):
        """Test input validation with overly long commit message."""
        long_message = "x" * 501  # Exceeds max_length of 500
        with pytest.raises(ValueError):
            DoltMergeInput(source_branch="valid-branch", commit_message=long_message)

    def test_input_validation_valid_max_lengths(self):
        """Test input validation with maximum allowed lengths."""
        # Test maximum valid lengths
        max_branch = "x" * 100
        max_message = "x" * 500

        # Should not raise an exception
        input_data = DoltMergeInput(
            source_branch=max_branch, commit_message=max_message, squash=True, no_ff=True
        )

        assert input_data.source_branch == max_branch
        assert input_data.commit_message == max_message
        assert input_data.squash is True
        assert input_data.no_ff is True

    def test_input_validation_boolean_defaults(self):
        """Test that boolean flags have correct default values."""
        input_data = DoltMergeInput(source_branch="test-branch")

        assert input_data.squash is False
        assert input_data.no_ff is False

    def test_output_model_serialization(self, mock_memory_bank):
        """Test that DoltMergeOutput can be properly serialized."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock successful merge
        mock_writer.merge_branch.return_value = (True, "merge successful")

        # Prepare input
        input_data = DoltMergeInput(
            source_branch="feature/serialization-test",
            squash=True,
            no_ff=False,
            commit_message="Serialization test merge",
        )

        # Execute tool
        result = dolt_merge_tool(input_data, memory_bank)

        # Test serialization
        serialized = result.model_dump(mode="json")

        # Verify all fields are present and properly typed
        assert isinstance(serialized["success"], bool)
        assert isinstance(serialized["source_branch"], str)
        assert isinstance(serialized["target_branch"], str)
        assert isinstance(serialized["squash"], bool)
        assert isinstance(serialized["no_ff"], bool)
        assert isinstance(serialized["fast_forward"], bool)
        assert isinstance(serialized["conflicts"], int)
        assert serialized["merge_hash"] is None  # Current implementation always returns None
        assert isinstance(serialized["message"], str)
        assert serialized["error"] is None
        assert isinstance(serialized["timestamp"], str)  # datetime becomes string in JSON

        # Verify specific values
        assert serialized["success"] is True
        assert serialized["source_branch"] == "feature/serialization-test"
        assert serialized["squash"] is True
        assert serialized["no_ff"] is False
        assert serialized["merge_hash"] is None

    def test_merge_preserves_target_branch_context(self, mock_memory_bank):
        """Test that merge operation preserves the current target branch context."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Set up memory bank to be on staging branch
        memory_bank.dolt_writer._current_branch = "staging"
        memory_bank.dolt_reader._current_branch = "staging"
        memory_bank.dolt_writer.active_branch = "staging"
        memory_bank.dolt_reader.active_branch = "staging"

        # Mock successful merge
        mock_writer.merge_branch.return_value = (True, "merge successful")

        # Prepare input
        input_data = DoltMergeInput(
            source_branch="feature/staging-test", commit_message="Merge into staging branch"
        )

        # Execute tool
        result = dolt_merge_tool(input_data, memory_bank)

        # Verify results - should show staging as target branch
        assert result.success is True
        assert result.source_branch == "feature/staging-test"
        assert result.target_branch == "staging"

    def test_merge_error_handling_comprehensive(self, mock_memory_bank):
        """Test comprehensive error handling scenarios."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Test various error scenarios
        error_scenarios = [
            ("Already up to date", "Already up to date"),
            ("cannot fast forward", "cannot fast forward"),
            ("Merge conflict in file.txt", "Merge conflict in file.txt"),
            ("Permission denied", "Permission denied"),
        ]

        for error_message, expected_error in error_scenarios:
            # Reset mock for each scenario
            mock_writer.reset_mock()
            mock_writer.merge_branch.return_value = (False, error_message)

            # Prepare input
            input_data = DoltMergeInput(
                source_branch=f"feature/test-{error_message.replace(' ', '-').lower()}",
                commit_message=f"Test merge with error: {error_message}",
            )

            # Execute tool
            result = dolt_merge_tool(input_data, memory_bank)

            # Verify error handling
            assert result.success is False
            assert result.merge_hash is None
            assert "Merge operation failed" in result.message
            assert expected_error in result.error

    def test_merge_with_writer_active_branch_property(self, mock_memory_bank):
        """Test that merge correctly uses writer's active_branch property."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Set different branch on writer
        mock_writer.active_branch = "feature-branch"

        # Mock successful merge
        mock_writer.merge_branch.return_value = (True, "merge successful")

        # Prepare input
        input_data = DoltMergeInput(
            source_branch="hotfix/urgent-fix", commit_message="Merge urgent hotfix"
        )

        # Execute tool
        result = dolt_merge_tool(input_data, memory_bank)

        # Verify results use the writer's active branch
        assert result.success is True
        assert result.target_branch == "feature-branch"
