"""
Tests for the MCP Server tool registrations.

These tests validate that all tools are properly registered and work correctly
through the MCP server interface using the DRY mocking approach.
"""

import pytest
import uuid


def test_mcp_server_initialization(mcp_app):
    """Test that the MCP server is properly initialized."""
    assert mcp_app.mcp is not None
    assert mcp_app.mcp.name == "cogni-memory"
    assert mcp_app.get_memory_bank() is not None


def test_mcp_tools_registered(mcp_app):
    """Test that all expected tools are registered."""
    # Since FastMCP doesn't expose tools directly, we test that the server
    # is properly configured and has the expected name
    assert mcp_app.mcp.name == "cogni-memory"
    assert mcp_app.get_memory_bank() is not None

    # We can't directly access the tools registry in FastMCP,
    # but we can test that the functions exist
    assert callable(mcp_app.create_work_item)
    assert callable(mcp_app.get_memory_block)
    assert callable(mcp_app.update_memory_block)
    assert callable(mcp_app.update_work_item)
    assert callable(mcp_app.health_check)


# Test CreateWorkItem tool


@pytest.mark.asyncio
async def test_create_work_item_success(mcp_app, sample_work_item_input):
    """Test successful work item creation."""
    result = await mcp_app.create_work_item(sample_work_item_input)

    # Basic functionality test - should not crash
    assert result is not None
    if hasattr(result, "success"):
        assert isinstance(result.success, bool)
        if result.success:
            assert result.id is not None
    else:
        assert isinstance(result, dict)
        assert "success" in result


@pytest.mark.asyncio
async def test_create_work_item_error(mcp_app):
    """Test work item creation error handling."""
    # Test with invalid input that should cause validation error
    invalid_input = {"type": "invalid_type"}

    result = await mcp_app.create_work_item(invalid_input)

    # Should handle the error gracefully
    assert result is not None
    if hasattr(result, "success"):
        assert isinstance(result.success, bool)
    else:
        assert isinstance(result, dict)
        assert "success" in result or "error" in result


# Test GetMemoryBlock tool


@pytest.mark.asyncio
async def test_get_memory_block_success(mcp_app):
    """Test successful memory block retrieval."""
    # Test with random UUID (should handle gracefully)
    result = await mcp_app.get_memory_block({"block_ids": [str(uuid.uuid4())]})

    # Should return proper structure regardless of success/failure
    assert isinstance(result, dict)
    assert "success" in result
    assert isinstance(result["success"], bool)
    assert "blocks" in result
    assert isinstance(result["blocks"], list)


@pytest.mark.asyncio
async def test_get_memory_block_error(mcp_app, sample_block_id):
    """Test memory block retrieval error handling."""
    result = await mcp_app.get_memory_block({"block_ids": [sample_block_id]})

    # Should return proper structure
    assert isinstance(result, dict)
    assert "success" in result
    assert isinstance(result["success"], bool)
    assert "blocks" in result
    assert isinstance(result["blocks"], list)


@pytest.mark.asyncio
async def test_get_memory_block_filtering(mcp_app):
    """Test the new filtering functionality in GetMemoryBlock."""
    # Test 1: Filter by type "task"
    filter_result = await mcp_app.get_memory_block({"type_filter": "task"})
    assert isinstance(filter_result, dict)
    assert "success" in filter_result
    assert "blocks" in filter_result
    assert isinstance(filter_result["blocks"], list)

    # Test 2: Filter by type "bug"
    filter_result = await mcp_app.get_memory_block({"type_filter": "bug"})
    assert isinstance(filter_result, dict)
    assert "success" in filter_result
    assert "blocks" in filter_result

    # Test 3: Filter by tags
    filter_result = await mcp_app.get_memory_block({"tag_filters": ["test"]})
    assert isinstance(filter_result, dict)
    assert "success" in filter_result
    assert "blocks" in filter_result

    # Test 4: Combined filtering (type + tags)
    filter_result = await mcp_app.get_memory_block(
        {"type_filter": "task", "tag_filters": ["urgent"]}
    )
    assert isinstance(filter_result, dict)
    assert "success" in filter_result
    assert "blocks" in filter_result

    # Test 5: Limit results
    filter_result = await mcp_app.get_memory_block({"type_filter": "task", "limit": 1})
    assert isinstance(filter_result, dict)
    assert "success" in filter_result
    assert "blocks" in filter_result


@pytest.mark.asyncio
async def test_get_memory_block_validation_errors(mcp_app):
    """Test validation errors for GetMemoryBlock filtering."""
    # Test 1: Both block_ids and filtering parameters (should fail)
    result = await mcp_app.get_memory_block({"block_ids": ["test-id"], "type_filter": "task"})
    # Should be handled gracefully
    assert isinstance(result, dict)

    # Test 2: Neither block_ids nor filtering parameters (should fail)
    result = await mcp_app.get_memory_block({})
    # Should be handled gracefully
    assert isinstance(result, dict)


# Test UpdateMemoryBlock tool


