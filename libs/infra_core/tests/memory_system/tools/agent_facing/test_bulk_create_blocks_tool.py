"""
Tests for BulkCreateBlocksTool.

This test suite validates the bulk block creation functionality including:
- Successful bulk creation
- Independent error handling
- Partial success scenarios
- Input validation
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from infra_core.memory_system.tools.agent_facing.bulk_create_blocks_tool import (
    bulk_create_blocks,
    BulkCreateBlocksInput,
    BlockSpec,
)
from infra_core.memory_system.tools.memory_core.create_memory_block_tool import (
    CreateMemoryBlockOutput,
)


class TestBulkCreateBlocksTool:
    """Test suite for bulk block creation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_memory_bank = Mock()
        self.mock_memory_bank.dolt_writer.active_branch = "test-branch"
        # Mock the get_latest_schema_version method to return proper integers
        self.mock_memory_bank.get_latest_schema_version.return_value = 1

    def test_successful_bulk_creation(self):
        """Test successful creation of multiple blocks."""
        # Arrange
        block_specs = [
            BlockSpec(
                type="knowledge",
                text="Test knowledge 1",
                metadata={
                    "title": "Knowledge Block 1",
                    "subject": "Testing",
                    "source": "Unit Test",
                },
            ),
            BlockSpec(
                type="doc",
                text="Test doc 1",
                tags=["test"],
                metadata={"title": "Doc Block 1", "audience": "developers", "section": "testing"},
            ),
            BlockSpec(
                type="log",
                text="Test log 1",
                metadata={"log_level": "INFO", "component": "test_suite"},
            ),
        ]

        input_data = BulkCreateBlocksInput(blocks=block_specs)

        # Mock successful responses
        mock_results = [
            CreateMemoryBlockOutput(
                success=True,
                id="12345678-1234-1234-1234-123456789001",
                active_branch="test-branch",
                timestamp=datetime.now(),
            ),
            CreateMemoryBlockOutput(
                success=True,
                id="12345678-1234-1234-1234-123456789002",
                active_branch="test-branch",
                timestamp=datetime.now(),
            ),
            CreateMemoryBlockOutput(
                success=True,
                id="12345678-1234-1234-1234-123456789003",
                active_branch="test-branch",
                timestamp=datetime.now(),
            ),
        ]

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_create_blocks_tool.create_memory_block"
        ) as mock_create:
            mock_create.side_effect = mock_results

            # Act
            result = bulk_create_blocks(input_data, self.mock_memory_bank)

            # Assert - Updated for new semantics
            assert result.success is True  # All blocks succeeded
            assert result.partial_success is True  # At least one block succeeded
            assert result.total_blocks == 3
            assert result.successful_blocks == 3
            assert result.failed_blocks == 0
            assert len(result.results) == 3
            assert all(r.success for r in result.results)
            assert result.active_branch == "test-branch"

            # Verify all blocks were attempted
            assert mock_create.call_count == 3

    def test_partial_success_scenario(self):
        """Test scenario where some blocks succeed and others fail."""
        # Arrange
        block_specs = [
            BlockSpec(
                type="knowledge",
                text="Good block",
                metadata={"title": "Good Knowledge", "subject": "Testing"},
            ),
            BlockSpec(
                type="doc",
                text="Another good block",
                metadata={"title": "Good Doc", "audience": "developers"},
            ),
        ]

        input_data = BulkCreateBlocksInput(blocks=block_specs, stop_on_first_error=False)

        # Mock mixed responses
        mock_results = [
            CreateMemoryBlockOutput(
                success=True,
                id="12345678-1234-1234-1234-123456789001",
                active_branch="test-branch",
                timestamp=datetime.now(),
            ),
            CreateMemoryBlockOutput(
                success=False,
                id=None,
                active_branch="test-branch",
                error="Some validation error",
                timestamp=datetime.now(),
            ),
        ]

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_create_blocks_tool.create_memory_block"
        ) as mock_create:
            mock_create.side_effect = mock_results

            # Act
            result = bulk_create_blocks(input_data, self.mock_memory_bank)

            # Assert - Updated for new semantics
            assert result.success is False  # NOT all blocks succeeded
            assert result.partial_success is True  # At least one block succeeded
            assert result.total_blocks == 2
            assert result.successful_blocks == 1
            assert result.failed_blocks == 1
            assert len(result.results) == 2

            # Check individual results
            assert result.results[0].success is True
            assert result.results[0].id == "12345678-1234-1234-1234-123456789001"
            assert result.results[1].success is False
            assert result.results[1].error == "Some validation error"

    def test_stop_on_first_error(self):
        """Test early termination when stop_on_first_error is True."""
        # Arrange
        block_specs = [
            BlockSpec(
                type="knowledge",
                text="Good block",
                metadata={"title": "Good Knowledge", "subject": "Testing"},
            ),
            BlockSpec(
                type="doc",
                text="Should not be processed",
                metadata={"title": "Unprocessed Doc", "audience": "developers"},
            ),
        ]

        input_data = BulkCreateBlocksInput(blocks=block_specs, stop_on_first_error=True)

        # Mock responses - first fails
        mock_results = [
            CreateMemoryBlockOutput(
                success=False,
                id=None,
                active_branch="test-branch",
                error="Validation error",
                timestamp=datetime.now(),
            ),
        ]

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_create_blocks_tool.create_memory_block"
        ) as mock_create:
            mock_create.side_effect = mock_results

            # Act
            result = bulk_create_blocks(input_data, self.mock_memory_bank)

            # Assert - Updated for new semantics
            assert result.success is False  # NOT all blocks succeeded
            assert result.partial_success is False  # No blocks succeeded
            assert result.total_blocks == 2
            assert result.successful_blocks == 0
            assert result.failed_blocks == 1
            assert len(result.results) == 1  # Second block not processed

            # Verify only 1 block was attempted
            assert mock_create.call_count == 1

    def test_exception_handling(self):
        """Test handling of unexpected exceptions during processing."""
        # Arrange
        block_specs = [
            BlockSpec(
                type="knowledge",
                text="Good block",
                metadata={"title": "Good Knowledge", "subject": "Testing"},
            ),
            BlockSpec(
                type="doc",
                text="Block that causes exception",
                metadata={"title": "Exception Doc", "audience": "developers"},
            ),
        ]

        input_data = BulkCreateBlocksInput(blocks=block_specs, stop_on_first_error=False)

        # Mock first success, second raises exception
        mock_success = CreateMemoryBlockOutput(
            success=True,
            id="12345678-1234-1234-1234-123456789001",
            active_branch="test-branch",
            timestamp=datetime.now(),
        )

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_create_blocks_tool.create_memory_block"
        ) as mock_create:
            mock_create.side_effect = [mock_success, Exception("Unexpected error")]

            # Act
            result = bulk_create_blocks(input_data, self.mock_memory_bank)

            # Assert - Updated for new semantics
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
            BulkCreateBlocksInput(blocks=[])

    def test_block_spec_validation(self):
        """Test validation of individual block specifications."""
        # Valid block spec
        valid_spec = BlockSpec(type="knowledge", text="Valid content")
        assert valid_spec.type == "knowledge"
        assert valid_spec.text == "Valid content"
        assert valid_spec.state == "draft"  # Default value
        assert valid_spec.tags == []  # Default empty list

        # Test with all optional fields
        full_spec = BlockSpec(
            type="doc",
            text="Full content",
            state="published",
            visibility="public",
            tags=["tag1", "tag2"],
            metadata={"key": "value"},
            source_file="test.md",
            created_by="test_agent",
        )
        assert full_spec.state == "published"
        assert full_spec.visibility == "public"
        assert full_spec.tags == ["tag1", "tag2"]
        assert full_spec.metadata == {"key": "value"}

    def test_large_batch_limit(self):
        """Test that batch size limits are enforced."""
        # Create a list that exceeds the max limit
        large_block_list = [
            BlockSpec(type="knowledge", text=f"Block {i}")
            for i in range(1001)  # Exceeds max_length=1000
        ]

        with pytest.raises(ValueError):
            BulkCreateBlocksInput(blocks=large_block_list)

    def test_all_failures_scenario(self):
        """Test scenario where all blocks fail to create."""
        # Arrange
        block_specs = [
            BlockSpec(
                type="knowledge",
                text="Bad block 1",
                metadata={"title": "Bad 1", "subject": "Testing"},
            ),
            BlockSpec(
                type="doc",
                text="Bad block 2",
                metadata={"title": "Bad 2", "audience": "developers"},
            ),
        ]

        input_data = BulkCreateBlocksInput(blocks=block_specs, stop_on_first_error=False)

        # Mock all failures
        mock_results = [
            CreateMemoryBlockOutput(
                success=False,
                id=None,
                active_branch="test-branch",
                error="Error 1",
                timestamp=datetime.now(),
            ),
            CreateMemoryBlockOutput(
                success=False,
                id=None,
                active_branch="test-branch",
                error="Error 2",
                timestamp=datetime.now(),
            ),
        ]

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_create_blocks_tool.create_memory_block"
        ) as mock_create:
            mock_create.side_effect = mock_results

            # Act
            result = bulk_create_blocks(input_data, self.mock_memory_bank)

            # Assert - Updated for new semantics
            assert result.success is False  # NOT all blocks succeeded
            assert result.partial_success is False  # No blocks succeeded
            assert result.total_blocks == 2
            assert result.successful_blocks == 0
            assert result.failed_blocks == 2
            assert len(result.results) == 2
            assert all(not r.success for r in result.results)
