"""
Tests for the LogInteractionBlockTool.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from pydantic import ValidationError

from infra_core.memory_system.tools.agent_facing.log_interaction_block_tool import (
    LogInteractionBlockInput,
    LogInteractionBlockOutput,
    log_interaction_block,
    log_interaction_block_tool,
)

# Import CreateMemoryBlockInput for type hinting in test
from infra_core.memory_system.tools.memory_core.create_memory_block_tool import (
    CreateMemoryBlockInput,
    CreateMemoryBlockOutput,  # Import Output for mocking return value
)
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank


@pytest.fixture
def mock_memory_bank():
    """Create a mock StructuredMemoryBank."""
    bank = MagicMock(spec=StructuredMemoryBank)
    bank.get_latest_schema_version.return_value = 1
    # Mock the core create_memory_block function's output
    mock_create_output = CreateMemoryBlockOutput(
        success=True, id="new_block_123", timestamp=datetime.now()
    )
    bank.create_memory_block.return_value = mock_create_output
    return bank


@pytest.fixture
def sample_input():
    """Create a sample input for testing using new field names."""
    return LogInteractionBlockInput(
        input_text="Hello",
        output_text="Hi there",
        x_session_id="test_session",  # Renamed
        model="gpt-4",
        token_count={"prompt": 150, "completion": 50},
        latency_ms=500.0,
        tags=["test"],
        created_by="test_creator",  # Specify creator for agent_id fallback test
    )


# Patch the core create_memory_block function within the tool's module scope
@patch("infra_core.memory_system.tools.agent_facing.log_interaction_block_tool.create_memory_block")
def test_log_interaction_block_success(mock_create_memory_block, mock_memory_bank, sample_input):
    """Test successful interaction logging and correct metadata passing."""
    # Configure the mock return value for create_memory_block
    mock_create_output = CreateMemoryBlockOutput(
        success=True, id="log-block-id-success", timestamp=datetime.now()
    )
    mock_create_memory_block.return_value = mock_create_output

    result = log_interaction_block(sample_input, mock_memory_bank)

    assert isinstance(result, LogInteractionBlockOutput)
    assert result.success is True
    assert result.id == "log-block-id-success"
    assert result.error is None
    assert isinstance(result.timestamp, datetime)

    # Verify create_memory_block was called correctly
    mock_create_memory_block.assert_called_once()
    call_args, call_kwargs = mock_create_memory_block.call_args
    created_block_input: CreateMemoryBlockInput = call_args[0]
    passed_memory_bank = call_args[1]

    assert passed_memory_bank is mock_memory_bank
    assert created_block_input.type == "log"
    assert created_block_input.created_by == sample_input.created_by

    # Verify metadata dictionary passed to create_memory_block
    metadata = created_block_input.metadata
    assert metadata["input_text"] == sample_input.input_text
    assert metadata["output_text"] == sample_input.output_text
    assert metadata["model"] == sample_input.model
    assert metadata["token_count"] == sample_input.token_count
    assert metadata["latency_ms"] == sample_input.latency_ms
    assert metadata["x_session_id"] == sample_input.x_session_id
    assert metadata["x_tool_id"] == "LogInteractionBlockTool"
    # Ensure fields not provided in input are not present (they'll be added by core tool if needed)
    assert "x_timestamp" not in metadata
    assert "x_agent_id" not in metadata
    assert "x_parent_block_id" not in metadata


# Patch the core create_memory_block function
@patch("infra_core.memory_system.tools.agent_facing.log_interaction_block_tool.create_memory_block")
def test_log_interaction_block_minimal_input(mock_create_memory_block, mock_memory_bank):
    """Test interaction logging with minimal required input."""
    mock_create_output = CreateMemoryBlockOutput(
        success=True, id="log-block-id-min", timestamp=datetime.now()
    )
    mock_create_memory_block.return_value = mock_create_output

    minimal_input = LogInteractionBlockInput(input_text="Min Hello", output_text="Min Hi")

    result = log_interaction_block(minimal_input, mock_memory_bank)

    assert isinstance(result, LogInteractionBlockOutput)
    assert result.success is True
    assert result.id == "log-block-id-min"

    # Verify metadata passed
    mock_create_memory_block.assert_called_once()
    call_args, call_kwargs = mock_create_memory_block.call_args
    created_block_input: CreateMemoryBlockInput = call_args[0]
    metadata = created_block_input.metadata

    assert metadata["input_text"] == "Min Hello"
    assert metadata["output_text"] == "Min Hi"
    assert metadata["x_tool_id"] == "LogInteractionBlockTool"
    assert "model" not in metadata
    assert "token_count" not in metadata
    assert "latency_ms" not in metadata
    assert "x_session_id" not in metadata
    assert "x_parent_block_id" not in metadata


# Patch the core create_memory_block function
@patch("infra_core.memory_system.tools.agent_facing.log_interaction_block_tool.create_memory_block")
def test_log_interaction_block_persistence_failure(
    mock_create_memory_block, mock_memory_bank, sample_input
):
    """Test interaction logging when core persistence fails."""
    # Simulate failure from the core create_memory_block function
    mock_create_output = CreateMemoryBlockOutput(
        success=False, error="Core persistence failed", timestamp=datetime.now()
    )
    mock_create_memory_block.return_value = mock_create_output

    result = log_interaction_block(sample_input, mock_memory_bank)

    assert isinstance(result, LogInteractionBlockOutput)
    assert result.success is False
    assert result.id is None
    assert result.error == "Core persistence failed"  # Error should propagate from core tool
    mock_create_memory_block.assert_called_once()


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
    # Check renamed fields in schema parameters
    assert "x_parent_block_id" in schema["parameters"]["properties"]
    assert "x_session_id" in schema["parameters"]["properties"]
    assert "parent_block" not in schema["parameters"]["properties"]
    assert "session_id" not in schema["parameters"]["properties"]


# Patch the core create_memory_block function
@patch("infra_core.memory_system.tools.agent_facing.log_interaction_block_tool.create_memory_block")
def test_log_interaction_block_tool_direct_invocation(
    mock_create_memory_block, mock_memory_bank, sample_input
):
    """Test direct invocation of LogInteractionBlock tool."""
    mock_create_output = CreateMemoryBlockOutput(
        success=True, id="log-block-id-direct", timestamp=datetime.now()
    )
    mock_create_memory_block.return_value = mock_create_output

    # Use new input field names
    result = log_interaction_block_tool(
        input_text=sample_input.input_text,
        output_text=sample_input.output_text,
        x_session_id=sample_input.x_session_id,
        model=sample_input.model,
        token_count=sample_input.token_count,
        latency_ms=sample_input.latency_ms,
        tags=sample_input.tags,
        created_by=sample_input.created_by,
        memory_bank=mock_memory_bank,
    )

    assert isinstance(result, LogInteractionBlockOutput)
    assert result.success is True
    assert result.id == "log-block-id-direct"
    mock_create_memory_block.assert_called_once()


def test_log_interaction_block_tool_invalid_input(mock_memory_bank):
    """Test LogInteractionBlock tool with invalid input (missing required field)."""
    # Mock the function directly called by the tool instance
    with patch(
        "infra_core.memory_system.tools.agent_facing.log_interaction_block_tool.log_interaction_block"
    ) as mock_func:
        # Tool input validation happens before the function is called
        result = log_interaction_block_tool(
            input_text="Hello",  # Missing required 'output_text'
            memory_bank=mock_memory_bank,
        )
        mock_func.assert_not_called()  # Function shouldn't be called if input validation fails

    # Expect structured error output model
    assert isinstance(result, LogInteractionBlockOutput)
    assert result.success is False
    # Error message should mention validation and the missing field
    assert "Validation error" in result.error
    assert "output_text" in (result.error or "")


# Test for failure if create_memory_block itself raises an exception (e.g., validation within core tool)
@patch("infra_core.memory_system.tools.agent_facing.log_interaction_block_tool.create_memory_block")
def test_log_interaction_block_core_validation_failure(
    mock_create_memory_block, mock_memory_bank, sample_input
):
    """Test handling when create_memory_block raises a validation error."""
    mock_create_memory_block.side_effect = ValidationError.from_exception_data(
        "Test Core Validation Error", line_errors=[]
    )

    result = log_interaction_block(sample_input, mock_memory_bank)

    assert isinstance(result, LogInteractionBlockOutput)
    assert result.success is False
    assert "Test Core Validation Error" in result.error
    mock_create_memory_block.assert_called_once()


# Patch the core create_memory_block function
@patch("infra_core.memory_system.tools.agent_facing.log_interaction_block_tool.create_memory_block")
def test_log_interaction_block_with_parent(mock_create_memory_block, mock_memory_bank):
    """Test logging an interaction with a parent block ID passed correctly."""
    mock_create_output = CreateMemoryBlockOutput(
        success=True, id="log-block-id-parent", timestamp=datetime.now()
    )
    mock_create_memory_block.return_value = mock_create_output

    parent_id = "task-123"
    # Use new input field name
    input_data = LogInteractionBlockInput(
        input_text="Sub-query for task.",
        output_text="Result found.",
        x_parent_block_id=parent_id,
        created_by="sub_agent",
    )

    result = log_interaction_block(input_data, mock_memory_bank)

    assert isinstance(result, LogInteractionBlockOutput)
    assert result.success is True
    assert result.id == "log-block-id-parent"

    # Verify create_memory_block was called correctly
    mock_create_memory_block.assert_called_once()
    call_args, call_kwargs = mock_create_memory_block.call_args
    created_block_input: CreateMemoryBlockInput = call_args[0]

    # Assert that parent_block_id is in the metadata passed to create_memory_block
    assert "x_parent_block_id" in created_block_input.metadata
    assert created_block_input.metadata["x_parent_block_id"] == parent_id
    # Assert created_by was passed correctly too
    assert created_block_input.created_by == "sub_agent"
    # Assert tool_id was passed
    assert created_block_input.metadata["x_tool_id"] == "LogInteractionBlockTool"
