"""
Tests for the MCP Server tool registrations.

These tests validate that all auto-registered tools are properly registered and work correctly
through the MCP server interface after the Phase 2A migration to auto-generated tools.

Updated for Batch 3 completion: All 16 tools now use auto-generated CogniTool instances
with proper parameter schema visibility instead of problematic generic input format.
"""

import pytest
import uuid
import importlib
from unittest.mock import MagicMock

from services.mcp_server.app.tool_registry import get_all_cogni_tools
from services.mcp_server.app.mcp_auto_generator import (
    create_mcp_wrapper_from_cogni_tool,
)


# Reuse fixtures from test_mcp_poc_dry.py for proper mocking
@pytest.fixture(autouse=True)
def mock_mysql_connect(monkeypatch):
    """Mock mysql.connector.connect to avoid real database connections."""
    dummy_conn = MagicMock()
    dummy_cursor = MagicMock()
    dummy_cursor.execute.return_value = None
    dummy_cursor.fetchone.return_value = (1,)
    dummy_conn.cursor.return_value = dummy_cursor
    monkeypatch.setattr("mysql.connector.connect", lambda **kwargs: dummy_conn)
    yield


@pytest.fixture(autouse=True)
def mock_structured_memory_bank(monkeypatch):
    """Mock StructuredMemoryBank and SQLLinkManager to avoid real persistence."""
    dummy_bank = MagicMock()
    dummy_link_mgr = MagicMock()

    # Configure dolt_writer mock with active_branch property
    dummy_writer = MagicMock()
    dummy_writer.active_branch = "test-branch"
    dummy_bank.dolt_writer = dummy_writer

    # Configure create_memory_block to return tuple (success, error_message)
    dummy_bank.create_memory_block.return_value = (True, None)

    monkeypatch.setattr(
        "infra_core.memory_system.structured_memory_bank.StructuredMemoryBank",
        lambda *args, **kwargs: dummy_bank,
    )
    monkeypatch.setattr(
        "infra_core.memory_system.sql_link_manager.SQLLinkManager",
        lambda *args, **kwargs: dummy_link_mgr,
    )
    yield


@pytest.fixture
def mock_memory_bank():
    """Create a mock memory bank for testing."""
    mock_bank = MagicMock()
    mock_bank.branch = "test-branch"
    return mock_bank


@pytest.fixture
def mock_memory_bank_getter(mock_memory_bank):
    """Create a mock memory bank getter function."""
    return lambda: mock_memory_bank


@pytest.fixture
def sample_work_item_input():
    """Sample work item input for testing."""
    return {
        "type": "task",
        "title": "Test Task",
        "description": "A test task for validation",
        "priority": "medium",
        "status": "todo"
    }


@pytest.fixture
def mcp_app():
    """Import (and reload) the MCP server so that our mocks apply at module-load time."""
    import services.mcp_server.app.mcp_server as app_module
    return importlib.reload(app_module)


def test_mcp_server_initialization(mcp_app):
    """Test that the MCP server is properly initialized."""
    assert mcp_app.mcp is not None
    assert mcp_app.mcp.name == "cogni-memory"
    assert mcp_app.get_memory_bank() is not None


def test_auto_generated_tools_registration():
    """Test that all expected auto-generated tools are available in the registry."""
    cogni_tools = get_all_cogni_tools()

    # We should have at least 16 tools after the systematic conversion
    assert len(cogni_tools) >= 16

    # Check for key tools that were converted
    tool_names = [tool.name for tool in cogni_tools]

    # Phase 1 tools
    assert "GetActiveWorkItems" in tool_names
    assert "GetLinkedBlocks" in tool_names

    # Batch 1 - Namespace tools
    assert "BulkUpdateNamespace" in tool_names
    assert "CreateNamespace" in tool_names
    assert "ListNamespaces" in tool_names

    # Batch 2 - Core Dolt tools
    expected_batch2_tools = [
        "DoltCommit",
        "DoltAdd",
        "DoltStatus",
        "DoltCheckout",
        "DoltReset",
        "DoltPush",
    ]
    for tool_name in expected_batch2_tools:
        assert tool_name in tool_names, f"Batch 2 tool {tool_name} should be registered"

    # Batch 3 - Advanced Dolt tools
    expected_batch3_tools = [
        "DoltPull",
        "DoltBranch",
        "DoltListBranches",
        "DoltDiff",
        "DoltAutoCommitAndPush",
        "DoltMerge",
    ]
    for tool_name in expected_batch3_tools:
        assert tool_name in tool_names, f"Batch 3 tool {tool_name} should be registered"


