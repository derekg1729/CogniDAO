"""Tests for type-specific status validation across different metadata models."""

import pytest
from pydantic import ValidationError

# Import metadata models to test
from infra_core.memory_system.schemas.metadata.task import TaskMetadata
from infra_core.memory_system.schemas.metadata.project import ProjectMetadata
from infra_core.memory_system.schemas.metadata.epic import EpicMetadata
from infra_core.memory_system.schemas.metadata.bug import BugMetadata, BugSeverity
from infra_core.memory_system.schemas.metadata.common.validation import (
    ValidationResult,
    ValidationReport,
)


def test_task_allowed_status():
    """Test the ALLOWED_STATUS set for TaskMetadata."""
    # Check the ALLOWED_STATUS contains expected values
    expected_statuses = {"backlog", "ready", "in_progress", "review", "blocked", "done"}
    assert expected_statuses.issubset(TaskMetadata.ALLOWED_STATUS)

    # Create a task with a valid status
    task = TaskMetadata(
        x_agent_id="agent-123",
        title="Test Task",
        description="This is a test task",
        acceptance_criteria=["Criterion 1"],
        status="in_progress",
    )
    assert task.status == "in_progress"

    # Try to create a task with an invalid status
    with pytest.raises(ValidationError) as excinfo:
        TaskMetadata(
            x_agent_id="agent-123",
            title="Test Task",
            description="This is a test task",
            acceptance_criteria=["Criterion 1"],
            status="invalid_status",  # Not in ALLOWED_STATUS
        )

    # Validate that an appropriate error message is returned
    assert "Input should be" in str(excinfo.value)
    assert "invalid_status" in str(excinfo.value)


def test_project_allowed_status():
    """Test the ALLOWED_STATUS set for ProjectMetadata."""
    # Check the ALLOWED_STATUS contains expected values
    expected_statuses = {"backlog", "ready", "in_progress", "review", "blocked", "done", "archived"}
    assert expected_statuses.issubset(ProjectMetadata.ALLOWED_STATUS)

    # Create a project with a valid status
    project = ProjectMetadata(
        x_agent_id="agent-123",
        owner="user-456",
        name="Test Project",
        description="This is a test project",
        acceptance_criteria=["Criterion 1"],
        status="in_progress",
    )
    assert project.status == "in_progress"

    # Try to create a project with an invalid status
    with pytest.raises(ValidationError) as excinfo:
        ProjectMetadata(
            x_agent_id="agent-123",
            owner="user-456",
            name="Test Project",
            description="This is a test project",
            acceptance_criteria=["Criterion 1"],
            status="invalid_status",  # Not in ALLOWED_STATUS
        )

    # Validate that an appropriate error message is returned
    assert "Input should be" in str(excinfo.value)
    assert "invalid_status" in str(excinfo.value)


def test_epic_allowed_status():
    """Test the ALLOWED_STATUS set for EpicMetadata."""
    # Check the ALLOWED_STATUS contains expected values
    expected_statuses = {"backlog", "ready", "in_progress", "review", "blocked", "done", "archived"}
    assert expected_statuses.issubset(EpicMetadata.ALLOWED_STATUS)

    # Create an epic with a valid status
    epic = EpicMetadata(
        x_agent_id="agent-123",
        owner="user-456",
        name="Test Epic",
        description="This is a test epic",
        acceptance_criteria=["Criterion 1"],
        status="in_progress",
    )
    assert epic.status == "in_progress"

    # Try to create an epic with an invalid status
    with pytest.raises(ValidationError) as excinfo:
        EpicMetadata(
            x_agent_id="agent-123",
            owner="user-456",
            name="Test Epic",
            description="This is a test epic",
            acceptance_criteria=["Criterion 1"],
            status="invalid_status",  # Not in ALLOWED_STATUS
        )

    # Validate that an appropriate error message is returned
    assert "Input should be" in str(excinfo.value)
    assert "invalid_status" in str(excinfo.value)


def test_bug_allowed_status():
    """Test the ALLOWED_STATUS set for BugMetadata."""
    # Check the ALLOWED_STATUS contains expected values
    expected_statuses = {"backlog", "ready", "in_progress", "blocked", "done", "released"}
    assert expected_statuses.issubset(BugMetadata.ALLOWED_STATUS)

    # Create a bug with a valid status
    bug = BugMetadata(
        x_agent_id="agent-123",
        reporter="user-456",
        title="Test Bug",
        description="This is a test bug",
        acceptance_criteria=["Criterion 1"],
        status="in_progress",
    )
    assert bug.status == "in_progress"

    # Try to create a bug with an invalid status
    with pytest.raises(ValidationError) as excinfo:
        BugMetadata(
            x_agent_id="agent-123",
            reporter="user-456",
            title="Test Bug",
            description="This is a test bug",
            acceptance_criteria=["Criterion 1"],
            status="invalid_status",  # Not in ALLOWED_STATUS
        )

    # Validate that an appropriate error message is returned
    assert "Input should be" in str(excinfo.value)
    assert "invalid_status" in str(excinfo.value)


def test_validation_required_for_done_status():
    """Test that validation report is required when status is 'done'."""
    # Try to create task with 'done' status without validation report
    with pytest.raises(ValidationError) as excinfo:
        TaskMetadata(
            x_agent_id="agent-123",
            title="Test Task",
            description="This is a test task",
            acceptance_criteria=["Criterion 1"],
            status="done",  # Should require validation report
        )

    assert "A validation report is required when status is 'done'" in str(excinfo.value)

    # Create task with 'done' status with validation report
    task = TaskMetadata(
        x_agent_id="agent-123",
        title="Test Task",
        description="This is a test task",
        acceptance_criteria=["Criterion 1"],
        status="done",
        validation_report=ValidationReport(
            validated_by="user-456",
            results=[ValidationResult(criterion="Criterion 1", status="pass")],
        ),
    )
    assert task.status == "done"
    assert task.validation_report is not None


def test_bug_severity_validation():
    """Test that bug severity is validated correctly."""
    # Create a bug with valid severity
    bug = BugMetadata(
        x_agent_id="agent-123",
        reporter="user-456",
        title="Test Bug",
        description="This is a test bug",
        acceptance_criteria=["Criterion 1"],
        severity="critical",
    )
    assert bug.severity == "critical"

    # Try to create a bug with invalid severity
    with pytest.raises(ValidationError) as excinfo:
        BugMetadata(
            x_agent_id="agent-123",
            reporter="user-456",
            title="Test Bug",
            description="This is a test bug",
            acceptance_criteria=["Criterion 1"],
            severity="ultra-critical",  # Not in BugSeverity enum
        )

    # Check that error message contains all valid severity values
    error_msg = str(excinfo.value)
    for severity in BugSeverity:
        assert severity.value in error_msg
