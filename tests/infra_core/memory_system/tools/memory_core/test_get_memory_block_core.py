"""
Tests for the GetMemoryBlock core tool.
"""

import pytest

from infra_core.memory_system.tools.memory_core.get_memory_block_core import (
    GetMemoryBlockInput,
    get_memory_block_core,
)
from infra_core.memory_system.schemas.memory_block import MemoryBlock


# Removed duplicate mock_memory_bank fixture - using the DRY one from conftest.py that includes dolt_writer


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


@pytest.fixture
def sample_input():
    """Create a sample input for testing."""
    return GetMemoryBlockInput(block_ids=["test-block-123"])


def test_get_memory_block_success(mock_memory_bank, sample_input, sample_memory_block):
    """Test successful memory block retrieval."""
    # Configure mock to return the sample block in a list (since get_all_memory_blocks returns a list)
    mock_memory_bank.get_all_memory_blocks.return_value = [sample_memory_block]

    # Call the function
    result = get_memory_block_core(sample_input, mock_memory_bank)

    # Verify success
    assert result.success is True
    assert len(result.blocks) == 1
    assert result.blocks[0] == sample_memory_block
    assert result.error is None

    # Verify the mock was called correctly with branch parameter
    mock_memory_bank.get_all_memory_blocks.assert_called_once_with(branch="main")


def test_get_memory_block_not_found(mock_memory_bank, sample_input):
    """Test memory block not found scenario."""
    # Configure mock to return empty list (no blocks found)
    mock_memory_bank.get_all_memory_blocks.return_value = []

    # Call the function
    result = get_memory_block_core(sample_input, mock_memory_bank)

    # Verify failure
    assert result.success is False
    assert len(result.blocks) == 0
    assert "not found" in result.error
    assert "test-block-123" in result.error


def test_get_memory_block_multiple_ids(mock_memory_bank, sample_memory_block):
    """Test retrieval of multiple blocks by IDs."""
    # Create multiple sample blocks
    block1 = sample_memory_block
    block2 = MemoryBlock(
        id="test-block-456", type="task", text="Another test block.", tags=["test"], metadata={}
    )

    # Configure mock to return all blocks (implementation filters by ID internally)
    mock_memory_bank.get_all_memory_blocks.return_value = [block1, block2]

    # Test input with multiple IDs
    input_data = GetMemoryBlockInput(block_ids=["test-block-123", "test-block-456"])
    result = get_memory_block_core(input_data, mock_memory_bank)

    # Verify success
    assert result.success is True
    assert len(result.blocks) == 2
    assert result.blocks[0] == block1
    assert result.blocks[1] == block2
    assert result.error is None


def test_get_memory_block_partial_found(mock_memory_bank, sample_memory_block):
    """Test retrieval where some blocks are found and some are not."""

    # Configure mock to return only the found block
    mock_memory_bank.get_all_memory_blocks.return_value = [sample_memory_block]

    # Test input with multiple IDs (one found, one not)
    input_data = GetMemoryBlockInput(block_ids=["test-block-123", "missing-block"])
    result = get_memory_block_core(input_data, mock_memory_bank)

    # Verify partial failure
    assert result.success is False
    assert len(result.blocks) == 1  # Found block still returned
    assert result.blocks[0] == sample_memory_block
    assert "not found" in result.error
    assert "missing-block" in result.error


def test_get_memory_block_exception(mock_memory_bank, sample_input):
    """Test error handling when an exception occurs."""
    # Configure mock to raise an exception
    mock_memory_bank.get_all_memory_blocks.side_effect = Exception("Database error")

    # Call the function
    result = get_memory_block_core(sample_input, mock_memory_bank)

    # Verify error handling
    assert result.success is False
    assert len(result.blocks) == 0
    assert "Database error" in result.error


