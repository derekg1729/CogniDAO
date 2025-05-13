"""
Tests for the GetMemoryBlock core tool.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

from infra_core.memory_system.tools.memory_core.get_memory_block_core import (
    GetMemoryBlockInput,
    GetMemoryBlockOutput,
    get_memory_block_core,
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


def test_get_memory_block_success(mock_memory_bank, sample_input, sample_memory_block):
    """Test successful memory block retrieval."""
    # Configure mock to return a memory block
    mock_memory_bank.get_memory_block.return_value = sample_memory_block

    # Call the function
    result = get_memory_block_core(sample_input, mock_memory_bank)

    # Verify the result
    assert isinstance(result, GetMemoryBlockOutput)
    assert result.success is True
    assert result.block is sample_memory_block
    assert result.error is None
    assert isinstance(result.timestamp, datetime)

    # Verify mock was called correctly
    mock_memory_bank.get_memory_block.assert_called_once_with("test-block-123")


def test_get_memory_block_not_found(mock_memory_bank, sample_input):
    """Test memory block not found."""
    # Configure mock to return None (block not found)
    mock_memory_bank.get_memory_block.return_value = None

    # Call the function
    result = get_memory_block_core(sample_input, mock_memory_bank)

    # Verify the result
    assert isinstance(result, GetMemoryBlockOutput)
    assert result.success is False
    assert result.block is None
    assert "not found" in result.error
    assert "test-block-123" in result.error
    assert isinstance(result.timestamp, datetime)

    # Verify mock was called correctly
    mock_memory_bank.get_memory_block.assert_called_once_with("test-block-123")


def test_get_memory_block_exception(mock_memory_bank, sample_input):
    """Test error handling when an exception occurs."""
    # Configure mock to raise an exception
    mock_memory_bank.get_memory_block.side_effect = Exception("Test error")

    # Call the function
    result = get_memory_block_core(sample_input, mock_memory_bank)

    # Verify the result
    assert isinstance(result, GetMemoryBlockOutput)
    assert result.success is False
    assert result.block is None
    assert "Error retrieving memory block" in result.error
    assert "Test error" in result.error
    assert isinstance(result.timestamp, datetime)

    # Verify mock was called correctly
    mock_memory_bank.get_memory_block.assert_called_once_with("test-block-123")
