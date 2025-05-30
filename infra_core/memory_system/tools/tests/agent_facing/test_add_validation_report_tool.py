"""
Tests for the AddValidationReportTool.
"""

import pytest
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

from infra_core.memory_system.tools.agent_facing.add_validation_report_tool import (
    ValidationResultInput,
    AddValidationReportInput,
    AddValidationReportOutput,
    add_validation_report,
    add_validation_report_tool,
)
from infra_core.memory_system.schemas.memory_block import MemoryBlock
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank


@pytest.fixture
def mock_memory_bank():
    """Create a mock StructuredMemoryBank."""
    bank = MagicMock(spec=StructuredMemoryBank)
    return bank


@pytest.fixture
def sample_block_id():
    """Generate a valid UUID for testing."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_memory_block(sample_block_id):
    """Create a sample memory block for testing."""
    return MemoryBlock(
        id=sample_block_id,
        type="task",
        text="Test task description",
        state="published",
        visibility="internal",
        metadata={
            "title": "Test Task",
            "description": "Test task description",
            "status": "in_progress",
            "acceptance_criteria": ["Criterion 1 should pass", "Criterion 2 should pass"],
            "x_agent_id": "test_agent",  # Required by TaskMetadata validation
        },
        created_by="test_agent",
        created_at=datetime.now(),
        schema_version=4,
    )


@pytest.fixture
def sample_validation_input(sample_block_id):
    """Create a sample validation report input."""
    return AddValidationReportInput(
        block_id=sample_block_id,
        results=[
            ValidationResultInput(
                criterion="Criterion 1 should pass",
                status="pass",
                notes="Passed with flying colors",
            ),
            ValidationResultInput(
                criterion="Criterion 2 should pass", status="pass", notes="Also passed"
            ),
        ],
        validated_by="validator_agent",
        mark_as_done=True,
    )


@patch("infra_core.memory_system.tools.agent_facing.add_validation_report_tool.uuid.UUID")
def test_validate_uuid_format(mock_uuid_validate):
    """Test that UUID validation is performed."""
    # Setup
    mock_uuid_validate.side_effect = None  # No exception means validation passes

    # Create input with a valid UUID format
    valid_uuid = "12345678-1234-1234-1234-123456789012"

    # Execute
    input_obj = AddValidationReportInput(
        block_id=valid_uuid,
        results=[ValidationResultInput(criterion="Test criterion", status="pass")],
        validated_by="test_agent",
    )

    # Assert
    assert input_obj.block_id == valid_uuid
    mock_uuid_validate.assert_called_once_with(valid_uuid)


@patch("infra_core.memory_system.tools.agent_facing.add_validation_report_tool.uuid.UUID")
def test_invalid_uuid_format(mock_uuid_validate):
    """Test validation with invalid UUID format."""
    # Setup
    mock_uuid_validate.side_effect = ValueError("Invalid UUID")

    # Execute
    with pytest.raises(ValueError) as excinfo:
        AddValidationReportInput(
            block_id="not-a-valid-uuid",
            results=[ValidationResultInput(criterion="Test criterion", status="pass")],
            validated_by="validator_agent",
        )

    # Assert
    assert "block_id must be a valid UUID" in str(excinfo.value)


def test_add_validation_report_success(
    mock_memory_bank, sample_memory_block, sample_validation_input
):
    """Test successful validation report addition that marks task as done."""
    # Setup
    mock_memory_bank.get_memory_block.return_value = sample_memory_block
    mock_memory_bank.update_memory_block.return_value = True

    # Execute
    result = add_validation_report(sample_validation_input, mock_memory_bank)

    # Assert
    assert isinstance(result, AddValidationReportOutput)
    assert result.success is True
    assert result.block_id == sample_memory_block.id
    assert result.status_updated is True
    assert result.validation_summary["pass"] == 2
    assert result.validation_summary["fail"] == 0
    assert result.validation_summary["total"] == 2
    assert result.updated_metadata is not None

    # Verify metadata was updated correctly
    mock_memory_bank.update_memory_block.assert_called_once()
    updated_block = mock_memory_bank.update_memory_block.call_args[0][0]
    assert updated_block.metadata["status"] == "done"
    assert "validation_report" in updated_block.metadata
    validation_report = updated_block.metadata["validation_report"]
    assert validation_report["validated_by"] == "validator_agent"
    assert len(validation_report["results"]) == 2
    assert all(r["status"] == "pass" for r in validation_report["results"])


def test_add_validation_report_dont_mark_as_done(
    mock_memory_bank, sample_memory_block, sample_validation_input
):
    """Test validation report addition without changing status to done."""
    # Setup
    mock_memory_bank.get_memory_block.return_value = sample_memory_block
    mock_memory_bank.update_memory_block.return_value = True

    # Modify input to not mark as done
    sample_validation_input.mark_as_done = False

    # Execute
    result = add_validation_report(sample_validation_input, mock_memory_bank)

    # Assert
    assert result.success is True
    assert result.status_updated is False

    # Verify status wasn't changed
    updated_block = mock_memory_bank.update_memory_block.call_args[0][0]
    assert updated_block.metadata["status"] == "in_progress"  # Original status preserved
    assert "validation_report" in updated_block.metadata  # But report was added


def test_add_validation_report_with_failing_criteria(
    mock_memory_bank, sample_memory_block, sample_block_id
):
    """Test validation report with failing criteria doesn't mark as done."""
    # Setup
    mock_memory_bank.get_memory_block.return_value = sample_memory_block
    mock_memory_bank.update_memory_block.return_value = True

    # Create input with a failing criterion
    input_with_failure = AddValidationReportInput(
        block_id=sample_block_id,
        results=[
            ValidationResultInput(
                criterion="Criterion 1 should pass",
                status="pass",
            ),
            ValidationResultInput(
                criterion="Criterion 2 should pass", status="fail", notes="This criterion failed"
            ),
        ],
        validated_by="validator_agent",
        mark_as_done=True,  # This should now cause an error because we have failing criteria
    )

    # Execute
    result = add_validation_report(input_with_failure, mock_memory_bank)

    # Assert
    assert result.success is False
    assert (
        result.error
        == "Cannot mark as done when there are failing validation results. Fix failures or set mark_as_done=False."
    )
    assert result.validation_summary == {"pass": 1, "fail": 1, "total": 2}

    # Check that update was not called because we returned early
    mock_memory_bank.update_memory_block.assert_not_called()

    # Now try with mark_as_done=False which should succeed
    input_without_marking_done = AddValidationReportInput(
        block_id=sample_block_id,
        results=[
            ValidationResultInput(
                criterion="Criterion 1 should pass",
                status="pass",
            ),
            ValidationResultInput(
                criterion="Criterion 2 should pass", status="fail", notes="This criterion failed"
            ),
        ],
        validated_by="validator_agent",
        mark_as_done=False,  # Don't mark as done, just record the validation results
    )

    # Reset mock
    mock_memory_bank.update_memory_block.reset_mock()

    # Execute again
    result = add_validation_report(input_without_marking_done, mock_memory_bank)

    # This time it should succeed
    assert result.success is True
    assert result.status_updated is False
    assert mock_memory_bank.update_memory_block.called


