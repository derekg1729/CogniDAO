"""
Tests for BulkUpdateNamespaceTool: Agent-facing tool for bulk namespace updates.

Tests cover successful operations, error handling, validation, and edge cases.
"""

from unittest.mock import Mock, patch
from datetime import datetime

from infra_core.memory_system.tools.agent_facing.bulk_update_namespace_tool import (
    bulk_update_namespace,
    BulkUpdateNamespaceInput,
    BlockUpdateSpec,
    bulk_update_namespace_tool,
)
from infra_core.memory_system.tools.memory_core.update_memory_block_models import UpdateErrorCode
from infra_core.memory_system.schemas.memory_block import MemoryBlock


class TestBulkUpdateNamespaceTool:
    """Test suite for bulk namespace update functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_memory_bank = Mock()
        self.mock_memory_bank.dolt_writer.active_branch = "test-branch"
        self.mock_memory_bank.branch = "test-branch"  # Ensure branch consistency

        # Mock add_to_staging to return success by default
        self.mock_memory_bank.dolt_writer.add_to_staging.return_value = (
            True,
            "Successfully staged changes for tables: ['memory_blocks', 'block_properties', 'block_links', 'block_proofs']",
        )

        # Mock commit_changes to return success by default
        self.mock_memory_bank.dolt_writer.commit_changes.return_value = (
            True,
            "mock_commit_hash_123",
        )

        # Mock get_diff_summary for guardrail check (simulate staged changes)
        self.mock_memory_bank.dolt_writer.get_diff_summary.return_value = [
            {"table_name": "memory_blocks", "rows_added": 0, "rows_deleted": 0, "rows_modified": 2}
        ]

        # Mock discard_changes for rollback scenarios
        self.mock_memory_bank.dolt_writer.discard_changes.return_value = None

        # Mock _store_block_proof method
        self.mock_memory_bank._store_block_proof.return_value = True

        # Create mock memory blocks with valid UUIDs
        self.mock_block_1 = Mock(spec=MemoryBlock)
        self.mock_block_1.id = "12345678-1234-1234-1234-123456789abc"
        self.mock_block_1.namespace_id = "old-namespace"
        self.mock_block_1.block_version = 1

        self.mock_block_2 = Mock(spec=MemoryBlock)
        self.mock_block_2.id = "87654321-4321-4321-4321-abcdef123456"
        self.mock_block_2.namespace_id = "old-namespace"
        self.mock_block_2.block_version = 1

    def test_successful_bulk_namespace_update(self):
        """Test successful update of multiple block namespaces."""

        # Setup: Configure mock to return blocks
        def mock_get_memory_block(block_id):
            if block_id == "12345678-1234-1234-1234-123456789abc":
                return self.mock_block_1
            elif block_id == "87654321-4321-4321-4321-abcdef123456":
                return self.mock_block_2
            return None

        self.mock_memory_bank.get_memory_block.side_effect = mock_get_memory_block

        # Mock successful update results
        def mock_update_core(input_data, memory_bank):
            result = Mock()
            result.success = True
            result.error = None
            result.error_code = None
            result.new_version = 2
            result.timestamp = datetime.now()
            result.processing_time_ms = 50.0
            return result

        # Setup input data
        input_data = BulkUpdateNamespaceInput(
            blocks=[
                BlockUpdateSpec(block_id="12345678-1234-1234-1234-123456789abc"),
                BlockUpdateSpec(block_id="87654321-4321-4321-4321-abcdef123456"),
            ],
            target_namespace_id="new-namespace",
            author="test-agent",
        )

        # Mock namespace validation
        with patch(
            "infra_core.memory_system.tools.agent_facing.dolt_namespace_tool.list_namespaces_tool"
        ) as mock_list_namespaces:
            mock_namespace = Mock()
            mock_namespace.id = "new-namespace"
            mock_list_namespaces.return_value = Mock(success=True, namespaces=[mock_namespace])

            # Mock update_memory_block_core
            with patch(
                "infra_core.memory_system.tools.agent_facing.bulk_update_namespace_tool.update_memory_block_core",
                side_effect=mock_update_core,
            ):
                # Execute the bulk update
                result = bulk_update_namespace(input_data, self.mock_memory_bank)

                # Assert successful operation
                assert result.success is True
                assert result.partial_success is True
                assert result.total_blocks == 2
                assert result.successful_blocks == 2
                assert result.failed_blocks == 0
                assert result.target_namespace_id == "new-namespace"
                assert result.namespace_validated is True
                assert len(result.results) == 2

                # Check individual results
                for block_result in result.results:
                    assert block_result.success is True
                    assert block_result.error is None
                    assert block_result.previous_namespace == "old-namespace"
                    assert block_result.new_namespace == "new-namespace"
                    assert block_result.block_version == 2

                # Verify commit was called
                self.mock_memory_bank.dolt_writer.commit_changes.assert_called_once()

    def test_namespace_validation_failure(self):
        """Test behavior when target namespace doesn't exist."""
        # Setup input data
        input_data = BulkUpdateNamespaceInput(
            blocks=[BlockUpdateSpec(block_id="12345678-1234-1234-1234-123456789abc")],
            target_namespace_id="nonexistent-namespace",
            author="test-agent",
        )

        # Mock namespace validation to return empty list
        with patch(
            "infra_core.memory_system.tools.agent_facing.dolt_namespace_tool.list_namespaces_tool"
        ) as mock_list_namespaces:
            mock_namespace = Mock()
            mock_namespace.id = "existing-namespace"
            mock_list_namespaces.return_value = Mock(success=True, namespaces=[mock_namespace])

            # Execute the bulk update
            result = bulk_update_namespace(input_data, self.mock_memory_bank)

            # Assert failure due to invalid namespace
            assert result.success is False
            assert result.partial_success is False
            assert result.total_blocks == 1
            assert result.successful_blocks == 0
            assert result.failed_blocks == 1
            assert result.target_namespace_id == "nonexistent-namespace"
            assert result.namespace_validated is False

            # Check error details
            assert len(result.results) == 1
            assert result.results[0].success is False
            assert "does not exist" in result.results[0].error
            assert result.results[0].error_code == UpdateErrorCode.VALIDATION_ERROR

            # Verify no commit was attempted
            self.mock_memory_bank.dolt_writer.commit_changes.assert_not_called()

    def test_block_not_found_error(self):
        """Test behavior when blocks don't exist."""
        # Setup: Mock returns None for get_memory_block
        self.mock_memory_bank.get_memory_block.return_value = None

        # Setup input data
        input_data = BulkUpdateNamespaceInput(
            blocks=[BlockUpdateSpec(block_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")],
            target_namespace_id="new-namespace",
            author="test-agent",
        )

        # Mock namespace validation
        with patch(
            "infra_core.memory_system.tools.agent_facing.dolt_namespace_tool.list_namespaces_tool"
        ) as mock_list_namespaces:
            mock_namespace = Mock()
            mock_namespace.id = "new-namespace"
            mock_list_namespaces.return_value = Mock(success=True, namespaces=[mock_namespace])

            # Execute the bulk update
            result = bulk_update_namespace(input_data, self.mock_memory_bank)

            # Assert failure due to missing block
            assert result.success is False
            assert result.partial_success is False
            assert result.total_blocks == 1
            assert result.successful_blocks == 0
            assert result.failed_blocks == 1

            # Check error details
            assert len(result.results) == 1
            assert result.results[0].success is False
            assert "not found" in result.results[0].error
            assert result.results[0].error_code == UpdateErrorCode.BLOCK_NOT_FOUND

    def test_skip_blocks_already_in_target_namespace(self):
        """Test that blocks already in target namespace are correctly skipped."""
        # Setup: Block is already in target namespace
        self.mock_block_1.namespace_id = "target-namespace"
        self.mock_memory_bank.get_memory_block.return_value = self.mock_block_1

        # Setup input data
        input_data = BulkUpdateNamespaceInput(
            blocks=[BlockUpdateSpec(block_id="12345678-1234-1234-1234-123456789abc")],
            target_namespace_id="target-namespace",
            author="test-agent",
        )

        # Mock namespace validation
        with patch(
            "infra_core.memory_system.tools.agent_facing.dolt_namespace_tool.list_namespaces_tool"
        ) as mock_list_namespaces:
            mock_namespace = Mock()
            mock_namespace.id = "target-namespace"
            mock_list_namespaces.return_value = Mock(success=True, namespaces=[mock_namespace])

            # Execute the bulk update
            result = bulk_update_namespace(input_data, self.mock_memory_bank)

            # Assert successful operation (no updates needed)
            assert result.success is True
            assert result.partial_success is True
            assert result.total_blocks == 1
            assert result.successful_blocks == 1
            assert result.failed_blocks == 0

            # Check that block was marked as successful without actual update
            assert len(result.results) == 1
            assert result.results[0].success is True
            assert result.results[0].previous_namespace == "target-namespace"
            assert result.results[0].new_namespace == "target-namespace"

    def test_commit_failure_rollback(self):
        """Test rollback behavior when commit fails."""
        # Setup: Configure mock to return block
        self.mock_memory_bank.get_memory_block.return_value = self.mock_block_1

        # Mock staging success but commit failure
        self.mock_memory_bank.dolt_writer.add_to_staging.return_value = (
            True,
            "Successfully staged changes",
        )
        self.mock_memory_bank.dolt_writer.commit_changes.return_value = (False, None)

        # Mock successful update core
        def mock_update_core(input_data, memory_bank):
            result = Mock()
            result.success = True
            result.error = None
            result.error_code = None
            result.new_version = 2
            result.timestamp = datetime.now()
            result.processing_time_ms = 50.0
            return result

        # Setup input data
        input_data = BulkUpdateNamespaceInput(
            blocks=[BlockUpdateSpec(block_id="12345678-1234-1234-1234-123456789abc")],
            target_namespace_id="new-namespace",
            author="test-agent",
        )

        # Mock namespace validation
        with patch(
            "infra_core.memory_system.tools.agent_facing.dolt_namespace_tool.list_namespaces_tool"
        ) as mock_list_namespaces:
            mock_namespace = Mock()
            mock_namespace.id = "new-namespace"
            mock_list_namespaces.return_value = Mock(success=True, namespaces=[mock_namespace])

            # Mock update_memory_block_core
            with patch(
                "infra_core.memory_system.tools.agent_facing.bulk_update_namespace_tool.update_memory_block_core",
                side_effect=mock_update_core,
            ):
                # Execute the bulk update
                result = bulk_update_namespace(input_data, self.mock_memory_bank)

                # Assert failure due to commit issue
                assert result.success is False
                assert result.partial_success is False
                assert result.total_blocks == 1
                assert result.successful_blocks == 0
                assert result.failed_blocks == 1

                # Check that result was marked as failed due to commit failure
                assert len(result.results) == 1
                assert result.results[0].success is False
                assert "commit failed" in result.results[0].error.lower()

                # Verify rollback was called (might be called more than once due to exception handling)
                assert self.mock_memory_bank.dolt_writer.discard_changes.call_count >= 1

    def test_stop_on_first_error(self):
        """Test that stop_on_first_error halts processing correctly."""

        # Setup: First block doesn't exist
        def mock_get_memory_block(block_id):
            if block_id == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb":
                return None
            return self.mock_block_1

        self.mock_memory_bank.get_memory_block.side_effect = mock_get_memory_block

        # Setup input data with stop_on_first_error=True
        input_data = BulkUpdateNamespaceInput(
            blocks=[
                BlockUpdateSpec(block_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
                BlockUpdateSpec(block_id="12345678-1234-1234-1234-123456789abc"),
            ],
            target_namespace_id="new-namespace",
            stop_on_first_error=True,
            author="test-agent",
        )

        # Mock namespace validation
        with patch(
            "infra_core.memory_system.tools.agent_facing.dolt_namespace_tool.list_namespaces_tool"
        ) as mock_list_namespaces:
            mock_namespace = Mock()
            mock_namespace.id = "new-namespace"
            mock_list_namespaces.return_value = Mock(success=True, namespaces=[mock_namespace])

            # Execute the bulk update
            result = bulk_update_namespace(input_data, self.mock_memory_bank)

            # Assert processing stopped after first error
            assert result.success is False
            assert result.partial_success is False
            assert result.total_blocks == 2
            assert result.successful_blocks == 0
            assert result.failed_blocks == 1

            # Check that only first block was processed
            assert len(result.results) == 1
            assert result.results[0].block_id == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
            assert result.results[0].success is False

            # Check that second block was skipped
            assert len(result.skipped_block_ids) == 1
            assert result.skipped_block_ids[0] == "12345678-1234-1234-1234-123456789abc"

    def test_agent_facing_tool_wrapper(self):
        """Test the agent-facing tool wrapper function."""
        # Test valid input
        input_dict = {
            "blocks": [{"block_id": "12345678-1234-1234-1234-123456789abc"}],
            "target_namespace_id": "new-namespace",
        }

        # Mock the bulk_update_namespace function
        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_update_namespace_tool.bulk_update_namespace"
        ) as mock_bulk_update:
            mock_result = Mock()
            mock_result.dict.return_value = {"success": True, "total_blocks": 1}
            mock_bulk_update.return_value = mock_result

            result = bulk_update_namespace_tool(input_dict, self.mock_memory_bank)

            assert result["success"] is True
            assert result["total_blocks"] == 1
            mock_bulk_update.assert_called_once()

    def test_agent_facing_tool_invalid_input(self):
        """Test agent-facing tool wrapper with invalid input."""
        # Test invalid input (missing required fields)
        input_dict = {"invalid": "data"}

        result = bulk_update_namespace_tool(input_dict, self.mock_memory_bank)

        assert result["success"] is False
        assert "Invalid input" in result["error"]
        assert "timestamp" in result

    def test_error_summary_generation(self):
        """Test that error summary is correctly generated."""

        # Setup: Mix of different error types
        def mock_get_memory_block(block_id):
            if block_id in [
                "cccccccc-cccc-cccc-cccc-cccccccccccc",
                "dddddddd-dddd-dddd-dddd-dddddddddddd",
            ]:
                return None
            return self.mock_block_1

        self.mock_memory_bank.get_memory_block.side_effect = mock_get_memory_block

        # Setup input data
        input_data = BulkUpdateNamespaceInput(
            blocks=[
                BlockUpdateSpec(block_id="cccccccc-cccc-cccc-cccc-cccccccccccc"),
                BlockUpdateSpec(block_id="dddddddd-dddd-dddd-dddd-dddddddddddd"),
            ],
            target_namespace_id="new-namespace",
            author="test-agent",
        )

        # Mock namespace validation
        with patch(
            "infra_core.memory_system.tools.agent_facing.dolt_namespace_tool.list_namespaces_tool"
        ) as mock_list_namespaces:
            mock_namespace = Mock()
            mock_namespace.id = "new-namespace"
            mock_list_namespaces.return_value = Mock(success=True, namespaces=[mock_namespace])

            # Execute the bulk update
            result = bulk_update_namespace(input_data, self.mock_memory_bank)

            # Check error summary
            assert "BLOCK_NOT_FOUND" in result.error_summary
            assert result.error_summary["BLOCK_NOT_FOUND"] == 2
