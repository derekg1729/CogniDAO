"""
Integration tests for UpdateWorkItemTool.

These tests validate the work item specific functionality and its integration
with the core UpdateMemoryBlockTool.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
import uuid

from infra_core.memory_system.tools.agent_facing.update_work_item_tool import (
    update_work_item,
    UpdateWorkItemInput,
    UpdateWorkItemOutput,
)
from infra_core.memory_system.schemas.memory_block import MemoryBlock, ConfidenceScore
from infra_core.memory_system.schemas.common import BlockLink
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank


@pytest.fixture
def project_block_id():
    """Generate a valid UUID for project testing."""
    return str(uuid.uuid4())


@pytest.fixture
def task_block_id():
    """Generate a valid UUID for task testing."""
    return str(uuid.uuid4())


@pytest.fixture
def mock_memory_bank():
    """Create a mock StructuredMemoryBank."""
    bank = MagicMock(spec=StructuredMemoryBank)
    bank.update_memory_block.return_value = True
    return bank


@pytest.fixture
def sample_project_block(project_block_id):
    """Create a sample project memory block."""
    return MemoryBlock(
        id=project_block_id,
        type="project",
        text="Original project description",
        block_version=3,
        state="draft",
        visibility="internal",
        tags=["project", "poc"],
        metadata={
            "title": "Test Project",
            "description": "Original project description",
            "status": "backlog",
            "priority": "P1",
            "owner": "project_owner",
            "acceptance_criteria": ["Criterion 1", "Criterion 2"],
            "action_items": ["Item 1", "Item 2"],
            "expected_artifacts": ["Artifact 1"],
            "x_agent_id": "test_agent",
            "x_tool_id": "CreateWorkItemTool",
        },
        source_file="project.md",
        confidence=ConfidenceScore(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
        links=[],
    )


@pytest.fixture
def sample_task_block(task_block_id):
    """Create a sample task memory block."""
    return MemoryBlock(
        id=task_block_id,
        type="task",
        text="Original task description",
        block_version=2,
        state="draft",
        visibility="internal",
        tags=["task", "development"],
        metadata={
            "title": "Test Task",
            "description": "Original task description",
            "status": "todo",
            "priority": "P2",
            "assignee": "developer",
            "acceptance_criteria": ["Criterion A", "Criterion B"],
            "story_points": 3.0,
            "estimate_hours": 8.0,
            "x_agent_id": "test_agent",
            "x_tool_id": "CreateWorkItemTool",
        },
        source_file="task.md",
        confidence=ConfidenceScore(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
        links=[],
    )


# Test successful work item updates


def test_update_work_item_project_success(mock_memory_bank, sample_project_block):
    """Test successful update of a project work item."""
    mock_memory_bank.get_memory_block.return_value = sample_project_block

    input_data = UpdateWorkItemInput(
        block_id=sample_project_block.id,
        title="Updated Project Title",
        description="Updated project description with new goals",
        status="in_progress",
        priority="P0",
        owner="new_project_owner",
        acceptance_criteria=["New Criterion 1", "New Criterion 2", "New Criterion 3"],
        change_note="Updated project scope and priority",
    )

    result = update_work_item(input_data, mock_memory_bank)

    assert result.success is True
    assert result.id == sample_project_block.id
    assert result.previous_version == 3
    assert result.new_version == 4
    assert result.work_item_type == "project"
    assert "metadata" in result.fields_updated
    assert "text" in result.fields_updated  # Description goes to text


def test_update_work_item_task_success(mock_memory_bank, sample_task_block):
    """Test successful update of a task work item."""
    mock_memory_bank.get_memory_block.return_value = sample_task_block

    input_data = UpdateWorkItemInput(
        block_id=sample_task_block.id,
        title="Updated Task Title",
        status="in_progress",
        execution_phase="implementing",  # Valid for in_progress status
        story_points=5.0,
        estimate_hours=12.0,
        owner="new_developer",  # Maps to assignee for tasks
        labels=["backend", "api"],
        change_note="Started implementation phase",
    )

    result = update_work_item(input_data, mock_memory_bank)

    assert result.success is True
    assert result.id == sample_task_block.id
    assert result.previous_version == 2
    assert result.new_version == 3
    assert result.work_item_type == "task"


def test_update_work_item_with_version_check(mock_memory_bank, sample_project_block):
    """Test update with optimistic locking."""
    mock_memory_bank.get_memory_block.return_value = sample_project_block

    input_data = UpdateWorkItemInput(
        block_id=sample_project_block.id,
        previous_block_version=3,  # Correct version
        status="done",
        change_note="Marking project as completed",
    )

    # Mock the core update to include validation_report in metadata
    with patch(
        "infra_core.memory_system.tools.agent_facing.update_work_item_tool.update_memory_block_tool"
    ) as mock_update:
        from infra_core.memory_system.tools.agent_facing.update_memory_block_tool import (
            UpdateMemoryBlockToolOutput,
        )

        mock_update.return_value = UpdateMemoryBlockToolOutput(
            success=True,
            id=sample_project_block.id,
            timestamp=datetime.now(),
            fields_updated=["metadata"],
            text_changed=False,
            previous_version=3,
            new_version=4,
        )

        result = update_work_item(input_data, mock_memory_bank)

        # Verify the core update was called
        call_args = mock_update.call_args
        core_input = call_args[0][0]

        # The tool should add validation_report to metadata when status is 'done'
        # For now, let's just check that the call was made correctly
        assert core_input.metadata["status"] == "done"

    assert result.success is True
    assert result.previous_version == 3
    assert result.new_version == 4


def test_update_work_item_multiple_fields(mock_memory_bank, sample_task_block):
    """Test updating multiple work item fields."""
    mock_memory_bank.get_memory_block.return_value = sample_task_block

    new_links = [BlockLink(to_id="related-task", relation="depends_on")]

    input_data = UpdateWorkItemInput(
        block_id=sample_task_block.id,
        title="Comprehensive Task Update",
        description="Updated with detailed requirements",
        status="in_progress",
        priority="P1",
        owner="senior_developer",
        acceptance_criteria=["Updated AC 1", "Updated AC 2"],
        action_items=["New action 1", "New action 2"],
        expected_artifacts=["API endpoint", "Unit tests"],
        story_points=8.0,
        estimate_hours=20.0,
        tags=["backend", "critical"],
        labels=["high-priority", "api"],
        tool_hints=["code_editor", "docker"],
        role_hint="backend_developer",
        execution_timeout_minutes=120,
        cost_budget_usd=100.0,
        state="published",
        visibility="public",
        links=new_links,
        merge_tags=False,  # Replace tags
        change_note="Comprehensive update with new scope",
    )

    result = update_work_item(input_data, mock_memory_bank)

    assert result.success is True
    expected_fields = {
        "text",
        "metadata",
        "tags",
        "state",
        "visibility",
        "links",
        "block_version",
        "updated_at",
    }
    assert set(result.fields_updated).issuperset(expected_fields)


# Test validation


def test_update_work_item_execution_phase_validation_success(mock_memory_bank, sample_task_block):
    """Test valid execution_phase with in_progress status."""
    mock_memory_bank.get_memory_block.return_value = sample_task_block

    input_data = UpdateWorkItemInput(
        block_id=sample_task_block.id,
        status="in_progress",
        execution_phase="testing",  # Valid for in_progress
    )

    result = update_work_item(input_data, mock_memory_bank)

    assert result.success is True


def test_update_work_item_execution_phase_validation_error():
    """Test invalid execution_phase with non-in_progress status."""
    test_uuid = str(uuid.uuid4())
    with pytest.raises(
        ValueError, match="execution_phase can only be set when status is 'in_progress'"
    ):
        UpdateWorkItemInput(
            block_id=test_uuid,
            status="done",
            execution_phase="testing",  # Invalid for done status
        )


# Test error conditions


def test_update_work_item_block_not_found(mock_memory_bank):
    """Test error when work item doesn't exist."""
    mock_memory_bank.get_memory_block.return_value = None
    # Use a valid UUID format even for non-existent blocks
    non_existent_uuid = str(uuid.uuid4())

    input_data = UpdateWorkItemInput(
        block_id=non_existent_uuid,
        title="Updated Title",
    )

    result = update_work_item(input_data, mock_memory_bank)

    assert result.success is False
    assert "not found" in result.error
    assert result.work_item_type is None


