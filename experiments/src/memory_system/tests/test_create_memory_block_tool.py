import pytest
from unittest.mock import MagicMock
from experiments.src.memory_system.tools.create_memory_block_tool import (
    create_memory_block_tool,
)
from experiments.src.memory_system.structured_memory_bank import StructuredMemoryBank


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
        # Call the tool with keyword arguments
        result = create_memory_block_tool(
            type="knowledge",
            text="Test knowledge block",
            state="draft",
            visibility="internal",
            tags=["test"],
            metadata={"source": "test"},
            memory_bank=mock_memory_bank,
        )

        # Verify result
        assert isinstance(result, dict)  # Result should be a dict since output_model is converted
        assert result["success"] is True
        assert result["id"] is not None
        assert result["error"] is None

        # Verify memory bank calls
        mock_memory_bank.get_latest_schema_version.assert_called_once_with("knowledge")
        mock_memory_bank.create_memory_block.assert_called_once()

    def test_create_memory_block_validation_error(self, mock_memory_bank):
        """Test memory block creation with invalid input."""
        # Call with missing required field
        result = create_memory_block_tool(
            type="knowledge",  # Missing required 'text' field
            memory_bank=mock_memory_bank,
        )

        # Verify validation error
        assert isinstance(result, dict)
        assert result["success"] is False
        assert "error" in result
        assert "Validation error" in result["error"]

    def test_create_memory_block_persistence_error(self, mock_memory_bank):
        """Test memory block creation when persistence fails."""
        # Configure mock to fail persistence
        mock_memory_bank.create_memory_block.return_value = False

        # Call the tool
        result = create_memory_block_tool(
            type="knowledge", text="Test knowledge block", memory_bank=mock_memory_bank
        )

        # Verify result
        assert isinstance(result, dict)
        assert result["success"] is False
        assert result["id"] is None
        assert result["error"] is not None

    def test_create_memory_block_schema_error(self, mock_memory_bank):
        """Test memory block creation when schema version lookup fails."""
        # Configure mock to fail schema lookup
        mock_memory_bank.get_latest_schema_version.return_value = None

        # Call the tool
        result = create_memory_block_tool(
            type="knowledge", text="Test knowledge block", memory_bank=mock_memory_bank
        )

        # Verify result
        assert isinstance(result, dict)
        assert result["success"] is False
        assert result["id"] is None
        assert "No schema version found" in result["error"]
