"""
Proof-of-Concept DRY Test for MCP Server functionality.

This test demonstrates proper mocking to test MCP server tools without requiring
real database connections or persistence layers.

Key approach:
- Mock mysql.connector.connect to avoid database connection during import
- Mock StructuredMemoryBank and SQLLinkManager to avoid real persistence
- Use importlib.reload to ensure mocks take effect before module import
- Test actual MCP tool functions directly using @pytest.mark.asyncio
- Leverage existing conftest.py fixtures for consistency
"""

import pytest
import importlib
from unittest.mock import MagicMock


# 1) Fixture: mock out mysql.connector.connect so we never hit a real Dolt/MySQL server
@pytest.fixture(autouse=True)
def mock_mysql_connect(monkeypatch):
    """
    Replace mysql.connector.connect with a dummy connection whose cursor.execute("SELECT 1")
    returns a single row, so the server's startup DB-check always "succeeds" without a real DB.
    """
    dummy_conn = MagicMock()
    dummy_cursor = MagicMock()
    dummy_cursor.execute.return_value = None
    dummy_cursor.fetchone.return_value = (1,)
    dummy_conn.cursor.return_value = dummy_cursor

    # Patch the connect() call
    monkeypatch.setattr("mysql.connector.connect", lambda **kwargs: dummy_conn)
    yield


# 2) Fixture: mock out StructuredMemoryBank (and SQLLinkManager) so no real Chroma or Dolt is used
@pytest.fixture(autouse=True)
def mock_structured_memory_bank(monkeypatch):
    """
    Replace StructuredMemoryBank and SQLLinkManager with simple MagicMocks.
    This ensures all MCP tools that expect memory_bank or link_manager still work,
    but nothing is persisted or queried for real.
    """
    dummy_bank = MagicMock()
    dummy_link_mgr = MagicMock()

    # Configure dolt_writer mock with active_branch property
    dummy_writer = MagicMock()
    dummy_writer.active_branch = "main"
    dummy_bank.dolt_writer = dummy_writer

    # Configure create_memory_block to return tuple (success, error_message)
    dummy_bank.create_memory_block.return_value = (True, None)

    # Patch the constructors in your server module's imports
    monkeypatch.setattr(
        "infra_core.memory_system.structured_memory_bank.StructuredMemoryBank",
        lambda *args, **kwargs: dummy_bank,
    )
    monkeypatch.setattr(
        "infra_core.memory_system.sql_link_manager.SQLLinkManager",
        lambda *args, **kwargs: dummy_link_mgr,
    )
    yield


# 3) Fixture to reload the server module under test, so the above patches take effect before import
@pytest.fixture
def mcp_app():
    """
    Import (and reload) the MCP server so that our mocks apply at module-load time.
    """
    import services.mcp_server.app.mcp_server as app_module

    return importlib.reload(app_module)


# 4) Test the HealthCheck tool—this one doesn't need any real DB or memory, just returns healthy=True.
@pytest.mark.asyncio
async def test_health_check_tool(mcp_app):
    """Test that HealthCheck tool works without real database and returns complete schema."""
    result = await mcp_app.health_check()

    # Validate return type and required keys
    assert isinstance(result, dict), "HealthCheck should return a dict"
    assert result["healthy"] is True, "HealthCheck should report healthy=True"
    assert result["memory_bank_status"] == "initialized", "Memory bank should be initialized"
    assert result["link_manager_status"] == "initialized", "Link manager should be initialized"
    assert "timestamp" in result, "Result should contain timestamp"


# 5) Parametrized test for basic read-only tools, verifying complete response schema
@pytest.mark.xfail(
    reason="Legacy implementation now requires MCP integration test - manual tool functions removed in Phase 2A"
)
@pytest.mark.parametrize(
    "tool_name,input_payload,expected_key",
    [
        ("get_memory_block", {"block_ids": ["dummy_id"]}, "blocks"),
        (
            "get_memory_links",
            {"relation_filter": None, "limit": 10},
            "links",
        ),
        (
            "get_active_work_items",
            {
                "priority_filter": None,
                "work_item_type_filter": None,
                "limit": 10,
            },
            "work_items",
        ),
    ],
)
@pytest.mark.asyncio
async def test_basic_tool_responses(mcp_app, tool_name, input_payload, expected_key):
    """
    Call each tool's async function directly and ensure the returned dict
    has the expected complete response schema.
    """
    # Get the async function from the reloaded module
    tool_func = getattr(mcp_app, tool_name)

    # Call the async function
    result = await tool_func(input_payload)

    # Validate response structure
    assert isinstance(result, dict), f"{tool_name} should return a dict"
    assert expected_key in result, f"{tool_name} result should contain '{expected_key}' key"
    assert isinstance(result[expected_key], list), f"{expected_key} should be a list"
    assert "success" in result, f"{tool_name} result should contain 'success' key"
    assert isinstance(result["success"], bool), "success should be a boolean"
    assert "error" in result, f"{tool_name} result should contain 'error' key"
    assert "timestamp" in result, f"{tool_name} result should contain 'timestamp' key"


# 6) Test create operation with proper input validation using conftest fixtures
@pytest.mark.xfail(
    reason="Legacy implementation now requires MCP integration test - manual tool functions removed in Phase 2A"
)
@pytest.mark.asyncio
async def test_create_work_item_with_conftest_fixture(mcp_app, sample_work_item_input):
    """Test CreateWorkItem tool using existing conftest.py fixture for input validation."""
    result = await mcp_app.create_work_item(sample_work_item_input)

    # Note: create_work_item returns a Pydantic model, not a dict like other tools
    # This appears to be an inconsistency in the MCP server implementation

    # Validate response structure - it should be a CreateWorkItemOutput model
    assert result is not None, "Result should not be None"

    # Handle both response formats (Pydantic model or dict)
    if hasattr(result, "success"):
        assert result.success is True, "CreateWorkItem should report success=True"
        assert hasattr(result, "id"), "Result should have an id attribute"
        assert hasattr(result, "work_item_type"), "Result should have work_item_type attribute"
        assert result.work_item_type == "task", "Work item type should match input"

    # If it's a dict response, check dict format
    elif isinstance(result, dict):
        if "error" in result and result["error"] is not None:
            pytest.fail(f"CreateWorkItem returned error: {result['error']}")
        else:
            assert result.get("success") is True, "CreateWorkItem should report success=True"
            assert result.get("id") is not None, "Result should have an id"
            assert result.get("work_item_type") == "task", "Work item type should match input"

    else:
        pytest.fail(f"CreateWorkItem returned unexpected type: {type(result)}")
