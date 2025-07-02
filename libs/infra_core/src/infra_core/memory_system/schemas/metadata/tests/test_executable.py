"""Tests for ExecutableMetadata mixin."""

import pytest
from pydantic import ValidationError
from typing import Literal

from infra_core.memory_system.schemas.metadata.common.executable import ExecutableMetadata
from infra_core.memory_system.schemas.metadata.common.validation import (
    ValidationResult,
    ValidationReport,
)


# Create a concrete class inheriting from ExecutableMetadata for testing
class TestExecutableModel(ExecutableMetadata):
    """Concrete implementation of ExecutableMetadata for testing."""

    status: Literal["backlog", "in_progress", "done"] = "backlog"
    title: str
    description: str


def test_executable_metadata_creation():
    """Test basic creation of a class using ExecutableMetadata."""
    model = TestExecutableModel(
        x_agent_id="agent-123",
        title="Test Task",
        description="This is a test task",
        acceptance_criteria=["Criterion 1", "Criterion 2"],
    )

    assert model.x_agent_id == "agent-123"
    assert model.title == "Test Task"
    assert model.description == "This is a test task"
    assert len(model.acceptance_criteria) == 2
    assert model.tool_hints == []
    assert model.action_items == []
    assert model.expected_artifacts == []
    assert model.blocked_by == []
    assert model.deliverables == []
    assert model.validation_report is None


def test_executable_metadata_all_fields():
    """Test creation with all fields populated."""
    # Valid UUID format for blocked_by
    valid_uuid1 = "123e4567-e89b-12d3-a456-426614174000"
    valid_uuid2 = "223e4567-e89b-12d3-a456-426614174001"

    model = TestExecutableModel(
        x_agent_id="agent-123",
        x_tool_id="tool-456",
        x_parent_block_id="parent-789",
        x_session_id="session-abc",
        title="Test Task",
        description="This is a test task",
        tool_hints=["python", "git"],
        action_items=["Step 1", "Step 2"],
        acceptance_criteria=["Criterion 1", "Criterion 2"],
        expected_artifacts=["output.py", "README.md"],
        blocked_by=[valid_uuid1, valid_uuid2],
        priority_score=0.8,
        reviewer="user-333",
        execution_timeout_minutes=60,
        cost_budget_usd=10.5,
        role_hint="developer",
        deliverables=["actual_output.py", "actual_README.md"],
        validation_report=ValidationReport(
            validated_by="user-333",
            results=[
                ValidationResult(criterion="Criterion 1", status="pass"),
                ValidationResult(criterion="Criterion 2", status="pass"),
            ],
        ),
        status="done",
    )

    assert model.x_agent_id == "agent-123"
    assert model.tool_hints == ["python", "git"]
    assert model.blocked_by == [valid_uuid1, valid_uuid2]
    assert model.execution_timeout_minutes == 60
    assert model.cost_budget_usd == 10.5
    assert model.role_hint == "developer"
    assert model.deliverables == ["actual_output.py", "actual_README.md"]
    assert model.validation_report.validated_by == "user-333"
    assert len(model.validation_report.results) == 2
    assert model.status == "done"


def test_executable_metadata_no_acceptance_criteria():
    """Test that missing acceptance_criteria raises an error."""
    with pytest.raises(ValidationError):
        TestExecutableModel(
            x_agent_id="agent-123",
            title="Test Task",
            description="This is a test task",
            acceptance_criteria=[],  # Empty list should cause validation error
        )


def test_executable_metadata_failing_validation():
    """Test that failing validation raises an error."""
    with pytest.raises(ValidationError):
        TestExecutableModel(
            x_agent_id="agent-123",
            title="Test Task",
            description="This is a test task",
            acceptance_criteria=["Criterion 1", "Criterion 2"],
            validation_report=ValidationReport(
                validated_by="user-333",
                results=[
                    ValidationResult(criterion="Criterion 1", status="pass"),
                    ValidationResult(
                        criterion="Criterion 2", status="fail", notes="Not implemented correctly"
                    ),
                ],
            ),
        )


def test_executable_metadata_negative_values():
    """Test that negative values for numeric fields raise errors."""
    with pytest.raises(ValidationError):
        TestExecutableModel(
            x_agent_id="agent-123",
            title="Test Task",
            description="This is a test task",
            acceptance_criteria=["Criterion 1"],
            priority_score=-0.5,  # Should raise validation error
        )

    with pytest.raises(ValidationError):
        TestExecutableModel(
            x_agent_id="agent-123",
            title="Test Task",
            description="This is a test task",
            acceptance_criteria=["Criterion 1"],
            execution_timeout_minutes=-10,  # Should raise validation error
        )

    with pytest.raises(ValidationError):
        TestExecutableModel(
            x_agent_id="agent-123",
            title="Test Task",
            description="This is a test task",
            acceptance_criteria=["Criterion 1"],
            cost_budget_usd=-5.0,  # Should raise validation error
        )