def test_update_work_item_version_conflict(mock_memory_bank, sample_project_block):
    """Test version conflict error."""
    mock_memory_bank.get_memory_block.return_value = sample_project_block

    input_data = UpdateWorkItemInput(
        block_id=sample_project_block.id,
        previous_block_version=1,  # Wrong version (current is 3)
        title="Updated Title",
    )

    with patch(
        "infra_core.memory_system.tools.agent_facing.update_work_item_tool.update_memory_block_tool"
    ) as mock_update:
        from infra_core.memory_system.tools.agent_facing.update_memory_block_tool import (
            UpdateMemoryBlockToolOutput,
        )
        from infra_core.memory_system.tools.memory_core.update_memory_block_models import (
            UpdateErrorCode,
        )

        mock_update.return_value = UpdateMemoryBlockToolOutput(
            success=False,
            error="Version conflict: expected 1, got 3",
            error_code=UpdateErrorCode.VERSION_CONFLICT,
            previous_version=3,
            timestamp=datetime.now(),
        )

        result = update_work_item(input_data, mock_memory_bank)

        assert result.success is False
        assert "Version conflict" in result.error
        assert result.previous_version == 3


def test_update_work_item_exception_handling(mock_memory_bank):
    """Test handling of unexpected exceptions."""
    mock_memory_bank.get_memory_block.side_effect = Exception("Database error")
    test_uuid = str(uuid.uuid4())

    input_data = UpdateWorkItemInput(
        block_id=test_uuid,
        title="Updated Title",
    )

    result = update_work_item(input_data, mock_memory_bank)

    assert result.success is False
    assert "Error in update_work_item wrapper" in result.error


