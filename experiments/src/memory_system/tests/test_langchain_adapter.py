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
    mock_bank.query_semantic = MagicMock(return_value=[])  # Default: return empty list
    mock_bank.create_memory_block = MagicMock(return_value=True)  # Default: simulate success
    return mock_bank


@pytest.fixture
def adapter(mock_memory_bank):  # Depends on the mock_memory_bank fixture
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
            created_at=now,
        ),
        MemoryBlock(
            id=str(uuid.uuid4()),
            type="interaction",
            text="User said hello.",
            tags=["test", "greeting"],
            created_at=now,
        ),
    ]


# --- Tests ---


def test_load_memory_variables_success(adapter, mock_memory_bank, sample_memory_blocks):
    """Test load_memory_variables calls query_semantic and formats output correctly."""
    # Arrange
    input_query = "Tell me about tests"
    mock_memory_bank.query_semantic.return_value = sample_memory_blocks
    expected_key = adapter.memory_key
    expected_markdown = adapter._format_blocks_to_markdown(
        sample_memory_blocks
    )  # Use helper to get expected format

    # Act
    result = adapter.load_memory_variables({adapter.input_key: input_query})

    # Assert
    mock_memory_bank.query_semantic.assert_called_once_with(
        query_text=input_query, top_k=adapter.top_k_retrieval
    )
    assert result == {expected_key: expected_markdown}
    assert "### Memory Block" in result[expected_key]  # Check for basic formatting
    assert "Content:" in result[expected_key]  # Check for content section
    assert "---" in result[expected_key]  # Check for block separator


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
    adapter.save_tags = fixed_tags  # Set specific tags for this test

    inputs = {adapter.input_key: input_text}
    outputs = {adapter.output_key: output_text}

    expected_block_text = f"[Interaction Record]\nInput: {input_text}\nOutput: {output_text}"

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
    assert "session123" in saved_block.tags
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


# --- New Tests for Enhanced save_context ---


def test_save_context_session_id_tag(adapter, mock_memory_bank):
    """Test that session_id from inputs gets added as a tag."""
    # Arrange
    session_id = "test_session_12345"
    inputs = {adapter.input_key: "Hello", "session_id": session_id}
    outputs = {adapter.output_key: "Hi there"}

    # Act
    adapter.save_context(inputs, outputs)

    # Assert
    mock_memory_bank.create_memory_block.assert_called_once()
    saved_block = mock_memory_bank.create_memory_block.call_args[0][0]
    assert f"session:{session_id}" in saved_block.tags
    assert "date:" in saved_block.tags[1]  # Date tag should be present
    assert f"type:{adapter.save_interaction_type}" in saved_block.tags
    assert session_id == saved_block.metadata["session_id"]


def test_save_context_model_metadata(adapter, mock_memory_bank):
    """Test that model information is saved in metadata."""
    # Arrange
    model_name = "gpt-4"
    inputs = {adapter.input_key: "Hello", "model": model_name}
    outputs = {adapter.output_key: "Hi there"}

    # Act
    adapter.save_context(inputs, outputs)

    # Assert
    mock_memory_bank.create_memory_block.assert_called_once()
    saved_block = mock_memory_bank.create_memory_block.call_args[0][0]
    assert saved_block.metadata["model"] == model_name
    assert "timestamp" in saved_block.metadata


def test_save_context_token_count_and_latency(adapter, mock_memory_bank):
    """Test that token counts and latency are saved in metadata."""
    # Arrange
    token_count = {"prompt": 150, "completion": 50}
    latency_ms = 500
    inputs = {adapter.input_key: "Hello", "token_count": token_count, "latency": latency_ms}
    outputs = {adapter.output_key: "Hi there"}

    # Act
    adapter.save_context(inputs, outputs)

    # Assert
    mock_memory_bank.create_memory_block.assert_called_once()
    saved_block = mock_memory_bank.create_memory_block.call_args[0][0]
    assert saved_block.metadata["token_count"] == token_count
    assert saved_block.metadata["latency_ms"] == latency_ms


