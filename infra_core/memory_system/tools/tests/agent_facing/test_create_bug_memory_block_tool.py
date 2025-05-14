"""
Tests for the CreateBugMemoryBlockTool.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from infra_core.memory_system.tools.agent_facing.create_bug_memory_block_tool import (
    CreateBugMemoryBlockInput,
    CreateBugMemoryBlockOutput,
    create_bug_memory_block,
    create_bug_memory_block_tool,
    BugSeverity,
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
        success=True, id="bug_block_123", timestamp=datetime.now()
    )
    bank.create_memory_block.return_value = mock_core_output
    return bank


@pytest.fixture
def sample_bug_input_data():
    """Create a sample input for testing CreateBugMemoryBlockInput with all fields."""
    return {
        # Core bug fields
        "title": "Memory corruption when processing large blocks",
        "description": "When processing memory blocks larger than 10MB, data corruption occurs.",
        "reporter": "user_1234",
        # Assignment and status fields
        "assignee": "user_5678",
        "status": "in_progress",
        "priority": "P1",
        "severity": "major",
        # Version tracking fields
        "version_found": "1.5.2",
        "version_fixed": None,
        "due_date": datetime(2024, 5, 15, 0, 0, 0),
        # ExecutableMetadata planning fields
        "action_items": [
            "Reproduce issue with test data",
            "Debug memory handling",
            "Fix buffer allocation",
        ],
        "acceptance_criteria": [
            "No data corruption occurs with 20MB blocks",
            "Performance impact is minimal",
        ],
        "expected_artifacts": [
            "Fixed memory handler",
            "Performance test results",
        ],
        "blocked_by": ["123e4567-e89b-12d3-a456-426614174000"],
        # Agent framework fields
        "tool_hints": ["editor", "test_runner", "profiler"],
        "role_hint": "developer",
        "execution_timeout_minutes": 60,
        "cost_budget_usd": 5.0,
        # Bug-specific detail fields
        "steps_to_reproduce": "1. Create a memory block > 10MB\n2. Process it with process_block()\n3. Observe corruption in output",
        "expected_behavior": "Data should be processed correctly without corruption",
        "actual_behavior": "Processed data is corrupted with random values",
        "environment": "Production server running v1.5.2",
        "logs_link": "https://logs.example.com/incident/12345",
        "repro_steps": ["Create large block", "Process block", "Check output"],
        # Classification fields
        "labels": ["memory", "data-integrity", "high-priority"],
        "confidence_score": {"human": 0.95, "ai": 0.85},
        # Additional fields from CoreCreateMemoryBlockInput
        "source_file": "bug_report.md",
        "state": "published",
        "visibility": "internal",
        "created_by": "test_agent",
    }


@pytest.fixture
def sample_bug_input(sample_bug_input_data):
    """Create a CreateBugMemoryBlockInput instance from sample data."""
    return CreateBugMemoryBlockInput(**sample_bug_input_data)


# Patch the core create_memory_block function within the tool's module scope
@patch(
    "infra_core.memory_system.tools.agent_facing.create_bug_memory_block_tool.create_memory_block"
)
def test_create_bug_memory_block_success(
    mock_core_create_block, mock_memory_bank, sample_bug_input
):
    """Test successful bug block creation and correct metadata passing."""
    mock_core_output = CoreCreateMemoryBlockOutput(
        success=True, id="new-bug-id-success", timestamp=datetime.now()
    )
    mock_core_create_block.return_value = mock_core_output

    result = create_bug_memory_block(sample_bug_input, mock_memory_bank)

    assert isinstance(result, CreateBugMemoryBlockOutput)
    assert result.success is True
    assert result.id == "new-bug-id-success"
    assert result.error is None
    assert isinstance(result.timestamp, datetime)

    mock_core_create_block.assert_called_once()
    call_args, _ = mock_core_create_block.call_args
    created_core_input: CoreCreateMemoryBlockInput = call_args[0]
    passed_memory_bank = call_args[1]

    assert passed_memory_bank is mock_memory_bank
    assert created_core_input.type == "bug"
    assert created_core_input.text == sample_bug_input.description
    assert created_core_input.created_by == sample_bug_input.created_by
    assert created_core_input.source_file == sample_bug_input.source_file
    assert created_core_input.tags == sample_bug_input.labels  # Labels used as tags for bugs

    # Verify key metadata fields
    metadata = created_core_input.metadata
    assert metadata["title"] == sample_bug_input.title
    assert metadata["description"] == sample_bug_input.description
    assert metadata["reporter"] == sample_bug_input.reporter
    assert metadata["assignee"] == sample_bug_input.assignee
    assert metadata["status"] == sample_bug_input.status
    assert metadata["priority"] == sample_bug_input.priority
    assert metadata["severity"] == sample_bug_input.severity

    # Verify ExecutableMetadata fields
    assert metadata["action_items"] == sample_bug_input.action_items
    assert metadata["acceptance_criteria"] == sample_bug_input.acceptance_criteria
    assert metadata["expected_artifacts"] == sample_bug_input.expected_artifacts
    assert metadata["blocked_by"] == sample_bug_input.blocked_by
    assert metadata["tool_hints"] == sample_bug_input.tool_hints
    assert metadata["role_hint"] == sample_bug_input.role_hint
    assert metadata["execution_timeout_minutes"] == sample_bug_input.execution_timeout_minutes
    assert metadata["cost_budget_usd"] == sample_bug_input.cost_budget_usd

    # Verify bug-specific fields
    assert metadata["version_found"] == sample_bug_input.version_found
    # Don't check for version_fixed as it's None and filtered out
    assert metadata["due_date"] == sample_bug_input.due_date
    assert metadata["steps_to_reproduce"] == sample_bug_input.steps_to_reproduce
    assert metadata["expected_behavior"] == sample_bug_input.expected_behavior
    assert metadata["actual_behavior"] == sample_bug_input.actual_behavior
    assert metadata["environment"] == sample_bug_input.environment
    assert metadata["logs_link"] == sample_bug_input.logs_link
    assert metadata["repro_steps"] == sample_bug_input.repro_steps
    assert metadata["labels"] == sample_bug_input.labels

    # Verify tool ID
    assert metadata["x_tool_id"] == "CreateBugMemoryBlockTool"

    # Verify completed set to false by default
    assert metadata["completed"] is False


@patch(
    "infra_core.memory_system.tools.agent_facing.create_bug_memory_block_tool.create_memory_block"
)
def test_create_bug_memory_block_minimal_input(mock_core_create_block, mock_memory_bank):
    """Test bug block creation with minimal required input."""
    mock_core_output = CoreCreateMemoryBlockOutput(
        success=True, id="min-bug-id", timestamp=datetime.now()
    )
    mock_core_create_block.return_value = mock_core_output

    minimal_input = CreateBugMemoryBlockInput(
        title="Minimal Bug",
        description="A minimal bug description",
        reporter="user_minimal",
        acceptance_criteria=["Bug is fixed with no regressions"],
    )

    result = create_bug_memory_block(minimal_input, mock_memory_bank)

    assert result.success is True
    assert result.id == "min-bug-id"
    mock_core_create_block.assert_called_once()
    call_args, _ = mock_core_create_block.call_args
    created_core_input: CoreCreateMemoryBlockInput = call_args[0]
    metadata = created_core_input.metadata

    assert created_core_input.type == "bug"
    assert created_core_input.text == "A minimal bug description"
    assert metadata["title"] == "Minimal Bug"
    assert metadata["description"] == "A minimal bug description"
    assert metadata["reporter"] == "user_minimal"
    assert metadata["x_tool_id"] == "CreateBugMemoryBlockTool"

    # Check defaults
    assert metadata["status"] == "backlog"
    assert metadata["completed"] is False
    assert "action_items" in metadata
    assert "acceptance_criteria" in metadata
    assert len(metadata["action_items"]) == 0
    assert len(metadata["acceptance_criteria"]) == 1
    assert metadata["acceptance_criteria"][0] == "Bug is fixed with no regressions"


@patch(
    "infra_core.memory_system.tools.agent_facing.create_bug_memory_block_tool.create_memory_block"
)
def test_create_bug_memory_block_severity_validation(mock_core_create_block, mock_memory_bank):
    """Test bug severity validation."""
    mock_core_output = CoreCreateMemoryBlockOutput(
        success=True, id="severity-bug-id", timestamp=datetime.now()
    )
    mock_core_create_block.return_value = mock_core_output

    # Test all valid severity values
    for severity in BugSeverity:
        valid_input = CreateBugMemoryBlockInput(
            title=f"{severity.value.capitalize()} Bug",
            description=f"Testing {severity.value} severity",
            reporter="user_test",
            acceptance_criteria=["Bug is fixed"],
            severity=severity.value,
        )

        result = create_bug_memory_block(valid_input, mock_memory_bank)
        assert result.success is True
        call_args, _ = mock_core_create_block.call_args
        created_core_input = call_args[0]
        assert created_core_input.metadata["severity"] == severity.value

    # Test invalid severity value is caught by validator
    with pytest.raises(ValueError):
        CreateBugMemoryBlockInput(
            title="Invalid Severity Bug",
            description="Testing invalid severity",
            reporter="user_test",
            acceptance_criteria=["Bug is fixed"],
            severity="invalid_severity",  # Not a valid severity
        )


@patch(
    "infra_core.memory_system.tools.agent_facing.create_bug_memory_block_tool.create_memory_block"
)
def test_create_bug_memory_block_persistence_failure(
    mock_core_create_block, mock_memory_bank, sample_bug_input
):
    """Test bug block creation when core persistence fails."""
    mock_core_output = CoreCreateMemoryBlockOutput(
        success=False, error="Core persistence layer failed", timestamp=datetime.now()
    )
    mock_core_create_block.return_value = mock_core_output

    result = create_bug_memory_block(sample_bug_input, mock_memory_bank)

    assert result.success is False
    assert result.id is None
    assert result.error == "Core persistence layer failed"
    mock_core_create_block.assert_called_once()


@patch(
    "infra_core.memory_system.tools.agent_facing.create_bug_memory_block_tool.create_memory_block"
)
def test_create_bug_memory_block_core_exception(
    mock_core_create_block, mock_memory_bank, sample_bug_input
):
    """Test handling when core create_memory_block raises an unexpected exception."""
    mock_core_create_block.side_effect = Exception("Unexpected core error")

    result = create_bug_memory_block(sample_bug_input, mock_memory_bank)

    assert result.success is False
    assert result.id is None
    assert "Error in create_bug_memory_block wrapper: Unexpected core error" in result.error
    mock_core_create_block.assert_called_once()


def test_create_bug_memory_block_tool_initialization():
    """Test CogniTool initialization for CreateBugMemoryBlockTool."""
    assert create_bug_memory_block_tool.name == "CreateBugMemoryBlock"
    assert create_bug_memory_block_tool.memory_linked is True
    assert create_bug_memory_block_tool.input_model == CreateBugMemoryBlockInput
    assert create_bug_memory_block_tool.output_model == CreateBugMemoryBlockOutput


def test_create_bug_memory_block_tool_schema():
    """Test schema generation for the tool."""
    schema = create_bug_memory_block_tool.schema
    assert schema["name"] == "CreateBugMemoryBlock"
    assert schema["type"] == "function"
    assert "parameters" in schema
    properties = schema["parameters"]["properties"]

    # Verify key fields are in the schema
    assert "title" in properties
    assert "description" in properties
    assert "reporter" in properties
    assert "assignee" in properties
    assert "status" in properties
    assert "priority" in properties
    assert "severity" in properties
    assert "action_items" in properties
    assert "acceptance_criteria" in properties
    assert "blocked_by" in properties
    assert "steps_to_reproduce" in properties
    assert "labels" in properties
