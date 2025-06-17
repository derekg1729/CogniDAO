"""
Tests for the QueryMemoryBlocks tool.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

from infra_core.memory_system.tools.memory_core.query_memory_blocks_tool import (
    QueryMemoryBlocksInput,
    QueryMemoryBlocksOutput,
    query_memory_blocks_core,
    query_memory_blocks_tool,
)
from infra_core.memory_system.schemas.memory_block import MemoryBlock
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank


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


def test_query_memory_blocks_with_epic_type_filter(mock_memory_bank):
    """Test memory block query with epic type filter."""
    # Mock epic blocks
    mock_memory_bank.query_semantic.return_value = [
        MemoryBlock(
            type="epic", text="Epic test block", tags=["epic"], metadata={"status": "ready"}
        ),
        MemoryBlock(
            type="task", text="Task test block", tags=["task"], metadata={"status": "backlog"}
        ),
    ]

    input_data = QueryMemoryBlocksInput(query_text="test query", type_filter="epic", top_k=5)

    result = query_memory_blocks_core(input_data, mock_memory_bank)

    assert isinstance(result, QueryMemoryBlocksOutput)
    assert result.success is True
    assert len(result.blocks) == 1
    assert result.blocks[0].type == "epic"
    assert result.blocks[0].text == "Epic test block"


def test_query_memory_blocks_with_bug_type_filter(mock_memory_bank):
    """Test memory block query with bug type filter."""
    # Mock bug blocks
    mock_memory_bank.query_semantic.return_value = [
        MemoryBlock(
            type="bug", text="Bug test block", tags=["bug"], metadata={"severity": "major"}
        ),
        MemoryBlock(
            type="task", text="Task test block", tags=["task"], metadata={"status": "backlog"}
        ),
    ]

    input_data = QueryMemoryBlocksInput(query_text="test query", type_filter="bug", top_k=5)

    result = query_memory_blocks_core(input_data, mock_memory_bank)

    assert isinstance(result, QueryMemoryBlocksOutput)
    assert result.success is True
    assert len(result.blocks) == 1
    assert result.blocks[0].type == "bug"
    assert result.blocks[0].text == "Bug test block"


def test_query_memory_blocks_with_log_type_filter(mock_memory_bank):
    """Test memory block query with log type filter."""
    # Mock log blocks
    mock_memory_bank.query_semantic.return_value = [
        MemoryBlock(type="log", text="Log test block", tags=["log"], metadata={"level": "info"}),
        MemoryBlock(type="doc", text="Doc test block", tags=["doc"], metadata={"section": "api"}),
    ]

    input_data = QueryMemoryBlocksInput(query_text="test query", type_filter="log", top_k=5)

    result = query_memory_blocks_core(input_data, mock_memory_bank)

    assert isinstance(result, QueryMemoryBlocksOutput)
    assert result.success is True
    assert len(result.blocks) == 1
    assert result.blocks[0].type == "log"
    assert result.blocks[0].text == "Log test block"


def test_query_memory_blocks_all_type_filters():
    """Test that all valid block types are accepted in type_filter."""
    valid_types = ["knowledge", "task", "project", "doc", "interaction", "log", "epic", "bug"]

    for block_type in valid_types:
        # This should not raise a validation error
        input_data = QueryMemoryBlocksInput(
            query_text="test query", type_filter=block_type, top_k=5
        )
        assert input_data.type_filter == block_type


def test_query_memory_blocks_invalid_type_filter():
    """Test that invalid type filters raise validation errors."""
    with pytest.raises(ValueError):
        QueryMemoryBlocksInput(query_text="test query", type_filter="invalid_type", top_k=5)


def test_query_memory_blocks_combined_filters(mock_memory_bank):
    """Test memory block query with multiple filters combined."""
    # Mock mixed blocks
    mock_memory_bank.query_semantic.return_value = [
        MemoryBlock(
            type="epic",
            text="Epic with matching tags and metadata",
            tags=["project", "priority"],
            metadata={"status": "ready", "priority": "P0"},
        ),
        MemoryBlock(
            type="epic",
            text="Epic with different metadata",
            tags=["project", "priority"],
            metadata={"status": "backlog", "priority": "P1"},
        ),
        MemoryBlock(
            type="task",
            text="Task with matching tags",
            tags=["project", "priority"],
            metadata={"status": "ready", "priority": "P0"},
        ),
    ]

    input_data = QueryMemoryBlocksInput(
        query_text="test query",
        type_filter="epic",
        tag_filters=["project", "priority"],
        metadata_filters={"status": "ready", "priority": "P0"},
        top_k=5,
    )

    result = query_memory_blocks_core(input_data, mock_memory_bank)

    assert isinstance(result, QueryMemoryBlocksOutput)
    assert result.success is True
    assert len(result.blocks) == 1
    assert result.blocks[0].type == "epic"
    assert result.blocks[0].text == "Epic with matching tags and metadata"
    assert all(tag in result.blocks[0].tags for tag in ["project", "priority"])
    assert result.blocks[0].metadata["status"] == "ready"
    assert result.blocks[0].metadata["priority"] == "P0"


def test_query_memory_blocks_empty_results(mock_memory_bank):
    """Test handling of empty semantic search results."""
    mock_memory_bank.query_semantic.return_value = []

    input_data = QueryMemoryBlocksInput(query_text="nonexistent query", top_k=5)

    result = query_memory_blocks_core(input_data, mock_memory_bank)

    assert isinstance(result, QueryMemoryBlocksOutput)
    assert result.success is True
    assert len(result.blocks) == 0
    assert result.error is None


def test_query_memory_blocks_top_k_limits():
    """Test that top_k parameter validation works correctly."""
    # Valid top_k values
    for k in [1, 5, 10, 20]:
        input_data = QueryMemoryBlocksInput(query_text="test query", top_k=k)
        assert input_data.top_k == k

    # Invalid top_k values should raise validation errors
    with pytest.raises(ValueError):
        QueryMemoryBlocksInput(query_text="test query", top_k=0)

    with pytest.raises(ValueError):
        QueryMemoryBlocksInput(query_text="test query", top_k=21)

    with pytest.raises(ValueError):
        QueryMemoryBlocksInput(query_text="test query", top_k=-1)
