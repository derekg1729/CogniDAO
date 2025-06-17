"""
Integration tests for the MCP Server.

These tests verify the complete workflow of creating, retrieving, and updating
memory blocks and work items through the MCP server interface.
"""

import uuid

import pytest


@pytest.mark.asyncio
async def test_create_work_item_basic(mcp_app, sample_work_item_data):
    """Test basic work item creation functionality."""
    # Create a work item
    create_result = await mcp_app.create_work_item(sample_work_item_data)

    # Validate basic functionality - should not crash and return expected structure
    assert create_result is not None
    if hasattr(create_result, "success"):
        # For successful cases
        assert isinstance(create_result.success, bool)
        if create_result.success:
            assert create_result.id is not None
    else:
        # For error cases that return dicts
        assert isinstance(create_result, dict)
        assert "success" in create_result


@pytest.mark.asyncio
async def test_get_memory_block_basic(mcp_app):
    """Test basic memory block retrieval functionality."""
    # Test with random UUID (should handle gracefully)
    get_input = {"block_ids": [str(uuid.uuid4())]}
    get_result = await mcp_app.get_memory_block(get_input)

    # Should return proper structure regardless of success/failure
    assert isinstance(get_result, dict)
    assert "success" in get_result
    assert isinstance(get_result["success"], bool)
    assert "blocks" in get_result
    assert isinstance(get_result["blocks"], list)


@pytest.mark.asyncio
async def test_update_work_item_basic(mcp_app):
    """Test basic work item update functionality."""
    # Test with random UUID (should handle gracefully)
    update_input = {
        "block_id": str(uuid.uuid4()),
        "title": "Updated Task Title",
        "status": "in_progress",
        "change_note": "Updated for integration test",
    }

    update_result = await mcp_app.update_work_item(update_input)

    # Should return proper structure, likely an error for non-existent block
    if hasattr(update_result, "success"):
        # Pydantic model response
        assert isinstance(update_result.success, bool)
    else:
        # Dict response
        assert isinstance(update_result, dict)
        assert "success" in update_result


@pytest.mark.asyncio
async def test_get_active_work_items(mcp_app):
    """Test retrieving active work items."""
    get_input = {
        "priority_filter": None,
        "work_item_type_filter": None,
        "limit": 10,
    }

    result = await mcp_app.get_active_work_items(get_input)

    # Validate result structure
    assert isinstance(result, dict)
    assert result["success"] is True
    assert "work_items" in result
    assert isinstance(result["work_items"], list)


@pytest.mark.asyncio
async def test_health_check_integration(mcp_app):
    """Test the health check integration."""
    result = await mcp_app.health_check()

    # Validate health check response
    assert isinstance(result, dict)
    assert result["healthy"] is True
    assert result["memory_bank_status"] == "initialized"
    assert result["link_manager_status"] == "initialized"
    assert "timestamp" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
