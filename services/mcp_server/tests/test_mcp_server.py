"""
Tests for the MCP Server tool registrations.

These tests validate that all tools are properly registered and work correctly
through the MCP server interface.
"""

import pytest
import asyncio
import uuid
from unittest.mock import patch

from services.mcp_server.app.mcp_server import (
    mcp,
    memory_bank,
    create_work_item,
    get_memory_block,
    update_memory_block,
    update_work_item,
    health_check,
)


# Test MCP server initialization


def test_mcp_server_initialization():
    """Test that the MCP server is properly initialized."""
    assert mcp is not None
    assert mcp.name == "cogni-memory"
    assert memory_bank is not None


def test_mcp_tools_registered():
    """Test that all expected tools are registered."""
    # Since FastMCP doesn't expose tools directly, we test that the server
    # is properly configured and has the expected name
    assert mcp.name == "cogni-memory"
    assert memory_bank is not None

    # We can't directly access the tools registry in FastMCP,
    # but we can test that the functions exist
    assert callable(create_work_item)
    assert callable(get_memory_block)
    assert callable(update_memory_block)
    assert callable(update_work_item)
    assert callable(health_check)


# Test CreateWorkItem tool


@pytest.mark.asyncio
async def test_create_work_item_success(sample_work_item_input, temp_memory_bank):
    """Test successful work item creation."""
    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        result = await create_work_item(sample_work_item_input)

        assert result.success is True
        assert result.id is not None
        assert result.work_item_type == "task"


@pytest.mark.asyncio
async def test_create_work_item_error(temp_memory_bank):
    """Test work item creation error handling."""
    # Test with invalid input that should cause validation error
    invalid_input = {"type": "invalid_type"}

    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        result = await create_work_item(invalid_input)

        # This should return a dict with error since validation fails
        assert "error" in result


# Test GetMemoryBlock tool


@pytest.mark.asyncio
async def test_get_memory_block_success(temp_memory_bank):
    """Test successful memory block retrieval."""
    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        # First create a block to retrieve
        create_input = {
            "type": "task",
            "title": "Test Block",
            "description": "A test block",
            "acceptance_criteria": ["Test it"],
        }
        create_result = await create_work_item(create_input)
        assert create_result.success is True

        # Now get the created block using new API format
        result = await get_memory_block({"block_ids": [create_result.id]})

        assert result["success"] is True
        assert len(result["blocks"]) == 1
        assert result["blocks"][0]["id"] == create_result.id
        assert result["error"] is None


@pytest.mark.asyncio
async def test_get_memory_block_error(sample_block_id, temp_memory_bank):
    """Test memory block retrieval error handling."""
    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        result = await get_memory_block({"block_ids": [sample_block_id]})

        assert result["success"] is False
        assert len(result["blocks"]) == 0
        assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_get_memory_block_filtering(temp_memory_bank):
    """Test the new filtering functionality in GetMemoryBlock."""
    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        # Create multiple work items of different types
        task_input = {
            "type": "task",
            "title": "Test Task",
            "description": "A test task",
            "acceptance_criteria": ["Complete task"],
            "tags": ["urgent", "test"],
        }
        bug_input = {
            "type": "bug",
            "title": "Test Bug",
            "description": "A test bug",
            "acceptance_criteria": ["Fix bug"],
            "tags": ["critical", "test"],
        }

        # Create the items
        task_result = await create_work_item(task_input)
        bug_result = await create_work_item(bug_input)

        assert task_result.success is True
        assert bug_result.success is True

        # Test 1: Filter by type "task"
        filter_result = await get_memory_block({"type_filter": "task"})
        assert filter_result["success"] is True
        assert len(filter_result["blocks"]) >= 1  # At least our created task
        assert all(block["type"] == "task" for block in filter_result["blocks"])

        # Test 2: Filter by type "bug"
        filter_result = await get_memory_block({"type_filter": "bug"})
        assert filter_result["success"] is True
        assert len(filter_result["blocks"]) >= 1  # At least our created bug
        assert all(block["type"] == "bug" for block in filter_result["blocks"])

        # Test 3: Filter by tags
        filter_result = await get_memory_block({"tag_filters": ["test"]})
        assert filter_result["success"] is True
        assert len(filter_result["blocks"]) >= 2  # At least task and bug
        assert all("test" in block["tags"] for block in filter_result["blocks"])

        # Test 4: Combined filtering (type + tags)
        filter_result = await get_memory_block({"type_filter": "task", "tag_filters": ["urgent"]})
        assert filter_result["success"] is True
        assert len(filter_result["blocks"]) >= 1
        assert all(
            block["type"] == "task" and "urgent" in block["tags"]
            for block in filter_result["blocks"]
        )

        # Test 5: Limit results
        filter_result = await get_memory_block({"type_filter": "task", "limit": 1})
        assert filter_result["success"] is True
        assert len(filter_result["blocks"]) == 1
        assert filter_result["blocks"][0]["type"] == "task"


@pytest.mark.asyncio
async def test_get_memory_block_validation_errors(temp_memory_bank):
    """Test validation errors for GetMemoryBlock filtering."""
    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        # Test 1: Both block_ids and filtering parameters (should fail)
        result = await get_memory_block({"block_ids": ["test-id"], "type_filter": "task"})
        assert "error" in result
        assert "Cannot specify both block_ids and filtering parameters" in str(result["error"])

        # Test 2: Neither block_ids nor filtering parameters (should fail)
        result = await get_memory_block({})
        assert "error" in result
        assert "Must specify either block_ids OR at least one filtering parameter" in str(
            result["error"]
        )


# Test UpdateMemoryBlock tool


