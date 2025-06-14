"""
Tests for the CogniStructuredMemoryAdapter.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import uuid
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.schemas.memory_block import MemoryBlock

# Assuming path setup allows importing these:
from infra_core.memory_system.langchain_adapter import CogniStructuredMemoryAdapter


# --- Helper Functions ---
def mock_log_tool_success():
    """Creates a standard success mock return object for log_interaction_block_tool."""
    return MagicMock(success=True, id=f"mock_block_{uuid.uuid4()}", timestamp=datetime.now())


# --- Fixtures ---


@pytest.fixture
def mock_memory_bank():
    """Provides a MagicMock instance of StructuredMemoryBank."""
    mock_bank = MagicMock(spec=StructuredMemoryBank)
    mock_bank.query_semantic = MagicMock(return_value=[])  # Default: return empty list
    mock_bank.create_memory_block = MagicMock(
        return_value=(True, None)
    )  # Default: simulate success
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


@pytest.mark.skip(reason="Deprecated - legacy LangChain adapter")
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


@pytest.mark.skip(reason="Deprecated - legacy LangChain adapter")
def test_load_memory_variables_no_input(adapter, mock_memory_bank):
    """Test load_memory_variables handles missing input key."""
    # Act
    result = adapter.load_memory_variables({"other_key": "some value"})

    # Assert
    mock_memory_bank.query_semantic.assert_not_called()
    assert result == {adapter.memory_key: "Input query not provided."}


@pytest.mark.skip(reason="Deprecated - legacy LangChain adapter")
@patch("infra_core.memory_system.langchain_adapter.log_interaction_block_tool")
def test_save_context_success(mock_log_tool, adapter, mock_memory_bank):
    """Test save_context calls log_interaction_block_tool correctly."""
    # Arrange
    mock_log_tool.return_value = mock_log_tool_success()
    input_text = "What is the weather?"
    output_text = "It is sunny."
    fixed_tags = ["session123"]
    adapter.save_tags = fixed_tags
    inputs = {adapter.input_key: input_text, "user_id": "test_user"}
    outputs = {adapter.output_key: output_text}

    # Act
    adapter.save_context(inputs, outputs)

    # Assert
    mock_log_tool.assert_called_once()
    call_args, call_kwargs = mock_log_tool.call_args
    assert call_kwargs["memory_bank"] == mock_memory_bank
    assert call_kwargs["input_text"] == input_text
    assert call_kwargs["output_text"] == output_text
    assert call_kwargs["created_by"] == "test_user"
    assert "session123" in call_kwargs["tags"]


@pytest.mark.skip(reason="Deprecated - legacy LangChain adapter")
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


@pytest.mark.skip(reason="Deprecated - legacy LangChain adapter")
@patch("infra_core.memory_system.langchain_adapter.log_interaction_block_tool")
def test_save_context_session_id_tag(mock_log_tool, adapter, mock_memory_bank):
    """Test session_id from inputs is passed to the tool."""
    # Arrange
    mock_log_tool.return_value = mock_log_tool_success()
    session_id = "test_session_12345"
    inputs = {adapter.input_key: "Hello", "session_id": session_id, "user_id": "test_user"}
    outputs = {adapter.output_key: "Hi there"}

    # Act
    adapter.save_context(inputs, outputs)

    # Assert
    mock_log_tool.assert_called_once()
    call_args, call_kwargs = mock_log_tool.call_args
    assert call_kwargs["memory_bank"] == mock_memory_bank
    assert call_kwargs["x_session_id"] == session_id


@pytest.mark.skip(reason="Deprecated - legacy LangChain adapter")
@patch("infra_core.memory_system.langchain_adapter.log_interaction_block_tool")
def test_save_context_model_metadata(mock_log_tool, adapter, mock_memory_bank):
    """Test model info is passed to the tool."""
    # Arrange
    mock_log_tool.return_value = mock_log_tool_success()
    model_name = "gpt-4"
    inputs = {adapter.input_key: "Hello", "model": model_name, "user_id": "test_user"}
    outputs = {adapter.output_key: "Hi there"}

    # Act
    adapter.save_context(inputs, outputs)

    # Assert
    mock_log_tool.assert_called_once()
    call_args, call_kwargs = mock_log_tool.call_args
    assert call_kwargs["memory_bank"] == mock_memory_bank
    assert call_kwargs["model"] == model_name


@pytest.mark.skip(reason="Deprecated - legacy LangChain adapter")
@patch("infra_core.memory_system.langchain_adapter.log_interaction_block_tool")
def test_save_context_token_count_and_latency(mock_log_tool, adapter, mock_memory_bank):
    """Test token counts and latency are passed to the tool correctly."""
    # Arrange
    mock_log_tool.return_value = mock_log_tool_success()
    token_count = {"prompt": 150, "completion": 50}
    latency_ms = 500
    inputs = {adapter.input_key: "Hello", "token_count": token_count, "latency": latency_ms}
    outputs = {adapter.output_key: "Hi there"}

    # Act
    adapter.save_context(inputs, outputs)

    # Assert
    mock_log_tool.assert_called_once()
    call_args, call_kwargs = mock_log_tool.call_args
    assert call_kwargs["memory_bank"] == mock_memory_bank
    assert call_kwargs["token_count"] == token_count
    assert call_kwargs["latency_ms"] == latency_ms


@pytest.mark.skip(reason="Deprecated - legacy LangChain adapter")
@patch("infra_core.memory_system.langchain_adapter.log_interaction_block_tool")
def test_save_context_sanitization(mock_log_tool, adapter, mock_memory_bank):
    """Test that input is sanitized to remove memory placeholders."""
    # Arrange
    mock_log_tool.return_value = mock_log_tool_success()
    memory_key = adapter.memory_key
    input_with_placeholder = f"Answer this question based on {{{memory_key}}}: What is Python?"
    inputs = {adapter.input_key: input_with_placeholder, "user_id": "test_user"}
    outputs = {adapter.output_key: "Python is a programming language"}

    # Expected sanitized input
    expected_sanitized = "Answer this question based on : What is Python?"

    # Act
    adapter.save_context(inputs, outputs)

    # Assert
    mock_log_tool.assert_called_once()
    call_args, call_kwargs = mock_log_tool.call_args
    assert call_kwargs["input_text"] == expected_sanitized
    assert call_kwargs["output_text"] == "Python is a programming language"


@pytest.mark.skip(reason="Deprecated - legacy LangChain adapter")
@patch("infra_core.memory_system.langchain_adapter.log_interaction_block_tool")
def test_save_context_dict_output(mock_log_tool, adapter, mock_memory_bank):
    """Test that dictionary outputs are handled correctly."""
    # Arrange
    mock_log_tool.return_value = mock_log_tool_success()
    inputs = {adapter.input_key: "Hello", "user_id": "test_user"}
    dict_output = {"output": "This is the main text", "metadata": {"confidence": 0.95}}
    outputs = {adapter.output_key: dict_output}

    # Act
    adapter.save_context(inputs, outputs)

    # Assert
    mock_log_tool.assert_called_once()
    call_args, call_kwargs = mock_log_tool.call_args
    assert call_kwargs["input_text"] == "Hello"
    # Check that it can handle dict outputs
    assert isinstance(call_kwargs["output_text"], dict)


@pytest.mark.skip(reason="Deprecated - legacy LangChain adapter")
@patch("infra_core.memory_system.langchain_adapter.log_interaction_block_tool")
def test_save_context_dict_output_no_text_key(mock_log_tool, adapter, mock_memory_bank):
    """Test that dictionary outputs without a 'text' key are converted to strings."""
    # Arrange
    mock_log_tool.return_value = mock_log_tool_success()
    inputs = {adapter.input_key: "Hello", "user_id": "test_user"}
    dict_output = {"output": {"choices": ["A", "B"]}, "metadata": {"confidence": 0.95}}
    outputs = {adapter.output_key: dict_output}

    # Act
    adapter.save_context(inputs, outputs)

    # Assert
    mock_log_tool.assert_called_once()
    call_args, call_kwargs = mock_log_tool.call_args
    assert call_kwargs["input_text"] == "Hello"
    # Check that it can handle complex dict outputs
    assert isinstance(call_kwargs["output_text"], dict)


@pytest.mark.skip(reason="Deprecated - legacy LangChain adapter")
@patch("infra_core.memory_system.langchain_adapter.log_interaction_block_tool")
def test_save_context_all_features_combined(mock_log_tool, adapter, mock_memory_bank):
    """Test save_context passes all features combined to the tool."""
    # Arrange
    mock_log_tool.return_value = mock_log_tool_success()
    session_id = "combined_session_007"
    model_name = "claude-3"
    token_count = {"input": 10, "output": 20}
    latency_ms = 123.4
    fixed_tags = ["project_x"]
    adapter.save_tags = fixed_tags
    inputs = {
        adapter.input_key: "Complex input?",
        "session_id": session_id,
        "model": model_name,
        "token_count": token_count,
        "latency": latency_ms,
        "user_id": "test_user",
    }
    outputs = {adapter.output_key: "Complex output!"}

    # Act
    adapter.save_context(inputs, outputs)

    # Assert
    mock_log_tool.assert_called_once()
    call_args, call_kwargs = mock_log_tool.call_args
    assert call_kwargs["memory_bank"] == mock_memory_bank
    assert call_kwargs["input_text"] == inputs[adapter.input_key]
    assert call_kwargs["output_text"] == outputs[adapter.output_key]
    assert call_kwargs["x_session_id"] == session_id
    assert call_kwargs["model"] == model_name
    assert call_kwargs["token_count"] == token_count
    assert call_kwargs["latency_ms"] == latency_ms
    assert "project_x" in call_kwargs["tags"]
    assert call_kwargs["created_by"] == "test_user"
    assert any(tag.startswith("date:") for tag in call_kwargs["tags"])


# TODO: Add tests for error handling in load/save
# TODO: Add tests for clear() method behavior (raising NotImplementedError)
# TODO: Add tests for _format_blocks_to_markdown specifically if needed
