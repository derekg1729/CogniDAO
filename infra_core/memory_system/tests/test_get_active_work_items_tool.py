"""
Tests for the GetActiveWorkItems tool.

Tests both core and agent-facing implementations.
"""

import pytest
import uuid
from unittest.mock import MagicMock, patch
from datetime import datetime
from pydantic import ValidationError

from infra_core.memory_system.schemas.memory_block import MemoryBlock
from infra_core.memory_system.tools.agent_facing.get_active_work_items_tool import (
    get_active_work_items_tool,
    get_active_work_items,
    GetActiveWorkItemsInput,
    GetActiveWorkItemsOutput,
)


def create_mock_work_item(
    block_id: str,
    work_item_type: str = "task",
    priority: str = "P1",
    status: str = "in_progress",
    title: str = "Test Work Item",
) -> MemoryBlock:
    """Create a mock MemoryBlock work item for testing."""
    return MemoryBlock(
        id=block_id,
        type=work_item_type,
        schema_version=5,
        text=f"Test {work_item_type} content",
        state="draft",
        visibility="internal",
        block_version=1,
        parent_id=None,
        has_children=False,
        tags=[],
        metadata={
            "status": status,
            "priority": priority,
            "title": title,
            "assignee": "test-user",
            "description": f"Test {work_item_type} description",
        },
        source_file=None,
        source_uri=None,
        confidence=None,
        created_by="test-agent",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        embedding=None,
    )


class TestGetActiveWorkItemsCore:
    """Test suite for the core get_active_work_items functionality."""

    @pytest.fixture
    def memory_bank(self):
        """Create a mock memory bank for testing."""
        mock_memory_bank = MagicMock()
        return mock_memory_bank

    @pytest.fixture
    def sample_work_items(self):
        """Generate sample work items for testing."""
        items = [
            create_mock_work_item(str(uuid.uuid4()), "task", "P0", "in_progress", "Critical Task"),
            create_mock_work_item(str(uuid.uuid4()), "bug", "P1", "in_progress", "Important Bug"),
            create_mock_work_item(
                str(uuid.uuid4()), "project", "P2", "in_progress", "Medium Project"
            ),
            create_mock_work_item(str(uuid.uuid4()), "epic", "P3", "in_progress", "Low Epic"),
            create_mock_work_item(
                str(uuid.uuid4()), "task", "P0", "done", "Completed Task"
            ),  # Not active
        ]
        return items

    def test_get_active_work_items_success(self, memory_bank, sample_work_items):
        """Test successful retrieval of active work items."""
        # Setup - filter to only in_progress items
        active_items = [
            item for item in sample_work_items if item.metadata["status"] == "in_progress"
        ]

        with patch(
            "infra_core.memory_system.tools.agent_facing.get_active_work_items_tool.get_memory_block_core"
        ) as mock_get_blocks:
            mock_get_blocks.return_value.success = True
            mock_get_blocks.return_value.blocks = active_items

            # Execute
            input_data = GetActiveWorkItemsInput()
            result = get_active_work_items(input_data, memory_bank)

            # Assert
            assert result.success is True
            assert len(result.work_items) == 4  # 4 active items
            assert result.total_count == 4
            assert result.error is None

            # Verify items are sorted by priority (P0 first)
            priorities = [item.metadata["priority"] for item in result.work_items]
            assert priorities[0] == "P0"  # Highest priority first

    def test_get_active_work_items_with_priority_filter(self, memory_bank, sample_work_items):
        """Test filtering by specific priority level."""
        # Setup - filter to only P0 and P1 items that are in_progress
        filtered_items = [
            item
            for item in sample_work_items
            if item.metadata["status"] == "in_progress"
            and item.metadata["priority"] in ["P0", "P1"]
        ]

        with patch(
            "infra_core.memory_system.tools.agent_facing.get_active_work_items_tool.get_memory_block_core"
        ) as mock_get_blocks:
            mock_get_blocks.return_value.success = True
            mock_get_blocks.return_value.blocks = filtered_items

            # Execute
            input_data = GetActiveWorkItemsInput(priority_filter="P1")
            result = get_active_work_items(input_data, memory_bank)

            # Assert
            assert result.success is True
            assert len(result.work_items) == 2  # P0 and P1 items
            assert all(item.metadata["priority"] in ["P0", "P1"] for item in result.work_items)

    def test_get_active_work_items_with_type_filter(self, memory_bank, sample_work_items):
        """Test filtering by specific work item type."""
        # Setup - filter to only task items that are in_progress
        filtered_items = [
            item
            for item in sample_work_items
            if item.metadata["status"] == "in_progress" and item.type == "task"
        ]

        with patch(
            "infra_core.memory_system.tools.agent_facing.get_active_work_items_tool.get_memory_block_core"
        ) as mock_get_blocks:
            mock_get_blocks.return_value.success = True
            mock_get_blocks.return_value.blocks = filtered_items

            # Execute
            input_data = GetActiveWorkItemsInput(work_item_type_filter="task")
            result = get_active_work_items(input_data, memory_bank)

            # Assert
            assert result.success is True
            assert len(result.work_items) == 1  # 1 task item
            assert all(item.type == "task" for item in result.work_items)

    def test_get_active_work_items_with_limit(self, memory_bank, sample_work_items):
        """Test limiting the number of results."""
        # Setup - only active items
        active_items = [
            item for item in sample_work_items if item.metadata["status"] == "in_progress"
        ]

        with patch(
            "infra_core.memory_system.tools.agent_facing.get_active_work_items_tool.get_memory_block_core"
        ) as mock_get_blocks:
            mock_get_blocks.return_value.success = True
            mock_get_blocks.return_value.blocks = active_items[:2]  # Simulate limit applied

            # Execute
            input_data = GetActiveWorkItemsInput(limit=2)
            result = get_active_work_items(input_data, memory_bank)

            # Assert
            assert result.success is True
            assert len(result.work_items) == 2
            assert result.total_count == 2

    def test_get_active_work_items_no_results(self, memory_bank):
        """Test handling when no active work items are found."""
        with patch(
            "infra_core.memory_system.tools.agent_facing.get_active_work_items_tool.get_memory_block_core"
        ) as mock_get_blocks:
            mock_get_blocks.return_value.success = True
            mock_get_blocks.return_value.blocks = []

            # Execute
            input_data = GetActiveWorkItemsInput()
            result = get_active_work_items(input_data, memory_bank)

            # Assert
            assert result.success is True
            assert len(result.work_items) == 0
            assert result.total_count == 0
            assert result.error is None

    def test_get_active_work_items_memory_bank_error(self, memory_bank):
        """Test handling of memory bank errors."""
        with patch(
            "infra_core.memory_system.tools.agent_facing.get_active_work_items_tool.get_memory_block_core"
        ) as mock_get_blocks:
            mock_get_blocks.return_value.success = False
            mock_get_blocks.return_value.error = "Database connection failed"

            # Execute
            input_data = GetActiveWorkItemsInput()
            result = get_active_work_items(input_data, memory_bank)

            # Assert
            assert result.success is False
            assert result.error == "Database connection failed"  # Direct error, no prefix
            assert len(result.work_items) == 0

    def test_invalid_limit_values(self):
        """Test validation of limit parameter."""
        # Test limit too low
        with pytest.raises(ValidationError):
            GetActiveWorkItemsInput(limit=0)

        # Test limit too high
        with pytest.raises(ValidationError):
            GetActiveWorkItemsInput(limit=201)

    def test_invalid_priority_filter(self):
        """Test validation of priority filter."""
        with pytest.raises(ValidationError):
            GetActiveWorkItemsInput(priority_filter="P6")  # Invalid priority

    def test_invalid_work_item_type_filter(self):
        """Test validation of work item type filter."""
        with pytest.raises(ValidationError):
            GetActiveWorkItemsInput(work_item_type_filter="invalid_type")


