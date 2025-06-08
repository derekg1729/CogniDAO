"""
Tests for the CreateMemoryBlock tool.
"""

import pytest
from unittest.mock import MagicMock
from infra_core.memory_system.tools.memory_core.create_memory_block_tool import (
    create_memory_block,
    CreateMemoryBlockInput,
    CreateMemoryBlockOutput,
)
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank


class TestCreateMemoryBlockTool:
    @pytest.fixture
    def mock_memory_bank(self):
        """Create a mock StructuredMemoryBank instance."""
        mock = MagicMock(spec=StructuredMemoryBank)
        mock.get_latest_schema_version.return_value = 1
        mock.create_memory_block.return_value = True
        return mock

    def test_create_memory_block_success(self, mock_memory_bank):
        """Test successful memory block creation."""
        # Create input model
        input_data = CreateMemoryBlockInput(
            type="knowledge",
            text="Test knowledge block",
            state="draft",
            visibility="internal",
            tags=["test"],
            metadata={"title": "Test Knowledge", "source": "test"},
        )

        # Call the tool
        result = create_memory_block(input_data=input_data, memory_bank=mock_memory_bank)

        # Verify result
        assert isinstance(result, CreateMemoryBlockOutput)
        assert result.success is True
        assert result.id is not None
        assert result.error is None

        # Verify memory bank calls
        mock_memory_bank.get_latest_schema_version.assert_called_once_with("knowledge")
        mock_memory_bank.create_memory_block.assert_called_once()

    def test_create_memory_block_validation_error(self, mock_memory_bank):
        """Test memory block creation with invalid input."""
        # Create input model with missing required field
        with pytest.raises(ValueError):
            CreateMemoryBlockInput(type="knowledge")  # Missing required 'text' field

    def test_create_memory_block_persistence_error(self, mock_memory_bank):
        """Test memory block creation when persistence fails."""
        # Configure mock to fail persistence
        mock_memory_bank.create_memory_block.return_value = False

        # Create input model
        input_data = CreateMemoryBlockInput(
            type="knowledge", text="Test knowledge block", metadata={"title": "Test Knowledge"}
        )

        # Call the tool
        result = create_memory_block(input_data=input_data, memory_bank=mock_memory_bank)

        # Verify result
        assert isinstance(result, CreateMemoryBlockOutput)
        assert result.success is False
        assert result.id is None
        assert "Failed to persist" in result.error

    def test_create_memory_block_schema_error(self, mock_memory_bank):
        """Test memory block creation when schema version lookup fails."""
        # Configure mock to fail schema lookup
        mock_memory_bank.get_latest_schema_version.return_value = None

        # Create input model
        input_data = CreateMemoryBlockInput(
            type="knowledge", text="Test knowledge block", metadata={"title": "Test Knowledge"}
        )

        # Call the tool
        result = create_memory_block(input_data=input_data, memory_bank=mock_memory_bank)

        # Verify result
        assert isinstance(result, CreateMemoryBlockOutput)
        assert result.success is False
        assert result.id is None
        assert (
            "Schema definition missing or lookup failed for registered type: knowledge"
            in result.error
        )