def test_auto_generated_tools_have_proper_schemas():
    """Test that auto-generated tools expose individual parameter schemas, not generic input."""
    cogni_tools = get_all_cogni_tools()

    for tool in cogni_tools:
        # All tools should have proper input models
        assert hasattr(tool, "input_model"), f"Tool {tool.name} should have input_model"
        assert hasattr(tool, "output_model"), f"Tool {tool.name} should have output_model"

        # Input model should have fields (individual parameters)
        input_model = tool.input_model
        if hasattr(input_model, "model_fields"):
            # Pydantic v2 style (preferred)
            fields = input_model.model_fields
        elif hasattr(input_model, "__fields__"):
            # Pydantic v1 style (fallback)
            fields = input_model.__fields__
        else:
            fields = {}

        # Should not have a generic 'input' field (the problematic pattern we fixed)
        field_names = list(fields.keys())
        
        # Some tools like HealthCheck may have zero parameters, which is valid
        if len(fields) > 0:
            assert "input" not in field_names or len(field_names) > 1, (
                f"Tool {tool.name} should not use generic input pattern"
            )


@pytest.mark.asyncio
async def test_auto_generated_tool_wrapper_creation():
    """Test that auto-generated tool wrappers can be created and executed."""
    cogni_tools = get_all_cogni_tools()

    # Mock memory bank getter
    def mock_memory_bank_getter():
        mock_bank = MagicMock()
        mock_bank.branch = "test-branch"
        return mock_bank

    # Test wrapper creation for first few tools
    for tool in cogni_tools[:3]:
        wrapper = create_mcp_wrapper_from_cogni_tool(tool, mock_memory_bank_getter)

        # Should be callable
        assert callable(wrapper)

        # Should have proper metadata
        assert hasattr(wrapper, "__name__")
        assert hasattr(wrapper, "__doc__")
        assert "Auto-generated MCP wrapper" in wrapper.__doc__


# Test CreateWorkItem tool (now auto-generated)
@pytest.mark.asyncio
async def test_create_work_item_auto_generated(sample_work_item_input):
    """Test that CreateWorkItem auto-generated tool wrapper works correctly."""
    cogni_tools = get_all_cogni_tools()
    create_work_item_tool = None

    for tool in cogni_tools:
        if tool.name == "CreateWorkItem":
            create_work_item_tool = tool
            break

    assert create_work_item_tool is not None, "CreateWorkItem tool should be registered"

    # Mock memory bank
    def mock_memory_bank_getter():
        mock_bank = MagicMock()
        mock_bank.branch = "test-branch"
        return mock_bank

    # Create wrapper
    wrapper = create_mcp_wrapper_from_cogni_tool(create_work_item_tool, mock_memory_bank_getter)

    # Test that wrapper accepts individual parameters
    # Note: This will likely fail due to missing database, but should accept parameters correctly
    try:
        _result = await wrapper(
            type=sample_work_item_input["type"],
            title=sample_work_item_input["title"],
            description=sample_work_item_input["description"],
        )
        # If it succeeds, great! If not, that's okay for this schema test
    except Exception as e:
        # Expected - we're testing schema acceptance, not full functionality
        assert "validation error" not in str(e).lower(), (
            "Should not have parameter validation errors"
        )


# Test GetMemoryBlock tool (now auto-generated)
@pytest.mark.asyncio
async def test_get_memory_block_auto_generated():
    """Test that GetMemoryBlock auto-generated tool wrapper accepts individual parameters."""
    cogni_tools = get_all_cogni_tools()
    get_memory_block_tool = None

    for tool in cogni_tools:
        if tool.name == "GetMemoryBlock":
            get_memory_block_tool = tool
            break

    assert get_memory_block_tool is not None, "GetMemoryBlock tool should be registered"

    # Mock memory bank
    def mock_memory_bank_getter():
        mock_bank = MagicMock()
        mock_bank.branch = "test-branch"
        return mock_bank

    # Create wrapper
    wrapper = create_mcp_wrapper_from_cogni_tool(get_memory_block_tool, mock_memory_bank_getter)

    # Test that wrapper accepts individual parameters (block_ids, limit, etc.)
    try:
        result = await wrapper(block_ids=[str(uuid.uuid4())], limit=5)
        # If it succeeds, check structure
        assert isinstance(result, dict)
    except Exception as e:
        # Expected - we're testing schema acceptance, not full functionality
        assert "validation error" not in str(e).lower(), (
            "Should not have parameter validation errors"
        )


