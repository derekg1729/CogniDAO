"""
Tests for the LogInteractionBlockTool.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

from experiments.src.memory_system.tools.agent_facing.log_interaction_block_tool import (
    LogInteractionBlockInput,
    LogInteractionBlockOutput,
    log_interaction_block,
    log_interaction_block_tool,
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
