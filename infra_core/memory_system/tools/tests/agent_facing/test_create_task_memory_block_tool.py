"""
Tests for the CreateTaskMemoryBlockTool.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from infra_core.memory_system.tools.agent_facing.create_task_memory_block_tool import (
    CreateTaskMemoryBlockInput,
    CreateTaskMemoryBlockOutput,
    create_task_memory_block,
    create_task_memory_block_tool,
)
from infra_core.memory_system.tools.memory_core.create_memory_block_tool import (
    CreateMemoryBlockInput as CoreCreateMemoryBlockInput,
    CreateMemoryBlockOutput as CoreCreateMemoryBlockOutput,
)
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank


@pytest.fixture
def mock_memory_bank():
    """Create a mock StructuredMemoryBank."""
    bank = MagicMock(spec=StructuredMemoryBank)
    # Mock the core create_memory_block function's typical success output
    mock_core_output = CoreCreateMemoryBlockOutput(
        success=True, id="task_block_123", timestamp=datetime.now()
    )
    bank.create_memory_block.return_value = mock_core_output
    return bank


@pytest.fixture
def sample_task_input_data():
    """Create a sample input for testing CreateTaskMemoryBlockInput with all fields."""
    return {
        # Core task fields
        "title": "Implement Task Creation Tool",
        "description": "Create an agent-facing tool for task creation with ExecutableMetadata fields",
        "assignee": "developer_123",
        # Status and planning fields
        "status": "in_progress",
        "priority": "P1",
        "execution_phase": "implementing",
        # Time tracking fields
        "story_points": 5.0,
        "estimate_hours": 8.0,
        "start_date": datetime(2023, 10, 1, 10, 0, 0),
        "due_date": datetime(2023, 10, 5, 17, 0, 0),
        # ExecutableMetadata planning fields
        "action_items": [
            "Create input model",
            "Implement metadata mapping",
            "Write tests",
        ],
        "acceptance_criteria": [
            "All metadata fields correctly mapped",
            "Tool passes validation tests",
            "Error handling works correctly",
        ],
        "expected_artifacts": [
            "create_task_memory_block_tool.py",
            "test_create_task_memory_block_tool.py",
        ],
        "blocked_by": ["123e4567-e89b-12d3-a456-426614174000"],
        # Agent framework fields
        "tool_hints": ["editor", "test_runner"],
        "role_hint": "developer",
        "execution_timeout_minutes": 60,
        "cost_budget_usd": 5.0,
        # Labels and additional metadata
        "labels": ["tool", "task-creation", "agent-facing"],
        "confidence_score": {"human": 0.9, "ai": 0.85},
        # Optional phase and implementation details
        "phase": "Implementation Phase",
        "implementation_details": {
            "target_file": "create_task_memory_block_tool.py",
            "dependencies": ["memory_block.py", "executable.py"],
        },
        # Additional fields from CoreCreateMemoryBlockInput
        "source_file": "task_tool.md",
        "tags": ["memory-system", "tools", "task"],
        "state": "published",
        "visibility": "internal",
        "created_by": "test_agent",
    }


@pytest.fixture
def sample_task_input(sample_task_input_data):
    """Create a CreateTaskMemoryBlockInput instance from sample data."""
    return CreateTaskMemoryBlockInput(**sample_task_input_data)


# Patch the core create_memory_block function within the tool's module scope
@patch(
    "infra_core.memory_system.tools.agent_facing.create_task_memory_block_tool.create_memory_block"
)
def test_create_task_memory_block_success(
    mock_core_create_block, mock_memory_bank, sample_task_input
):
    """Test successful task block creation and correct metadata passing."""
    mock_core_output = CoreCreateMemoryBlockOutput(
        success=True, id="new-task-id-success", timestamp=datetime.now()
    )
    mock_core_create_block.return_value = mock_core_output

    result = create_task_memory_block(sample_task_input, mock_memory_bank)

    assert isinstance(result, CreateTaskMemoryBlockOutput)
    assert result.success is True
    assert result.id == "new-task-id-success"
    assert result.error is None
    assert isinstance(result.timestamp, datetime)

    mock_core_create_block.assert_called_once()
    call_args, _ = mock_core_create_block.call_args
    created_core_input: CoreCreateMemoryBlockInput = call_args[0]
    passed_memory_bank = call_args[1]

    assert passed_memory_bank is mock_memory_bank
    assert created_core_input.type == "task"
    assert created_core_input.text == sample_task_input.description
    assert created_core_input.created_by == sample_task_input.created_by
    assert created_core_input.source_file == sample_task_input.source_file
    assert created_core_input.tags == sample_task_input.tags

    # Verify key metadata fields
    metadata = created_core_input.metadata
    assert metadata["title"] == sample_task_input.title
    assert metadata["description"] == sample_task_input.description
    assert metadata["assignee"] == sample_task_input.assignee
    assert metadata["status"] == sample_task_input.status
    assert metadata["priority"] == sample_task_input.priority
    assert metadata["execution_phase"] == sample_task_input.execution_phase

    # Verify ExecutableMetadata fields
    assert metadata["action_items"] == sample_task_input.action_items
    assert metadata["acceptance_criteria"] == sample_task_input.acceptance_criteria
    assert metadata["expected_artifacts"] == sample_task_input.expected_artifacts
    assert metadata["blocked_by"] == sample_task_input.blocked_by
    assert metadata["tool_hints"] == sample_task_input.tool_hints
    assert metadata["role_hint"] == sample_task_input.role_hint
    assert metadata["execution_timeout_minutes"] == sample_task_input.execution_timeout_minutes
    assert metadata["cost_budget_usd"] == sample_task_input.cost_budget_usd

    # Verify additional fields
    assert metadata["story_points"] == sample_task_input.story_points
    assert metadata["estimate_hours"] == sample_task_input.estimate_hours
    assert metadata["start_date"] == sample_task_input.start_date
    assert metadata["due_date"] == sample_task_input.due_date
    assert metadata["labels"] == sample_task_input.labels
    assert metadata["phase"] == sample_task_input.phase
    assert metadata["implementation_details"] == sample_task_input.implementation_details

    # Verify tool ID
    assert metadata["x_tool_id"] == "CreateTaskMemoryBlockTool"

    # Verify completed set to false by default
    assert metadata["completed"] is False


@patch(
    "infra_core.memory_system.tools.agent_facing.create_task_memory_block_tool.create_memory_block"
)
def test_create_task_memory_block_minimal_input(mock_core_create_block, mock_memory_bank):
    """Test task block creation with minimal required input."""
    mock_core_output = CoreCreateMemoryBlockOutput(
        success=True, id="min-task-id", timestamp=datetime.now()
    )
    mock_core_create_block.return_value = mock_core_output

    minimal_input = CreateTaskMemoryBlockInput(
        title="Setup Project", description="Initial project setup and configuration."
    )
    result = create_task_memory_block(minimal_input, mock_memory_bank)

    assert result.success is True
    assert result.id == "min-task-id"

    mock_core_create_block.assert_called_once()
    call_args, _ = mock_core_create_block.call_args
    created_core_input: CoreCreateMemoryBlockInput = call_args[0]
    metadata = created_core_input.metadata

    assert created_core_input.type == "task"
    assert created_core_input.text == "Initial project setup and configuration."
    assert metadata["title"] == "Setup Project"
    assert metadata["description"] == "Initial project setup and configuration."
    assert metadata["x_tool_id"] == "CreateTaskMemoryBlockTool"

    # Check defaults
    assert metadata["status"] == "backlog"
    assert metadata["completed"] is False
    assert "action_items" in metadata
    assert "acceptance_criteria" in metadata
    assert len(metadata["action_items"]) == 0
    assert len(metadata["acceptance_criteria"]) == 0


@patch(
    "infra_core.memory_system.tools.agent_facing.create_task_memory_block_tool.create_memory_block"
)
def test_create_task_memory_block_with_executable_fields(mock_core_create_block, mock_memory_bank):
    """Test task creation focusing on ExecutableMetadata fields."""
    mock_core_output = CoreCreateMemoryBlockOutput(
        success=True, id="executable-task-id", timestamp=datetime.now()
    )
    mock_core_create_block.return_value = mock_core_output

    executable_input = CreateTaskMemoryBlockInput(
        title="Test Executable Fields",
        description="Testing ExecutableMetadata fields",
        status="in_progress",
        execution_phase="implementing",
        action_items=["Step 1", "Step 2"],
        acceptance_criteria=["Criteria 1", "Criteria 2"],
        expected_artifacts=["Artifact 1"],
        tool_hints=["Tool 1", "Tool 2"],
        role_hint="tester",
        blocked_by=["123e4567-e89b-12d3-a456-426614174000"],
    )

    result = create_task_memory_block(executable_input, mock_memory_bank)
    assert result.success is True

    call_args, _ = mock_core_create_block.call_args
    created_core_input: CoreCreateMemoryBlockInput = call_args[0]
    metadata = created_core_input.metadata

    # Verify executable-specific fields
    assert metadata["status"] == "in_progress"
    assert metadata["execution_phase"] == "implementing"
    assert metadata["action_items"] == ["Step 1", "Step 2"]
    assert metadata["acceptance_criteria"] == ["Criteria 1", "Criteria 2"]
    assert metadata["expected_artifacts"] == ["Artifact 1"]
    assert metadata["tool_hints"] == ["Tool 1", "Tool 2"]
    assert metadata["role_hint"] == "tester"
    assert metadata["blocked_by"] == ["123e4567-e89b-12d3-a456-426614174000"]


@patch(
    "infra_core.memory_system.tools.agent_facing.create_task_memory_block_tool.create_memory_block"
)
def test_create_task_memory_block_persistence_failure(
    mock_core_create_block, mock_memory_bank, sample_task_input
):
    """Test task block creation when core persistence fails."""
    mock_core_output = CoreCreateMemoryBlockOutput(
        success=False, error="Core persistence layer failed", timestamp=datetime.now()
    )
    mock_core_create_block.return_value = mock_core_output

    result = create_task_memory_block(sample_task_input, mock_memory_bank)

    assert result.success is False
    assert result.id is None
    assert result.error == "Core persistence layer failed"
    mock_core_create_block.assert_called_once()


@patch(
    "infra_core.memory_system.tools.agent_facing.create_task_memory_block_tool.create_memory_block"
)
def test_create_task_memory_block_core_exception(
    mock_core_create_block, mock_memory_bank, sample_task_input
):
    """Test handling when core create_memory_block raises an unexpected exception."""
    mock_core_create_block.side_effect = Exception("Unexpected core error")

    result = create_task_memory_block(sample_task_input, mock_memory_bank)

    assert result.success is False
    assert result.id is None
    assert "Error in create_task_memory_block wrapper: Unexpected core error" in result.error
    mock_core_create_block.assert_called_once()


def test_create_task_memory_block_tool_initialization():
    """Test CogniTool initialization for CreateTaskMemoryBlockTool."""
    assert create_task_memory_block_tool.name == "CreateTaskMemoryBlock"
    assert create_task_memory_block_tool.memory_linked is True
    assert create_task_memory_block_tool.input_model == CreateTaskMemoryBlockInput
    assert create_task_memory_block_tool.output_model == CreateTaskMemoryBlockOutput


def test_create_task_memory_block_tool_schema():
    """Test schema generation for the tool."""
    schema = create_task_memory_block_tool.schema
    assert schema["name"] == "CreateTaskMemoryBlock"
    assert schema["type"] == "function"
    assert "parameters" in schema
    properties = schema["parameters"]["properties"]

    # Verify key fields are in the schema
    assert "title" in properties
    assert "description" in properties
    assert "status" in properties
    assert "priority" in properties
    assert "execution_phase" in properties
    assert "action_items" in properties
    assert "acceptance_criteria" in properties
    assert "blocked_by" in properties
