"""
Tests for the CreateMemoryBlockTool.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from experiments.src.memory_system.tools.create_memory_block_tool import (
    CreateMemoryBlockInput,
    CreateMemoryBlockOutput,
    create_memory_block,
    create_memory_block_tool,
)
from experiments.src.memory_system.schemas.memory_block import ConfidenceScore
from experiments.src.memory_system.structured_memory_bank import StructuredMemoryBank


@pytest.fixture
def mock_memory_bank():
    """Create a mock StructuredMemoryBank."""
    bank = MagicMock(spec=StructuredMemoryBank)
    bank.get_latest_schema_version.return_value = 1
    bank.create_memory_block.return_value = True
    return bank


@pytest.fixture
def sample_input():
    """Create sample input data."""
    return CreateMemoryBlockInput(
        type="knowledge",
        text="Test memory block content",
        state="draft",
        visibility="internal",
        tags=["test"],
        metadata={"key": "value"},
        source_file="test.md",
        confidence=ConfidenceScore(confidence=0.8, source="test"),
        created_by="test_agent",
    )


def test_create_memory_block_success(mock_memory_bank, sample_input):
    """Test successful memory block creation."""
    result = create_memory_block(sample_input, mock_memory_bank)

    assert result.success is True
    assert result.id is not None
    assert result.error is None
    assert isinstance(result.timestamp, datetime)

    # Verify memory bank was called correctly
    mock_memory_bank.get_latest_schema_version.assert_called_once_with("knowledge")
    mock_memory_bank.create_memory_block.assert_called_once()


def test_create_memory_block_schema_not_found(mock_memory_bank, sample_input):
    """Test memory block creation when schema version is not found."""
    mock_memory_bank.get_latest_schema_version.return_value = None

    result = create_memory_block(sample_input, mock_memory_bank)

    assert result.success is False
    assert result.id is None
    assert "No schema version found" in result.error
    assert isinstance(result.timestamp, datetime)


def test_create_memory_block_persistence_failure(mock_memory_bank, sample_input):
    """Test memory block creation when persistence fails."""
    mock_memory_bank.create_memory_block.return_value = False

    result = create_memory_block(sample_input, mock_memory_bank)

    assert result.success is False
    assert result.id is None
    assert "Failed to persist" in result.error
    assert isinstance(result.timestamp, datetime)


def test_create_memory_block_tool_initialization():
    """Test tool initialization."""
    assert create_memory_block_tool.name == "CreateMemoryBlock"
    assert create_memory_block_tool.memory_linked is True
    assert create_memory_block_tool.input_model == CreateMemoryBlockInput
    assert create_memory_block_tool.output_model == CreateMemoryBlockOutput


def test_create_memory_block_tool_schema():
    """Test tool schema generation."""
    schema = create_memory_block_tool.schema
    assert schema["name"] == "CreateMemoryBlock"
    assert schema["type"] == "function"
    assert schema["memory_linked"] is True
    assert "parameters" in schema
    assert "returns" in schema


def test_create_memory_block_tool_direct_invocation(mock_memory_bank):
    """Test direct tool invocation with kwargs."""
    with patch.object(create_memory_block_tool, "raw_function") as mock_create:
        mock_create.return_value = CreateMemoryBlockOutput(
            success=True, id="test-id", timestamp=datetime.now()
        )

        result = create_memory_block_tool(
            type="knowledge", text="Test content", memory_bank=mock_memory_bank
        )

        assert result["success"] is True
        assert result["id"] == "test-id"
        mock_create.assert_called_once()


def test_create_memory_block_tool_invalid_input():
    """Test tool with invalid input."""
    result = create_memory_block_tool(invalid_field="test")
    assert result["success"] is False
    assert "error" in result
    assert "Validation error" in result["error"]
