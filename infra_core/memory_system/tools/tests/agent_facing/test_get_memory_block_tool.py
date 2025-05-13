"""
Tests for the GetMemoryBlock agent-facing tool.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from infra_core.memory_system.tools.agent_facing.get_memory_block_tool import (
    GetMemoryBlockInput,
    GetMemoryBlockOutput,
    get_memory_block,
    get_memory_block_tool,
)
from infra_core.memory_system.tools.memory_core.get_memory_block_core import (
    GetMemoryBlockInput as CoreGetMemoryBlockInput,
    GetMemoryBlockOutput as CoreGetMemoryBlockOutput,
)
from infra_core.memory_system.schemas.memory_block import MemoryBlock
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank


@pytest.fixture
def mock_memory_bank():
    """Create a mock StructuredMemoryBank."""
    bank = MagicMock(spec=StructuredMemoryBank)
    return bank


@pytest.fixture
def sample_memory_block():
    """Create a sample MemoryBlock for testing."""
    return MemoryBlock(
        id="test-block-123",
        type="knowledge",
        text="Test memory block content",
        tags=["test", "memory"],
        metadata={"key": "value"},
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@pytest.fixture
def sample_input():
    """Create a sample input for testing."""
    return GetMemoryBlockInput(block_id="test-block-123")


# Patch the core get_memory_block_core function within the tool's module scope
@patch("infra_core.memory_system.tools.agent_facing.get_memory_block_tool.get_memory_block_core")
def test_get_memory_block_success(
    mock_core_get_block, mock_memory_bank, sample_input, sample_memory_block
):
    """Test successful memory block retrieval via agent-facing wrapper."""
    # Configure mock to return success output
    mock_core_output = CoreGetMemoryBlockOutput(
        success=True, block=sample_memory_block, timestamp=datetime.now()
    )
    mock_core_get_block.return_value = mock_core_output

    # Call the function
    result = get_memory_block(sample_input, mock_memory_bank)

    # Verify the result
    assert isinstance(result, GetMemoryBlockOutput)
    assert result.success is True
    assert result.block == sample_memory_block
    assert result.error is None
    assert isinstance(result.timestamp, datetime)

    # Verify mock was called correctly
    mock_core_get_block.assert_called_once()
    call_args, _ = mock_core_get_block.call_args
    passed_input, passed_memory_bank = call_args

    assert passed_memory_bank is mock_memory_bank
    assert isinstance(passed_input, CoreGetMemoryBlockInput)
    assert passed_input.block_id == "test-block-123"


@patch("infra_core.memory_system.tools.agent_facing.get_memory_block_tool.get_memory_block_core")
def test_get_memory_block_not_found(mock_core_get_block, mock_memory_bank, sample_input):
    """Test memory block not found via agent-facing wrapper."""
    # Configure mock to return not found output
    mock_core_output = CoreGetMemoryBlockOutput(
        success=False,
        block=None,
        error="Memory block with ID 'test-block-123' not found.",
        timestamp=datetime.now(),
    )
    mock_core_get_block.return_value = mock_core_output

    # Call the function
    result = get_memory_block(sample_input, mock_memory_bank)

    # Verify the result
    assert isinstance(result, GetMemoryBlockOutput)
    assert result.success is False
    assert result.block is None
    assert "not found" in result.error
    assert isinstance(result.timestamp, datetime)

    # Verify mock was called correctly
    mock_core_get_block.assert_called_once()


@patch("infra_core.memory_system.tools.agent_facing.get_memory_block_tool.get_memory_block_core")
def test_get_memory_block_core_exception(mock_core_get_block, mock_memory_bank, sample_input):
    """Test handling when core function raises an unexpected exception."""
    # Configure mock to raise an exception
    mock_core_get_block.side_effect = Exception("Unexpected core error")

    # Call the function
    result = get_memory_block(sample_input, mock_memory_bank)

    # Verify the result
    assert isinstance(result, GetMemoryBlockOutput)
    assert result.success is False
    assert result.block is None
    assert "Error in get_memory_block wrapper" in result.error
    assert "Unexpected core error" in result.error
    assert isinstance(result.timestamp, datetime)

    # Verify mock was called correctly
    mock_core_get_block.assert_called_once()


def test_get_memory_block_tool_initialization():
    """Test CogniTool initialization for GetMemoryBlockTool."""
    assert get_memory_block_tool.name == "GetMemoryBlock"
    assert get_memory_block_tool.memory_linked is True
    assert get_memory_block_tool.input_model == GetMemoryBlockInput
    assert get_memory_block_tool.output_model == GetMemoryBlockOutput


def test_get_memory_block_tool_schema():
    """Test schema generation for the GetMemoryBlock tool."""
    schema = get_memory_block_tool.schema
    assert schema["name"] == "GetMemoryBlock"
    assert schema["type"] == "function"
    assert "parameters" in schema
    properties = schema["parameters"]["properties"]
    assert "block_id" in properties


@patch("infra_core.memory_system.tools.agent_facing.get_memory_block_tool.get_memory_block_core")
def test_get_memory_block_tool_direct_invocation(
    mock_core_get_block, mock_memory_bank, sample_memory_block
):
    """Test direct invocation of the tool instance."""
    # Configure mock to return success output
    mock_core_output = CoreGetMemoryBlockOutput(
        success=True, block=sample_memory_block, timestamp=datetime.now()
    )
    mock_core_get_block.return_value = mock_core_output

    # Call the tool directly
    result = get_memory_block_tool(memory_bank=mock_memory_bank, block_id="test-block-123")

    # Verify the result
    assert isinstance(result, GetMemoryBlockOutput)
    assert result.success is True
    assert result.block == sample_memory_block
    mock_core_get_block.assert_called_once()


def test_get_memory_block_tool_invalid_input(mock_memory_bank):
    """Test tool with invalid input (e.g., missing required field 'block_id')."""
    with patch(
        "infra_core.memory_system.tools.agent_facing.get_memory_block_tool.get_memory_block"
    ) as mock_func:
        # Call without required block_id
        result = get_memory_block_tool(
            memory_bank=mock_memory_bank,
        )
        mock_func.assert_not_called()

    # Verify validation error
    assert isinstance(result, GetMemoryBlockOutput)
    assert result.success is False
    assert "Validation error" in result.error
    assert "block_id" in (result.error or "")
    assert "Field required" in (result.error or "")
