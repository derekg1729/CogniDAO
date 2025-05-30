"""
Test the CreateBlockLink MCP tool integration.

These tests ensure the CreateBlockLink tool works correctly through the MCP server
and continues to function properly as the codebase evolves.
"""

import pytest
import uuid
from unittest.mock import patch

# Import the MCP server functions
from services.mcp_server.app.mcp_server import create_block_link, create_work_item


@pytest.mark.asyncio
async def test_create_block_link_tool_success(temp_memory_bank):
    """Test the CreateBlockLink MCP tool with successful link creation."""
    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        # First create two work items to link
        item1_input = {
            "type": "task",
            "title": "Source Task",
            "description": "A source task for linking",
            "acceptance_criteria": ["Should be linkable"],
        }

        item2_input = {
            "type": "task",
            "title": "Target Task",
            "description": "A target task for linking",
            "acceptance_criteria": ["Should be linkable"],
        }

        # Create the items
        item1_result = await create_work_item(item1_input)
        item2_result = await create_work_item(item2_input)

        assert item1_result.success is True
        assert item2_result.success is True

        source_id = item1_result.id
        target_id = item2_result.id

        # Now create a link between them
        link_input = {
            "source_block_id": source_id,
            "target_block_id": target_id,
            "relation": "depends_on",
            "bidirectional": False,
            "priority": 1,
            "metadata": {"test": "true"},
        }

        link_result = await create_block_link(link_input)

        # Check the result
        assert isinstance(link_result, dict)
        assert link_result["success"] is True
        assert "Successfully created link" in link_result["message"]
        assert len(link_result["created_links"]) >= 1


@pytest.mark.asyncio
async def test_create_block_link_tool_bidirectional(temp_memory_bank):
    """Test the CreateBlockLink MCP tool with bidirectional links."""
    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        # Create two work items
        item1_input = {
            "type": "task",
            "title": "Source Task",
            "description": "A source task for linking",
            "acceptance_criteria": ["Should be linkable"],
        }

        item2_input = {
            "type": "task",
            "title": "Target Task",
            "description": "A target task for linking",
            "acceptance_criteria": ["Should be linkable"],
        }

        item1_result = await create_work_item(item1_input)
        item2_result = await create_work_item(item2_input)

        source_id = item1_result.id
        target_id = item2_result.id

        # Create bidirectional link
        link_input = {
            "source_block_id": source_id,
            "target_block_id": target_id,
            "relation": "blocks",  # Use "blocks" which has inverse "depends_on"
            "bidirectional": True,
            "priority": 1,
        }

        link_result = await create_block_link(link_input)

        # Should create two links (forward and inverse)
        assert link_result["success"] is True
        assert "Successfully created bidirectional link" in link_result["message"]
        # Bidirectional should create 2 links
        assert len(link_result["created_links"]) == 2


@pytest.mark.asyncio
async def test_create_block_link_tool_validation_error(temp_memory_bank):
    """Test the CreateBlockLink MCP tool with validation errors."""
    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        # Test with invalid UUID format
        link_input = {
            "source_block_id": "invalid-uuid",
            "target_block_id": str(uuid.uuid4()),
            "relation": "depends_on",
        }

        link_result = await create_block_link(link_input)

        assert link_result["success"] is False
        assert "Failed to create block link" == link_result["message"]


@pytest.mark.asyncio
async def test_create_block_link_tool_nonexistent_blocks(temp_memory_bank):
    """Test the CreateBlockLink MCP tool with non-existent blocks."""
    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        # Test with non-existent block IDs
        link_input = {
            "source_block_id": str(uuid.uuid4()),
            "target_block_id": str(uuid.uuid4()),
            "relation": "depends_on",
        }

        link_result = await create_block_link(link_input)

        assert link_result["success"] is False
        assert "One or both blocks don't exist" in link_result["message"]


@pytest.mark.asyncio
async def test_create_block_link_tool_invalid_relation(temp_memory_bank):
    """Test the CreateBlockLink MCP tool with invalid relation types."""
    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        # Create two work items first
        item1_input = {
            "type": "task",
            "title": "Source Task",
            "description": "A source task for linking",
            "acceptance_criteria": ["Should be linkable"],
        }

        item2_input = {
            "type": "task",
            "title": "Target Task",
            "description": "A target task for linking",
            "acceptance_criteria": ["Should be linkable"],
        }

        item1_result = await create_work_item(item1_input)
        item2_result = await create_work_item(item2_input)

        source_id = item1_result.id
        target_id = item2_result.id

        # Test with invalid relation type
        link_input = {
            "source_block_id": source_id,
            "target_block_id": target_id,
            "relation": "invalid_relation_type",
        }

        link_result = await create_block_link(link_input)

        assert link_result["success"] is False
        assert "Failed to create block link" == link_result["message"]
