"""
Tests for CreateMemoryBlockTool: Agent-facing tool for creating general memory blocks.

These tests verify that the CreateMemoryBlock tool correctly creates doc, knowledge, and log
memory blocks with appropriate type-specific metadata and validation.
"""

import uuid
from datetime import datetime
from unittest.mock import patch

from infra_core.memory_system.tools.agent_facing.create_memory_block_agent_tool import (
    CreateMemoryBlockAgentInput,
    CreateMemoryBlockAgentOutput,
    create_memory_block_agent,
    create_memory_block_agent_tool,
)


class TestCreateMemoryBlockAgentTool:
    """Test suite for the CreateMemoryBlock agent-facing tool."""

    def test_create_doc_memory_block_success(self, temp_memory_bank):
        """Test successful creation of a doc memory block with doc-specific metadata."""
        input_data = CreateMemoryBlockAgentInput(
            type="doc",
            content="This is comprehensive API documentation for the memory system.",
            title="Memory System API Guide",
            audience="developers",
            section="core-apis",
            doc_version="v2.1",
            completed=True,
            tags=["documentation", "api", "memory-system"],
        )

        mock_id = str(uuid.uuid4())
        with patch(
            "infra_core.memory_system.tools.agent_facing.create_memory_block_agent_tool.create_memory_block"
        ) as mock_create:
            # Mock successful creation
            mock_create.return_value.success = True
            mock_create.return_value.id = mock_id
            mock_create.return_value.error = None
            mock_create.return_value.timestamp = datetime.now()

            result = create_memory_block_agent(input_data, temp_memory_bank)

            # Verify result
            assert result.success is True
            assert result.id == mock_id
            assert result.block_type == "doc"

            # Verify the core function was called with correct parameters
            mock_create.assert_called_once()
            call_args = mock_create.call_args[0][0]  # Get the CoreCreateMemoryBlockInput

            assert call_args.type == "doc"
            assert (
                call_args.text == "This is comprehensive API documentation for the memory system."
            )
            assert call_args.tags == ["documentation", "api", "memory-system"]

            # Verify doc-specific metadata was properly mapped
            metadata = call_args.metadata
            assert metadata["title"] == "Memory System API Guide"
            assert metadata["audience"] == "developers"
            assert metadata["section"] == "core-apis"
            assert metadata["version"] == "v2.1"  # doc_version maps to version
            assert metadata["completed"] is True
            assert metadata["x_tool_id"] == "CreateMemoryBlockTool"

    def test_create_knowledge_memory_block_success(self, temp_memory_bank):
        """Test successful creation of a knowledge memory block with knowledge-specific metadata."""
        input_data = CreateMemoryBlockAgentInput(
            type="knowledge",
            content="Machine learning algorithms require large datasets for training.",
            title="AI Knowledge Base",
            subject="artificial-intelligence",
            keywords=["ai", "ml", "training", "datasets"],
            source="AI Research Paper 2023",
            confidence=0.95,
            tags=["ai", "ml", "research"],
        )

        mock_id = str(uuid.uuid4())
        with patch(
            "infra_core.memory_system.tools.agent_facing.create_memory_block_agent_tool.create_memory_block"
        ) as mock_create:
            # Mock successful creation
            mock_create.return_value.success = True
            mock_create.return_value.id = mock_id
            mock_create.return_value.error = None
            mock_create.return_value.timestamp = datetime.now()

            result = create_memory_block_agent(input_data, temp_memory_bank)

            # Verify result
            assert result.success is True
            assert result.id == mock_id
            assert result.block_type == "knowledge"

            # Verify the core function was called with correct parameters
            mock_create.assert_called_once()
            call_args = mock_create.call_args[0][0]  # Get the CoreCreateMemoryBlockInput

            assert call_args.type == "knowledge"
            assert (
                call_args.text == "Machine learning algorithms require large datasets for training."
            )
            assert call_args.tags == ["ai", "ml", "research"]

            # Verify knowledge-specific metadata was properly mapped
            metadata = call_args.metadata
            assert metadata["title"] == "AI Knowledge Base"
            assert metadata["subject"] == "artificial-intelligence"
            assert metadata["keywords"] == ["ai", "ml", "training", "datasets"]
            assert metadata["source"] == "AI Research Paper 2023"
            assert metadata["confidence"] == 0.95
            assert metadata["x_tool_id"] == "CreateMemoryBlockTool"

    def test_create_log_memory_block_success(self, temp_memory_bank):
        """Test successful creation of a log memory block with log-specific metadata."""
        input_data = CreateMemoryBlockAgentInput(
            type="log",
            content="Agent successfully processed search request and returned 5 documents",
            title="Agent Search Log",
            log_level="INFO",
            component="search-agent",
            input_text="Search for documentation",
            output_text="Found 5 documents",
            model="gpt-4",
            token_count={"input": 25, "output": 15},
            latency_ms=1250.0,
            event_timestamp=datetime(2023, 11, 1, 14, 30, 0),
            tags=["agent", "search", "log"],
        )

        mock_id = str(uuid.uuid4())
        with patch(
            "infra_core.memory_system.tools.agent_facing.create_memory_block_agent_tool.create_memory_block"
        ) as mock_create:
            # Mock successful creation
            mock_create.return_value.success = True
            mock_create.return_value.id = mock_id
            mock_create.return_value.error = None
            mock_create.return_value.timestamp = datetime.now()

            result = create_memory_block_agent(input_data, temp_memory_bank)

            # Verify result
            assert result.success is True
            assert result.id == mock_id
            assert result.block_type == "log"

            # Verify the core function was called with correct parameters
            mock_create.assert_called_once()
            call_args = mock_create.call_args[0][0]  # Get the CoreCreateMemoryBlockInput

            assert call_args.type == "log"
            assert (
                call_args.text
                == "Agent successfully processed search request and returned 5 documents"
            )
            assert call_args.tags == ["agent", "search", "log"]

            # Verify log-specific metadata was properly mapped
            metadata = call_args.metadata
            assert metadata["title"] == "Agent Search Log"
            assert metadata["log_level"] == "INFO"
            assert metadata["component"] == "search-agent"
            assert metadata["input_text"] == "Search for documentation"
            assert metadata["output_text"] == "Found 5 documents"
            assert metadata["model"] == "gpt-4"
            assert metadata["token_count"] == {"input": 25, "output": 15}
            assert metadata["latency_ms"] == 1250.0
            assert metadata["event_timestamp"] == datetime(2023, 11, 1, 14, 30, 0)
            assert metadata["x_tool_id"] == "CreateMemoryBlockTool"

    def test_create_memory_block_minimal_fields(self, temp_memory_bank):
        """Test creation with only required fields."""
        input_data = CreateMemoryBlockAgentInput(
            type="doc",
            content="Minimal documentation content.",
        )

        mock_id = str(uuid.uuid4())
        with patch(
            "infra_core.memory_system.tools.agent_facing.create_memory_block_agent_tool.create_memory_block"
        ) as mock_create:
            # Mock successful creation
            mock_create.return_value.success = True
            mock_create.return_value.id = mock_id
            mock_create.return_value.error = None
            mock_create.return_value.timestamp = datetime.now()

            result = create_memory_block_agent(input_data, temp_memory_bank)

            # Verify result
            assert result.success is True
            assert result.id == mock_id
            assert result.block_type == "doc"

            # Verify the core function was called with minimal metadata
            mock_create.assert_called_once()
            call_args = mock_create.call_args[0][0]

            assert call_args.type == "doc"
            assert call_args.text == "Minimal documentation content."
            assert call_args.tags == []  # Default empty list

            # Only x_tool_id should be in metadata
            metadata = call_args.metadata
            assert metadata["x_tool_id"] == "CreateMemoryBlockTool"
            # Verify no other metadata fields are present
            assert "title" not in metadata
            assert "audience" not in metadata

    def test_create_memory_block_core_error_handling(self, temp_memory_bank):
        """Test error handling when the core create_memory_block function fails."""
        input_data = CreateMemoryBlockAgentInput(
            type="doc",  # Changed from "knowledge" to "doc" to focus on error handling, not type validation
            content="Test doc content.",
        )

        with patch(
            "infra_core.memory_system.tools.agent_facing.create_memory_block_agent_tool.create_memory_block"
        ) as mock_create:
            # Mock failure from core function
            mock_create.return_value.success = False
            mock_create.return_value.id = None
            mock_create.return_value.error = "Validation failed"
            mock_create.return_value.timestamp = datetime.now()

            result = create_memory_block_agent(input_data, temp_memory_bank)

            # Verify error is propagated
            assert result.success is False
            assert result.id is None
            assert result.error == "Validation failed"
            assert result.block_type == "doc"

    def test_create_memory_block_exception_handling(self, temp_memory_bank):
        """Test exception handling in the wrapper function."""
        input_data = CreateMemoryBlockAgentInput(
            type="log",
            content="Test log content.",
        )

        with patch(
            "infra_core.memory_system.tools.agent_facing.create_memory_block_agent_tool.create_memory_block"
        ) as mock_create:
            # Mock exception from core function
            mock_create.side_effect = Exception("Unexpected error occurred")

            result = create_memory_block_agent(input_data, temp_memory_bank)

            # Verify exception is handled
            assert result.success is False
            assert result.id is None
            assert "Error in create_memory_block_agent wrapper" in result.error
            assert "Unexpected error occurred" in result.error
            assert result.block_type == "log"

    def test_none_values_excluded_from_metadata(self, temp_memory_bank):
        """Test that None values are excluded from the metadata dict."""
        input_data = CreateMemoryBlockAgentInput(
            type="doc",
            title="Test Doc",
            content="Test content",
            audience="developers",
            section=None,  # Should be excluded
            doc_version=None,  # Should be excluded
            completed=False,  # Should be included (False is not None)
        )

        mock_id = str(uuid.uuid4())
        with patch(
            "infra_core.memory_system.tools.agent_facing.create_memory_block_agent_tool.create_memory_block"
        ) as mock_create:
            # Mock successful creation
            mock_create.return_value.success = True
            mock_create.return_value.id = mock_id
            mock_create.return_value.error = None
            mock_create.return_value.timestamp = datetime.now()

            result = create_memory_block_agent(input_data, temp_memory_bank)

            # Verify the metadata excludes None values
            call_args = mock_create.call_args[0][0]
            metadata = call_args.metadata

            assert metadata["title"] == "Test Doc"
            assert metadata["audience"] == "developers"
            assert metadata["completed"] is False  # False should be included
            assert metadata["x_tool_id"] == "CreateMemoryBlockTool"

            # None values should not be in metadata
            assert "section" not in metadata
            assert "version" not in metadata  # doc_version maps to version

            # Verify successful result
            assert result.success is True

    def test_cogni_tool_instance(self):
        """Test that the CogniTool instance is properly configured."""
        assert create_memory_block_agent_tool.name == "CreateMemoryBlock"
        assert "doc, knowledge, log" in create_memory_block_agent_tool.description
        assert create_memory_block_agent_tool.input_model == CreateMemoryBlockAgentInput
        assert create_memory_block_agent_tool.output_model == CreateMemoryBlockAgentOutput
        assert create_memory_block_agent_tool.memory_linked is True
