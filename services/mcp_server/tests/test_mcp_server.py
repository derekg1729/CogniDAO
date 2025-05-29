"""
Tests for the MCP Server tool registrations.

These tests validate that all tools are properly registered and work correctly
through the MCP server interface.
"""

import pytest
import asyncio
import uuid
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.mcp_server import (
    mcp,
    memory_bank,
    create_work_item,
    get_memory_block,
    update_memory_block,
    update_work_item,
    health_check,
)


@pytest.fixture
def sample_block_id():
    """Generate a valid UUID for testing."""
    return str(uuid.uuid4())


@pytest.fixture
def mock_memory_bank():
    """Create a mock memory bank for testing."""
    mock_bank = MagicMock()
    mock_bank.get_memory_block.return_value = None
    mock_bank.update_memory_block.return_value = True
    return mock_bank


@pytest.fixture
def sample_work_item_input():
    """Sample input for creating a work item."""
    return {
        "type": "task",
        "title": "Test Task",
        "description": "A test task for validation",
        "owner": "test_user",
        "acceptance_criteria": ["Criterion 1", "Criterion 2"],
    }


@pytest.fixture
def sample_memory_block_input(sample_block_id):
    """Sample input for updating a memory block."""
    return {
        "block_id": sample_block_id,
        "text": "Updated text content",
        "tags": ["test", "updated"],
        "change_note": "Test update",
    }


@pytest.fixture
def sample_work_item_update_input(sample_block_id):
    """Sample input for updating a work item."""
    return {
        "block_id": sample_block_id,
        "title": "Updated Task Title",
        "status": "in_progress",
        "change_note": "Updated task status",
    }


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
async def test_create_work_item_success(sample_work_item_input):
    """Test successful work item creation."""
    with patch("app.mcp_server.create_work_item_tool") as mock_tool:
        mock_tool.return_value = {
            "success": True,
            "id": str(uuid.uuid4()),
            "type": "task",
            "timestamp": datetime.now().isoformat(),
        }

        result = await create_work_item(sample_work_item_input)

        assert result["success"] is True
        assert "id" in result
        mock_tool.assert_called_once()


@pytest.mark.asyncio
async def test_create_work_item_error(sample_work_item_input):
    """Test work item creation error handling."""
    with patch("app.mcp_server.create_work_item_tool") as mock_tool:
        mock_tool.side_effect = Exception("Database error")

        result = await create_work_item(sample_work_item_input)

        assert "error" in result
        assert "Database error" in result["error"]


# Test GetMemoryBlock tool


@pytest.mark.asyncio
async def test_get_memory_block_success(sample_block_id):
    """Test successful memory block retrieval."""
    with patch("app.mcp_server.get_memory_block_tool") as mock_tool:
        mock_tool.return_value = {
            "success": True,
            "block": {
                "id": sample_block_id,
                "type": "task",
                "text": "Sample text",
            },
        }

        result = await get_memory_block({"block_id": sample_block_id})

        assert result["success"] is True
        assert "block" in result
        mock_tool.assert_called_once()


@pytest.mark.asyncio
async def test_get_memory_block_error(sample_block_id):
    """Test memory block retrieval error handling."""
    with patch("app.mcp_server.get_memory_block_tool") as mock_tool:
        mock_tool.side_effect = Exception("Block not found")

        result = await get_memory_block({"block_id": sample_block_id})

        assert "error" in result
        assert "Block not found" in result["error"]


# Test UpdateMemoryBlock tool


@pytest.mark.asyncio
async def test_update_memory_block_success(sample_memory_block_input):
    """Test successful memory block update."""
    with patch("app.mcp_server.update_memory_block_tool") as mock_tool:
        mock_tool.return_value = {
            "success": True,
            "id": sample_memory_block_input["block_id"],
            "fields_updated": ["text", "tags"],
            "timestamp": datetime.now().isoformat(),
        }

        result = await update_memory_block(sample_memory_block_input)

        assert result["success"] is True
        assert "fields_updated" in result
        mock_tool.assert_called_once()


@pytest.mark.asyncio
async def test_update_memory_block_error(sample_memory_block_input):
    """Test memory block update error handling."""
    with patch("app.mcp_server.update_memory_block_tool") as mock_tool:
        mock_tool.side_effect = Exception("Update failed")

        result = await update_memory_block(sample_memory_block_input)

        assert "error" in result
        assert "Update failed" in result["error"]


# Test UpdateWorkItem tool


@pytest.mark.asyncio
async def test_update_work_item_success(sample_work_item_update_input):
    """Test successful work item update."""
    with patch("app.mcp_server.update_work_item_tool") as mock_tool:
        mock_tool.return_value = {
            "success": True,
            "id": sample_work_item_update_input["block_id"],
            "work_item_type": "task",
            "fields_updated": ["metadata"],
            "timestamp": datetime.now().isoformat(),
        }

        result = await update_work_item(sample_work_item_update_input)

        assert result["success"] is True
        assert "work_item_type" in result
        mock_tool.assert_called_once()


