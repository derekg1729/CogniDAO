"""
Tests for the QueryDocMemoryBlockTool.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from infra_core.memory_system.tools.agent_facing.query_doc_memory_block_tool import (
    QueryDocMemoryBlockInput,
    QueryDocMemoryBlockOutput,
    query_doc_memory_block,
    query_doc_memory_block_tool,
)
from infra_core.memory_system.tools.memory_core.query_memory_blocks_tool import (
    QueryMemoryBlocksInput as CoreQueryMemoryBlocksInput,
    QueryMemoryBlocksOutput as CoreQueryMemoryBlocksOutput,
)
from infra_core.memory_system.schemas.memory_block import (
    MemoryBlock,
)  # For constructing mock results
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank


@pytest.fixture
def mock_memory_bank():
    """Create a mock StructuredMemoryBank."""
    bank = MagicMock(spec=StructuredMemoryBank)
    # Mock the core query_memory_blocks_core function's typical success output
    mock_core_output = CoreQueryMemoryBlocksOutput(
        success=True, blocks=[], timestamp=datetime.now()
    )
    # This is for the bank instance if called directly, but we'll patch the imported function.
    bank.query_semantic.return_value = []  # or appropriate mock for core query method
    bank.query_memory_blocks_core = MagicMock(return_value=mock_core_output)
    return bank


@pytest.fixture
def sample_query_doc_input_data():
    """Create a sample input data dict for testing QueryDocMemoryBlockInput."""
    return {
        "query_text": "Tell me about testing documents.",
        "title_filter": "Test Document Title",
        "audience_filter": "developers",
        "section_filter": "testing",
        "doc_version_filter": "1.0.1",
        "doc_format_filter": "markdown",
        "completed_filter": True,
        "tag_filters": ["test", "doc"],
        "top_k": 3,
    }


@pytest.fixture
def sample_query_doc_input(sample_query_doc_input_data):
    return QueryDocMemoryBlockInput(**sample_query_doc_input_data)


@pytest.fixture
def mock_retrieved_block_data():
    """Data for a single mock MemoryBlock."""
    return {
        "id": "doc-retrieved-123",
        "type": "doc",
        "text": "This is a retrieved test document.",
        "metadata": {
            "title": "Test Document Title",
            "audience": "developers",
            "section": "testing",
            "version": "1.0.1",
            "format": "markdown",
            "completed": True,
            "x_tool_id": "CreateDocMemoryBlockTool",  # Simulating it was created by the other tool
        },
        "tags": ["test", "doc"],
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "schema_version": 1,
    }


# Patch the core query_memory_blocks_core function within the tool's module scope
@patch(
    "infra_core.memory_system.tools.agent_facing.query_doc_memory_block_tool.query_memory_blocks_core"
)
def test_query_doc_memory_block_success(
    mock_core_query_blocks, mock_memory_bank, sample_query_doc_input, mock_retrieved_block_data
):
    """Test successful doc block querying and correct filter passing."""
    retrieved_block = MemoryBlock(**mock_retrieved_block_data)
    mock_core_output = CoreQueryMemoryBlocksOutput(
        success=True, blocks=[retrieved_block], timestamp=datetime.now()
    )
    mock_core_query_blocks.return_value = mock_core_output

    result = query_doc_memory_block(sample_query_doc_input, mock_memory_bank)

    assert isinstance(result, QueryDocMemoryBlockOutput)
    assert result.success is True
    assert len(result.blocks) == 1
    assert result.blocks[0].id == "doc-retrieved-123"
    assert result.error is None
    assert isinstance(result.timestamp, datetime)

    mock_core_query_blocks.assert_called_once()
    call_args, _ = mock_core_query_blocks.call_args
    queried_core_input: CoreQueryMemoryBlocksInput = call_args[0]
    passed_memory_bank = call_args[1]

    assert passed_memory_bank is mock_memory_bank
    assert queried_core_input.type_filter == "doc"
    assert queried_core_input.query_text == sample_query_doc_input.query_text
    assert queried_core_input.tag_filters == sample_query_doc_input.tag_filters
    assert queried_core_input.top_k == sample_query_doc_input.top_k

    metadata_filters = queried_core_input.metadata_filters
    assert metadata_filters is not None
    assert metadata_filters["title"] == sample_query_doc_input.title_filter
    assert metadata_filters["audience"] == sample_query_doc_input.audience_filter
    assert metadata_filters["section"] == sample_query_doc_input.section_filter
    assert metadata_filters["version"] == sample_query_doc_input.doc_version_filter
    assert metadata_filters["format"] == sample_query_doc_input.doc_format_filter
    assert metadata_filters["completed"] == sample_query_doc_input.completed_filter


@patch(
    "infra_core.memory_system.tools.agent_facing.query_doc_memory_block_tool.query_memory_blocks_core"
)
def test_query_doc_memory_block_minimal_input(mock_core_query_blocks, mock_memory_bank):
    """Test doc block querying with minimal required input."""
    mock_core_output = CoreQueryMemoryBlocksOutput(
        success=True, blocks=[], timestamp=datetime.now()
    )
    mock_core_query_blocks.return_value = mock_core_output

    minimal_input = QueryDocMemoryBlockInput(query_text="Minimal query")
    result = query_doc_memory_block(minimal_input, mock_memory_bank)

    assert result.success is True
    assert len(result.blocks) == 0

    mock_core_query_blocks.assert_called_once()
    call_args, _ = mock_core_query_blocks.call_args
    queried_core_input: CoreQueryMemoryBlocksInput = call_args[0]
    assert queried_core_input.type_filter == "doc"
    assert queried_core_input.query_text == "Minimal query"
    assert queried_core_input.metadata_filters is None  # Important check for None if empty


@patch(
    "infra_core.memory_system.tools.agent_facing.query_doc_memory_block_tool.query_memory_blocks_core"
)
def test_query_doc_memory_block_core_failure(
    mock_core_query_blocks, mock_memory_bank, sample_query_doc_input
):
    """Test doc block querying when core query fails."""
    mock_core_output = CoreQueryMemoryBlocksOutput(
        success=False, error="Core query layer failed", timestamp=datetime.now(), blocks=[]
    )
    mock_core_query_blocks.return_value = mock_core_output

    result = query_doc_memory_block(sample_query_doc_input, mock_memory_bank)

    assert result.success is False
    assert len(result.blocks) == 0
    assert result.error == "Core query layer failed"
    mock_core_query_blocks.assert_called_once()


@patch(
    "infra_core.memory_system.tools.agent_facing.query_doc_memory_block_tool.query_memory_blocks_core"
)
def test_query_doc_memory_block_core_exception(
    mock_core_query_blocks, mock_memory_bank, sample_query_doc_input
):
    """Test handling when core query_memory_blocks_core raises an unexpected exception."""
    mock_core_query_blocks.side_effect = Exception("Unexpected core query error")

    result = query_doc_memory_block(sample_query_doc_input, mock_memory_bank)

    assert result.success is False
    assert len(result.blocks) == 0
    assert "Error in query_doc_memory_block wrapper: Unexpected core query error" in result.error
    mock_core_query_blocks.assert_called_once()


def test_query_doc_memory_block_tool_initialization():
    """Test CogniTool initialization for QueryDocMemoryBlockTool."""
    assert query_doc_memory_block_tool.name == "QueryDocMemoryBlock"
    assert query_doc_memory_block_tool.memory_linked is True
    assert query_doc_memory_block_tool.input_model == QueryDocMemoryBlockInput
    assert query_doc_memory_block_tool.output_model == QueryDocMemoryBlockOutput


def test_query_doc_memory_block_tool_schema():
    """Test schema generation for the tool."""
    schema = query_doc_memory_block_tool.schema
    assert schema["name"] == "QueryDocMemoryBlock"
    assert schema["type"] == "function"
    assert "parameters" in schema
    properties = schema["parameters"]["properties"]
    assert "query_text" in properties
    assert "title_filter" in properties
    assert "doc_version_filter" in properties
    assert "doc_format_filter" in properties


@patch(
    "infra_core.memory_system.tools.agent_facing.query_doc_memory_block_tool.query_memory_blocks_core"
)
def test_query_doc_memory_block_tool_direct_invocation(
    mock_core_query_blocks,
    mock_memory_bank,
    sample_query_doc_input_data,  # Use data dict
):
    """Test direct invocation of the tool instance."""
    mock_core_output = CoreQueryMemoryBlocksOutput(
        success=True, blocks=[], timestamp=datetime.now()
    )
    mock_core_query_blocks.return_value = mock_core_output

    result = query_doc_memory_block_tool(
        memory_bank=mock_memory_bank, **sample_query_doc_input_data
    )

    assert isinstance(result, QueryDocMemoryBlockOutput)
    assert result.success is True
    mock_core_query_blocks.assert_called_once()


def test_query_doc_memory_block_tool_invalid_input(mock_memory_bank):
    """Test tool with invalid input (e.g., missing required field 'query_text')."""
    with patch(
        "infra_core.memory_system.tools.agent_facing.query_doc_memory_block_tool.query_doc_memory_block"
    ) as mock_func:
        result = query_doc_memory_block_tool(
            title_filter="Some title",  # Missing 'query_text'
            memory_bank=mock_memory_bank,
        )
        mock_func.assert_not_called()

    assert isinstance(result, QueryDocMemoryBlockOutput)
    assert result.success is False
    assert "Validation error" in result.error
    assert "query_text" in (result.error or "")
    assert "Field required" in (result.error or "")
