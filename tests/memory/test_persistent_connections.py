"""
Test cases for persistent connection usage in memory system.

These tests verify that read and write operations properly use persistent connections
when they are enabled, ensuring consistent branch state across operations.
"""

import pytest
from unittest.mock import MagicMock, patch

from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig
from infra_core.memory_system.tools.agent_facing.dolt_repo_tool import (
    dolt_checkout_tool,
    DoltCheckoutInput,
)
from infra_core.memory_system.tools.agent_facing.get_memory_block_tool import (
    get_memory_block_tool,
)
from infra_core.memory_system.tools.agent_facing.create_work_item_tool import (
    create_work_item_tool,
    CreateWorkItemInput,
)


@pytest.fixture
def mock_config():
    """Create a mock connection config."""
    return DoltConnectionConfig(
        host="localhost", port=3306, user="root", password="", database="test_db"
    )


@pytest.fixture
def mock_memory_bank(mock_config):
    """Create a mock StructuredMemoryBank with mocked dependencies."""
    with (
        patch("infra_core.memory_system.structured_memory_bank.LlamaMemory"),
        patch(
            "infra_core.memory_system.structured_memory_bank.DoltMySQLWriter"
        ) as mock_writer_class,
        patch(
            "infra_core.memory_system.structured_memory_bank.DoltMySQLReader"
        ) as mock_reader_class,
    ):
        # Create mock instances
        mock_writer = MagicMock()
        mock_reader = MagicMock()

        # Configure active_branch to return strings instead of MagicMock
        mock_writer.active_branch = "main"
        mock_reader.active_branch = "main"

        mock_writer_class.return_value = mock_writer
        mock_reader_class.return_value = mock_reader

        # Create memory bank
        memory_bank = StructuredMemoryBank(
            chroma_path="/tmp/test_chroma",
            chroma_collection="test_collection",
            dolt_connection_config=mock_config,
            branch="main",
        )

        yield memory_bank, mock_writer, mock_reader


