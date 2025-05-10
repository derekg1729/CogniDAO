"""
Tests for the CreateDocMemoryBlockTool.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from infra_core.memory_system.tools.agent_facing.create_doc_memory_block_tool import (
    CreateDocMemoryBlockInput,
    CreateDocMemoryBlockOutput,
    create_doc_memory_block,
    create_doc_memory_block_tool,
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
    # This mock is for the bank instance if it were called directly,
    # but we will primarily patch the imported create_memory_block function.
    mock_core_output = CoreCreateMemoryBlockOutput(
        success=True, id="doc_block_123", timestamp=datetime.now()
    )
    bank.create_memory_block.return_value = mock_core_output  # For direct bank calls if any
    return bank


@pytest.fixture
def sample_doc_input_data():
    """Create a sample input for testing CreateDocMemoryBlockInput."""
    return {
        "title": "Test Document Title",
        "content": "This is the content of the test document.",
        "audience": "developers",
        "section": "testing",
        "doc_version": "1.0.1",
        "last_reviewed": datetime(2023, 10, 1, 10, 0, 0),
        "doc_format": "markdown",
        "completed": True,
        "source_file": "test_doc.md",
        "tags": ["test", "doc"],
        "created_by": "test_agent",
    }


@pytest.fixture
def sample_doc_input(sample_doc_input_data):
    return CreateDocMemoryBlockInput(**sample_doc_input_data)


# Patch the core create_memory_block function within the tool's module scope
@patch(
    "infra_core.memory_system.tools.agent_facing.create_doc_memory_block_tool.create_memory_block"
)
def test_create_doc_memory_block_success(
    mock_core_create_block, mock_memory_bank, sample_doc_input
):
    """Test successful doc block creation and correct metadata passing."""
    mock_core_output = CoreCreateMemoryBlockOutput(
        success=True, id="new-doc-id-success", timestamp=datetime.now()
    )
    mock_core_create_block.return_value = mock_core_output

    result = create_doc_memory_block(sample_doc_input, mock_memory_bank)

    assert isinstance(result, CreateDocMemoryBlockOutput)
    assert result.success is True
    assert result.id == "new-doc-id-success"
    assert result.error is None
    assert isinstance(result.timestamp, datetime)

    mock_core_create_block.assert_called_once()
    call_args, _ = mock_core_create_block.call_args
    created_core_input: CoreCreateMemoryBlockInput = call_args[0]
    passed_memory_bank = call_args[1]

    assert passed_memory_bank is mock_memory_bank
    assert created_core_input.type == "doc"
    assert created_core_input.text == sample_doc_input.content
    assert created_core_input.created_by == sample_doc_input.created_by
    assert created_core_input.source_file == sample_doc_input.source_file
    assert created_core_input.tags == sample_doc_input.tags

    metadata = created_core_input.metadata
    assert metadata["title"] == sample_doc_input.title
    assert metadata["audience"] == sample_doc_input.audience
    assert metadata["section"] == sample_doc_input.section
    assert metadata["version"] == sample_doc_input.doc_version
    assert metadata["last_reviewed"] == sample_doc_input.last_reviewed
    assert metadata["format"] == sample_doc_input.doc_format
    assert metadata["completed"] == sample_doc_input.completed
    assert metadata["x_tool_id"] == "CreateDocMemoryBlockTool"


@patch(
    "infra_core.memory_system.tools.agent_facing.create_doc_memory_block_tool.create_memory_block"
)
def test_create_doc_memory_block_minimal_input(mock_core_create_block, mock_memory_bank):
    """Test doc block creation with minimal required input."""
    mock_core_output = CoreCreateMemoryBlockOutput(
        success=True, id="min-doc-id", timestamp=datetime.now()
    )
    mock_core_create_block.return_value = mock_core_output

    minimal_input = CreateDocMemoryBlockInput(title="Minimal Doc", content="Minimal content.")
    result = create_doc_memory_block(minimal_input, mock_memory_bank)

    assert result.success is True
    assert result.id == "min-doc-id"

    mock_core_create_block.assert_called_once()
    call_args, _ = mock_core_create_block.call_args
    created_core_input: CoreCreateMemoryBlockInput = call_args[0]
    metadata = created_core_input.metadata

    assert created_core_input.type == "doc"
    assert created_core_input.text == "Minimal content."
    assert metadata["title"] == "Minimal Doc"
    assert metadata["x_tool_id"] == "CreateDocMemoryBlockTool"
    assert metadata.get("audience") is None  # Ensure not present if not provided and not defaulted
    assert metadata.get("completed") is False  # Default from CreateDocMemoryBlockInput


@patch(
    "infra_core.memory_system.tools.agent_facing.create_doc_memory_block_tool.create_memory_block"
)
def test_create_doc_memory_block_persistence_failure(
    mock_core_create_block, mock_memory_bank, sample_doc_input
):
    """Test doc block creation when core persistence fails."""
    mock_core_output = CoreCreateMemoryBlockOutput(
        success=False, error="Core persistence layer failed", timestamp=datetime.now()
    )
    mock_core_create_block.return_value = mock_core_output

    result = create_doc_memory_block(sample_doc_input, mock_memory_bank)

    assert result.success is False
    assert result.id is None
    assert result.error == "Core persistence layer failed"
    mock_core_create_block.assert_called_once()


@patch(
    "infra_core.memory_system.tools.agent_facing.create_doc_memory_block_tool.create_memory_block"
)
def test_create_doc_memory_block_core_exception(
    mock_core_create_block, mock_memory_bank, sample_doc_input
):
    """Test handling when core create_memory_block raises an unexpected exception."""
    mock_core_create_block.side_effect = Exception("Unexpected core error")

    result = create_doc_memory_block(sample_doc_input, mock_memory_bank)

    assert result.success is False
    assert result.id is None
    assert "Error in create_doc_memory_block wrapper: Unexpected core error" in result.error
    mock_core_create_block.assert_called_once()


def test_create_doc_memory_block_tool_initialization():
    """Test CogniTool initialization for CreateDocMemoryBlockTool."""
    assert create_doc_memory_block_tool.name == "CreateDocMemoryBlock"
    assert create_doc_memory_block_tool.memory_linked is True
    assert create_doc_memory_block_tool.input_model == CreateDocMemoryBlockInput
    assert create_doc_memory_block_tool.output_model == CreateDocMemoryBlockOutput


def test_create_doc_memory_block_tool_schema():
    """Test schema generation for the tool."""
    schema = create_doc_memory_block_tool.schema
    assert schema["name"] == "CreateDocMemoryBlock"
    assert schema["type"] == "function"
    assert "parameters" in schema
    properties = schema["parameters"]["properties"]
    assert "title" in properties
    assert "content" in properties
    assert "audience" in properties
    assert "doc_version" in properties  # Check renamed field
    assert "doc_format" in properties  # Check renamed field


@patch(
    "infra_core.memory_system.tools.agent_facing.create_doc_memory_block_tool.create_memory_block"
)
def test_create_doc_memory_block_tool_direct_invocation(
    mock_core_create_block,
    mock_memory_bank,
    sample_doc_input_data,  # Use data dict for direct call
):
    """Test direct invocation of the tool instance."""
    mock_core_output = CoreCreateMemoryBlockOutput(
        success=True, id="direct-doc-id", timestamp=datetime.now()
    )
    mock_core_create_block.return_value = mock_core_output

    # Call tool instance directly with kwargs
    result = create_doc_memory_block_tool(memory_bank=mock_memory_bank, **sample_doc_input_data)

    assert isinstance(result, CreateDocMemoryBlockOutput)
    assert result.success is True
    assert result.id == "direct-doc-id"
    mock_core_create_block.assert_called_once()


def test_create_doc_memory_block_tool_invalid_input(mock_memory_bank):
    """Test tool with invalid input (e.g., missing required field 'title')."""
    # Tool input validation happens before the function is called
    # Mock the actual function to ensure it's not called if Pydantic validation fails
    with patch(
        "infra_core.memory_system.tools.agent_facing.create_doc_memory_block_tool.create_doc_memory_block"
    ) as mock_func:
        result = create_doc_memory_block_tool(
            content="Some content",  # Missing 'title'
            memory_bank=mock_memory_bank,
        )
        mock_func.assert_not_called()

    assert isinstance(result, CreateDocMemoryBlockOutput)
    assert result.success is False
    assert "Validation error" in result.error
    assert "title" in (result.error or "")
    assert "Field required" in (result.error or "")
