"""
Tests for the LogInteractionBlockTool.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from experiments.src.memory_system.tools.agent_facing.log_interaction_block_tool import (
    LogInteractionBlockInput,
    LogInteractionBlockOutput,
    log_interaction_block,
    log_interaction_block_tool,
)

# Import CreateMemoryBlockInput for type hinting in test
from experiments.src.memory_system.tools.memory_core.create_memory_block_tool import (
    CreateMemoryBlockInput,
)
from experiments.src.memory_system.structured_memory_bank import StructuredMemoryBank


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
    return LogInteractionBlockInput(
        input_text="Hello",
        output_text="Hi there",
        session_id="test_session",
        model="gpt-4",
        token_count={"prompt": 150, "completion": 50},
        latency_ms=500.0,
        tags=["test"],
    )


def test_log_interaction_block_success(mock_memory_bank, sample_input):
    """Test successful interaction logging."""
    result = log_interaction_block(sample_input, mock_memory_bank)

    assert isinstance(result, LogInteractionBlockOutput)
    assert result.success is True
    assert result.id is not None
    assert result.error is None
    assert isinstance(result.timestamp, datetime)

    # Verify memory bank calls
    mock_memory_bank.get_latest_schema_version.assert_called_once_with("log")
    mock_memory_bank.create_memory_block.assert_called_once()


def test_log_interaction_block_minimal_input(mock_memory_bank):
    """Test interaction logging with minimal required input."""
    minimal_input = LogInteractionBlockInput(input_text="Hello", output_text="Hi there")

    result = log_interaction_block(minimal_input, mock_memory_bank)

    assert isinstance(result, LogInteractionBlockOutput)
    assert result.success is True
    assert result.id is not None
    assert result.error is None


def test_log_interaction_block_persistence_failure(mock_memory_bank, sample_input):
    """Test interaction logging when persistence fails."""
    mock_memory_bank.create_memory_block.return_value = False

    result = log_interaction_block(sample_input, mock_memory_bank)

    assert isinstance(result, LogInteractionBlockOutput)
    assert result.success is False
    assert result.id is None
    assert "Failed to persist" in result.error


def test_log_interaction_block_tool_initialization():
    """Test CogniTool initialization with LogInteractionBlock."""
    assert log_interaction_block_tool.name == "LogInteractionBlock"
    assert log_interaction_block_tool.memory_linked is True
    assert log_interaction_block_tool.input_model == LogInteractionBlockInput
    assert log_interaction_block_tool.output_model == LogInteractionBlockOutput


def test_log_interaction_block_tool_schema():
    """Test schema generation for LogInteractionBlock tool."""
    schema = log_interaction_block_tool.schema
    assert schema["name"] == "LogInteractionBlock"
    assert schema["type"] == "function"
    assert schema["memory_linked"] is True
    assert "parameters" in schema
    assert "returns" in schema


def test_log_interaction_block_tool_direct_invocation(mock_memory_bank, sample_input):
    """Test direct invocation of LogInteractionBlock tool."""
    result = log_interaction_block_tool(
        input_text=sample_input.input_text,
        output_text=sample_input.output_text,
        session_id=sample_input.session_id,
        model=sample_input.model,
        token_count=sample_input.token_count,
        latency_ms=sample_input.latency_ms,
        tags=sample_input.tags,
        memory_bank=mock_memory_bank,
    )

    assert isinstance(result, LogInteractionBlockOutput)
    assert result.success is True
    assert result.id is not None
    assert result.error is None


def test_log_interaction_block_tool_invalid_input(mock_memory_bank):
    """Test LogInteractionBlock tool with invalid input."""
    result = log_interaction_block_tool(
        input_text="Hello",  # Missing required 'output_text' field
        memory_bank=mock_memory_bank,
    )

    # Expect dict for input validation error
    assert isinstance(result, dict)
    assert result["success"] is False
    assert result["error"] == "Validation error"
    assert "details" in result


def test_log_interaction_block_unregistered_type(mock_memory_bank, sample_input):
    """Test interaction logging with an unregistered type."""
    # Configure mock to return None for schema version lookup
    mock_memory_bank.get_latest_schema_version.return_value = None

    result = log_interaction_block(sample_input, mock_memory_bank)

    assert isinstance(result, LogInteractionBlockOutput)
    assert result.success is False
    assert result.id is None
    assert "Schema definition missing or lookup failed for registered type: log" in result.error
    mock_memory_bank.get_latest_schema_version.assert_called_once_with("log")
    mock_memory_bank.create_memory_block.assert_not_called()


def test_log_interaction_block_with_parent(mock_memory_bank):
    """Test logging an interaction with a parent block ID."""
    parent_id = "task-123"
    input_data = LogInteractionBlockInput(
        input_text="Sub-query for task.",
        output_text="Result found.",
        parent_block=parent_id,
        created_by="sub_agent",
    )

    # Mock the underlying create_memory_block to capture its input
    # We assume create_memory_block itself works (tested elsewhere)
    # Need to return a valid success output from create_memory_block mock
    mock_create_output = MagicMock()
    mock_create_output.success = True
    mock_create_output.id = "log-abc"
    mock_create_output.timestamp = datetime.now()
    with patch(
        "experiments.src.memory_system.tools.agent_facing.log_interaction_block_tool.create_memory_block"
    ) as mock_create:
        mock_create.return_value = mock_create_output

        result = log_interaction_block(input_data, mock_memory_bank)

        assert isinstance(result, LogInteractionBlockOutput)
        assert result.success is True
        assert result.id == "log-abc"

        # Verify create_memory_block was called correctly
        mock_create.assert_called_once()
        call_args, call_kwargs = mock_create.call_args
        created_block_input: CreateMemoryBlockInput = call_args[0]

        # Assert that parent_block is in the metadata passed to create_memory_block
        assert "parent_block" in created_block_input.metadata
        assert created_block_input.metadata["parent_block"] == parent_id
        # Assert created_by was passed correctly too
        assert created_block_input.created_by == "sub_agent"
