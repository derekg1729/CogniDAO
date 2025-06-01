"""
Tests for Epic and Bug metadata models.
"""

import pytest
from infra_core.memory_system.schemas.metadata.epic import EpicMetadata
from infra_core.memory_system.schemas.metadata.bug import BugMetadata
from infra_core.memory_system.schemas.metadata.common.validation import (
    ValidationResult,
    ValidationReport,
)
from pydantic import ValidationError


def test_epic_metadata_instantiation():
    """Test that EpicMetadata can be instantiated with required fields."""
    epic = EpicMetadata(
        x_agent_id="agent_123",
        owner="user_456",
        title="Test Epic",
        description="A test epic for unit tests",
        acceptance_criteria=["Test criterion"],
    )
    assert epic.owner == "user_456"
    assert epic.title == "Test Epic"
    assert epic.description == "A test epic for unit tests"
    assert epic.status == "backlog"  # Default value


def test_epic_metadata_full():
    """Test that EpicMetadata can be instantiated with all fields."""
    epic = EpicMetadata(
        x_agent_id="agent_123",
        owner="user_456",
        title="Test Epic",
        description="A test epic for unit tests",
        status="in_progress",
        start_date="2023-01-01T00:00:00Z",
        target_date="2023-12-31T23:59:59Z",
        priority="P1",
        progress_percent=25.0,
        tags=["feature", "infrastructure"],
        acceptance_criteria=["Criterion 1", "Criterion 2"],
        action_items=["Step 1", "Step 2"],
        tool_hints=["python", "git"],
        expected_artifacts=["module.py", "README.md"],
    )

    assert epic.status == "in_progress"
    assert epic.priority == "P1"
    assert epic.progress_percent == 25.0
    assert epic.tags == ["feature", "infrastructure"]
    assert len(epic.acceptance_criteria) == 2
    assert len(epic.action_items) == 2
    assert len(epic.tool_hints) == 2
    assert len(epic.expected_artifacts) == 2


def test_epic_metadata_status_completion_sync():
    """Test that status and validation report are properly synchronized."""
    # Create a validation report for testing
    validation_report = ValidationReport(
        validated_by="agent_123",
        results=[ValidationResult(criterion="Test criterion", status="pass")],
    )

    # Test that setting status to 'done' requires a validation report
    epic = EpicMetadata(
        x_agent_id="agent_123",
        owner="user_456",
        title="Test Epic",
        description="A test epic for unit tests",
        status="done",
        acceptance_criteria=["Test criterion"],
        validation_report=validation_report,
    )
    assert epic.status == "done"

    # TODO: Temporarily skipped - validation_report requirement disabled for workflow flexibility
    pytest.skip("validation_report requirement temporarily disabled")

    # Test that a validation report is required for 'done' status
    with pytest.raises(ValidationError):
        EpicMetadata(
            x_agent_id="agent_123",
            owner="user_456",
            title="Test Epic",
            description="A test epic for unit tests",
            status="done",
            acceptance_criteria=["Test criterion"],
        )


def test_epic_metadata_validation():
    """Test validation rules for EpicMetadata."""
    # Test that progress_percent must be 0-100
    with pytest.raises(ValidationError):
        EpicMetadata(
            x_agent_id="agent_123",
            owner="user_456",
            title="Test Epic",
            description="A test epic for unit tests",
            progress_percent=101.0,  # Invalid: > 100
            acceptance_criteria=["Test criterion"],
        )

    with pytest.raises(ValidationError):
        EpicMetadata(
            x_agent_id="agent_123",
            owner="user_456",
            title="Test Epic",
            description="A test epic for unit tests",
            progress_percent=-1.0,  # Invalid: < 0
            acceptance_criteria=["Test criterion"],
        )

    # TODO: Temporarily skipped - validation_report requirement disabled for workflow flexibility
    # Test that status='done' requires validation_report
    # with pytest.raises(ValidationError):
    #     EpicMetadata(
    #         x_agent_id="agent_123",
    #         owner="user_456",
    #         title="Test Epic",
    #         description="A test epic for unit tests",
    #         status="done",  # Requires validation_report
    #         acceptance_criteria=["Test criterion"],
    #     )


def test_bug_metadata_instantiation():
    """Test that BugMetadata can be instantiated with required fields."""
    bug = BugMetadata(
        x_agent_id="agent_123",
        owner="user_456",
        title="Test Bug",
        description="A test bug for unit tests",
        acceptance_criteria=["Test criterion"],
    )
    assert bug.owner == "user_456"
    assert bug.title == "Test Bug"
    assert bug.description == "A test bug for unit tests"
    assert bug.status == "backlog"  # Default value


def test_bug_metadata_full():
    """Test that BugMetadata can be instantiated with all fields."""
    bug = BugMetadata(
        x_agent_id="agent_123",
        owner="user_456",
        title="Test Bug",
        description="A test bug for unit tests",
        assignee="user_789",
        priority="P1",
        severity="major",
        version_found="1.0.0",
        version_fixed="1.0.1",
        steps_to_reproduce="1. Step one\n2. Step two",
        due_date="2023-12-31T23:59:59Z",
        tags=["frontend", "ui"],
        confidence_score={"human": 0.9, "ai": 0.85},
        expected_behavior="The button should be centered",
        actual_behavior="The button is offset to the right",
        environment="Production",
        logs_link="https://logs.example.com/123",
        repro_steps=["Navigate to page", "Click button"],
        status="in_progress",
        acceptance_criteria=["Button is centered"],
    )

    assert bug.status == "in_progress"
    assert bug.assignee == "user_789"
    assert bug.priority == "P1"
    assert bug.severity == "major"
    assert bug.version_found == "1.0.0"
    assert bug.version_fixed == "1.0.1"
    assert "frontend" in bug.tags
    assert bug.confidence_score["human"] == 0.9
    assert bug.expected_behavior == "The button should be centered"
    assert bug.environment == "Production"
    assert len(bug.repro_steps) == 2


def test_bug_metadata_validation():
    """Test validation rules for BugMetadata."""
    # Test that severity must be a valid value
    with pytest.raises(ValidationError):
        BugMetadata(
            x_agent_id="agent_123",
            owner="user_456",
            title="Test Bug",
            description="A test bug for unit tests",
            severity="not_a_valid_severity",  # Invalid severity
            acceptance_criteria=["Test criterion"],
        )

    # Test that confidence_score values must be 0-1
    with pytest.raises(ValidationError):
        BugMetadata(
            x_agent_id="agent_123",
            owner="user_456",
            title="Test Bug",
            description="A test bug for unit tests",
            confidence_score={"human": 1.5},  # Invalid: > 1
            acceptance_criteria=["Test criterion"],
        )

    # TODO: Temporarily skipped - validation_report requirement disabled for workflow flexibility
    # Test that status='fixed' requires validation_report
    # with pytest.raises(ValidationError):
    #     BugMetadata(
    #         x_agent_id="agent_123",
    #         owner="user_456",
    #         title="Test Bug",
    #         description="A test bug for unit tests",
    #         status="done",  # Requires validation_report since we now use 'done' instead of 'fixed'
    #         acceptance_criteria=["Test criterion"],
    #     )
