"""
Tests for the CreateWorkItemTool that creates work items of different types.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from infra_core.memory_system.tools.agent_facing.create_work_item_tool import (
    create_work_item_tool,
    create_work_item,
    CreateWorkItemInput,
    CreateWorkItemOutput,
)
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.schemas.metadata.project import ProjectMetadata


@pytest.fixture
def mock_memory_bank():
    """Create a mock StructuredMemoryBank."""
    bank = MagicMock(spec=StructuredMemoryBank)
    bank.create_memory_block.return_value = True
    return bank


def test_create_work_item_project_success(mock_memory_bank):
    """Test successful creation of a project work item."""
    # Arrange
    input_data = CreateWorkItemInput(
        type="project",
        title="Test Project",
        description="Test project description",
        owner="test_user",
        acceptance_criteria=["Criterion 1", "Criterion 2"],
    )

    # Act
    with patch(
        "infra_core.memory_system.tools.agent_facing.create_work_item_tool.create_memory_block"
    ) as mock_create:
        mock_create.return_value = CreateWorkItemOutput(
            success=True,
            id="test-id-123",
            timestamp=datetime.now(),
        )
        result = create_work_item(input_data, mock_memory_bank)

    # Assert
    assert result.success is True
    assert result.id == "test-id-123"
    assert result.work_item_type == "project"
    assert mock_create.called


def test_create_work_item_task_success(mock_memory_bank):
    """Test successful creation of a task work item."""
    # Arrange
    input_data = CreateWorkItemInput(
        type="task",
        title="Test Task",
        description="Test task description",
        owner="test_user",
        acceptance_criteria=["Criterion 1", "Criterion 2"],
    )

    # Act
    with patch(
        "infra_core.memory_system.tools.agent_facing.create_work_item_tool.create_memory_block"
    ) as mock_create:
        mock_create.return_value = CreateWorkItemOutput(
            success=True,
            id="test-id-456",
            timestamp=datetime.now(),
        )
        result = create_work_item(input_data, mock_memory_bank)

    # Assert
    assert result.success is True
    assert result.id == "test-id-456"
    assert result.work_item_type == "task"
    assert mock_create.called


def test_create_work_item_project_missing_owner(mock_memory_bank):
    """Test project creation fails when owner is missing."""
    # Arrange
    input_data = CreateWorkItemInput(
        type="project",
        title="Test Project",
        description="Test project description",
        owner=None,  # Missing owner
        acceptance_criteria=["Criterion 1", "Criterion 2"],
    )

    # Act
    result = create_work_item(input_data, mock_memory_bank)

    # Assert
    assert result.success is False
    assert "owner cannot be null" in result.error
    assert result.work_item_type == "project"


def test_create_work_item_core_exception(mock_memory_bank):
    """Test handling of exceptions from core create_memory_block."""
    # Arrange
    input_data = CreateWorkItemInput(
        type="bug",
        title="Test Bug",
        description="Test bug description",
        owner="test_user",
        acceptance_criteria=["Criterion 1", "Criterion 2"],
    )

    # Act
    with patch(
        "infra_core.memory_system.tools.agent_facing.create_work_item_tool.create_memory_block"
    ) as mock_create:
        mock_create.side_effect = Exception("Test exception")
        result = create_work_item(input_data, mock_memory_bank)

    # Assert
    assert result.success is False
    assert "Error in create_work_item wrapper" in result.error
    assert result.work_item_type == "bug"


def test_create_work_item_tool_initialization():
    """Test that the CreateWorkItem tool is properly initialized."""
    assert create_work_item_tool.name == "CreateWorkItem"
    assert create_work_item_tool.input_model == CreateWorkItemInput
    assert create_work_item_tool.output_model == CreateWorkItemOutput
    assert create_work_item_tool._function == create_work_item  # Using _function not func
    assert create_work_item_tool.memory_linked is True


def test_create_work_item_tool_schema():
    """Test that the CreateWorkItem tool's schema is properly generated."""
    schema = create_work_item_tool.schema  # Using schema property
    assert schema["name"] == "CreateWorkItem"
    assert "type" in schema["parameters"]["properties"]
    assert "title" in schema["parameters"]["properties"]
    assert "description" in schema["parameters"]["properties"]
    assert "owner" in schema["parameters"]["properties"]


def test_create_work_item_project_validation_compatibility():
    """Test to verify CreateWorkItem input data is compatible with ProjectMetadata schema."""
    # This test verifies that our CreateWorkItem tool input data structure
    # is compatible with the actual ProjectMetadata schema

    # Test successful creation with valid tags field
    project_data = ProjectMetadata(
        x_agent_id="test-agent",
        title="Test Project",
        description="Test project description",
        owner="test_user",
        acceptance_criteria=["Criterion 1"],
        tags=["test-tag", "another-tag"],  # This should work fine
        status="backlog",
    )

    # Verify the project was created successfully
    assert project_data.title == "Test Project"
    assert project_data.tags == ["test-tag", "another-tag"]
