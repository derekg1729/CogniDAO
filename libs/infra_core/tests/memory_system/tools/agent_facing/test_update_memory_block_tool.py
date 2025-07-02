"""
Integration tests for UpdateMemoryBlockTool.

These tests validate the agent-facing tool interface and its integration
with the core update functionality using real memory bank interactions.
"""

import pytest
from datetime import datetime
from unittest.mock import patch
import uuid

from infra_core.memory_system.tools.agent_facing.update_memory_block_tool import (
    update_memory_block_tool,
    UpdateMemoryBlockToolInput,
    UpdateMemoryBlockToolOutput,
)
from infra_core.memory_system.tools.memory_core.update_memory_block_models import (
    PatchType,
    UpdateErrorCode,
)
from infra_core.memory_system.schemas.memory_block import MemoryBlock, ConfidenceScore


@pytest.fixture
def test_block_id():
    """Generate a valid UUID for testing."""
    return str(uuid.uuid4())


# mock_memory_bank fixture now provided by conftest.py


@pytest.fixture
def sample_memory_block(test_block_id):
    """Create a sample memory block for testing."""
    return MemoryBlock(
        id=test_block_id,
        type="knowledge",
        text="Original content",
        block_version=5,
        state="draft",
        visibility="internal",
        tags=["test", "original"],
        metadata={
            "title": "Test Knowledge Block",  # Required field for KnowledgeMetadata
            "source": "test_fixture",
            "keywords": ["testing", "sample"],
            "confidence": 0.9,
            "x_agent_id": "test_agent",
        },
        source_file="test.md",
        confidence=ConfidenceScore(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
        links=[],
    )


# Test successful tool operations


def test_update_memory_block_tool_basic_text_update(mock_memory_bank, sample_memory_block):
    """Test basic text update through the agent tool."""
    mock_memory_bank.get_memory_block.return_value = sample_memory_block

    input_data = UpdateMemoryBlockToolInput(
        block_id=sample_memory_block.id,
        text="Updated content by agent",
        author="test_agent",
        change_note="Agent updated the content",
    )

    # Import the tool instance instead of the function
    from infra_core.memory_system.tools.agent_facing.update_memory_block_tool import (
        update_memory_block_tool_instance,
    )

    result = update_memory_block_tool_instance(input_data, memory_bank=mock_memory_bank)

    assert isinstance(result, UpdateMemoryBlockToolOutput)
    assert result.success is True
    assert result.id == sample_memory_block.id
    assert result.error is None
    assert result.error_code is None
    assert result.previous_version == 5
    assert result.new_version == 6
    assert result.text_changed is True
    assert result.processing_time_ms is not None

    # Verify memory bank interactions
    mock_memory_bank.get_memory_block.assert_called_once_with(sample_memory_block.id)
    mock_memory_bank.update_memory_block.assert_called_once()


def test_update_memory_block_tool_multiple_fields(mock_memory_bank, sample_memory_block):
    """Test updating multiple fields through the agent tool."""
    mock_memory_bank.get_memory_block.return_value = sample_memory_block

    input_data = UpdateMemoryBlockToolInput(
        block_id=sample_memory_block.id,
        text="New content",
        state="published",
        visibility="public",
        tags=["updated", "published"],
        metadata={
            "title": "Updated Knowledge Block",  # Add required title field
            "source": "agent_update",
            "keywords": ["agent-testing", "updated"],  # Replace domain with keywords
            "confidence": 0.95,  # Replace validity with confidence score
            "x_agent_id": "test_agent",
        },
        merge_tags=False,  # Replace tags
        merge_metadata=True,  # Merge metadata
        author="test_agent",
        change_note="Multi-field update by agent",
    )

    result = update_memory_block_tool(input_data, mock_memory_bank)

    assert result.success is True
    assert result.new_version == 6
    expected_fields = {
        "text",
        "state",
        "visibility",
        "tags",
        "metadata",
        "block_version",
        "updated_at",
    }
    assert set(result.fields_updated).issuperset(expected_fields)
    assert result.text_changed is True


def test_update_memory_block_tool_with_version_check(mock_memory_bank, sample_memory_block):
    """Test optimistic locking through the agent tool."""
    mock_memory_bank.get_memory_block.return_value = sample_memory_block

    input_data = UpdateMemoryBlockToolInput(
        block_id=sample_memory_block.id,
        previous_block_version=5,  # Correct version
        text="Version-checked update",
        author="test_agent",
    )

    result = update_memory_block_tool(input_data, mock_memory_bank)

    assert result.success is True
    assert result.previous_version == 5
    assert result.new_version == 6


# Test patch operations


def test_update_memory_block_tool_text_patch(mock_memory_bank, sample_memory_block):
    """Test text patch application through the agent tool."""
    mock_memory_bank.get_memory_block.return_value = sample_memory_block

    input_data = UpdateMemoryBlockToolInput(
        block_id=sample_memory_block.id,
        text_patch="@@ -1,1 +1,1 @@\n-Original content\n+Patched content",
        patch_type=PatchType.UNIFIED_DIFF,
        author="test_agent",
        change_note="Applied text patch",
    )

    with patch(
        "infra_core.memory_system.tools.memory_core.update_memory_block_core.apply_text_patch_safe"
    ) as mock_patch:
        mock_patch.return_value = "Patched content"
        result = update_memory_block_tool(input_data, mock_memory_bank)

    assert result.success is True
    assert "text" in result.fields_updated
    assert result.text_changed is True


def test_update_memory_block_tool_json_patch(mock_memory_bank, sample_memory_block):
    """Test JSON patch application through the agent tool."""
    mock_memory_bank.get_memory_block.return_value = sample_memory_block

    json_patch = [
        {"op": "replace", "path": "/metadata/source", "value": "updated_source"},
        {
            "op": "replace",
            "path": "/metadata/keywords",
            "value": ["json-patch-testing"],
        },  # Replace domain with keywords
    ]

    input_data = UpdateMemoryBlockToolInput(
        block_id=sample_memory_block.id,
        structured_patch=json_patch,
        patch_type=PatchType.JSON_PATCH,
        author="test_agent",
        change_note="Applied JSON patch",
    )

    result = update_memory_block_tool(input_data, mock_memory_bank)

    assert result.success is True


# Test error conditions


def test_update_memory_block_tool_block_not_found(mock_memory_bank):
    """Test error when block doesn't exist."""
    mock_memory_bank.get_memory_block.return_value = None
    # Use a valid UUID format even for non-existent blocks
    non_existent_uuid = str(uuid.uuid4())

    input_data = UpdateMemoryBlockToolInput(
        block_id=non_existent_uuid,
        text="Updated content",
        author="test_agent",
    )

    result = update_memory_block_tool(input_data, mock_memory_bank)

    assert result.success is False
    assert "not found" in result.error
    assert result.error_code == UpdateErrorCode.BLOCK_NOT_FOUND


def test_update_memory_block_tool_version_conflict(mock_memory_bank, sample_memory_block):
    """Test version conflict error through the agent tool."""
    mock_memory_bank.get_memory_block.return_value = sample_memory_block

    input_data = UpdateMemoryBlockToolInput(
        block_id=sample_memory_block.id,
        previous_block_version=3,  # Wrong version (current is 5)
        text="Updated content",
        author="test_agent",
    )

    result = update_memory_block_tool(input_data, mock_memory_bank)

    assert result.success is False
    assert result.error_code == UpdateErrorCode.VERSION_CONFLICT
    assert "expected 3, got 5" in result.error
    assert result.previous_version == 5


def test_update_memory_block_tool_persistence_failure(mock_memory_bank, sample_memory_block):
    """Test persistence failure through the agent tool."""
    mock_memory_bank.get_memory_block.return_value = sample_memory_block
    mock_memory_bank.update_memory_block.return_value = False

    input_data = UpdateMemoryBlockToolInput(
        block_id=sample_memory_block.id,
        text="Updated content",
        author="test_agent",
    )

    result = update_memory_block_tool(input_data, mock_memory_bank)

    assert result.success is False
    assert result.error_code == UpdateErrorCode.PERSISTENCE_FAILURE
    assert "Failed to persist" in result.error


def test_update_memory_block_tool_validation_error(mock_memory_bank, sample_memory_block):
    """Test validation error through the agent tool."""
    mock_memory_bank.get_memory_block.return_value = sample_memory_block

    # Add existing tags to cause validation error when merged
    sample_memory_block.tags = [f"existing_tag_{i}" for i in range(15)]

    input_data = UpdateMemoryBlockToolInput(
        block_id=sample_memory_block.id,
        tags=[f"new_tag_{i}" for i in range(10)],  # Total will exceed 20
        merge_tags=True,
        author="test_agent",
    )

    result = update_memory_block_tool(input_data, mock_memory_bank)

    assert result.success is False
    assert result.error_code == UpdateErrorCode.VALIDATION_ERROR
    assert "List should have at most 20 items" in result.error


# Test edge cases


def test_update_memory_block_tool_no_changes(mock_memory_bank, sample_memory_block):
    """Test update with no actual changes."""
    mock_memory_bank.get_memory_block.return_value = sample_memory_block

    input_data = UpdateMemoryBlockToolInput(
        block_id=sample_memory_block.id,
        author="test_agent",
        change_note="No-op update",
    )

    result = update_memory_block_tool(input_data, mock_memory_bank)

    assert result.success is True
    # Should still increment version and update timestamp
    assert result.new_version == 6
    assert "block_version" in result.fields_updated
    assert "updated_at" in result.fields_updated


def test_update_memory_block_tool_exception_handling(mock_memory_bank):
    """Test handling of unexpected exceptions."""
    mock_memory_bank.get_memory_block.side_effect = Exception("Database error")
    test_uuid = str(uuid.uuid4())

    input_data = UpdateMemoryBlockToolInput(
        block_id=test_uuid,
        text="Updated content",
        author="test_agent",
    )

    result = update_memory_block_tool(input_data, mock_memory_bank)

    assert result.success is False
    assert "Unexpected error updating memory block" in result.error


# Test tool initialization


def test_update_memory_block_tool_initialization():
    """Test that the UpdateMemoryBlock tool is properly initialized."""
    from infra_core.memory_system.tools.agent_facing.update_memory_block_tool import (
        update_memory_block_tool_instance,
    )

    assert update_memory_block_tool_instance.name == "UpdateMemoryBlock"
    assert update_memory_block_tool_instance.input_model == UpdateMemoryBlockToolInput
    assert update_memory_block_tool_instance.output_model == UpdateMemoryBlockToolOutput
    assert update_memory_block_tool_instance._function == update_memory_block_tool
    assert update_memory_block_tool_instance.memory_linked is True


# Integration test with real scenarios


def test_update_memory_block_tool_agent_workflow(mock_memory_bank, sample_memory_block):
    """Test a realistic agent workflow for updating a memory block."""
    mock_memory_bank.get_memory_block.return_value = sample_memory_block

    # Simulate an agent updating a knowledge block with new information
    input_data = UpdateMemoryBlockToolInput(
        block_id=sample_memory_block.id,
        text="Original content\n\nNew insights added by agent.",
        tags=["original", "test", "agent-updated"],
        metadata={
            "title": "Agent-Enhanced Knowledge Block",  # Add required title field
            "source": "cogni_agent_update",
            "keywords": ["agent-enriched", "updated"],  # Replace domain with keywords
            "confidence": 0.95,  # Replace validity with confidence score
            "x_agent_id": "cogni_agent",
        },
        state="published",  # Promote to published
        merge_tags=True,  # Merge with existing tags
        merge_metadata=True,  # Merge with existing metadata
        author="cogni_agent",
        agent_id="test_agent",
        change_note="Agent enriched content with new insights",
    )

    result = update_memory_block_tool(input_data, mock_memory_bank)

    assert result.success is True
    assert result.new_version == 6
    assert result.text_changed is True

    # Should update multiple fields
    expected_fields = {"text", "tags", "metadata", "state", "block_version", "updated_at"}
    assert set(result.fields_updated).issuperset(expected_fields)

    # Processing metadata should be available
    assert result.processing_time_ms is not None
    assert result.timestamp is not None


def test_update_memory_block_tool_with_tags(mock_memory_bank, sample_memory_block):
    """Test updating block tags through the agent tool."""
    mock_memory_bank.get_memory_block.return_value = sample_memory_block

    new_tags = ["updated", "agent-modified", "test"]

    input_data = UpdateMemoryBlockToolInput(
        block_id=sample_memory_block.id,
        tags=new_tags,
        merge_tags=False,  # Replace tags
        author="test_agent",
        change_note="Updated tags",
    )

    result = update_memory_block_tool(input_data, mock_memory_bank)

    assert result.success is True
    assert "tags" in result.fields_updated