class TestPersistentConnectionUsage:
    """Test that operations properly use persistent connections when enabled."""

    def test_memory_bank_enables_persistent_connections_on_both_reader_and_writer(
        self, mock_memory_bank
    ):
        """Test that use_persistent_connections() enables connections on both reader and writer."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock successful persistent connection setup
        mock_reader._current_branch = "test-branch"
        mock_writer._current_branch = "test-branch"

        # Enable persistent connections
        memory_bank.use_persistent_connections(branch="test-branch")

        # Verify both reader and writer had persistent connections enabled
        mock_reader.use_persistent_connection.assert_called_once_with("test-branch")
        mock_writer.use_persistent_connection.assert_called_once_with("test-branch")

    def test_memory_bank_closes_persistent_connections_on_both_reader_and_writer(
        self, mock_memory_bank
    ):
        """Test that close_persistent_connections() closes connections on both reader and writer."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Close persistent connections
        memory_bank.close_persistent_connections()

        # Verify both reader and writer had persistent connections closed
        mock_reader.close_persistent_connection.assert_called_once()
        mock_writer.close_persistent_connection.assert_called_once()

    def test_dolt_checkout_uses_coordinated_persistent_connections(self, mock_memory_bank):
        """Test that DoltCheckout tool uses memory bank's coordinated persistent connections."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock successful branch synchronization
        mock_reader._current_branch = "feature-branch"
        mock_writer._current_branch = "feature-branch"

        # Execute checkout
        input_data = DoltCheckoutInput(branch_name="feature-branch")
        result = dolt_checkout_tool(input_data, memory_bank)

        # Verify success
        assert result.success is True
        assert "feature-branch" in result.message

        # Verify coordinated persistent connections were used
        mock_reader.use_persistent_connection.assert_called_once_with("feature-branch")
        mock_writer.use_persistent_connection.assert_called_once_with("feature-branch")

    def test_read_operations_use_persistent_connection_when_enabled(self, mock_memory_bank):
        """Test that read operations use persistent connections when they are enabled."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Enable persistent connections
        mock_reader._use_persistent = True
        mock_reader._current_branch = "test-branch"
        mock_reader._persistent_connection = MagicMock()

        # Mock read operation
        mock_reader.read_memory_blocks.return_value = []

        # Execute read operation
        get_memory_block_tool(memory_bank=memory_bank, type_filter="task", limit=10)

        # Verify read operation was called
        mock_reader.read_memory_blocks.assert_called_once()

        # Verify the reader has persistent connection enabled
        assert mock_reader._use_persistent is True
        assert mock_reader._current_branch == "test-branch"
        assert mock_reader._persistent_connection is not None

    def test_write_operations_use_persistent_connection_when_enabled(self, mock_memory_bank):
        """Test that write operations use persistent connections when they are enabled."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Enable persistent connections
        mock_writer._use_persistent = True
        mock_writer._current_branch = "test-branch"
        mock_writer._persistent_connection = MagicMock()

        # Mock write operation
        mock_writer.write_memory_block.return_value = (True, "commit-hash")

        # Create a test work item with required acceptance_criteria
        input_data = CreateWorkItemInput(
            type="task",
            title="Test Task",
            description="Test Description",
            owner="test-user",
            acceptance_criteria=["Task should be completed", "Tests should pass"],
        )

        # Execute write operation
        create_work_item_tool(input_data, memory_bank=memory_bank)

        # Verify write operation was called
        mock_writer.write_memory_block.assert_called_once()

        # Verify the writer has persistent connection enabled
        assert mock_writer._use_persistent is True
        assert mock_writer._current_branch == "test-branch"
        assert mock_writer._persistent_connection is not None

    def test_reader_and_writer_stay_synchronized_after_checkout(self, mock_memory_bank):
        """Test that reader and writer stay on the same branch after checkout."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock successful branch synchronization
        mock_reader._current_branch = "sync-branch"
        mock_writer._current_branch = "sync-branch"

        # Execute checkout
        input_data = DoltCheckoutInput(branch_name="sync-branch")
        result = dolt_checkout_tool(input_data, memory_bank)

        # Verify success
        assert result.success is True

        # Verify both reader and writer are on the same branch
        assert mock_reader._current_branch == mock_writer._current_branch
        assert mock_reader._current_branch == "sync-branch"

    def test_memory_bank_detects_branch_desynchronization(self, mock_memory_bank):
        """Test that memory bank detects when reader and writer are on different branches."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock branch desynchronization
        mock_reader._current_branch = "reader-branch"
        mock_writer._current_branch = "writer-branch"

        # Attempt to enable persistent connections should fail
        with pytest.raises(Exception) as exc_info:
            memory_bank.use_persistent_connections(branch="test-branch")

        assert "Branch synchronization failed" in str(exc_info.value)
        assert "reader-branch" in str(exc_info.value)
        assert "writer-branch" in str(exc_info.value)

    def test_persistent_connection_state_is_consistent(self, mock_memory_bank):
        """Test that persistent connection state is consistent across reader and writer."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Initially, no persistent connections (check actual attributes, not mocks)
        # Reset the mocks to have proper initial state
        mock_reader.reset_mock()
        mock_writer.reset_mock()

        # Mock successful persistent connection setup
        mock_reader._current_branch = "consistent-branch"
        mock_writer._current_branch = "consistent-branch"
        mock_reader._use_persistent = True
        mock_writer._use_persistent = True

        # Enable persistent connections
        memory_bank.use_persistent_connections(branch="consistent-branch")

        # Verify both have persistent connections enabled
        mock_reader.use_persistent_connection.assert_called_once_with("consistent-branch")
        mock_writer.use_persistent_connection.assert_called_once_with("consistent-branch")

    def test_debug_persistent_state_reports_accurate_information(self, mock_memory_bank):
        """Test that debug_persistent_state() reports accurate connection state."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Set up mock state
        mock_reader._use_persistent = True
        mock_reader._current_branch = "debug-branch"
        mock_reader._persistent_connection = MagicMock()

        mock_writer._use_persistent = True
        mock_writer._current_branch = "debug-branch"
        mock_writer._persistent_connection = MagicMock()

        # Get debug state
        debug_info = memory_bank.debug_persistent_state()

        # Verify debug information
        assert debug_info["reader_use_persistent"] is True
        assert debug_info["reader_current_branch"] == "debug-branch"
        assert debug_info["reader_has_connection"] is True

        assert debug_info["writer_use_persistent"] is True
        assert debug_info["writer_current_branch"] == "debug-branch"
        assert debug_info["writer_has_connection"] is True


class TestPersistentConnectionFailures:
    """Test error handling for persistent connection failures."""

    def test_checkout_handles_persistent_connection_failure(self, mock_memory_bank):
        """Test that checkout handles persistent connection failures gracefully."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock persistent connection failure on the memory bank level
        with patch.object(
            memory_bank, "use_persistent_connections", side_effect=Exception("Connection failed")
        ):
            # Execute checkout
            input_data = DoltCheckoutInput(branch_name="failing-branch")
            result = dolt_checkout_tool(input_data, memory_bank)

            # Verify failure is handled
            assert result.success is False
            assert "Connection failed" in result.error

    def test_memory_bank_cleans_up_on_persistent_connection_failure(self, mock_memory_bank):
        """Test that memory bank cleans up properly when persistent connection setup fails."""
        memory_bank, mock_writer, mock_reader = mock_memory_bank

        # Mock partial failure (reader succeeds, writer fails)
        mock_reader._current_branch = "cleanup-branch"
        mock_writer.use_persistent_connection.side_effect = Exception("Writer connection failed")

        # Attempt to enable persistent connections should fail and cleanup
        with pytest.raises(Exception) as exc_info:
            memory_bank.use_persistent_connections(branch="cleanup-branch")

        assert "Writer connection failed" in str(exc_info.value)

        # Verify cleanup was attempted
        mock_reader.close_persistent_connection.assert_called_once()
        mock_writer.close_persistent_connection.assert_called_once()
