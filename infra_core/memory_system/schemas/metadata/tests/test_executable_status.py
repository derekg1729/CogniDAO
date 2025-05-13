"""Tests for ExecutableMetadata status validation."""

import pytest
from pydantic import ValidationError

from infra_core.memory_system.schemas.metadata.common.executable import (
    ExecutableMetadata,
    WorkStatusLiteral,
    PriorityLiteral,
)
from infra_core.memory_system.schemas.metadata.common.validation import (
    ValidationResult,
    ValidationReport,
)


# Create a concrete class inheriting from ExecutableMetadata for testing
class TestExecutableModel(ExecutableMetadata):
    """Concrete implementation of ExecutableMetadata for testing."""

    # Define a subset of allowed statuses for this test class
    ALLOWED_STATUS = {"backlog", "ready", "in_progress", "blocked", "review", "done"}

    status: WorkStatusLiteral = "backlog"
    title: str
    description: str


def test_allowed_status_validation():
    """Test that status must be in the ALLOWED_STATUS set for the class."""
    # Valid status should pass
    model = TestExecutableModel(
        x_agent_id="agent-123",
        title="Test Task",
        description="This is a test task",
        acceptance_criteria=["Criterion 1"],
        status="ready",
    )
    assert model.status == "ready"

    # Invalid status (not in ALLOWED_STATUS) should fail
    with pytest.raises(ValidationError) as excinfo:
        TestExecutableModel(
            x_agent_id="agent-123",
            title="Test Task",
            description="This is a test task",
            acceptance_criteria=["Criterion 1"],
            status="merged",  # Not in TestExecutableModel.ALLOWED_STATUS
        )

    # Check that error message mentions allowed values
    error_msg = str(excinfo.value)
    assert "Status 'merged' not allowed" in error_msg
    assert "Allowed values:" in error_msg
    for status in TestExecutableModel.ALLOWED_STATUS:
        assert f"'{status}'" in error_msg


def test_execution_phase_validation():
    """Test that execution_phase can only be set when status is 'in_progress'."""
    # Valid: status='in_progress' with execution_phase set
    model = TestExecutableModel(
        x_agent_id="agent-123",
        title="Test Task",
        description="This is a test task",
        acceptance_criteria=["Criterion 1"],
        status="in_progress",
        execution_phase="implementing",
    )
    assert model.status == "in_progress"
    assert model.execution_phase == "implementing"

    # Invalid: execution_phase with status not 'in_progress'
    with pytest.raises(ValidationError) as excinfo:
        TestExecutableModel(
            x_agent_id="agent-123",
            title="Test Task",
            description="This is a test task",
            acceptance_criteria=["Criterion 1"],
            status="ready",
            execution_phase="designing",  # Not allowed because status is not 'in_progress'
        )

    assert "execution_phase can only be set when status is 'in_progress'" in str(excinfo.value)


def test_validation_report_required_for_done():
    """Test that validation_report is required when status is 'done' or 'released'."""
    # Invalid: status='done' without validation_report
    with pytest.raises(ValidationError) as excinfo:
        TestExecutableModel(
            x_agent_id="agent-123",
            title="Test Task",
            description="This is a test task",
            acceptance_criteria=["Criterion 1"],
            status="done",
            # Missing validation_report
        )

    assert "A validation report is required when status is 'done'" in str(excinfo.value)

    # Valid: status='done' with validation_report
    model = TestExecutableModel(
        x_agent_id="agent-123",
        title="Test Task",
        description="This is a test task",
        acceptance_criteria=["Criterion 1"],
        status="done",
        validation_report=ValidationReport(
            validated_by="user-123",
            results=[
                ValidationResult(criterion="Criterion 1", status="pass"),
            ],
        ),
    )
    assert model.status == "done"
    assert model.validation_report is not None
    assert len(model.validation_report.results) == 1


def test_failing_validation_report():
    """Test that all validation results must pass when a report is provided."""
    # Invalid: validation report with failing results
    with pytest.raises(ValidationError) as excinfo:
        TestExecutableModel(
            x_agent_id="agent-123",
            title="Test Task",
            description="This is a test task",
            acceptance_criteria=["Criterion 1", "Criterion 2"],
            status="done",
            validation_report=ValidationReport(
                validated_by="user-123",
                results=[
                    ValidationResult(criterion="Criterion 1", status="pass"),
                    ValidationResult(
                        criterion="Criterion 2", status="fail", notes="Not implemented"
                    ),
                ],
            ),
        )

    assert "Validation failed for the following criteria" in str(excinfo.value)
    assert "Criterion 2" in str(excinfo.value)


def test_blocked_by_uuid_format():
    """Test that blocked_by field enforces UUID format."""
    # Valid UUID format
    model = TestExecutableModel(
        x_agent_id="agent-123",
        title="Test Task",
        description="This is a test task",
        acceptance_criteria=["Criterion 1"],
        blocked_by=["123e4567-e89b-12d3-a456-426614174000"],
    )
    assert len(model.blocked_by) == 1

    # Invalid UUID format
    with pytest.raises(ValidationError) as excinfo:
        TestExecutableModel(
            x_agent_id="agent-123",
            title="Test Task",
            description="This is a test task",
            acceptance_criteria=["Criterion 1"],
            blocked_by=["invalid-uuid-format"],  # Not a valid UUID format
        )

    assert "String should match pattern" in str(excinfo.value)
    assert "^[a-f0-9-]{36}$" in str(excinfo.value)


def test_priority_literal():
    """Test that priority literal accepts only valid values."""

    # Create a test class with priority field to test PriorityLiteral
    class ModelWithPriority(ExecutableMetadata):
        """Test model with priority field."""

        ALLOWED_STATUS = {"backlog", "done"}
        status: WorkStatusLiteral = "backlog"
        title: str
        description: str
        priority: PriorityLiteral

    # Valid priority
    model = ModelWithPriority(
        x_agent_id="agent-123",
        title="Test Task",
        description="This is a test task",
        acceptance_criteria=["Criterion 1"],
        priority="P1",
    )
    assert model.priority == "P1"

    # Invalid priority
    with pytest.raises(ValidationError) as excinfo:
        ModelWithPriority(
            x_agent_id="agent-123",
            title="Test Task",
            description="This is a test task",
            acceptance_criteria=["Criterion 1"],
            priority="High",  # Not a valid PriorityLiteral
        )

    assert "Input should be" in str(excinfo.value)
    assert "P0" in str(excinfo.value) and "P5" in str(excinfo.value)
