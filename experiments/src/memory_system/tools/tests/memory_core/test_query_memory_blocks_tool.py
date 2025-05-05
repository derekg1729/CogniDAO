"""
Tests for the QueryMemoryBlocks tool.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

from experiments.src.memory_system.tools.memory_core.query_memory_blocks_tool import (
    QueryMemoryBlocksInput,
    QueryMemoryBlocksOutput,
    query_memory_blocks_core,
    query_memory_blocks_tool,
)
from experiments.src.memory_system.schemas.memory_block import MemoryBlock
from experiments.src.memory_system.structured_memory_bank import StructuredMemoryBank


@pytest.fixture
def mock_memory_bank():
    """Create a mock StructuredMemoryBank."""
    bank = MagicMock(spec=StructuredMemoryBank)
    bank.query_semantic.return_value = [
        MemoryBlock(
            type="knowledge", text="Test block 1", tags=["test"], metadata={"key": "value"}
        ),
        MemoryBlock(
            type="task", text="Test block 2", tags=["test", "task"], metadata={"key": "value"}
        ),
    ]
    return bank


@pytest.fixture
def sample_input():
    """Create a sample input for testing."""
    return QueryMemoryBlocksInput(
        query_text="test query", type_filter=None, tag_filters=None, top_k=5, metadata_filters=None
    )


def test_query_memory_blocks_success(mock_memory_bank, sample_input):
    """Test successful memory block query."""
    result = query_memory_blocks_core(sample_input, mock_memory_bank)

    assert isinstance(result, QueryMemoryBlocksOutput)
    assert result.success is True
    assert len(result.blocks) == 2
    assert result.error is None
    assert isinstance(result.timestamp, datetime)

    mock_memory_bank.query_semantic.assert_called_once_with(query_text="test query", top_k=5)


def test_query_memory_blocks_with_type_filter(mock_memory_bank):
    """Test memory block query with type filter."""
    input_data = QueryMemoryBlocksInput(query_text="test query", type_filter="knowledge", top_k=5)

    result = query_memory_blocks_core(input_data, mock_memory_bank)

    assert isinstance(result, QueryMemoryBlocksOutput)
    assert result.success is True
    assert len(result.blocks) == 1
    assert result.blocks[0].type == "knowledge"


def test_query_memory_blocks_with_tag_filter(mock_memory_bank):
    """Test memory block query with tag filter."""
    input_data = QueryMemoryBlocksInput(query_text="test query", tag_filters=["task"], top_k=5)

    result = query_memory_blocks_core(input_data, mock_memory_bank)

    assert isinstance(result, QueryMemoryBlocksOutput)
    assert result.success is True
    assert len(result.blocks) == 1
    assert "task" in result.blocks[0].tags


def test_query_memory_blocks_with_metadata_filter(mock_memory_bank):
    """Test memory block query with metadata filter."""
    input_data = QueryMemoryBlocksInput(
        query_text="test query", metadata_filters={"key": "value"}, top_k=5
    )

    result = query_memory_blocks_core(input_data, mock_memory_bank)

    assert isinstance(result, QueryMemoryBlocksOutput)
    assert result.success is True
    assert len(result.blocks) == 2
    assert all(b.metadata.get("key") == "value" for b in result.blocks)


def test_query_memory_blocks_error_handling(mock_memory_bank, sample_input):
    """Test error handling in memory block query."""
    mock_memory_bank.query_semantic.side_effect = Exception("Test error")

    result = query_memory_blocks_core(sample_input, mock_memory_bank)

    assert isinstance(result, QueryMemoryBlocksOutput)
    assert result.success is False
    assert len(result.blocks) == 0
    assert "Test error" in result.error


def test_query_memory_blocks_tool_initialization():
    """Test CogniTool initialization with QueryMemoryBlocks."""
    assert query_memory_blocks_tool.name == "QueryMemoryBlocks"
    assert query_memory_blocks_tool.memory_linked is True
    assert query_memory_blocks_tool.input_model == QueryMemoryBlocksInput
    assert query_memory_blocks_tool.output_model == QueryMemoryBlocksOutput


def test_query_memory_blocks_tool_schema():
    """Test schema generation for QueryMemoryBlocks tool."""
    schema = query_memory_blocks_tool.schema
    assert schema["name"] == "QueryMemoryBlocks"
    assert schema["memory_linked"] is True
    assert "parameters" in schema
    assert "returns" in schema
