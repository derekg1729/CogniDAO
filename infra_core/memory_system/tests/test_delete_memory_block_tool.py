"""
Tests for DeleteMemoryBlockTool - agent-facing delete functionality.

This test file validates the delete tool's core functionality including:
- Basic deletion operations
- Dependency validation
- Error handling
- Integration with the core deletion logic
"""

from datetime import datetime
from unittest.mock import Mock, patch

from infra_core.memory_system.tools.agent_facing.delete_memory_block_tool import (
    delete_memory_block_tool,
    DeleteMemoryBlockToolInput,
    DeleteMemoryBlockToolOutput,
)
from infra_core.memory_system.tools.memory_core.delete_memory_block_models import DeleteErrorCode


class TestDeleteMemoryBlockTool:
    """Test cases for the agent-facing delete memory block tool."""

    def test_successful_deletion(self):
        """Test successful deletion of a memory block."""
        # Arrange
        mock_memory_bank = Mock()
        test_block_id = "12345678-1234-1234-1234-123456789abc"

        # Mock the core function response
        mock_core_result = Mock()
        mock_core_result.success = True
        mock_core_result.id = test_block_id
        mock_core_result.error = None
        mock_core_result.error_code = None
        mock_core_result.deleted_block_type = "task"
        mock_core_result.deleted_block_version = 1
        mock_core_result.timestamp = datetime.now()
        mock_core_result.processing_time_ms = 100.0

        with patch(
            "infra_core.memory_system.tools.agent_facing.delete_memory_block_tool.delete_memory_block_core"
        ) as mock_core:
            mock_core.return_value = mock_core_result

            input_data = DeleteMemoryBlockToolInput(
                block_id=test_block_id,
                validate_dependencies=True,
                author="test_agent",
                change_note="Testing deletion",
            )

            # Act
            result = delete_memory_block_tool(input_data, mock_memory_bank)

            # Assert
            assert isinstance(result, DeleteMemoryBlockToolOutput)
            assert result.success is True
            assert result.id == test_block_id
            assert result.error is None
            assert result.error_code is None
            assert result.deleted_block_type == "task"
            assert result.deleted_block_version == 1
            assert result.processing_time_ms is not None

            # Verify core function was called with correct parameters
            mock_core.assert_called_once()
            core_call_args = mock_core.call_args[0][0]
            assert core_call_args.block_id == test_block_id
            assert core_call_args.validate_dependencies is True
            assert core_call_args.author == "test_agent"
            assert core_call_args.change_note == "Testing deletion"

    def test_deletion_with_block_not_found(self):
        """Test deletion when block doesn't exist."""
        # Arrange
        mock_memory_bank = Mock()
        test_block_id = "87654321-4321-4321-4321-ba9876543210"

        mock_core_result = Mock()
        mock_core_result.success = False
        mock_core_result.id = None
        mock_core_result.error = f"Memory block with ID '{test_block_id}' not found"
        mock_core_result.error_code = DeleteErrorCode.BLOCK_NOT_FOUND
        mock_core_result.deleted_block_type = None
        mock_core_result.deleted_block_version = None
        mock_core_result.timestamp = datetime.now()
        mock_core_result.processing_time_ms = 50.0

        with patch(
            "infra_core.memory_system.tools.agent_facing.delete_memory_block_tool.delete_memory_block_core"
        ) as mock_core:
            mock_core.return_value = mock_core_result

            input_data = DeleteMemoryBlockToolInput(
                block_id=test_block_id, validate_dependencies=True
            )

            # Act
            result = delete_memory_block_tool(input_data, mock_memory_bank)

            # Assert
            assert result.success is False
            assert result.id is None
            assert result.error == f"Memory block with ID '{test_block_id}' not found"
            assert result.error_code == DeleteErrorCode.BLOCK_NOT_FOUND
            assert result.deleted_block_type is None
            assert result.deleted_block_version is None

    def test_deletion_with_dependencies(self):
        """Test deletion when block has dependencies."""
        # Arrange
        mock_memory_bank = Mock()
        test_block_id = "abcdef12-3456-7890-abcd-ef1234567890"

        mock_core_result = Mock()
        mock_core_result.success = False
        mock_core_result.id = None
        mock_core_result.error = (
            f"Cannot delete block {test_block_id} - it has 2 dependent blocks: dep1, dep2"
        )
        mock_core_result.error_code = DeleteErrorCode.DEPENDENCIES_EXIST
        mock_core_result.deleted_block_type = None
        mock_core_result.deleted_block_version = None
        mock_core_result.timestamp = datetime.now()
        mock_core_result.processing_time_ms = 75.0

        with patch(
            "infra_core.memory_system.tools.agent_facing.delete_memory_block_tool.delete_memory_block_core"
        ) as mock_core:
            mock_core.return_value = mock_core_result

            input_data = DeleteMemoryBlockToolInput(
                block_id=test_block_id, validate_dependencies=True
            )

            # Act
            result = delete_memory_block_tool(input_data, mock_memory_bank)

            # Assert
            assert result.success is False
            assert result.error_code == DeleteErrorCode.DEPENDENCIES_EXIST
            assert "dependent blocks" in result.error

    def test_force_deletion_without_dependency_validation(self):
        """Test deletion with dependency validation disabled."""
        # Arrange
        mock_memory_bank = Mock()
        test_block_id = "fedcba09-8765-4321-fedc-ba0987654321"

        mock_core_result = Mock()
        mock_core_result.success = True
        mock_core_result.id = test_block_id
        mock_core_result.error = None
        mock_core_result.error_code = None
        mock_core_result.deleted_block_type = "knowledge"
        mock_core_result.deleted_block_version = 3
        mock_core_result.timestamp = datetime.now()
        mock_core_result.processing_time_ms = 120.0

        with patch(
            "infra_core.memory_system.tools.agent_facing.delete_memory_block_tool.delete_memory_block_core"
        ) as mock_core:
            mock_core.return_value = mock_core_result

            input_data = DeleteMemoryBlockToolInput(
                block_id=test_block_id,
                validate_dependencies=False,  # Force deletion
                author="admin_agent",
            )

            # Act
            result = delete_memory_block_tool(input_data, mock_memory_bank)

            # Assert
            assert result.success is True
            assert result.id == test_block_id

            # Verify dependency validation was disabled
            core_call_args = mock_core.call_args[0][0]
            assert core_call_args.validate_dependencies is False

    def test_exception_handling(self):
        """Test that exceptions are properly handled and returned."""
        # Arrange
        mock_memory_bank = Mock()
        test_block_id = "11111111-2222-3333-4444-555555555555"

        with patch(
            "infra_core.memory_system.tools.agent_facing.delete_memory_block_tool.delete_memory_block_core"
        ) as mock_core:
            mock_core.side_effect = Exception("Unexpected error during deletion")

            input_data = DeleteMemoryBlockToolInput(block_id=test_block_id)

            # Act
            result = delete_memory_block_tool(input_data, mock_memory_bank)

            # Assert
            assert result.success is False
            assert "Error in delete_memory_block wrapper" in result.error
            assert "Unexpected error during deletion" in result.error
            assert result.processing_time_ms is not None

    def test_default_values(self):
        """Test that default values are properly set."""
        # Arrange
        mock_memory_bank = Mock()
        test_block_id = "99999999-8888-7777-6666-555544443333"

        mock_core_result = Mock()
        mock_core_result.success = True
        mock_core_result.id = test_block_id
        mock_core_result.error = None
        mock_core_result.error_code = None
        mock_core_result.deleted_block_type = "project"
        mock_core_result.deleted_block_version = 2
        mock_core_result.timestamp = datetime.now()
        mock_core_result.processing_time_ms = 85.0

        with patch(
            "infra_core.memory_system.tools.agent_facing.delete_memory_block_tool.delete_memory_block_core"
        ) as mock_core:
            mock_core.return_value = mock_core_result

            # Use minimal input to test defaults
            input_data = DeleteMemoryBlockToolInput(block_id=test_block_id)

            # Act
            result = delete_memory_block_tool(input_data, mock_memory_bank)

            # Assert
            assert result.success is True
            core_call_args = mock_core.call_args[0][0]
            assert core_call_args.validate_dependencies is True  # Default
            assert core_call_args.author == "agent"  # Default
            assert core_call_args.agent_id == "cogni_agent"  # Default
            assert core_call_args.change_note is None  # Default
