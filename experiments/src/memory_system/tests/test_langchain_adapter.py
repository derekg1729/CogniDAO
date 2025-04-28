"""
Tests for the CogniStructuredMemoryAdapter.
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime
import uuid

# Assuming path setup allows importing these:
from experiments.src.memory_system.langchain_adapter import CogniStructuredMemoryAdapter
from experiments.src.memory_system.structured_memory_bank import StructuredMemoryBank
from experiments.src.memory_system.schemas.memory_block import MemoryBlock

# --- Fixtures ---

@pytest.fixture
def mock_memory_bank():
    """Provides a MagicMock instance of StructuredMemoryBank."""
    mock_bank = MagicMock(spec=StructuredMemoryBank)
    mock_bank.query_semantic = MagicMock(return_value=[]) # Default: return empty list
    mock_bank.create_memory_block = MagicMock(return_value=True) # Default: simulate success
    return mock_bank

@pytest.fixture
def adapter(mock_memory_bank): # Depends on the mock_memory_bank fixture
    """Provides an instance of CogniStructuredMemoryAdapter with a mocked bank."""
    return CogniStructuredMemoryAdapter(memory_bank=mock_memory_bank)

@pytest.fixture
def sample_memory_blocks():
    """Provides a list of sample MemoryBlock objects for testing."""
    now = datetime.now()
    return [
        MemoryBlock(
            id=str(uuid.uuid4()),
            type="knowledge",
            text="This is the first block.",
            tags=["test", "first"],
            created_at=now
        ),
        MemoryBlock(
            id=str(uuid.uuid4()),
            type="interaction",
            text="User said hello.",
            tags=["test", "greeting"],
            created_at=now
        )
    ]

# --- Tests ---

def test_load_memory_variables_success(adapter, mock_memory_bank, sample_memory_blocks):
    """Test load_memory_variables calls query_semantic and formats output correctly."""
    # Arrange
    input_query = "Tell me about tests"
    mock_memory_bank.query_semantic.return_value = sample_memory_blocks
    expected_key = adapter.memory_key
    expected_markdown = adapter._format_blocks_to_markdown(sample_memory_blocks) # Use helper to get expected format

    # Act
    result = adapter.load_memory_variables({adapter.input_key: input_query})

    # Assert
    mock_memory_bank.query_semantic.assert_called_once_with(
        query_text=input_query,
        top_k=adapter.top_k_retrieval
    )
    assert result == {expected_key: expected_markdown}
    assert "Memory Block:" in result[expected_key] # Check for basic formatting
    assert sample_memory_blocks[0].id in result[expected_key]
    assert sample_memory_blocks[1].id in result[expected_key]

def test_load_memory_variables_no_input(adapter, mock_memory_bank):
    """Test load_memory_variables handles missing input key."""
    # Act
    result = adapter.load_memory_variables({"other_key": "some value"})

    # Assert
    mock_memory_bank.query_semantic.assert_not_called()
    assert result == {adapter.memory_key: "Input query not provided."}

def test_save_context_success(adapter, mock_memory_bank):
    """Test save_context creates a correctly formatted block and calls create_memory_block."""
    # Arrange
    input_text = "What is the weather?"
    output_text = "It is sunny."
    fixed_tags = ["session123"]
    adapter.save_tags = fixed_tags # Set specific tags for this test

    inputs = {adapter.input_key: input_text}
    outputs = {adapter.output_key: output_text}

    expected_block_text = (
        f"[Interaction Record]\n"
        f"Input: {input_text}\n"
        f"Output: {output_text}"
    )

    # Act
    adapter.save_context(inputs, outputs)

    # Assert
    mock_memory_bank.create_memory_block.assert_called_once()
    # Get the MemoryBlock object passed to the mock
    call_args, call_kwargs = mock_memory_bank.create_memory_block.call_args
    saved_block: MemoryBlock = call_args[0]

    assert isinstance(saved_block, MemoryBlock)
    assert saved_block.type == adapter.save_interaction_type
    assert saved_block.text == expected_block_text
    assert saved_block.tags == fixed_tags
    assert saved_block.metadata["input_key"] == adapter.input_key
    assert saved_block.metadata["output_key"] == adapter.output_key

def test_save_context_missing_input_output(adapter, mock_memory_bank):
    """Test save_context handles missing input or output keys gracefully."""
    # Arrange
    inputs_missing = {"other_in": "value"}
    outputs_missing = {"other_out": "value"}
    inputs_ok = {adapter.input_key: "hello"}
    outputs_ok = {adapter.output_key: "hi"}

    # Act & Assert for missing input
    adapter.save_context(inputs_missing, outputs_ok)
    mock_memory_bank.create_memory_block.assert_not_called()

    # Act & Assert for missing output
    adapter.save_context(inputs_ok, outputs_missing)
    mock_memory_bank.create_memory_block.assert_not_called()

    # Act & Assert for both missing
    adapter.save_context(inputs_missing, outputs_missing)
    mock_memory_bank.create_memory_block.assert_not_called()

# TODO: Add tests for error handling in load/save
# TODO: Add tests for clear() method behavior (raising NotImplementedError)
# TODO: Add tests for _format_blocks_to_markdown specifically if needed
