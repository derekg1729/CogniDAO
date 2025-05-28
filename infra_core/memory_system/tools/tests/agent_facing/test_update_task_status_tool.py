"""
Tests for the UpdateTaskStatusTool.
"""

import uuid
import pytest
from unittest.mock import MagicMock
from datetime import datetime

from infra_core.memory_system.schemas.memory_block import MemoryBlock
from infra_core.memory_system.tools.agent_facing.update_task_status_tool import (
    update_task_status_tool,
    update_task_status,
    UpdateTaskStatusInput,
    UpdateTaskStatusOutput,
)


@pytest.fixture
def mock_memory_bank():
    """Create a mock memory bank for testing."""
    mock_bank = MagicMock()
    return mock_bank


@pytest.fixture
def task_memory_block():
    """Create a sample task memory block for testing."""
    block_id = str(uuid.uuid4())
    return MemoryBlock(
        id=block_id,
        type="task",
        text="Sample task description",
        metadata={
            # Required fields
            "x_agent_id": "test_agent",
            "x_timestamp": datetime.now().isoformat(),
            # Task-specific fields
            "title": "Sample Task",
            "description": "Sample task description",
            "status": "backlog",
            "acceptance_criteria": ["Criterion 1", "Criterion 2"],
        },
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def test_update_task_status_success(mock_memory_bank, task_memory_block):
    """Test successful status update."""
    # Setup
    mock_memory_bank.get_memory_block.return_value = task_memory_block
    mock_memory_bank.update_memory_block.return_value = True

    # Execute
    input_data = UpdateTaskStatusInput(
        block_id=task_memory_block.id,
        status="in_progress",
        update_message="Starting work on this task",
    )
    result = update_task_status(input_data, mock_memory_bank)

    # Assert
    assert result.success is True
    assert result.block_id == task_memory_block.id
    assert result.previous_status == "backlog"
    assert result.new_status == "in_progress"
    assert "execution_phase" in result.updated_metadata
    assert result.updated_metadata["execution_phase"] == "implementing"

    # Verify call to update_memory_block was made
    mock_memory_bank.update_memory_block.assert_called_once()


def test_update_task_status_with_execution_phase(mock_memory_bank, task_memory_block):
    """Test status update with explicit execution phase."""
    # Setup
    mock_memory_bank.get_memory_block.return_value = task_memory_block
    mock_memory_bank.update_memory_block.return_value = True

    # Execute
    input_data = UpdateTaskStatusInput(
        block_id=task_memory_block.id,
        status="in_progress",
        execution_phase="designing",
        update_message="Starting design work",
    )
    result = update_task_status(input_data, mock_memory_bank)

    # Assert
    assert result.success is True
    assert result.new_status == "in_progress"
    assert result.updated_metadata["execution_phase"] == "designing"


def test_update_task_status_to_done(mock_memory_bank, task_memory_block):
    """Test update to done status with validation report."""
    # Setup - create task with validation report
    task_with_validation = task_memory_block.model_copy(deep=True)
    task_with_validation.metadata["validation_report"] = {
        "validated_by": "test-agent",
        "timestamp": datetime.now().isoformat(),
        "results": [
            {"criterion": "Criterion 1", "status": "pass", "notes": None},
            {"criterion": "Criterion 2", "status": "pass", "notes": None},
        ],
    }
    mock_memory_bank.get_memory_block.return_value = task_with_validation
    mock_memory_bank.update_memory_block.return_value = True

    # Execute
    input_data = UpdateTaskStatusInput(
        block_id=task_with_validation.id,
        status="done",
        update_message="Task completed and validated",
    )
    result = update_task_status(input_data, mock_memory_bank)

    # Assert
    assert result.success is True
    assert result.new_status == "done"
    assert result.updated_metadata["execution_phase"] is None


def test_update_task_status_to_done_without_validation(mock_memory_bank, task_memory_block):
    """Test update to done status without validation report (should fail)."""
    # Setup
    mock_memory_bank.get_memory_block.return_value = task_memory_block

    # Execute
    input_data = UpdateTaskStatusInput(
        block_id=task_memory_block.id,
        status="done",
        update_message="Trying to mark as done without validation",
    )
    result = update_task_status(input_data, mock_memory_bank)

    # Assert
    assert result.success is False
    assert (
        "validation report" in result.error.lower()
        or "cannot set status to 'done'" in result.error.lower()
    )
    mock_memory_bank.update_memory_block.assert_not_called()


def test_update_task_status_to_done_force(mock_memory_bank, task_memory_block):
    """Test forced update to done status without validation report."""
    # Setup
    mock_memory_bank.get_memory_block.return_value = task_memory_block
    mock_memory_bank.update_memory_block.return_value = True

    # Execute
    input_data = UpdateTaskStatusInput(
        block_id=task_memory_block.id,
        status="done",
        force=True,
        update_message="Forcing completion without validation",
    )
    result = update_task_status(input_data, mock_memory_bank)

    # Assert
    assert result.success is True
    assert result.new_status == "done"


def test_update_task_status_no_change(mock_memory_bank, task_memory_block):
    """Test update with same status (no change)."""
    # Setup
    mock_memory_bank.get_memory_block.return_value = task_memory_block

    # Execute
    input_data = UpdateTaskStatusInput(
        block_id=task_memory_block.id,
        status="backlog",  # Same as current status
    )
    result = update_task_status(input_data, mock_memory_bank)

    # Assert
    assert result.success is True
    assert "no status change needed" in result.error.lower()
    mock_memory_bank.update_memory_block.assert_not_called()


def test_update_task_status_force_same(mock_memory_bank, task_memory_block):
    """Test forced update with same status."""
    # Setup
    mock_memory_bank.get_memory_block.return_value = task_memory_block
    mock_memory_bank.update_memory_block.return_value = True

    # Execute
    input_data = UpdateTaskStatusInput(
        block_id=task_memory_block.id,
        status="backlog",  # Same as current status
        force=True,
    )
    result = update_task_status(input_data, mock_memory_bank)

    # Assert
    assert result.success is True
    assert result.previous_status == "backlog"
    assert result.new_status == "backlog"
    mock_memory_bank.update_memory_block.assert_called_once()


def test_update_task_status_execution_phase_reset(mock_memory_bank, task_memory_block):
    """Test execution_phase is reset when status is not in_progress."""
    # Setup - task with execution_phase set
    task_in_progress = task_memory_block.model_copy(deep=True)
    task_in_progress.metadata["status"] = "in_progress"
    task_in_progress.metadata["execution_phase"] = "implementing"
    mock_memory_bank.get_memory_block.return_value = task_in_progress
    mock_memory_bank.update_memory_block.return_value = True

    # Execute - change to review
    input_data = UpdateTaskStatusInput(
        block_id=task_in_progress.id, status="review", update_message="Ready for review"
    )
    result = update_task_status(input_data, mock_memory_bank)

    # Assert
    assert result.success is True
    assert result.new_status == "review"
    assert result.updated_metadata["execution_phase"] is None


def test_update_task_status_history_addition(mock_memory_bank, task_memory_block):
    """Test status history entry is added with update message."""
    # Setup
    mock_memory_bank.get_memory_block.return_value = task_memory_block
    mock_memory_bank.update_memory_block.return_value = True

    # Execute
    input_data = UpdateTaskStatusInput(
        block_id=task_memory_block.id,
        status="in_progress",
        update_message="Starting work on this task",
    )
    result = update_task_status(input_data, mock_memory_bank)

    # Assert
    assert result.success is True
    assert "status_history" in result.updated_metadata
    history_entry = result.updated_metadata["status_history"][0]
    assert history_entry["from_status"] == "backlog"
    assert history_entry["to_status"] == "in_progress"
    assert history_entry["message"] == "Starting work on this task"
    assert "timestamp" in history_entry


def test_update_task_status_block_not_found(mock_memory_bank):
    """Test update with non-existent block ID."""
    # Setup
    mock_memory_bank.get_memory_block.return_value = None

    # Execute
    input_data = UpdateTaskStatusInput(block_id=str(uuid.uuid4()), status="in_progress")
    result = update_task_status(input_data, mock_memory_bank)

    # Assert
    assert result.success is False
    assert "not found" in result.error.lower()


def test_update_task_status_wrong_block_type(mock_memory_bank, task_memory_block):
    """Test update with non-task block type."""
    # Setup - change block type to something else
    non_task_block = task_memory_block.model_copy(deep=True)
    non_task_block.type = "project"
    mock_memory_bank.get_memory_block.return_value = non_task_block

    # Execute
    input_data = UpdateTaskStatusInput(block_id=non_task_block.id, status="in_progress")
    result = update_task_status(input_data, mock_memory_bank)

    # Assert
    assert result.success is False
    assert "not a task" in result.error.lower()


def test_update_task_status_metadata_validation_error(mock_memory_bank, task_memory_block):
    """Test update with invalid metadata structure."""
    # Setup - create invalid metadata
    invalid_task = task_memory_block.model_copy(deep=True)
    # Remove required field from metadata
    del invalid_task.metadata["title"]
    mock_memory_bank.get_memory_block.return_value = invalid_task

    # Execute
    input_data = UpdateTaskStatusInput(block_id=invalid_task.id, status="in_progress")
    result = update_task_status(input_data, mock_memory_bank)

    # Assert
    assert result.success is False
    assert "failed to validate" in result.error.lower()


def test_update_task_status_update_failure(mock_memory_bank, task_memory_block):
    """Test update failure in memory bank."""
    # Setup
    mock_memory_bank.get_memory_block.return_value = task_memory_block
    mock_memory_bank.update_memory_block.return_value = False  # Update fails

    # Execute
    input_data = UpdateTaskStatusInput(block_id=task_memory_block.id, status="in_progress")
    result = update_task_status(input_data, mock_memory_bank)

    # Assert
    assert result.success is False
    assert (
        "failed to update" in result.error.lower()
        or "memory block in database" in result.error.lower()
    )


def test_update_task_status_exception(mock_memory_bank, task_memory_block):
    """Test exception handling."""
    # Setup
    mock_memory_bank.get_memory_block.return_value = task_memory_block
    mock_memory_bank.update_memory_block.side_effect = Exception("Simulated error")

    # Execute
    input_data = UpdateTaskStatusInput(block_id=task_memory_block.id, status="in_progress")
    result = update_task_status(input_data, mock_memory_bank)

    # Assert
    assert result.success is False
    assert "an error occurred" in result.error.lower() or "simulated error" in result.error.lower()


def test_update_task_status_tool_initialization():
    """Test CogniTool initialization for UpdateTaskStatusTool."""
    assert update_task_status_tool.name == "update_task_status"
    assert update_task_status_tool.input_model == UpdateTaskStatusInput
    assert update_task_status_tool.output_model == UpdateTaskStatusOutput


def test_update_task_status_tool_schema():
    """Test UpdateTaskStatusTool schema properties."""
    # Update to access the input schema from the tool's input_model
    input_schema = update_task_status_tool.input_model.model_json_schema()

    # Check required fields in schema
    assert "block_id" in input_schema["properties"]
    assert "status" in input_schema["properties"]
    assert input_schema["properties"]["block_id"]["description"] is not None
    assert input_schema["properties"]["status"]["description"] is not None

    # Check optional fields
    assert "execution_phase" in input_schema["properties"]
    assert "update_message" in input_schema["properties"]
    assert "force" in input_schema["properties"]