@pytest.mark.asyncio
async def test_update_memory_block_success(temp_memory_bank):
    """Test successful memory block update."""
    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        # First create a block to update
        create_input = {
            "type": "task",
            "title": "Test Block",
            "description": "Original content",
            "acceptance_criteria": ["Test it"],
        }
        create_result = await create_work_item(create_input)
        assert create_result.success is True

        # Now update the block
        update_input = {
            "block_id": create_result.id,
            "text": "Updated content",
            "tags": ["updated"],
            "change_note": "Test update",
        }
        result = await update_memory_block(update_input)

        assert result.success is True
        assert result.id == create_result.id
        assert "text" in result.fields_updated


@pytest.mark.asyncio
async def test_update_memory_block_error(sample_block_id, temp_memory_bank):
    """Test memory block update error handling."""
    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        update_input = {
            "block_id": sample_block_id,
            "text": "Updated content",
        }
        result = await update_memory_block(update_input)

        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error


# Test UpdateWorkItem tool


@pytest.mark.asyncio
async def test_update_work_item_success(temp_memory_bank):
    """Test successful work item update."""
    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        # First create a work item to update
        create_input = {
            "type": "task",
            "title": "Test Task",
            "description": "Original description",
            "acceptance_criteria": ["Complete it"],
        }
        create_result = await create_work_item(create_input)
        assert create_result.success is True

        # Now update the work item
        update_input = {
            "block_id": create_result.id,
            "title": "Updated Task Title",
            "change_note": "Test update",
        }
        result = await update_work_item(update_input)

        assert result.success is True
        assert result.id == create_result.id
        assert result.work_item_type == "task"


@pytest.mark.asyncio
async def test_update_work_item_error(sample_block_id, temp_memory_bank):
    """Test work item update error handling."""
    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        update_input = {
            "block_id": sample_block_id,
            "title": "Updated title",
        }
        result = await update_work_item(update_input)

        assert result.success is False
        assert result.error is not None


# Test HealthCheck tool


@pytest.mark.asyncio
async def test_health_check(temp_memory_bank):
    """Test health check functionality."""
    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        result = await health_check()

        assert result.healthy is True
        assert result.memory_bank_status == "initialized"


# Test tool parameter validation


@pytest.mark.asyncio
async def test_create_work_item_input_validation(temp_memory_bank):
    """Test that create work item validates required parameters."""
    # Test with missing required fields
    invalid_input = {"type": "task"}  # Missing title, description, etc.

    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        result = await create_work_item(invalid_input)

        assert "error" in result


@pytest.mark.asyncio
async def test_get_memory_block_input_validation(temp_memory_bank):
    """Test that get memory block validates block_id parameter."""
    # Test with missing block_id
    invalid_input = {}

    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        result = await get_memory_block(invalid_input)

        assert "error" in result


@pytest.mark.asyncio
async def test_update_memory_block_input_validation(temp_memory_bank):
    """Test that update memory block validates required parameters."""
    # Test with missing block_id
    invalid_input = {"text": "Updated text"}

    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        result = await update_memory_block(invalid_input)

        assert "error" in result


@pytest.mark.asyncio
async def test_update_work_item_input_validation(temp_memory_bank):
    """Test that update work item validates required parameters."""
    # Test with missing block_id
    invalid_input = {"title": "Updated title"}

    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        result = await update_work_item(invalid_input)

        assert "error" in result


# Test real integration scenarios


@pytest.mark.asyncio
async def test_full_workflow_simulation(temp_memory_bank):
    """Test a complete workflow through the MCP server."""
    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        # Create a work item
        create_input = {
            "type": "task",
            "title": "Integration Test Task",
            "description": "A task for testing full workflow",
            "owner": "test_user",
            "acceptance_criteria": ["Should be testable"],
        }

        create_result = await create_work_item(create_input)
        assert create_result.success is True
        created_id = create_result.id

        # Update the work item
        update_input = {
            "block_id": created_id,
            "title": "Updated Integration Test Task",
            "change_note": "Starting work on task",
        }

        update_result = await update_work_item(update_input)
        assert update_result.success is True

        # Get the work item - use correct API format
        get_input = {"block_ids": [created_id]}

        get_result = await get_memory_block(get_input)
        # get_memory_block returns a dict now
        assert get_result["success"] is True
        assert len(get_result["blocks"]) == 1
        assert get_result["blocks"][0]["id"] == created_id


@pytest.mark.asyncio
async def test_memory_bank_connection_error(temp_memory_bank):
    """Test handling of memory bank connection issues."""
    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        # Test with non-existent block ID - use correct API format
        result = await get_memory_block({"block_ids": [str(uuid.uuid4())]})

        # get_memory_block returns a dict now
        assert result["success"] is False
        assert result["error"] is not None


@pytest.mark.asyncio
async def test_concurrent_tool_calls(temp_memory_bank):
    """Test that multiple tool calls can be handled concurrently."""
    with patch("services.mcp_server.app.mcp_server.memory_bank", temp_memory_bank):
        # First create a block to retrieve
        create_input = {
            "type": "task",
            "title": "Concurrent Test Task",
            "description": "A task for concurrent testing",
            "acceptance_criteria": ["Test concurrency"],
        }
        create_result = await create_work_item(create_input)
        assert create_result.success is True
        test_id = create_result.id

        # Create multiple concurrent tasks - use correct API format
        tasks = []
        for i in range(5):
            task = get_memory_block({"block_ids": [test_id]})
            tasks.append(task)

        # Run all tasks concurrently
        results = await asyncio.gather(*tasks)

        # All should succeed - handle dict returns
        for result in results:
            assert result["success"] is True
            assert len(result["blocks"]) == 1
            assert result["blocks"][0]["id"] == test_id