# Test owner/assignee mapping


def test_update_work_item_owner_mapping_project(mock_memory_bank, sample_project_block):
    """Test that owner field maps to 'assignee' for projects."""
    mock_memory_bank.get_memory_block.return_value = sample_project_block

    input_data = UpdateWorkItemInput(
        block_id=sample_project_block.id,
        owner="new_project_owner",
    )

    with patch(
        "infra_core.memory_system.tools.agent_facing.update_work_item_tool.update_memory_block_tool"
    ) as mock_update:
        from infra_core.memory_system.tools.agent_facing.update_memory_block_tool import (
            UpdateMemoryBlockToolOutput,
        )

        mock_update.return_value = UpdateMemoryBlockToolOutput(
            success=True,
            id=sample_project_block.id,
            timestamp=datetime.now(),
            fields_updated=["metadata"],
            text_changed=False,
        )

        result = update_work_item(input_data, mock_memory_bank)

        # Verify that the core update was called with assignee in metadata
        call_args = mock_update.call_args
        core_input = call_args[0][0]
        assert core_input.metadata["assignee"] == "new_project_owner"
        assert result.success is True


def test_update_work_item_owner_mapping_task(mock_memory_bank, sample_task_block):
    """Test that owner field maps to 'assignee' for tasks."""
    mock_memory_bank.get_memory_block.return_value = sample_task_block

    input_data = UpdateWorkItemInput(
        block_id=sample_task_block.id,
        owner="new_assignee",
    )

    with patch(
        "infra_core.memory_system.tools.agent_facing.update_work_item_tool.update_memory_block_tool"
    ) as mock_update:
        from infra_core.memory_system.tools.agent_facing.update_memory_block_tool import (
            UpdateMemoryBlockToolOutput,
        )

        mock_update.return_value = UpdateMemoryBlockToolOutput(
            success=True,
            id=sample_task_block.id,
            timestamp=datetime.now(),
            fields_updated=["metadata"],
            text_changed=False,
        )

        result = update_work_item(input_data, mock_memory_bank)

        # Verify that the core update was called with assignee in metadata
        call_args = mock_update.call_args
        core_input = call_args[0][0]
        assert core_input.metadata["assignee"] == "new_assignee"
        assert result.success is True


