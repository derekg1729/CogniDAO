"""
Integration tests for MCP server with SQLLinkManager.

These tests ensure that the MCP server correctly uses SQLLinkManager
and that link operations persist to the actual database.

SKIPPED: All tests in this file are skipped to prevent production database contamination
as referenced in bug 84c5996e-8fe5-49c1-90e5-36f1cf8555ad.
"""

import pytest
import uuid

pytestmark = pytest.mark.skip(
    reason="CRITICAL: MCP integration tests contaminate production namespace - bug 84c5996e-8fe5-49c1-90e5-36f1cf8555ad"
)


@pytest.mark.asyncio
async def test_basic_link_manager_functionality(mcp_app):
    """Test basic link manager functionality through MCP server."""
    # Test health check to ensure link manager is working
    result = await mcp_app.health_check()

    assert isinstance(result, dict)
    assert result["healthy"] is True
    assert result["link_manager_status"] == "initialized"


@pytest.mark.asyncio
async def test_get_memory_links_basic(mcp_app):
    """Test basic memory links retrieval functionality."""
    # Test basic get_memory_links functionality
    get_input = {
        "relation_filter": None,
        "limit": 10,
    }

    result = await mcp_app.get_memory_links(get_input)

    # Should return proper structure
    assert isinstance(result, dict)
    assert result["success"] is True
    assert "links" in result
    assert isinstance(result["links"], list)


@pytest.mark.asyncio
async def test_create_block_link_basic_functionality(mcp_app):
    """Test basic create block link functionality."""
    # Test with valid input structure
    link_input = {
        "source_block_id": str(uuid.uuid4()),
        "target_block_id": str(uuid.uuid4()),
        "relation": "depends_on",
        "bidirectional": False,
        "priority": 1,
    }

    link_result = await mcp_app.create_block_link(link_input)

    # Should return proper structure (success or error)
    assert isinstance(link_result, dict)
    assert "success" in link_result
    assert isinstance(link_result["success"], bool)
    assert "message" in link_result


@pytest.mark.asyncio
async def test_create_work_item_then_link_basic(mcp_app, sample_work_item_data):
    """Test creating work items and basic link operations."""
    # Create a work item first
    create_result = await mcp_app.create_work_item(sample_work_item_data)

    # Basic validation - should not crash
    assert create_result is not None
    if hasattr(create_result, "success"):
        assert isinstance(create_result.success, bool)
    else:
        assert isinstance(create_result, dict)
        assert "success" in create_result

    # Test get_memory_links after potential creation
    get_links_input = {"relation_filter": None, "limit": 5}
    links_result = await mcp_app.get_memory_links(get_links_input)

    assert isinstance(links_result, dict)
    assert links_result["success"] is True
    assert "links" in links_result


@pytest.mark.asyncio
async def test_error_handling_invalid_link_data(mcp_app):
    """Test error handling with invalid link data."""
    # Test with invalid UUID
    invalid_link_input = {
        "source_block_id": "invalid-uuid",
        "target_block_id": str(uuid.uuid4()),
        "relation": "depends_on",
    }

    result = await mcp_app.create_block_link(invalid_link_input)

    # Should handle error gracefully
    assert isinstance(result, dict)
    assert result["success"] is False
    assert "message" in result