class TestGetActiveWorkItemsTool:
    """Test suite for the tool wrapper function."""

    @pytest.fixture
    def memory_bank(self):
        """Create a mock memory bank for testing."""
        return MagicMock()

    def test_tool_wrapper_success(self, memory_bank):
        """Test the tool wrapper function with valid inputs."""
        with patch(
            "infra_core.memory_system.tools.agent_facing.get_active_work_items_tool.get_active_work_items"
        ) as mock_core:
            mock_core.return_value = GetActiveWorkItemsOutput(
                success=True,
                work_items=[],
                total_count=0,
                timestamp=datetime.now(),
            )

            # Execute
            result = get_active_work_items_tool(
                priority_filter="P1",
                work_item_type_filter="task",
                limit=10,
                memory_bank=memory_bank,
            )

            # Assert
            assert result.success is True
            mock_core.assert_called_once()

    def test_tool_wrapper_input_validation_error(self, memory_bank):
        """Test tool wrapper handling of input validation errors."""
        # Execute with invalid priority
        result = get_active_work_items_tool(
            priority_filter="P10",  # Invalid priority
            memory_bank=memory_bank,
        )

        # Assert
        assert result.success is False
        assert "Validation error:" in result.error  # Matches actual error format

    def test_tool_wrapper_exception_handling(self, memory_bank):
        """Test tool wrapper handling of unexpected exceptions."""
        with patch(
            "infra_core.memory_system.tools.agent_facing.get_active_work_items_tool.get_active_work_items"
        ) as mock_core:
            mock_core.side_effect = Exception("Unexpected error")

            # Execute
            result = get_active_work_items_tool(memory_bank=memory_bank)

            # Assert
            assert result.success is False
            assert (
                "Validation error:" in result.error
            )  # Tool wrapper catches all exceptions as validation errors