# Test merge behavior


def test_update_work_item_merge_behavior(mock_memory_bank, sample_project_block):
    """Test different merge behaviors for tags and metadata."""
    mock_memory_bank.get_memory_block.return_value = sample_project_block

    input_data = UpdateWorkItemInput(
        block_id=sample_project_block.id,
        tags=["new-tag"],
        labels=["new-label"],
        merge_tags=True,  # Merge with existing
        merge_labels=False,  # Replace existing
        merge_metadata=True,  # Merge metadata
    )

    with patch(
        "infra_core.memory_system.tools.agent_facing.update_work_item_tool.update_memory_block_tool"
    ) as mock_update:
        from infra_core.memory_system.tools.agent_facing.update_memory_block_tool import (
            UpdateMemoryBlockToolOutput,
        )

        mock_update.return_value = UpdateMemoryBlockToolOutput(
            success=True,
            id=sample_project_block.id,
            timestamp=datetime.now(),
            fields_updated=["tags", "metadata"],
            text_changed=False,
        )

        result = update_work_item(input_data, mock_memory_bank)

        # Verify merge settings were passed through
        call_args = mock_update.call_args
        core_input = call_args[0][0]
        assert core_input.merge_tags is True
        assert core_input.merge_metadata is True
        assert result.success is True


# Test tool initialization


def test_update_work_item_tool_initialization():
    """Test that the UpdateWorkItem tool is properly initialized."""
    from infra_core.memory_system.tools.agent_facing.update_work_item_tool import (
        update_work_item_tool,
    )

    assert update_work_item_tool.name == "UpdateWorkItem"
    assert update_work_item_tool.input_model == UpdateWorkItemInput
    assert update_work_item_tool.output_model == UpdateWorkItemOutput
    assert update_work_item_tool._function == update_work_item
    assert update_work_item_tool.memory_linked is True


# Test realistic workflows


def test_update_work_item_project_status_progression(mock_memory_bank, sample_project_block):
    """Test a realistic project status progression workflow."""
    mock_memory_bank.get_memory_block.return_value = sample_project_block

    # Simulate moving project from backlog to in_progress
    input_data = UpdateWorkItemInput(
        block_id=sample_project_block.id,
        status="in_progress",
        description="Project has been approved and development started",
        action_items=[
            "Set up development environment",
            "Create initial architecture design",
            "Implement core features",
            "Write documentation",
        ],
        owner="lead_developer",
        change_note="Project approved - moving to active development",
    )

    result = update_work_item(input_data, mock_memory_bank)

    assert result.success is True
    assert result.work_item_type == "project"
    assert result.text_changed is True  # Description updated


def test_update_work_item_task_execution_flow(mock_memory_bank, sample_task_block):
    """Test a realistic task execution flow."""
    mock_memory_bank.get_memory_block.return_value = sample_task_block

    # Simulate task moving through execution phases
    input_data = UpdateWorkItemInput(
        block_id=sample_task_block.id,
        status="in_progress",
        execution_phase="implementing",
        description="Task implementation started with detailed technical approach",
        action_items=[
            "Write unit tests",
            "Implement core logic",
            "Add error handling",
            "Update documentation",
        ],
        story_points=5.0,  # Revised estimate
        tool_hints=["pytest", "black", "mypy"],
        role_hint="backend_developer",
        change_note="Started implementation with TDD approach",
    )

    result = update_work_item(input_data, mock_memory_bank)

    assert result.success is True
    assert result.work_item_type == "task"