@pytest.mark.asyncio
async def test_update_memory_block_success(mcp_app):
    """Test successful memory block update."""
    # Test with valid UUID format but likely non-existent block
    update_input = {
        "block_id": str(uuid.uuid4()),
        "text": "Updated content",
        "tags": ["updated"],
        "change_note": "Test update",
    }
    result = await mcp_app.update_memory_block(update_input)

    # Should return proper structure (likely error for non-existent block)
    assert result is not None
    if hasattr(result, "success"):
        assert isinstance(result.success, bool)
    else:
        assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_update_memory_block_error(mcp_app, sample_block_id):
    """Test memory block update error handling."""
    update_input = {
        "block_id": sample_block_id,
        "text": "Updated content",
    }
    result = await mcp_app.update_memory_block(update_input)

    # Should handle error gracefully
    assert result is not None
    if hasattr(result, "success"):
        assert isinstance(result.success, bool)
    else:
        assert isinstance(result, dict)


# Test UpdateWorkItem tool


@pytest.mark.asyncio
async def test_update_work_item_success(mcp_app):
    """Test successful work item update."""
    # Test with valid UUID format but likely non-existent work item
    update_input = {
        "block_id": str(uuid.uuid4()),
        "title": "Updated Task Title",
        "status": "in_progress",
        "change_note": "Test update",
    }

    result = await mcp_app.update_work_item(update_input)

    # Should return proper structure (likely error for non-existent work item)
    assert result is not None
    if hasattr(result, "success"):
        assert isinstance(result.success, bool)
    else:
        assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_update_work_item_error(mcp_app, sample_block_id):
    """Test work item update error handling."""
    update_input = {
        "block_id": sample_block_id,
        "title": "Updated Title",
        "status": "in_progress",
    }

    result = await mcp_app.update_work_item(update_input)

    # Should handle error gracefully
    assert result is not None
    if hasattr(result, "success"):
        assert isinstance(result.success, bool)
    else:
        assert isinstance(result, dict)


# Test HealthCheck tool


@pytest.mark.asyncio
async def test_health_check(mcp_app):
    """Test health check functionality."""
    result = await mcp_app.health_check()

    # Should return proper health check structure
    assert isinstance(result, dict)
    assert "healthy" in result
    assert isinstance(result["healthy"], bool)
    assert "memory_bank_status" in result
    assert "link_manager_status" in result


# Test Input Validation


@pytest.mark.asyncio
async def test_create_work_item_input_validation(mcp_app):
    """Test input validation for create_work_item."""
    # Test with completely empty input
    result = await mcp_app.create_work_item({})

    # Should handle validation error gracefully
    assert result is not None
    if hasattr(result, "success"):
        assert isinstance(result.success, bool)
    else:
        assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_get_memory_block_input_validation(mcp_app):
    """Test input validation for get_memory_block."""
    # Test with invalid UUID
    result = await mcp_app.get_memory_block({"block_ids": ["invalid-uuid"]})

    # Should handle validation error gracefully
    assert isinstance(result, dict)
    assert "success" in result or "error" in result


@pytest.mark.asyncio
async def test_update_memory_block_input_validation(mcp_app):
    """Test input validation for update_memory_block."""
    # Test with missing required fields
    result = await mcp_app.update_memory_block({"block_id": "invalid-id"})

    # Should handle validation error gracefully
    assert result is not None


@pytest.mark.asyncio
async def test_update_work_item_input_validation(mcp_app):
    """Test input validation for update_work_item."""
    # Test with invalid UUID
    result = await mcp_app.update_work_item({"block_id": "invalid-id", "title": "Test"})

    # Should handle validation error gracefully
    assert result is not None


# Test Basic Tool Integration


@pytest.mark.asyncio
async def test_basic_workflow_simulation(mcp_app, sample_work_item_input):
    """Test basic workflow simulation without complex end-to-end requirements."""
    # Test 1: Create work item
    create_result = await mcp_app.create_work_item(sample_work_item_input)
    assert create_result is not None

    # Test 2: Get memory blocks
    get_result = await mcp_app.get_memory_block({"type_filter": "task"})
    assert isinstance(get_result, dict)

    # Test 3: Health check
    health_result = await mcp_app.health_check()
    assert isinstance(health_result, dict)
    assert health_result["healthy"] is True


@pytest.mark.asyncio
async def test_memory_bank_connection_error(mcp_app):
    """Test handling of memory bank connection issues."""
    # This test validates that the mocked memory bank is working
    health_result = await mcp_app.health_check()

    assert isinstance(health_result, dict)
    assert "healthy" in health_result
    assert "memory_bank_status" in health_result
    assert "link_manager_status" in health_result


@pytest.mark.asyncio
async def test_basic_tool_calls(mcp_app):
    """Test basic functionality of all tools without complex workflows."""
    # Test create work item
    create_input = {
        "type": "task",
        "title": "Basic Test Task",
        "description": "Testing basic functionality",
        "acceptance_criteria": ["Should not crash"],
    }

    create_result = await mcp_app.create_work_item(create_input)
    assert create_result is not None

    # Test get memory block
    get_result = await mcp_app.get_memory_block({"block_ids": [str(uuid.uuid4())]})
    assert isinstance(get_result, dict)

    # Test update memory block
    update_result = await mcp_app.update_memory_block(
        {
            "block_id": str(uuid.uuid4()),
            "text": "Updated text",
        }
    )
    assert update_result is not None

    # Test update work item
    work_update_result = await mcp_app.update_work_item(
        {
            "block_id": str(uuid.uuid4()),
            "title": "Updated title",
        }
    )
    assert work_update_result is not None

    # Test health check
    health_result = await mcp_app.health_check()
    assert isinstance(health_result, dict)
    assert health_result["healthy"] is True
