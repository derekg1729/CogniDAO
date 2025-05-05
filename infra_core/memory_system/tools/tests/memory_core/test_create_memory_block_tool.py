"""
Tests for the CreateMemoryBlock tool.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock
from pydantic import ValidationError

from infra_core.memory_system.tools.memory_core.create_memory_block_tool import (
    CreateMemoryBlockInput,
    CreateMemoryBlockOutput,
    create_memory_block,
    CogniTool,
)
from infra_core.memory_system.schemas.memory_block import ConfidenceScore
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank


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
        metadata={},
        source_file="test.md",
        confidence=ConfidenceScore(),
        created_by="test_agent",
    )


def test_create_memory_block_success(mock_memory_bank, sample_input):
    """Test successful memory block creation."""
    result = create_memory_block(sample_input, mock_memory_bank)

    assert isinstance(result, CreateMemoryBlockOutput)
    assert result.success is True
    assert result.id is not None
    assert result.error is None
    assert isinstance(result.timestamp, datetime)

    mock_memory_bank.get_latest_schema_version.assert_called_once_with("knowledge")
    mock_memory_bank.create_memory_block.assert_called_once()


def test_create_memory_block_invalid_type(mock_memory_bank):
    """Test memory block creation fails with ValidationError for invalid type."""
    # Expect a ValidationError when creating input with an invalid type
    with pytest.raises(ValidationError) as excinfo:
        CreateMemoryBlockInput(
            type="invalid_type",  # This type is not registered
            text="Test memory block content",
            state="draft",
            visibility="internal",
            tags=["test"],
            metadata={"key": "value"},
            created_by="test_agent",
        )

    # Check the error message
    assert "Invalid block type 'invalid_type'" in str(excinfo.value)

    # Verify that the memory bank methods were not called
    mock_memory_bank.get_latest_schema_version.assert_not_called()
    mock_memory_bank.create_memory_block.assert_not_called()


def test_create_memory_block_schema_lookup_fails(mock_memory_bank):
    """Test memory block creation when schema version lookup fails for a registered type."""
    # Configure mock to fail schema lookup even for a valid type
    mock_memory_bank.get_latest_schema_version.return_value = None

    # Use a valid type, but expect the lookup to fail
    input_data = CreateMemoryBlockInput(type="knowledge", text="Test knowledge block")

    # Call the tool
    result = create_memory_block(input_data=input_data, memory_bank=mock_memory_bank)

    # Verify result
    assert isinstance(result, CreateMemoryBlockOutput)
    assert result.success is False
    assert result.id is None
    # Assert the new defensive error message
    assert (
        "Schema definition missing or lookup failed for registered type: knowledge" in result.error
    )

    # Verify the mock was called correctly
    mock_memory_bank.get_latest_schema_version.assert_called_once_with("knowledge")
    mock_memory_bank.create_memory_block.assert_not_called()


def test_create_memory_block_persistence_failure(mock_memory_bank, sample_input):
    """Test memory block creation when persistence fails."""
    mock_memory_bank.create_memory_block.return_value = False

    result = create_memory_block(sample_input, mock_memory_bank)

    assert isinstance(result, CreateMemoryBlockOutput)
    assert result.success is False
    assert result.id is None
    assert "Failed to persist" in result.error


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

    assert isinstance(result, CreateMemoryBlockOutput)
    assert result.success is True
    assert result.id is not None
    assert result.error is None


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

    # Check that the result is a dictionary indicating validation error
    assert isinstance(result, dict)
    assert result.get("success") is False
    assert "error" in result
    assert "Validation error" in result["error"]
    assert "details" in result


def test_create_memory_block_injects_system_metadata(mock_memory_bank):
    """Test that create_memory_block injects missing x_timestamp and x_agent_id."""
    input_data = CreateMemoryBlockInput(
        type="knowledge",
        text="Test content for metadata injection.",
        metadata={},  # Start with empty metadata
        created_by="test_creator_for_injection",
    )

    # Mock the memory bank's create call to inspect the block passed to it
    block_passed_to_bank = None

    def capture_block(*args, **kwargs):
        nonlocal block_passed_to_bank
        block_passed_to_bank = args[0]  # First arg is the block
        return True  # Simulate successful persistence

    mock_memory_bank.create_memory_block.side_effect = capture_block
    mock_memory_bank.get_latest_schema_version.return_value = 1  # Assume schema exists

    result = create_memory_block(input_data, mock_memory_bank)

    assert result.success is True
    assert result.id is not None  # ID is generated within MemoryBlock
    assert result.error is None

    mock_memory_bank.create_memory_block.assert_called_once()
    assert block_passed_to_bank is not None
    assert isinstance(block_passed_to_bank.metadata, dict)

    # Verify injected fields
    assert "x_timestamp" in block_passed_to_bank.metadata
    assert isinstance(block_passed_to_bank.metadata["x_timestamp"], datetime)
    assert "x_agent_id" in block_passed_to_bank.metadata
    assert block_passed_to_bank.metadata["x_agent_id"] == "test_creator_for_injection"


def test_create_memory_block_respects_provided_system_metadata(mock_memory_bank):
    """Test that create_memory_block uses provided x_timestamp and x_agent_id if present."""
    provided_timestamp = datetime(2024, 1, 1, 12, 0, 0)
    provided_agent_id = "explicit_agent_id"

    input_data = CreateMemoryBlockInput(
        type="knowledge",
        text="Test content with provided metadata.",
        metadata={
            "x_timestamp": provided_timestamp,
            "x_agent_id": provided_agent_id,
        },
        created_by="fallback_creator",  # Should be ignored
    )

    # Mock the memory bank's create call
    block_passed_to_bank = None

    def capture_block(*args, **kwargs):
        nonlocal block_passed_to_bank
        block_passed_to_bank = args[0]
        return True

    mock_memory_bank.create_memory_block.side_effect = capture_block
    mock_memory_bank.get_latest_schema_version.return_value = 1

    result = create_memory_block(input_data, mock_memory_bank)

    assert result.success is True
    mock_memory_bank.create_memory_block.assert_called_once()
    assert block_passed_to_bank is not None

    # Verify provided fields were used and not overridden
    assert block_passed_to_bank.metadata["x_timestamp"] == provided_timestamp
    assert block_passed_to_bank.metadata["x_agent_id"] == provided_agent_id