@pytest.fixture
def sample_blocks():
    """Create sample blocks for filtering tests."""
    return [
        MemoryBlock(
            id="task-1",
            type="task",
            text="Task 1",
            tags=["urgent", "work"],
            metadata={"priority": "high", "owner": "alice"},
        ),
        MemoryBlock(
            id="task-2",
            type="task",
            text="Task 2",
            tags=["work"],
            metadata={"priority": "low", "owner": "bob"},
        ),
        MemoryBlock(
            id="doc-1",
            type="doc",
            text="Document 1",
            tags=["reference"],
            metadata={"category": "technical"},
        ),
    ]


def test_get_memory_blocks_by_type_filter(mock_memory_bank, sample_blocks):
    """Test filtering blocks by type."""
    mock_memory_bank.get_all_memory_blocks.return_value = sample_blocks

    input_data = GetMemoryBlockInput(type_filter="task")
    result = get_memory_block_core(input_data, mock_memory_bank)

    assert result.success is True
    assert len(result.blocks) == 2
    assert all(block.type == "task" for block in result.blocks)


def test_get_memory_blocks_by_tag_filter(mock_memory_bank, sample_blocks):
    """Test filtering blocks by tags."""
    mock_memory_bank.get_all_memory_blocks.return_value = sample_blocks

    input_data = GetMemoryBlockInput(tag_filters=["work"])
    result = get_memory_block_core(input_data, mock_memory_bank)

    assert result.success is True
    assert len(result.blocks) == 2
    assert all("work" in block.tags for block in result.blocks)


def test_get_memory_blocks_by_metadata_filter(mock_memory_bank, sample_blocks):
    """Test filtering blocks by metadata."""
    mock_memory_bank.get_all_memory_blocks.return_value = sample_blocks

    input_data = GetMemoryBlockInput(metadata_filters={"owner": "alice"})
    result = get_memory_block_core(input_data, mock_memory_bank)

    assert result.success is True
    assert len(result.blocks) == 1
    assert result.blocks[0].metadata["owner"] == "alice"


def test_get_memory_blocks_combined_filters(mock_memory_bank, sample_blocks):
    """Test filtering blocks with multiple filter criteria."""
    mock_memory_bank.get_all_memory_blocks.return_value = sample_blocks

    input_data = GetMemoryBlockInput(
        type_filter="task", tag_filters=["urgent"], metadata_filters={"priority": "high"}
    )
    result = get_memory_block_core(input_data, mock_memory_bank)

    assert result.success is True
    assert len(result.blocks) == 1
    assert result.blocks[0].id == "task-1"


def test_get_memory_blocks_with_limit(mock_memory_bank, sample_blocks):
    """Test filtering with limit parameter."""
    mock_memory_bank.get_all_memory_blocks.return_value = sample_blocks

    input_data = GetMemoryBlockInput(type_filter="task", limit=1)
    result = get_memory_block_core(input_data, mock_memory_bank)

    assert result.success is True
    assert len(result.blocks) == 1


def test_get_memory_blocks_no_matches(mock_memory_bank, sample_blocks):
    """Test filtering that returns no matches."""
    mock_memory_bank.get_all_memory_blocks.return_value = sample_blocks

    input_data = GetMemoryBlockInput(
        type_filter="epic"
    )  # Valid type but no matches in sample_blocks
    result = get_memory_block_core(input_data, mock_memory_bank)

    assert result.success is True
    assert len(result.blocks) == 0


def test_input_validation_both_id_and_filter():
    """Test validation error when both block_ids and filtering parameters are provided."""
    with pytest.raises(ValueError, match="Cannot specify both block_ids and filtering parameters"):
        GetMemoryBlockInput(block_ids=["test-id"], type_filter="task")


def test_input_validation_neither_id_nor_filter():
    """Test validation error when neither block_ids nor filtering parameters are provided."""
    with pytest.raises(
        ValueError, match="Must specify either block_ids OR at least one filtering parameter"
    ):
        GetMemoryBlockInput()