@pytest.mark.asyncio
async def test_update_work_item_error(sample_work_item_update_input):
    """Test work item update error handling."""
    with patch("app.mcp_server.update_work_item_tool") as mock_tool:
        mock_tool.side_effect = Exception("Update failed")

        result = await update_work_item(sample_work_item_update_input)

        assert "error" in result
        assert "Update failed" in result["error"]


# Test HealthCheck tool


@pytest.mark.asyncio
async def test_health_check():
    """Test health check functionality."""
    result = await health_check()

    assert result.healthy is True
    assert result.memory_bank_status == "initialized"


# Test tool parameter validation


@pytest.mark.asyncio
async def test_create_work_item_input_validation():
    """Test that create work item validates required parameters."""
    # Test with missing required fields
    invalid_input = {"type": "task"}  # Missing title, description, etc.

    with patch("app.mcp_server.create_work_item_tool") as mock_tool:
        mock_tool.side_effect = ValueError("Missing required field: title")

        result = await create_work_item(invalid_input)

        assert "error" in result


@pytest.mark.asyncio
async def test_get_memory_block_input_validation():
    """Test that get memory block validates block_id parameter."""
    # Test with missing block_id
    invalid_input = {}

    with patch("app.mcp_server.get_memory_block_tool") as mock_tool:
        mock_tool.side_effect = ValueError("Missing required field: block_id")

        result = await get_memory_block(invalid_input)

        assert "error" in result


@pytest.mark.asyncio
async def test_update_memory_block_input_validation():
    """Test that update memory block validates required parameters."""
    # Test with missing block_id
    invalid_input = {"text": "Updated text"}

    with patch("app.mcp_server.update_memory_block_tool") as mock_tool:
        mock_tool.side_effect = ValueError("Missing required field: block_id")

        result = await update_memory_block(invalid_input)

        assert "error" in result


@pytest.mark.asyncio
async def test_update_work_item_input_validation():
    """Test that update work item validates required parameters."""
    # Test with missing block_id
    invalid_input = {"title": "Updated title"}

    with patch("app.mcp_server.update_work_item_tool") as mock_tool:
        mock_tool.side_effect = ValueError("Missing required field: block_id")

        result = await update_work_item(invalid_input)

        assert "error" in result


# Test real integration scenarios


@pytest.mark.asyncio
async def test_full_workflow_simulation():
    """Test a complete workflow through the MCP server."""
    # Create a work item
    create_input = {
        "type": "task",
        "title": "Integration Test Task",
        "description": "A task for testing full workflow",
        "owner": "test_user",
        "acceptance_criteria": ["Should be testable"],
    }

    with patch("app.mcp_server.create_work_item_tool") as mock_create:
        test_id = str(uuid.uuid4())
        mock_create.return_value = {
            "success": True,
            "id": test_id,
            "type": "task",
            "timestamp": datetime.now().isoformat(),
        }

        create_result = await create_work_item(create_input)
        assert create_result["success"] is True
        created_id = create_result["id"]

    # Update the work item
    update_input = {
        "block_id": created_id,
        "status": "in_progress",
        "change_note": "Starting work on task",
    }

    with patch("app.mcp_server.update_work_item_tool") as mock_update:
        mock_update.return_value = {
            "success": True,
            "id": created_id,
            "work_item_type": "task",
            "fields_updated": ["metadata"],
            "timestamp": datetime.now().isoformat(),
        }

        update_result = await update_work_item(update_input)
        assert update_result["success"] is True

    # Get the work item
    get_input = {"block_id": created_id}

    with patch("app.mcp_server.get_memory_block_tool") as mock_get:
        mock_get.return_value = {
            "success": True,
            "block": {
                "id": created_id,
                "type": "task",
                "metadata": {"status": "in_progress"},
            },
        }

        get_result = await get_memory_block(get_input)
        assert get_result["success"] is True
        assert get_result["block"]["id"] == created_id


# Test error scenarios with real memory bank issues


@pytest.mark.asyncio
async def test_memory_bank_connection_error():
    """Test handling of memory bank connection issues."""
    # Simulate memory bank being None or connection error
    with patch("app.mcp_server.memory_bank", None):
        with patch("app.mcp_server.get_memory_block_tool") as mock_tool:
            mock_tool.side_effect = AttributeError(
                "'NoneType' object has no attribute 'get_memory_block'"
            )

            result = await get_memory_block({"block_id": str(uuid.uuid4())})

            assert "error" in result


@pytest.mark.asyncio
async def test_concurrent_tool_calls():
    """Test that multiple tool calls can be handled concurrently."""
    test_id = str(uuid.uuid4())

    # Create multiple concurrent tasks
    tasks = []

    with patch("app.mcp_server.get_memory_block_tool") as mock_tool:
        mock_tool.return_value = {
            "success": True,
            "block": {"id": test_id, "type": "task"},
        }

        for i in range(5):
            task = get_memory_block({"block_id": test_id})
            tasks.append(task)

        # Run all tasks concurrently
        results = await asyncio.gather(*tasks)

        # All should succeed
        for result in results:
            assert result["success"] is True
            assert result["block"]["id"] == test_id

        # Should have been called 5 times
        assert mock_tool.call_count == 5
