"""Tests for ValidationReport and ValidationResult models."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from infra_core.memory_system.schemas.metadata.common.validation import (
    ValidationResult,
    ValidationReport,
)
from infra_core.memory_system.schemas.metadata.common.executable import ExecutableMetadata


class TestModelWithValidation(ExecutableMetadata):
    """Concrete implementation of ExecutableMetadata for testing validation."""

    ALLOWED_STATUS = {"backlog", "in_progress", "done"}
    title: str
    description: str


def test_validation_result_pass():
    """Test creating a passing ValidationResult."""
    result = ValidationResult(
        criterion="Code is properly formatted",
        status="pass",
    )

    assert result.criterion == "Code is properly formatted"
    assert result.status == "pass"
    assert result.notes is None


def test_validation_result_with_notes():
    """Test creating a ValidationResult with notes."""
    result = ValidationResult(
        criterion="Code is properly formatted",
        status="pass",
        notes="All files follow PEP 8 standards",
    )

    assert result.criterion == "Code is properly formatted"
    assert result.status == "pass"
    assert result.notes == "All files follow PEP 8 standards"


def test_validation_result_fail():
    """Test creating a failing ValidationResult."""
    result = ValidationResult(
        criterion="All tests pass", status="fail", notes="Test failures in module X"
    )

    assert result.criterion == "All tests pass"
    assert result.status == "fail"
    assert result.notes == "Test failures in module X"


def test_validation_result_invalid_status():
    """Test that ValidationResult rejects invalid status values."""
    with pytest.raises(ValidationError) as excinfo:
        ValidationResult(
            criterion="Test criterion",
            status="maybe",  # Not "pass" or "fail"
        )

    # Check for specific error message about valid values
    assert "Input should be 'pass' or 'fail'" in str(excinfo.value)


def test_validation_report_creation():
    """Test creating a ValidationReport with multiple results."""
    report = ValidationReport(
        validated_by="reviewer-123",
        results=[
            ValidationResult(criterion="Criterion 1", status="pass"),
            ValidationResult(criterion="Criterion 2", status="pass", notes="Excellent work"),
        ],
    )

    assert report.validated_by == "reviewer-123"
    assert isinstance(report.timestamp, datetime)
    assert len(report.results) == 2
    assert report.results[0].criterion == "Criterion 1"
    assert report.results[1].notes == "Excellent work"


def test_validation_report_with_timestamp():
    """Test creating a ValidationReport with a specific timestamp."""
    now = datetime.now()
    report = ValidationReport(
        validated_by="reviewer-123",
        results=[
            ValidationResult(criterion="Criterion 1", status="pass"),
        ],
        timestamp=now,
    )

    assert report.validated_by == "reviewer-123"
    assert report.timestamp == now
    assert len(report.results) == 1


def test_validation_report_empty_results():
    """Test that ValidationReport with empty results raises an error."""
    with pytest.raises(ValidationError) as excinfo:
        ValidationReport(validated_by="reviewer-123", results=[])

    # Check for specific error message about empty results
    assert "Validation report must contain at least one result" in str(excinfo.value)


def test_validation_report_in_executable_model():
    """Test using ValidationReport within an ExecutableMetadata subclass."""
    # First create a report
    report = ValidationReport(
        validated_by="reviewer-123",
        results=[
            ValidationResult(criterion="Criterion 1", status="pass"),
            ValidationResult(criterion="Criterion 2", status="pass"),
        ],
    )

    # Now use it in a model
    model = TestModelWithValidation(
        x_agent_id="agent-123",
        title="Test Task",
        description="This is a test task",
        acceptance_criteria=["Criterion 1", "Criterion 2"],
        status="done",
        validation_report=report,
    )

    assert model.validation_report is not None
    assert model.validation_report.validated_by == "reviewer-123"
    assert len(model.validation_report.results) == 2


def test_validation_report_match_criteria():
    """Test that validation report criteria should match acceptance criteria."""
    # This test doesn't enforce perfect matching at the schema level,
    # but demonstrates a recommended pattern where report criteria match acceptance criteria

    acceptance_criteria = ["Code is documented", "Tests are passing"]

    model = TestModelWithValidation(
        x_agent_id="agent-123",
        title="Test Task",
        description="This is a test task",
        acceptance_criteria=acceptance_criteria,
        status="done",
        validation_report=ValidationReport(
            validated_by="reviewer-123",
            results=[
                ValidationResult(criterion="Code is documented", status="pass"),
                ValidationResult(criterion="Tests are passing", status="pass"),
            ],
        ),
    )

    # Verify each validation result matches an acceptance criterion
    for result in model.validation_report.results:
        assert result.criterion in acceptance_criteria


def test_validation_report_with_mixed_results():
    """Test that a ValidationReport with mixed pass/fail results is rejected."""
    with pytest.raises(ValidationError) as excinfo:
        TestModelWithValidation(
            x_agent_id="agent-123",
            title="Test Task",
            description="This is a test task",
            acceptance_criteria=["Criterion 1", "Criterion 2"],
            status="done",
            validation_report=ValidationReport(
                validated_by="reviewer-123",
                results=[
                    ValidationResult(criterion="Criterion 1", status="pass"),
                    ValidationResult(
                        criterion="Criterion 2", status="fail", notes="Not implemented"
                    ),
                ],
            ),
        )

    assert "Validation failed for the following criteria" in str(excinfo.value)


def test_validation_report_serialization():
    """Test that ValidationReport can be serialized and deserialized."""
    report = ValidationReport(
        validated_by="reviewer-123",
        results=[
            ValidationResult(criterion="Test passes", status="pass"),
        ],
    )

    # Convert to dict
    report_dict = report.model_dump()

    # Check dictionary structure
    assert "validated_by" in report_dict
    assert "timestamp" in report_dict
    assert "results" in report_dict
    assert len(report_dict["results"]) == 1
    assert report_dict["results"][0]["criterion"] == "Test passes"

    # Recreate from dict
    recreated = ValidationReport(**report_dict)
    assert recreated.validated_by == report.validated_by
    assert recreated.timestamp == report.timestamp
    assert recreated.results[0].criterion == report.results[0].criterion
