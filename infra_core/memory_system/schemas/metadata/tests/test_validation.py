"""Tests for validation models."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from infra_core.memory_system.schemas.metadata.common.validation import (
    ValidationResult,
    ValidationReport,
)


def test_validation_result_creation():
    """Test basic creation of a ValidationResult."""
    result = ValidationResult(
        criterion="Code should be well-documented",
        status="pass",
        notes="Documentation is thorough and clear",
    )

    assert result.criterion == "Code should be well-documented"
    assert result.status == "pass"
    assert result.notes == "Documentation is thorough and clear"


def test_validation_result_invalid_status():
    """Test that ValidationResult rejects invalid status values."""
    with pytest.raises(ValidationError):
        ValidationResult(
            criterion="Test criterion",
            status="invalid_status",  # Not "pass" or "fail"
        )


def test_validation_report_creation():
    """Test basic creation of a ValidationReport."""
    report = ValidationReport(
        validated_by="user-123",
        results=[
            ValidationResult(criterion="Criterion 1", status="pass"),
            ValidationResult(criterion="Criterion 2", status="pass", notes="Good work"),
        ],
    )

    assert report.validated_by == "user-123"
    assert isinstance(report.timestamp, datetime)
    assert len(report.results) == 2
    assert report.results[0].criterion == "Criterion 1"
    assert report.results[1].notes == "Good work"


def test_validation_report_empty_results():
    """Test that ValidationReport with empty results raises an error."""
    with pytest.raises(ValidationError):
        ValidationReport(validated_by="user-123", results=[])


def test_validation_report_extra_fields():
    """Test that ValidationReport rejects extra fields."""
    with pytest.raises(ValidationError):
        ValidationReport(
            validated_by="user-123",
            results=[ValidationResult(criterion="Criterion 1", status="pass")],
            extra_field="This should cause an error",
        )
