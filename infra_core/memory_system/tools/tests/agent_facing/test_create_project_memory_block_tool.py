"""
Tests for the CreateProjectMemoryBlockTool.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from infra_core.memory_system.tools.agent_facing.create_project_memory_block_tool import (
    CreateProjectMemoryBlockInput,
    CreateProjectMemoryBlockOutput,
    create_project_memory_block,
    create_project_memory_block_tool,
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
        success=True, id="project_block_123", timestamp=datetime.now()
    )
    bank.create_memory_block.return_value = mock_core_output
    return bank


@pytest.fixture
def sample_project_input_data():
    """Create a sample input for testing CreateProjectMemoryBlockInput with all fields."""
    return {
        # Core project fields
        "name": "Memory System Overhaul",
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
        # Project-specific fields
        "tags": ["memory", "reliability", "infrastructure"],
        "confidence_score": {"human": 0.9, "ai": 0.85},
        "phase": "Phase 1: Schema Enhancement",
        "implementation_flow": ["task-3.1", "task-3.2"],
        "success_criteria": [{"phase_1": ["BlockLink as source of truth for relationships"]}],
        "design_decisions": {"relationship_model": "link-first approach"},
        "references": {"docs": "https://example.com/memory-system-docs"},
        # Additional fields from CoreCreateMemoryBlockInput
        "source_file": "project_spec.md",
        "state": "published",
        "visibility": "internal",
        "created_by": "test_agent",
    }


@pytest.fixture
def sample_project_input(sample_project_input_data):
    """Create a CreateProjectMemoryBlockInput instance from sample data."""
    return CreateProjectMemoryBlockInput(**sample_project_input_data)


# Patch the core create_memory_block function within the tool's module scope
@patch(
    "infra_core.memory_system.tools.agent_facing.create_project_memory_block_tool.create_memory_block"
)
def test_create_project_memory_block_success(
    mock_core_create_block, mock_memory_bank, sample_project_input
):
    """Test successful project block creation and correct metadata passing."""
    mock_core_output = CoreCreateMemoryBlockOutput(
        success=True, id="new-project-id-success", timestamp=datetime.now()
    )
    mock_core_create_block.return_value = mock_core_output

    result = create_project_memory_block(sample_project_input, mock_memory_bank)

    assert isinstance(result, CreateProjectMemoryBlockOutput)
    assert result.success is True
    assert result.id == "new-project-id-success"
    assert result.error is None
    assert isinstance(result.timestamp, datetime)

    mock_core_create_block.assert_called_once()
    call_args, _ = mock_core_create_block.call_args
    created_core_input: CoreCreateMemoryBlockInput = call_args[0]
    passed_memory_bank = call_args[1]

    assert passed_memory_bank is mock_memory_bank
    assert created_core_input.type == "project"
    assert created_core_input.text == sample_project_input.description
    assert created_core_input.created_by == sample_project_input.created_by
    assert created_core_input.source_file == sample_project_input.source_file
    assert created_core_input.tags == sample_project_input.tags

    # Verify key metadata fields
    metadata = created_core_input.metadata
    assert metadata["name"] == sample_project_input.name
    assert metadata["description"] == sample_project_input.description
    assert metadata["owner"] == sample_project_input.owner
    assert metadata["status"] == sample_project_input.status
    assert metadata["priority"] == sample_project_input.priority

    # Verify ExecutableMetadata fields
    assert metadata["action_items"] == sample_project_input.action_items
    assert metadata["acceptance_criteria"] == sample_project_input.acceptance_criteria
    assert metadata["expected_artifacts"] == sample_project_input.expected_artifacts
    assert metadata["blocked_by"] == sample_project_input.blocked_by
    assert metadata["tool_hints"] == sample_project_input.tool_hints
    assert metadata["role_hint"] == sample_project_input.role_hint
    assert metadata["execution_timeout_minutes"] == sample_project_input.execution_timeout_minutes
    assert metadata["cost_budget_usd"] == sample_project_input.cost_budget_usd

    # Verify project-specific fields
    assert metadata["start_date"] == sample_project_input.start_date
    assert metadata["target_date"] == sample_project_input.target_date
    assert metadata["progress_percent"] == sample_project_input.progress_percent
    assert metadata["tags"] == sample_project_input.tags
    assert metadata["phase"] == sample_project_input.phase
    assert metadata["implementation_flow"] == sample_project_input.implementation_flow
    assert metadata["success_criteria"] == sample_project_input.success_criteria
    assert metadata["design_decisions"] == sample_project_input.design_decisions
    assert metadata["references"] == sample_project_input.references

    # Verify tool ID
    assert metadata["x_tool_id"] == "CreateProjectMemoryBlockTool"

    # Verify completed set to false by default
    assert metadata["completed"] is False


@patch(
    "infra_core.memory_system.tools.agent_facing.create_project_memory_block_tool.create_memory_block"
)
def test_create_project_memory_block_minimal_input(mock_core_create_block, mock_memory_bank):
    """Test project block creation with minimal required input."""
    mock_core_output = CoreCreateMemoryBlockOutput(
        success=True, id="min-project-id", timestamp=datetime.now()
    )
    mock_core_create_block.return_value = mock_core_output

    minimal_input = CreateProjectMemoryBlockInput(
        name="Minimal Project",
        description="A minimal project description",
        owner="user_minimal",
        acceptance_criteria=["Project meets minimal requirements"],
    )

    result = create_project_memory_block(minimal_input, mock_memory_bank)

    assert result.success is True
    assert result.id == "min-project-id"
    mock_core_create_block.assert_called_once()
    call_args, _ = mock_core_create_block.call_args
    created_core_input: CoreCreateMemoryBlockInput = call_args[0]
    metadata = created_core_input.metadata

    assert created_core_input.type == "project"
    assert created_core_input.text == "A minimal project description"
    assert metadata["name"] == "Minimal Project"
    assert metadata["description"] == "A minimal project description"
    assert metadata["owner"] == "user_minimal"
    assert metadata["x_tool_id"] == "CreateProjectMemoryBlockTool"

    # Check defaults
    assert metadata["status"] == "backlog"
    assert metadata["completed"] is False
    assert "action_items" in metadata
    assert "acceptance_criteria" in metadata
    assert len(metadata["action_items"]) == 0
    assert len(metadata["acceptance_criteria"]) == 1
    assert metadata["acceptance_criteria"][0] == "Project meets minimal requirements"


@patch(
    "infra_core.memory_system.tools.agent_facing.create_project_memory_block_tool.create_memory_block"
)
def test_create_project_memory_block_persistence_failure(
    mock_core_create_block, mock_memory_bank, sample_project_input
):
    """Test project block creation when core persistence fails."""
    mock_core_output = CoreCreateMemoryBlockOutput(
        success=False, error="Core persistence layer failed", timestamp=datetime.now()
    )
    mock_core_create_block.return_value = mock_core_output

    result = create_project_memory_block(sample_project_input, mock_memory_bank)

    assert result.success is False
    assert result.id is None
    assert result.error == "Core persistence layer failed"
    mock_core_create_block.assert_called_once()


@patch(
    "infra_core.memory_system.tools.agent_facing.create_project_memory_block_tool.create_memory_block"
)
def test_create_project_memory_block_core_exception(
    mock_core_create_block, mock_memory_bank, sample_project_input
):
    """Test handling when core create_memory_block raises an unexpected exception."""
    mock_core_create_block.side_effect = Exception("Unexpected core error")

    result = create_project_memory_block(sample_project_input, mock_memory_bank)

    assert result.success is False
    assert result.id is None
    assert "Error in create_project_memory_block wrapper: Unexpected core error" in result.error
    mock_core_create_block.assert_called_once()


def test_create_project_memory_block_tool_initialization():
    """Test CogniTool initialization for CreateProjectMemoryBlockTool."""
    assert create_project_memory_block_tool.name == "CreateProjectMemoryBlock"
    assert create_project_memory_block_tool.memory_linked is True
    assert create_project_memory_block_tool.input_model == CreateProjectMemoryBlockInput
    assert create_project_memory_block_tool.output_model == CreateProjectMemoryBlockOutput


def test_create_project_memory_block_tool_schema():
    """Test schema generation for the tool."""
    schema = create_project_memory_block_tool.schema
    assert schema["name"] == "CreateProjectMemoryBlock"
    assert schema["type"] == "function"
    assert "parameters" in schema
    properties = schema["parameters"]["properties"]

    # Verify key fields are in the schema
    assert "name" in properties
    assert "description" in properties
    assert "owner" in properties
    assert "status" in properties
    assert "priority" in properties
    assert "action_items" in properties
    assert "acceptance_criteria" in properties
    assert "blocked_by" in properties
    assert "tags" in properties
    assert "phase" in properties
