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

            # Verify the default was used
            call_args = mock_delete.call_args[0][0]
            assert call_args.validate_dependencies is False  # Should use the default override
