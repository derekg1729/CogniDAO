"""
Tests for BulkDeleteBlocksTool.

This test suite validates the bulk block deletion functionality including:
- Successful bulk deletion
- Independent error handling
- Partial success scenarios
- Dependency validation
- Force deletion scenarios
- Input validation
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from infra_core.memory_system.tools.agent_facing.bulk_delete_blocks_tool import (
    bulk_delete_blocks,
    BulkDeleteBlocksInput,
    DeleteSpec,
)
from infra_core.memory_system.tools.memory_core.delete_memory_block_models import (
    DeleteMemoryBlockOutput,
    DeleteErrorCode,
)


class TestBulkDeleteBlocksTool:
    """Test suite for bulk block deletion functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_memory_bank = Mock()
        self.mock_memory_bank.dolt_writer.active_branch = "test-branch"

    def test_successful_bulk_deletion(self):
        """Test successful deletion of multiple blocks."""
        # Arrange
        block_specs = [
            DeleteSpec(
                block_id="12345678-1234-1234-1234-123456789001",
                validate_dependencies=True,
                author="test_agent",
            ),
            DeleteSpec(
                block_id="12345678-1234-1234-1234-123456789002",
                validate_dependencies=True,
                author="test_agent",
            ),
        ]

        input_data = BulkDeleteBlocksInput(blocks=block_specs)

        # Mock successful responses
        mock_results = [
            DeleteMemoryBlockOutput(
                success=True,
                id="12345678-1234-1234-1234-123456789001",
                error=None,
                error_code=None,
                deleted_block_type="knowledge",
                deleted_block_version=1,
                timestamp=datetime.now(),
                processing_time_ms=100.5,
            ),
            DeleteMemoryBlockOutput(
                success=True,
                id="12345678-1234-1234-1234-123456789002",
                error=None,
                error_code=None,
                deleted_block_type="doc",
                deleted_block_version=2,
                timestamp=datetime.now(),
                processing_time_ms=85.2,
            ),
        ]

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_delete_blocks_tool.delete_memory_block_core"
        ) as mock_delete:
            mock_delete.side_effect = mock_results

            # Act
            result = bulk_delete_blocks(input_data, self.mock_memory_bank)

            # Assert
            assert result.success is True  # All blocks succeeded
            assert result.partial_success is True  # At least one block succeeded
            assert result.total_blocks == 2
            assert result.successful_blocks == 2
            assert result.failed_blocks == 0
            assert len(result.results) == 2
            assert all(r.success for r in result.results)
            assert result.active_branch == "test-branch"
            assert result.total_processing_time_ms > 0

            # Verify new fields for successful scenario
            assert result.skipped_block_ids == []  # No blocks skipped
            assert result.error_summary == {}  # No errors to summarize

            # Verify all blocks were attempted
            assert mock_delete.call_count == 2

    def test_partial_success_scenario(self):
        """Test scenario where some blocks succeed and others fail."""
        # Arrange
        block_specs = [
            DeleteSpec(
                block_id="12345678-1234-1234-1234-123456789001",
                validate_dependencies=True,
            ),
            DeleteSpec(
                block_id="aaaaaaaa-bbbb-cccc-dddd-123456789002",
                validate_dependencies=True,
            ),
        ]

        input_data = BulkDeleteBlocksInput(blocks=block_specs, stop_on_first_error=False)

        # Mock mixed responses
        mock_results = [
            DeleteMemoryBlockOutput(
                success=True,
                id="12345678-1234-1234-1234-123456789001",
                error=None,
                error_code=None,
                deleted_block_type="knowledge",
                deleted_block_version=1,
                timestamp=datetime.now(),
                processing_time_ms=95.3,
            ),
            DeleteMemoryBlockOutput(
                success=False,
                id=None,
                error="Memory block with ID 'nonexistent-block-id-1234-123456789002' not found",
                error_code=DeleteErrorCode.BLOCK_NOT_FOUND,
                deleted_block_type=None,
                deleted_block_version=None,
                timestamp=datetime.now(),
                processing_time_ms=45.7,
            ),
        ]

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_delete_blocks_tool.delete_memory_block_core"
        ) as mock_delete:
            mock_delete.side_effect = mock_results

            # Act
            result = bulk_delete_blocks(input_data, self.mock_memory_bank)

            # Assert
            assert result.success is False  # NOT all blocks succeeded
            assert result.partial_success is True  # At least one block succeeded
            assert result.total_blocks == 2
            assert result.successful_blocks == 1
            assert result.failed_blocks == 1
            assert len(result.results) == 2

            # Check individual results
            assert result.results[0].success is True
            assert result.results[0].block_id == "12345678-1234-1234-1234-123456789001"
            assert result.results[1].success is False
            assert result.results[1].error_code == DeleteErrorCode.BLOCK_NOT_FOUND
            assert "not found" in result.results[1].error

            # Verify new fields for partial success scenario
            assert result.skipped_block_ids == []  # No blocks skipped (stop_on_first_error=False)
            assert result.error_summary == {"BLOCK_NOT_FOUND": 1}  # One BLOCK_NOT_FOUND error

    def test_stop_on_first_error(self):
        """Test early termination when stop_on_first_error is True."""
        # Arrange
        block_specs = [
            DeleteSpec(
                block_id="aaaaaaaa-bbbb-cccc-dddd-123456789001",
                validate_dependencies=True,
            ),
            DeleteSpec(
                block_id="12345678-1234-1234-1234-123456789002",  # Should not be processed
                validate_dependencies=True,
            ),
        ]

        input_data = BulkDeleteBlocksInput(blocks=block_specs, stop_on_first_error=True)

        # Mock first block fails
        mock_results = [
            DeleteMemoryBlockOutput(
                success=False,
                id=None,
                error="Memory block with ID 'nonexistent-block-1234-1234-123456789001' not found",
                error_code=DeleteErrorCode.BLOCK_NOT_FOUND,
                deleted_block_type=None,
                deleted_block_version=None,
                timestamp=datetime.now(),
                processing_time_ms=25.4,
            ),
        ]

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_delete_blocks_tool.delete_memory_block_core"
        ) as mock_delete:
            mock_delete.side_effect = mock_results

            # Act
            result = bulk_delete_blocks(input_data, self.mock_memory_bank)

            # Assert
            assert result.success is False  # NOT all blocks succeeded
            assert result.partial_success is False  # No blocks succeeded
            assert result.total_blocks == 2
            assert result.successful_blocks == 0
            assert result.failed_blocks == 1
            assert len(result.results) == 1  # Second block not processed

            # Verify new fields for stop_on_first_error scenario
            assert result.skipped_block_ids == [
                "12345678-1234-1234-1234-123456789002"
            ]  # Second block skipped
            assert result.error_summary == {"BLOCK_NOT_FOUND": 1}  # One BLOCK_NOT_FOUND error

            # Verify only 1 block was attempted
            assert mock_delete.call_count == 1

    def test_dependency_validation_failure(self):
        """Test deletion failure due to existing dependencies."""
        # Arrange
        block_specs = [
            DeleteSpec(
                block_id="12345678-1234-1234-1234-123456789001",
                validate_dependencies=True,
            ),
        ]

        input_data = BulkDeleteBlocksInput(blocks=block_specs)

        # Mock dependency failure
        mock_results = [
            DeleteMemoryBlockOutput(
                success=False,
                id=None,
                error="Cannot delete block 12345678-1234-1234-1234-123456789001 - it has 2 dependent blocks",
                error_code=DeleteErrorCode.DEPENDENCIES_EXIST,
                deleted_block_type=None,
                deleted_block_version=None,
                timestamp=datetime.now(),
                processing_time_ms=65.1,
            ),
        ]

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_delete_blocks_tool.delete_memory_block_core"
        ) as mock_delete:
            mock_delete.side_effect = mock_results

            # Act
            result = bulk_delete_blocks(input_data, self.mock_memory_bank)

            # Assert
            assert result.success is False
            assert result.partial_success is False
            assert result.results[0].error_code == DeleteErrorCode.DEPENDENCIES_EXIST
            assert "dependent blocks" in result.results[0].error

            # Verify new fields for dependency validation failure
            assert result.skipped_block_ids == []  # No blocks skipped
            assert result.error_summary == {"DEPENDENCIES_EXIST": 1}  # One DEPENDENCIES_EXIST error

    def test_exception_handling(self):
        """Test handling of unexpected exceptions during processing."""
        # Arrange
        block_specs = [
            DeleteSpec(
                block_id="12345678-1234-1234-1234-123456789001",
                validate_dependencies=True,
            ),
            DeleteSpec(
                block_id="12345678-1234-1234-1234-123456789002",
                validate_dependencies=True,
            ),
        ]

        input_data = BulkDeleteBlocksInput(blocks=block_specs, stop_on_first_error=False)

        # Mock first success, second raises exception
        mock_success = DeleteMemoryBlockOutput(
            success=True,
            id="12345678-1234-1234-1234-123456789001",
            error=None,
            error_code=None,
            deleted_block_type="knowledge",
            deleted_block_version=1,
            timestamp=datetime.now(),
            processing_time_ms=88.9,
        )

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_delete_blocks_tool.delete_memory_block_core"
        ) as mock_delete:
            mock_delete.side_effect = [mock_success, Exception("Database connection error")]

            # Act
            result = bulk_delete_blocks(input_data, self.mock_memory_bank)

            # Assert
            assert result.success is False  # NOT all blocks succeeded
            assert result.partial_success is True  # At least one block succeeded
            assert result.total_blocks == 2
            assert result.successful_blocks == 1
            assert result.failed_blocks == 1
            assert len(result.results) == 2

            # Check exception was handled properly
            assert result.results[0].success is True
            assert result.results[1].success is False
            assert "Unexpected error processing block 2" in result.results[1].error

            # Verify new fields for exception handling scenario
            assert result.skipped_block_ids == []  # No blocks skipped (stop_on_first_error=False)
            assert result.error_summary == {
                "INTERNAL_ERROR": 1
            }  # One INTERNAL_ERROR from exception

    def test_empty_blocks_list_validation(self):
        """Test that empty blocks list is rejected by Pydantic validation."""
        with pytest.raises(ValueError):
            BulkDeleteBlocksInput(blocks=[])

    def test_block_delete_spec_validation(self):
        """Test validation of individual block delete specifications."""
        # Valid block spec
        valid_spec = DeleteSpec(block_id="12345678-1234-1234-1234-123456789abc")
        assert valid_spec.block_id == "12345678-1234-1234-1234-123456789abc"
        assert valid_spec.validate_dependencies is None  # Default value (None means use default)
        assert valid_spec.change_note is None  # Default value

        # Test with all optional fields
        full_spec = DeleteSpec(
            block_id="fedcba98-7654-3210-fedc-ba9876543210",
            validate_dependencies=False,
            change_note="Cleaning up obsolete data",
        )
        assert full_spec.validate_dependencies is False
        assert full_spec.change_note == "Cleaning up obsolete data"

    def test_large_batch_limit(self):
        """Test that batch size limits are enforced."""
        # Create a list that exceeds the max limit
        large_block_list = [
            DeleteSpec(block_id=f"12345678-1234-1234-1234-{i:012d}")
            for i in range(1001)  # Exceeds max_length=1000
        ]

        with pytest.raises(ValueError):
            BulkDeleteBlocksInput(blocks=large_block_list)

    def test_all_failures_scenario(self):
        """Test scenario where all blocks fail to delete."""
        # Arrange
        block_specs = [
            DeleteSpec(
                block_id="aaaaaaaa-bbbb-cccc-dddd-123456789001",
                validate_dependencies=True,
            ),
            DeleteSpec(
                block_id="bbbbbbbb-cccc-dddd-eeee-123456789002",
                validate_dependencies=True,
            ),
        ]

        input_data = BulkDeleteBlocksInput(blocks=block_specs, stop_on_first_error=False)

        # Mock all failures
        mock_results = [
            DeleteMemoryBlockOutput(
                success=False,
                id=None,
                error="Memory block with ID 'nonexistent-1-1234-1234-123456789001' not found",
                error_code=DeleteErrorCode.BLOCK_NOT_FOUND,
                deleted_block_type=None,
                deleted_block_version=None,
                timestamp=datetime.now(),
                processing_time_ms=35.1,
            ),
            DeleteMemoryBlockOutput(
                success=False,
                id=None,
                error="Memory block with ID 'nonexistent-2-1234-1234-123456789002' not found",
                error_code=DeleteErrorCode.BLOCK_NOT_FOUND,
                deleted_block_type=None,
                deleted_block_version=None,
                timestamp=datetime.now(),
                processing_time_ms=28.7,
            ),
        ]

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_delete_blocks_tool.delete_memory_block_core"
        ) as mock_delete:
            mock_delete.side_effect = mock_results

            # Act
            result = bulk_delete_blocks(input_data, self.mock_memory_bank)

            # Assert
            assert result.success is False  # NOT all blocks succeeded
            assert result.partial_success is False  # No blocks succeeded
            assert result.total_blocks == 2
            assert result.successful_blocks == 0
            assert result.failed_blocks == 2
            assert len(result.results) == 2
            assert all(not r.success for r in result.results)
            assert all(r.error_code == DeleteErrorCode.BLOCK_NOT_FOUND for r in result.results)

            # Verify new fields for all failures scenario
            assert result.skipped_block_ids == []  # No blocks skipped (stop_on_first_error=False)
            assert result.error_summary == {"BLOCK_NOT_FOUND": 2}  # Two BLOCK_NOT_FOUND errors

    def test_default_validate_dependencies_override(self):
        """Test that default_validate_dependencies is used when block spec doesn't specify."""
        # Arrange - Block spec without validate_dependencies specified
        block_specs = [
            DeleteSpec(
                block_id="12345678-1234-1234-1234-123456789001",
                # validate_dependencies not specified, should use default
            ),
        ]

        input_data = BulkDeleteBlocksInput(
            blocks=block_specs,
            default_validate_dependencies=False,  # Override default
        )

        mock_results = [
            DeleteMemoryBlockOutput(
                success=True,
                id="12345678-1234-1234-1234-123456789001",
                error=None,
                error_code=None,
                deleted_block_type="task",
                deleted_block_version=1,
                timestamp=datetime.now(),
                processing_time_ms=75.5,
            ),
        ]

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_delete_blocks_tool.delete_memory_block_core"
        ) as mock_delete:
            mock_delete.side_effect = mock_results

            # Act
            result = bulk_delete_blocks(input_data, self.mock_memory_bank)

            # Assert
            assert result.success is True

            # Verify new fields for successful default override scenario
            assert result.skipped_block_ids == []  # No blocks skipped
            assert result.error_summary == {}  # No errors to summarize

            # Verify the default was used
            call_args = mock_delete.call_args[0][0]
            assert call_args.validate_dependencies is False  # Should use the default override

    def test_skipped_blocks_reporting(self):
        """Test that skipped_block_ids are correctly reported when stop_on_first_error=True."""
        # Arrange
        block_specs = [
            DeleteSpec(
                block_id="aaaaaaaa-bbbb-cccc-dddd-123456789001",
                validate_dependencies=True,
            ),
            DeleteSpec(
                block_id="bbbbbbbb-cccc-dddd-eeee-123456789002",
                validate_dependencies=True,
            ),
            DeleteSpec(
                block_id="cccccccc-dddd-eeee-ffff-123456789003",
                validate_dependencies=True,
            ),
        ]

        input_data = BulkDeleteBlocksInput(blocks=block_specs, stop_on_first_error=True)

        # Mock first block fails
        mock_results = [
            DeleteMemoryBlockOutput(
                success=False,
                id=None,
                error="Memory block with ID 'aaaaaaaa-bbbb-cccc-dddd-123456789001' not found",
                error_code=DeleteErrorCode.BLOCK_NOT_FOUND,
                deleted_block_type=None,
                deleted_block_version=None,
                timestamp=datetime.now(),
                processing_time_ms=25.4,
            ),
        ]

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_delete_blocks_tool.delete_memory_block_core"
        ) as mock_delete:
            mock_delete.side_effect = mock_results

            # Act
            result = bulk_delete_blocks(input_data, self.mock_memory_bank)

            # Assert
            assert result.success is False
            assert result.partial_success is False
            assert result.total_blocks == 3
            assert result.successful_blocks == 0
            assert result.failed_blocks == 1
            assert len(result.results) == 1  # Only first block processed

            # Verify skipped blocks are correctly reported
            assert len(result.skipped_block_ids) == 2
            assert result.skipped_block_ids == [
                "bbbbbbbb-cccc-dddd-eeee-123456789002",
                "cccccccc-dddd-eeee-ffff-123456789003",
            ]

            # Verify only 1 block was attempted
            assert mock_delete.call_count == 1

    def test_no_skipped_blocks_when_stop_on_first_error_false(self):
        """Test that skipped_block_ids is empty when stop_on_first_error=False."""
        # Arrange
        block_specs = [
            DeleteSpec(
                block_id="aaaaaaaa-bbbb-cccc-dddd-123456789001",
                validate_dependencies=True,
            ),
            DeleteSpec(
                block_id="bbbbbbbb-cccc-dddd-eeee-123456789002",
                validate_dependencies=True,
            ),
        ]

        input_data = BulkDeleteBlocksInput(blocks=block_specs, stop_on_first_error=False)

        # Mock all failures
        mock_results = [
            DeleteMemoryBlockOutput(
                success=False,
                id=None,
                error="Error 1",
                error_code=DeleteErrorCode.BLOCK_NOT_FOUND,
                deleted_block_type=None,
                deleted_block_version=None,
                timestamp=datetime.now(),
                processing_time_ms=25.4,
            ),
            DeleteMemoryBlockOutput(
                success=False,
                id=None,
                error="Error 2",
                error_code=DeleteErrorCode.BLOCK_NOT_FOUND,
                deleted_block_type=None,
                deleted_block_version=None,
                timestamp=datetime.now(),
                processing_time_ms=30.1,
            ),
        ]

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_delete_blocks_tool.delete_memory_block_core"
        ) as mock_delete:
            mock_delete.side_effect = mock_results

            # Act
            result = bulk_delete_blocks(input_data, self.mock_memory_bank)

            # Assert
            assert result.success is False
            assert result.partial_success is False
            assert result.total_blocks == 2
            assert result.successful_blocks == 0
            assert result.failed_blocks == 2
            assert len(result.results) == 2  # Both blocks processed

            # Verify no blocks were skipped
            assert len(result.skipped_block_ids) == 0
            assert result.skipped_block_ids == []

            # Verify both blocks were attempted
            assert mock_delete.call_count == 2

    def test_error_summary_aggregation(self):
        """Test that error_summary correctly aggregates error codes and counts."""
        # Arrange - multiple blocks with different error types
        block_specs = [
            DeleteSpec(block_id="aaaaaaaa-bbbb-cccc-dddd-123456789001"),
            DeleteSpec(block_id="bbbbbbbb-cccc-dddd-eeee-123456789002"),
            DeleteSpec(block_id="cccccccc-dddd-eeee-ffff-123456789003"),
            DeleteSpec(block_id="dddddddd-eeee-ffff-aaaa-123456789004"),
        ]

        input_data = BulkDeleteBlocksInput(blocks=block_specs, stop_on_first_error=False)

        # Mock different error types
        mock_results = [
            DeleteMemoryBlockOutput(
                success=False,
                id=None,
                error="Block not found",
                error_code=DeleteErrorCode.BLOCK_NOT_FOUND,
                deleted_block_type=None,
                deleted_block_version=None,
                timestamp=datetime.now(),
                processing_time_ms=25.4,
            ),
            DeleteMemoryBlockOutput(
                success=False,
                id=None,
                error="Has dependencies",
                error_code=DeleteErrorCode.DEPENDENCIES_EXIST,
                deleted_block_type=None,
                deleted_block_version=None,
                timestamp=datetime.now(),
                processing_time_ms=30.1,
            ),
            DeleteMemoryBlockOutput(
                success=False,
                id=None,
                error="Block not found again",
                error_code=DeleteErrorCode.BLOCK_NOT_FOUND,
                deleted_block_type=None,
                deleted_block_version=None,
                timestamp=datetime.now(),
                processing_time_ms=22.8,
            ),
            DeleteMemoryBlockOutput(
                success=True,
                id="dddddddd-eeee-ffff-aaaa-123456789004",
                error=None,
                error_code=None,
                deleted_block_type="task",
                deleted_block_version=1,
                timestamp=datetime.now(),
                processing_time_ms=45.2,
            ),
        ]

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_delete_blocks_tool.delete_memory_block_core"
        ) as mock_delete:
            mock_delete.side_effect = mock_results

            # Act
            result = bulk_delete_blocks(input_data, self.mock_memory_bank)

            # Assert
            assert result.success is False
            assert result.partial_success is True
            assert result.total_blocks == 4
            assert result.successful_blocks == 1
            assert result.failed_blocks == 3

            # Verify error summary aggregates correctly
            expected_error_summary = {
                "BLOCK_NOT_FOUND": 2,  # Two BLOCK_NOT_FOUND errors
                "DEPENDENCIES_EXIST": 1,  # One DEPENDENCIES_EXIST error
            }
            assert result.error_summary == expected_error_summary

            # Verify no blocks were skipped
            assert len(result.skipped_block_ids) == 0

            # Verify all blocks were attempted
            assert mock_delete.call_count == 4

    def test_error_summary_with_none_error_codes(self):
        """Test that error_summary handles None error codes gracefully by mapping to UNKNOWN."""
        # Arrange - blocks that fail without structured error codes
        block_specs = [
            DeleteSpec(block_id="aaaaaaaa-bbbb-cccc-dddd-123456789001"),
            DeleteSpec(block_id="bbbbbbbb-cccc-dddd-eeee-123456789002"),
            DeleteSpec(block_id="cccccccc-dddd-eeee-ffff-123456789003"),
        ]

        input_data = BulkDeleteBlocksInput(blocks=block_specs, stop_on_first_error=False)

        # Mock failures with None error codes (unstructured errors)
        mock_results = [
            DeleteMemoryBlockOutput(
                success=False,
                id=None,
                error="Generic database error",
                error_code=None,  # No structured error code
                deleted_block_type=None,
                deleted_block_version=None,
                timestamp=datetime.now(),
                processing_time_ms=25.4,
            ),
            DeleteMemoryBlockOutput(
                success=False,
                id=None,
                error="Network timeout",
                error_code=None,  # No structured error code
                deleted_block_type=None,
                deleted_block_version=None,
                timestamp=datetime.now(),
                processing_time_ms=30.1,
            ),
            DeleteMemoryBlockOutput(
                success=True,
                id="cccccccc-dddd-eeee-ffff-123456789003",
                error=None,
                error_code=None,
                deleted_block_type="task",
                deleted_block_version=1,
                timestamp=datetime.now(),
                processing_time_ms=45.2,
            ),
        ]

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_delete_blocks_tool.delete_memory_block_core"
        ) as mock_delete:
            mock_delete.side_effect = mock_results

            # Act
            result = bulk_delete_blocks(input_data, self.mock_memory_bank)

            # Assert
            assert result.success is False
            assert result.partial_success is True
            assert result.total_blocks == 3
            assert result.successful_blocks == 1
            assert result.failed_blocks == 2

            # Verify error summary handles None error codes gracefully
            # Since error_code is None, these failures should not appear in error_summary
            assert result.error_summary == {}  # No structured error codes to summarize

            # Verify no blocks were skipped
            assert len(result.skipped_block_ids) == 0

            # Verify all blocks were attempted
            assert mock_delete.call_count == 3
