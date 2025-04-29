"""
Tests for the CreateMemoryBlock tool.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

from experiments.src.memory_system.tools.memory_core.create_memory_block_tool import (
    CreateMemoryBlockInput,
    CreateMemoryBlockOutput,
    create_memory_block,
    CogniTool,
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
    """Create a sample input for testing."""
    return CreateMemoryBlockInput(
        type="knowledge",
        text="Test memory block content",
        state="draft",
        visibility="internal",
        tags=["test"],
        metadata={"key": "value"},
        source_file="test.md",
        confidence=ConfidenceScore(),
        created_by="test_agent",
    )


def test_create_memory_block_success(mock_memory_bank, sample_input):
    """Test successful memory block creation."""
    result = create_memory_block(sample_input, mock_memory_bank)

    assert isinstance(result, dict)
    assert result["success"] is True
    assert result["id"] is not None
    assert result["error"] is None
    assert isinstance(result["timestamp"], datetime)

    mock_memory_bank.get_latest_schema_version.assert_called_once_with("knowledge")
    mock_memory_bank.create_memory_block.assert_called_once()


def test_create_memory_block_schema_not_found(mock_memory_bank, sample_input):
    """Test memory block creation when schema version is not found."""
    mock_memory_bank.get_latest_schema_version.return_value = None

    result = create_memory_block(sample_input, mock_memory_bank)

    assert isinstance(result, dict)
    assert result["success"] is False
    assert result["id"] is None
    assert "No schema version found" in result["error"]


def test_create_memory_block_persistence_failure(mock_memory_bank, sample_input):
    """Test memory block creation when persistence fails."""
    mock_memory_bank.create_memory_block.return_value = False

    result = create_memory_block(sample_input, mock_memory_bank)

    assert isinstance(result, dict)
    assert result["success"] is False
    assert result["id"] is None
    assert "Failed to persist" in result["error"]


def test_create_memory_block_tool_initialization():
    """Test CogniTool initialization with CreateMemoryBlock."""
    tool = CogniTool(
        name="CreateMemoryBlock",
        description="Test description",
        input_model=CreateMemoryBlockInput,
        output_model=CreateMemoryBlockOutput,
        function=create_memory_block,
        memory_linked=True,
    )

    assert tool.name == "CreateMemoryBlock"
    assert tool.memory_linked is True
    assert tool.input_model == CreateMemoryBlockInput
    assert tool.output_model == CreateMemoryBlockOutput


def test_create_memory_block_tool_schema():
    """Test schema generation for CreateMemoryBlock tool."""
    tool = CogniTool(
        name="CreateMemoryBlock",
        description="Test description",
        input_model=CreateMemoryBlockInput,
        output_model=CreateMemoryBlockOutput,
        function=create_memory_block,
        memory_linked=True,
    )

    schema = tool.schema
    assert schema["name"] == "CreateMemoryBlock"
    assert schema["type"] == "function"
    assert schema["memory_linked"] is True
    assert "parameters" in schema
    assert "returns" in schema


def test_create_memory_block_tool_direct_invocation(mock_memory_bank, sample_input):
    """Test direct invocation of CreateMemoryBlock tool."""
    tool = CogniTool(
        name="CreateMemoryBlock",
        description="Test description",
        input_model=CreateMemoryBlockInput,
        output_model=CreateMemoryBlockOutput,
        function=create_memory_block,
        memory_linked=True,
    )

    result = tool(
        type=sample_input.type,
        text=sample_input.text,
        state=sample_input.state,
        visibility=sample_input.visibility,
        tags=sample_input.tags,
        metadata=sample_input.metadata,
        source_file=sample_input.source_file,
        confidence=sample_input.confidence,
        created_by=sample_input.created_by,
        memory_bank=mock_memory_bank,
    )

    assert isinstance(result, dict)
    assert result["success"] is True
    assert result["id"] is not None
    assert result["error"] is None


def test_create_memory_block_tool_invalid_input(mock_memory_bank):
    """Test CreateMemoryBlock tool with invalid input."""
    tool = CogniTool(
        name="CreateMemoryBlock",
        description="Test description",
        input_model=CreateMemoryBlockInput,
        output_model=CreateMemoryBlockOutput,
        function=create_memory_block,
        memory_linked=True,
    )

    result = tool(type="knowledge", memory_bank=mock_memory_bank)  # Missing required 'text' field

    assert isinstance(result, dict)
    assert result["success"] is False
    assert "error" in result
    assert "Validation error" in result["error"]