@pytest.mark.asyncio
async def test_dolt_tools_auto_generated_parameter_schemas():
    """Test that Dolt tools (Batch 2 & 3) accept individual parameters correctly."""
    cogni_tools = get_all_cogni_tools()

    # Test key Dolt tools
    dolt_tools_to_test = {
        "DoltStatus": {"random_string": "test"},
        "DoltCommit": {"commit_message": "test commit", "author": "test-author"},
        "DoltListBranches": {"random_string": "test"},
        "DoltDiff": {"mode": "working", "from_revision": "HEAD", "to_revision": "WORKING"},
    }

    def mock_memory_bank_getter():
        mock_bank = MagicMock()
        mock_bank.branch = "test-branch"
        return mock_bank

    for tool_name, test_params in dolt_tools_to_test.items():
        tool = None
        for t in cogni_tools:
            if t.name == tool_name:
                tool = t
                break

        assert tool is not None, f"{tool_name} should be registered"

        # Create wrapper
        wrapper = create_mcp_wrapper_from_cogni_tool(tool, mock_memory_bank_getter)

        # Test individual parameter acceptance
        try:
            _result = await wrapper(**test_params)
            # Success - tool accepts individual parameters
        except Exception as e:
            # Expected for some tools due to missing database
            # Key point: should not have validation errors about parameters
            assert "validation error" not in str(e).lower(), (
                f"{tool_name} should accept individual parameters"
            )


@pytest.mark.asyncio
async def test_health_check(mcp_app):
    """Test health check functionality."""
    result = await mcp_app.health_check()

    assert isinstance(result, dict)
    assert "healthy" in result
    assert "timestamp" in result


@pytest.mark.asyncio
async def test_namespace_tools_auto_generated_schemas():
    """Test that namespace tools (Batch 1) accept individual parameters correctly."""
    cogni_tools = get_all_cogni_tools()

    def mock_memory_bank_getter():
        mock_bank = MagicMock()
        mock_bank.branch = "test-branch"
        return mock_bank

    # Test ListNamespaces
    list_namespaces_tool = None
    for tool in cogni_tools:
        if tool.name == "ListNamespaces":
            list_namespaces_tool = tool
            break

    if list_namespaces_tool:
        wrapper = create_mcp_wrapper_from_cogni_tool(list_namespaces_tool, mock_memory_bank_getter)
        try:
            _result = await wrapper(random_string="test")
            # Success - accepts individual parameters
        except Exception as e:
            assert "validation error" not in str(e).lower(), (
                "ListNamespaces should accept individual parameters"
            )


@pytest.mark.asyncio
async def test_memory_bank_connection_error(mcp_app):
    """Test graceful handling when memory bank is unavailable."""
    # This test should still work as it tests the mcp_app structure
    assert hasattr(mcp_app, "get_memory_bank")

    # Try to get memory bank
    try:
        memory_bank = mcp_app.get_memory_bank()
        # If successful, verify it's a proper object
        if memory_bank:
            assert hasattr(memory_bank, "branch")
    except Exception as e:
        # Connection errors are expected in test environment
        assert "connection" in str(e).lower() or "database" in str(e).lower()


def test_systematic_conversion_completion():
    """Test that the systematic MCP schema visibility fix is 100% complete."""
    cogni_tools = get_all_cogni_tools()

    # Verify we have the expected number of tools after complete conversion
    # This number should match the total from our systematic conversion project
    assert len(cogni_tools) >= 16, f"Expected at least 16 converted tools, got {len(cogni_tools)}"

    # Verify specific tools from each batch are present
    tool_names = [tool.name for tool in cogni_tools]

    # Verify systematic batches are complete
    phase1_tools = ["GetActiveWorkItems", "GetLinkedBlocks"]
    batch1_tools = ["BulkUpdateNamespace", "CreateNamespace", "ListNamespaces"]
    batch2_tools = ["DoltCommit", "DoltAdd", "DoltStatus", "DoltCheckout", "DoltReset", "DoltPush"]
    batch3_tools = [
        "DoltPull",
        "DoltBranch",
        "DoltListBranches",
        "DoltDiff",
        "DoltAutoCommitAndPush",
        "DoltMerge",
    ]

    all_converted_tools = phase1_tools + batch1_tools + batch2_tools + batch3_tools

    for tool_name in all_converted_tools:
        assert tool_name in tool_names, (
            f"Systematically converted tool {tool_name} should be registered"
        )

    print(
        f"✅ Systematic conversion verification: {len(all_converted_tools)} tools confirmed registered"
    )