def test_save_context_sanitization(adapter, mock_memory_bank):
    """Test that input is sanitized to remove memory placeholders."""
    # Arrange
    memory_key = adapter.memory_key
    input_with_placeholder = f"Answer this question based on {{{memory_key}}}: What is Python?"
    inputs = {adapter.input_key: input_with_placeholder}
    outputs = {adapter.output_key: "Python is a programming language"}

    # Expected sanitized input
    expected_sanitized = "Answer this question based on : What is Python?"

    # Act
    adapter.save_context(inputs, outputs)

    # Assert
    mock_memory_bank.create_memory_block.assert_called_once()
    saved_block = mock_memory_bank.create_memory_block.call_args[0][0]
    assert f"Input: {expected_sanitized}" in saved_block.text
    assert "Python is a programming language" in saved_block.text


def test_save_context_dict_output(adapter, mock_memory_bank):
    """Test that dictionary outputs are handled correctly."""
    # Arrange
    inputs = {adapter.input_key: "Hello"}
    dict_output = {"output": "This is the main text", "metadata": {"confidence": 0.95}}
    outputs = {adapter.output_key: dict_output}

    # Act
    adapter.save_context(inputs, outputs)

    # Assert
    mock_memory_bank.create_memory_block.assert_called_once()
    saved_block = mock_memory_bank.create_memory_block.call_args[0][0]
    assert "Output: This is the main text" in saved_block.text
    assert saved_block.metadata.get("confidence") == 0.95


def test_save_context_dict_output_no_text_key(adapter, mock_memory_bank):
    """Test that dictionary outputs without a 'text' key are converted to strings."""
    # Arrange
    inputs = {adapter.input_key: "Hello"}
    dict_output = {"output": {"choices": ["A", "B"]}, "metadata": {"confidence": 0.95}}
    outputs = {adapter.output_key: dict_output}

    # Act
    adapter.save_context(inputs, outputs)

    # Assert
    mock_memory_bank.create_memory_block.assert_called_once()
    saved_block = mock_memory_bank.create_memory_block.call_args[0][0]
    assert "Output: " in saved_block.text
    assert "choices" in saved_block.text
    assert saved_block.metadata.get("confidence") == 0.95


def test_save_context_all_features_combined(adapter, mock_memory_bank):
    """Test all enhanced features together in one save operation."""
    # Arrange
    session_id = "comprehensive_test_session"
    model_name = "gpt-3.5-turbo"
    token_count = {"prompt": 200, "completion": 75}
    latency_ms = 650

    inputs = {
        adapter.input_key: f"Using {{{adapter.memory_key}}}, answer: What is ML?",
        "session_id": session_id,
        "model": model_name,
        "token_count": token_count,
        "latency": latency_ms,
    }
    outputs = {
        adapter.output_key: {
            "output": "Machine Learning is...",
            "metadata": {"confidence": 0.95, "other_info": "additional details"},
        }
    }

    # Act
    adapter.save_context(inputs, outputs)

    # Assert
    mock_memory_bank.create_memory_block.assert_called_once()
    saved_block = mock_memory_bank.create_memory_block.call_args[0][0]

    # Check sanitization
    assert "Input: Using , answer: What is ML?" in saved_block.text

    # Check output handling
    assert "Output: Machine Learning is..." in saved_block.text

    # Check tags
    assert f"session:{session_id}" in saved_block.tags
    assert "date:" in saved_block.tags[1]
    assert f"type:{adapter.save_interaction_type}" in saved_block.tags

    # Check metadata
    assert saved_block.metadata["model"] == model_name
    assert saved_block.metadata["session_id"] == session_id
    assert saved_block.metadata["token_count"] == token_count
    assert saved_block.metadata["latency_ms"] == latency_ms
    assert saved_block.metadata["confidence"] == 0.95
    assert "timestamp" in saved_block.metadata


# TODO: Add tests for error handling in load/save
# TODO: Add tests for clear() method behavior (raising NotImplementedError)
# TODO: Add tests for _format_blocks_to_markdown specifically if needed
