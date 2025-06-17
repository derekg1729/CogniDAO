"""
Tests for the GetMemoryBlock agent-facing tool.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from infra_core.memory_system.tools.agent_facing.get_memory_block_tool import (
    GetMemoryBlockInput,
    GetMemoryBlockOutput,
    get_memory_block,
    get_memory_block_tool,
)
from infra_core.memory_system.tools.memory_core.get_memory_block_core import (
    GetMemoryBlockOutput as CoreGetMemoryBlockOutput,
)
from infra_core.memory_system.schemas.memory_block import MemoryBlock
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank


@pytest.fixture
def mock_memory_bank():
    """Create a mock StructuredMemoryBank."""
    return MagicMock(spec=StructuredMemoryBank)


@pytest.fixture
def sample_input():
    """Create a sample input for testing."""
    return GetMemoryBlockInput(block_ids=["test-block-123"])


@pytest.fixture
def sample_memory_block():
    """Create a sample MemoryBlock for testing."""
    return MemoryBlock(
        id="test-block-123",
        type="knowledge",
        text="This is a test memory block.",
        tags=["test", "sample"],
        metadata={"source": "pytest"},
    )


# Patch the core get_memory_block_core function within the tool's module scope
@patch("infra_core.memory_system.tools.agent_facing.get_memory_block_tool.get_memory_block_core")
def test_get_memory_block_success(
    mock_core_get_block, mock_memory_bank, sample_input, sample_memory_block
):
    """Test successful memory block retrieval via agent-facing wrapper."""
    # Configure mock to return success output
    mock_core_output = CoreGetMemoryBlockOutput(
        success=True, blocks=[sample_memory_block], timestamp=datetime.now()
    )
    mock_core_get_block.return_value = mock_core_output

    # Call the function
    result = get_memory_block(sample_input, mock_memory_bank)

    # Verify the result
    assert isinstance(result, GetMemoryBlockOutput)
    assert result.success is True
    assert len(result.blocks) == 1
    assert result.blocks[0] == sample_memory_block
    assert result.error is None

    # Verify the core function was called correctly
    mock_core_get_block.assert_called_once_with(sample_input, mock_memory_bank)


@patch("infra_core.memory_system.tools.agent_facing.get_memory_block_tool.get_memory_block_core")
def test_get_memory_block_not_found(mock_core_get_block, mock_memory_bank, sample_input):
    """Test memory block not found scenario."""
    # Configure mock to return failure output
    mock_core_output = CoreGetMemoryBlockOutput(
        success=False,
        blocks=[],
        error="Memory block with ID 'test-block-123' not found.",
        timestamp=datetime.now(),
    )
    mock_core_get_block.return_value = mock_core_output

    # Call the function
    result = get_memory_block(sample_input, mock_memory_bank)

    # Verify the result
    assert isinstance(result, GetMemoryBlockOutput)
    assert result.success is False
    assert len(result.blocks) == 0
    assert "not found" in result.error

    # Verify the core function was called correctly
    mock_core_get_block.assert_called_once_with(sample_input, mock_memory_bank)


@patch("infra_core.memory_system.tools.agent_facing.get_memory_block_tool.get_memory_block_core")
def test_get_memory_block_tool_direct_invocation(
    mock_core_get_block, mock_memory_bank, sample_memory_block
):
    """Test direct invocation of the tool convenience function."""
    # Configure mock to return success output
    mock_core_output = CoreGetMemoryBlockOutput(
        success=True, blocks=[sample_memory_block], timestamp=datetime.now()
    )
    mock_core_get_block.return_value = mock_core_output

    # Call the tool directly using convenience function
    result = get_memory_block_tool(block_id="test-block-123", memory_bank=mock_memory_bank)

    # Verify the result
    assert isinstance(result, GetMemoryBlockOutput)
    assert result.success is True
    assert len(result.blocks) == 1
    assert result.blocks[0] == sample_memory_block

    # Verify the core function was called with correct input
    mock_core_get_block.assert_called_once()
    call_args = mock_core_get_block.call_args[0]
    input_data = call_args[0]
    assert input_data.block_ids == ["test-block-123"]


def test_get_memory_block_tool_invalid_input(mock_memory_bank):
    """Test tool with invalid input (e.g., missing required parameters)."""
    with patch(
        "infra_core.memory_system.tools.agent_facing.get_memory_block_tool.get_memory_block"
    ) as mock_func:
        # Call without required parameters
        result = get_memory_block_tool(memory_bank=mock_memory_bank)
        mock_func.assert_not_called()

    # Verify validation error
    assert isinstance(result, GetMemoryBlockOutput)
    assert result.success is False
    assert "Validation error" in result.error
    assert "Must specify either block_ids OR at least one filtering parameter" in (
        result.error or ""
    )


def test_get_memory_block_tool_with_filtering(mock_memory_bank):
    """Test tool with filtering parameters."""
    with patch(
        "infra_core.memory_system.tools.agent_facing.get_memory_block_tool.get_memory_block_core"
    ) as mock_core:
        # Configure mock to return success
        mock_core.return_value = CoreGetMemoryBlockOutput(
            success=True, blocks=[], timestamp=datetime.now()
        )

        # Call with filtering parameters
        result = get_memory_block_tool(
            memory_bank=mock_memory_bank, type_filter="task", tag_filters=["urgent"]
        )

        # Verify the call was made
        assert result.success is True
        mock_core.assert_called_once()

        # Verify the input was constructed correctly
        call_args = mock_core.call_args[0]
        input_data = call_args[0]
        assert input_data.type_filter == "task"
        assert input_data.tag_filters == ["urgent"]
        assert input_data.block_ids is None
