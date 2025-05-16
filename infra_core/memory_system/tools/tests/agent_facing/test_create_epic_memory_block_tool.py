"""
Tests for the CreateEpicMemoryBlockTool.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from infra_core.memory_system.tools.agent_facing.create_epic_memory_block_tool import (
    CreateEpicMemoryBlockInput,
    CreateEpicMemoryBlockOutput,
    create_epic_memory_block,
    create_epic_memory_block_tool,
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
        success=True, id="epic_block_123", timestamp=datetime.now()
    )
    bank.create_memory_block.return_value = mock_core_output
    return bank


@pytest.fixture
def sample_epic_input_data():
    """Create a sample input for testing CreateEpicMemoryBlockInput with all fields."""
    return {
        # Core epic fields
        "title": "Memory System Overhaul",
        "description": "Comprehensive updates to improve memory system reliability and capabilities",
        "owner": "user_1234",
        # Status and planning fields
        "status": "in_progress",
        "priority": "P1",
        # Time tracking fields
        "start_date": datetime(2024, 4, 1, 0, 0, 0),
        "target_date": datetime(2024, 6, 30, 0, 0, 0),
        "progress_percent": 35.0,
        # ExecutableMetadata planning fields
        "action_items": [
            "Update memory schemas",
            "Implement block links",
            "Create agent-facing tools",
        ],
        "acceptance_criteria": [
            "All memory system components pass integration tests",
            "Performance benchmarks show 50% improvement",
        ],
        "expected_artifacts": [
            "Updated schema documentation",
            "New agent-facing tools",
        ],
        "blocked_by": ["123e4567-e89b-12d3-a456-426614174000"],
        # Agent framework fields
        "tool_hints": ["editor", "test_runner"],
        "role_hint": "developer",
        "execution_timeout_minutes": 120,
        "cost_budget_usd": 10.0,
        # Epic-specific fields
        "tags": ["memory", "reliability", "infrastructure"],
        "confidence_score": {"human": 0.9, "ai": 0.85},
        # Additional fields from CoreCreateMemoryBlockInput
        "source_file": "epic_spec.md",
        "state": "published",
        "visibility": "internal",
        "created_by": "test_agent",
    }


@pytest.fixture
def sample_epic_input(sample_epic_input_data):
    """Create a CreateEpicMemoryBlockInput instance from sample data."""
    return CreateEpicMemoryBlockInput(**sample_epic_input_data)


# Patch the core create_memory_block function within the tool's module scope
@patch(
    "infra_core.memory_system.tools.agent_facing.create_epic_memory_block_tool.create_memory_block"
)
def test_create_epic_memory_block_success(
    mock_core_create_block, mock_memory_bank, sample_epic_input
):
    """Test successful epic block creation and correct metadata passing."""
    mock_core_output = CoreCreateMemoryBlockOutput(
        success=True, id="new-epic-id-success", timestamp=datetime.now()
    )
    mock_core_create_block.return_value = mock_core_output

    result = create_epic_memory_block(sample_epic_input, mock_memory_bank)

    assert isinstance(result, CreateEpicMemoryBlockOutput)
    assert result.success is True
    assert result.id == "new-epic-id-success"
    assert result.error is None
    assert isinstance(result.timestamp, datetime)

    mock_core_create_block.assert_called_once()
    call_args, _ = mock_core_create_block.call_args
    created_core_input: CoreCreateMemoryBlockInput = call_args[0]
    passed_memory_bank = call_args[1]

    assert passed_memory_bank is mock_memory_bank
    assert created_core_input.type == "epic"
    assert created_core_input.text == sample_epic_input.description
    assert created_core_input.created_by == sample_epic_input.created_by
    assert created_core_input.source_file == sample_epic_input.source_file
    assert created_core_input.tags == sample_epic_input.tags

    # Verify key metadata fields
    metadata = created_core_input.metadata
    assert metadata["title"] == sample_epic_input.title
    assert metadata["description"] == sample_epic_input.description
    assert metadata["owner"] == sample_epic_input.owner
    assert metadata["status"] == sample_epic_input.status
    assert metadata["priority"] == sample_epic_input.priority

    # Verify ExecutableMetadata fields
    assert metadata["action_items"] == sample_epic_input.action_items
    assert metadata["acceptance_criteria"] == sample_epic_input.acceptance_criteria
    assert metadata["expected_artifacts"] == sample_epic_input.expected_artifacts
    assert metadata["blocked_by"] == sample_epic_input.blocked_by
    assert metadata["tool_hints"] == sample_epic_input.tool_hints
    assert metadata["role_hint"] == sample_epic_input.role_hint
    assert metadata["execution_timeout_minutes"] == sample_epic_input.execution_timeout_minutes
    assert metadata["cost_budget_usd"] == sample_epic_input.cost_budget_usd

    # Verify epic-specific fields
    assert metadata["start_date"] == sample_epic_input.start_date
    assert metadata["target_date"] == sample_epic_input.target_date
    assert metadata["progress_percent"] == sample_epic_input.progress_percent
    assert metadata["tags"] == sample_epic_input.tags

    # Verify tool ID
    assert metadata["x_tool_id"] == "CreateEpicMemoryBlockTool"

    # Verify completed set to false by default
    assert metadata["completed"] is False


@patch(
    "infra_core.memory_system.tools.agent_facing.create_epic_memory_block_tool.create_memory_block"
)
def test_create_epic_memory_block_minimal_input(mock_core_create_block, mock_memory_bank):
    """Test epic block creation with minimal required input."""
    mock_core_output = CoreCreateMemoryBlockOutput(
        success=True, id="min-epic-id", timestamp=datetime.now()
    )
    mock_core_create_block.return_value = mock_core_output

    minimal_input = CreateEpicMemoryBlockInput(
        title="Minimal Epic",
        description="A minimal epic description",
        owner="user_minimal",
        acceptance_criteria=["Epic meets minimal requirements"],
    )

    result = create_epic_memory_block(minimal_input, mock_memory_bank)

    assert result.success is True
    assert result.id == "min-epic-id"
    mock_core_create_block.assert_called_once()
    call_args, _ = mock_core_create_block.call_args
    created_core_input: CoreCreateMemoryBlockInput = call_args[0]
    metadata = created_core_input.metadata

    assert created_core_input.type == "epic"
    assert created_core_input.text == "A minimal epic description"
    assert metadata["title"] == "Minimal Epic"
    assert metadata["description"] == "A minimal epic description"
    assert metadata["owner"] == "user_minimal"
    assert metadata["x_tool_id"] == "CreateEpicMemoryBlockTool"

    # Check defaults
    assert metadata["status"] == "backlog"
    assert metadata["completed"] is False
    assert "action_items" in metadata
    assert "acceptance_criteria" in metadata
    assert len(metadata["action_items"]) == 0
    assert len(metadata["acceptance_criteria"]) == 1
    assert metadata["acceptance_criteria"][0] == "Epic meets minimal requirements"


@patch(
    "infra_core.memory_system.tools.agent_facing.create_epic_memory_block_tool.create_memory_block"
)
def test_create_epic_memory_block_validation(mock_core_create_block, mock_memory_bank):
    """Test progress_percent validation."""
    mock_core_output = CoreCreateMemoryBlockOutput(
        success=True, id="valid-epic-id", timestamp=datetime.now()
    )
    mock_core_create_block.return_value = mock_core_output

    # Test valid values
    valid_input = CreateEpicMemoryBlockInput(
        title="Valid Progress Epic",
        description="Testing progress validation",
        owner="user_test",
        acceptance_criteria=["Validation works properly"],
        progress_percent=75.5,
    )

    result = create_epic_memory_block(valid_input, mock_memory_bank)
    assert result.success is True

    # Test invalid values would be caught by Pydantic validators
    with pytest.raises(ValueError):
        CreateEpicMemoryBlockInput(
            title="Invalid Progress Epic",
            description="Testing progress validation",
            owner="user_test",
            acceptance_criteria=["Validation works properly"],
            progress_percent=101.0,  # Invalid: > 100
        )


@patch(
    "infra_core.memory_system.tools.agent_facing.create_epic_memory_block_tool.create_memory_block"
)
def test_create_epic_memory_block_persistence_failure(
    mock_core_create_block, mock_memory_bank, sample_epic_input
):
    """Test epic block creation when core persistence fails."""
    mock_core_output = CoreCreateMemoryBlockOutput(
        success=False, error="Core persistence layer failed", timestamp=datetime.now()
    )
    mock_core_create_block.return_value = mock_core_output

    result = create_epic_memory_block(sample_epic_input, mock_memory_bank)

    assert result.success is False
    assert result.id is None
    assert result.error == "Core persistence layer failed"
    mock_core_create_block.assert_called_once()


@patch(
    "infra_core.memory_system.tools.agent_facing.create_epic_memory_block_tool.create_memory_block"
)
def test_create_epic_memory_block_core_exception(
    mock_core_create_block, mock_memory_bank, sample_epic_input
):
    """Test handling when core create_memory_block raises an unexpected exception."""
    mock_core_create_block.side_effect = Exception("Unexpected core error")

    result = create_epic_memory_block(sample_epic_input, mock_memory_bank)

    assert result.success is False
    assert result.id is None
    assert "Error in create_epic_memory_block wrapper: Unexpected core error" in result.error
    mock_core_create_block.assert_called_once()


def test_create_epic_memory_block_tool_initialization():
    """Test CogniTool initialization for CreateEpicMemoryBlockTool."""
    assert create_epic_memory_block_tool.name == "CreateEpicMemoryBlock"
    assert create_epic_memory_block_tool.memory_linked is True
    assert create_epic_memory_block_tool.input_model == CreateEpicMemoryBlockInput
    assert create_epic_memory_block_tool.output_model == CreateEpicMemoryBlockOutput


def test_create_epic_memory_block_tool_schema():
    """Test schema generation for the tool."""
    schema = create_epic_memory_block_tool.schema
    assert schema["name"] == "CreateEpicMemoryBlock"
    assert schema["type"] == "function"
    assert "parameters" in schema
    properties = schema["parameters"]["properties"]

    # Verify key fields are in the schema
    assert "title" in properties
    assert "description" in properties
    assert "owner" in properties
    assert "status" in properties
    assert "priority" in properties
    assert "action_items" in properties
    assert "acceptance_criteria" in properties
    assert "blocked_by" in properties
    assert "tags" in properties
