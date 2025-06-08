"""
Test the CreateBlockLink MCP tool integration.

These tests ensure the CreateBlockLink tool works correctly through the MCP server
and continues to function properly as the codebase evolves.
"""

import pytest
import uuid


@pytest.mark.asyncio
async def test_create_block_link_tool_basic_call(mcp_app):
    """Test that CreateBlockLink MCP tool can be called without crashing."""
    # Test with minimal valid input - this should not crash
    link_input = {
        "source_block_id": str(uuid.uuid4()),
        "target_block_id": str(uuid.uuid4()),
        "relation": "depends_on",
        "bidirectional": False,
        "priority": 1,
    }

    link_result = await mcp_app.create_block_link(link_input)

    # Basic schema validation - should be a dict with expected keys
    assert isinstance(link_result, dict)
    assert "success" in link_result
    assert isinstance(link_result["success"], bool)
    assert "message" in link_result
    # Note: timestamp may or may not be present depending on success/failure path


@pytest.mark.asyncio
async def test_create_block_link_tool_invalid_uuid(mcp_app):
    """Test the CreateBlockLink MCP tool with invalid UUID format."""
    # Test with invalid UUID format
    link_input = {
        "source_block_id": "invalid-uuid",
        "target_block_id": str(uuid.uuid4()),
        "relation": "depends_on",
    }

    link_result = await mcp_app.create_block_link(link_input)

    # Should handle the error gracefully
    assert isinstance(link_result, dict)
    assert link_result["success"] is False
    assert "message" in link_result
    # Error responses include error_details instead of timestamp
    assert "error_details" in link_result or "timestamp" in link_result


@pytest.mark.asyncio
async def test_create_block_link_tool_invalid_relation(mcp_app):
    """Test the CreateBlockLink MCP tool with invalid relation types."""
    # Test with invalid relation type
    link_input = {
        "source_block_id": str(uuid.uuid4()),
        "target_block_id": str(uuid.uuid4()),
        "relation": "invalid_relation_type",
    }

    link_result = await mcp_app.create_block_link(link_input)

    # Should handle the error gracefully
    assert isinstance(link_result, dict)
    assert link_result["success"] is False
    assert "message" in link_result
    # Error responses include error_details instead of timestamp
    assert "error_details" in link_result or "timestamp" in link_result