def test_block_not_found(mock_memory_bank, sample_validation_input):
    """Test error handling when block is not found."""
    # Setup
    mock_memory_bank.get_memory_block.return_value = None

    # Execute
    result = add_validation_report(sample_validation_input, mock_memory_bank)

    # Assert
    assert result.success is False
    assert "not found" in result.error
    assert mock_memory_bank.update_memory_block.call_count == 0  # Should not attempt to update


def test_existing_validation_report(mock_memory_bank, sample_memory_block, sample_validation_input):
    """Test error handling when block already has a validation report."""
    # Setup - add a validation report to the block with valid results
    sample_memory_block.metadata["validation_report"] = {
        "validated_by": "previous_agent",
        "timestamp": "2025-01-01T00:00:00.000000",
        "results": [
            {"criterion": "Previous criterion", "status": "pass", "notes": "Already validated"}
        ],
    }
    mock_memory_bank.get_memory_block.return_value = sample_memory_block

    # Execute - without force flag
    sample_validation_input.force = False
    result = add_validation_report(sample_validation_input, mock_memory_bank)

    # Assert
    assert result.success is False
    assert "already exists" in result.error
    assert "force=True" in result.error

    # Now try with force flag
    sample_validation_input.force = True
    result = add_validation_report(sample_validation_input, mock_memory_bank)

    # Should succeed with force flag
    assert result.success is True


def test_non_executable_block_type(mock_memory_bank, sample_validation_input):
    """Test error handling when block is not an executable type."""
    # Setup - create a non-executable block type (e.g., 'doc')
    non_executable_block = MemoryBlock(
        id=sample_validation_input.block_id,
        type="doc",  # Not an executable type
        text="Documentation text",
        state="published",
        metadata={"title": "Documentation"},
        created_by="test_agent",
        created_at=datetime.now(),
    )
    mock_memory_bank.get_memory_block.return_value = non_executable_block

    # Execute
    result = add_validation_report(sample_validation_input, mock_memory_bank)

    # Assert
    assert result.success is False
    assert "is not an executable type" in result.error
    assert mock_memory_bank.update_memory_block.call_count == 0  # Should not attempt to update


def test_update_failure(mock_memory_bank, sample_memory_block, sample_validation_input):
    """Test error handling when memory bank update fails."""
    # Setup
    mock_memory_bank.get_memory_block.return_value = sample_memory_block
    mock_memory_bank.update_memory_block.return_value = False  # Update fails

    # Execute
    result = add_validation_report(sample_validation_input, mock_memory_bank)

    # Assert
    assert result.success is False
    assert "Failed to update memory block" in result.error


def test_add_validation_report_tool_initialization():
    """Test CogniTool initialization for AddValidationReportTool."""
    assert add_validation_report_tool.name == "AddValidationReport"
    assert add_validation_report_tool.memory_linked is True
    assert add_validation_report_tool.input_model == AddValidationReportInput
    assert add_validation_report_tool.output_model == AddValidationReportOutput


def test_add_validation_report_tool_schema():
    """Test schema generation for the tool."""
    schema = add_validation_report_tool.schema
    assert schema["name"] == "AddValidationReport"
    assert schema["type"] == "function"
    assert "parameters" in schema
    properties = schema["parameters"]["properties"]

    # Verify key fields are in the schema
    assert "block_id" in properties
    assert "results" in properties
    assert "validated_by" in properties
    assert "mark_as_done" in properties
    assert "force" in properties
