"""
Tests for namespace validation functionality in MCP Server.

These tests validate that namespace validation works correctly across all
memory block creation and update operations, ensuring that only valid
namespaces can be used and invalid ones are properly rejected.
"""

import pytest
import importlib
from unittest.mock import MagicMock
import uuid


# Mock mysql.connector.connect to avoid database connection during import
@pytest.fixture(autouse=True)
def mock_mysql_connect(monkeypatch):
    """Replace mysql.connector.connect with a dummy connection for testing."""
    dummy_conn = MagicMock()
    dummy_cursor = MagicMock()
    dummy_cursor.execute.return_value = None
    dummy_cursor.fetchone.return_value = (1,)
    dummy_conn.cursor.return_value = dummy_cursor

    monkeypatch.setattr("mysql.connector.connect", lambda **kwargs: dummy_conn)
    yield


# Mock StructuredMemoryBank with namespace validation behavior
@pytest.fixture(autouse=True)
def mock_structured_memory_bank_with_namespace_validation(monkeypatch):
    """
    Replace StructuredMemoryBank with a mock that simulates namespace validation.
    This mock will:
    - Accept 'legacy' namespace as valid
    - Reject any other namespace as invalid
    - Return appropriate error messages for namespace validation failures
    """
    dummy_bank = MagicMock()
    dummy_link_mgr = MagicMock()

    # Configure dolt_writer mock with active_branch property
    dummy_writer = MagicMock()
    dummy_writer.active_branch = "feat/namespaces"
    dummy_bank.dolt_writer = dummy_writer

    # Configure dolt_reader for namespace queries
    dummy_reader = MagicMock()
    dummy_bank.dolt_reader = dummy_reader

    def mock_execute_query(query, params=None):
        """Mock database query execution for namespace validation."""
        # Handle case-insensitive namespace queries
        if "SELECT id FROM namespaces WHERE LOWER(id) = %s" in query:
            if params and params[0].lower() in ["legacy", "cogni-core"]:
                return [{"id": params[0]}]  # Legacy and cogni-core namespaces exist
            else:
                return []  # Other namespaces don't exist
        # Handle legacy case-sensitive queries for backwards compatibility
        elif "SELECT id FROM namespaces WHERE id = %s" in query:
            if params and params[0] in ["legacy", "cogni-core"]:
                return [{"id": params[0]}]  # Legacy and cogni-core namespaces exist
            else:
                return []  # Other namespaces don't exist
        # Handle bulk case-insensitive queries
        elif "SELECT LOWER(id) as normalized_id FROM namespaces WHERE LOWER(id) IN" in query:
            if params:
                # Check if any of the normalized params match valid namespaces
                normalized_params = [p.lower() for p in params]
                valid_namespaces = ["legacy", "cogni-core"]
                for ns in valid_namespaces:
                    if ns in normalized_params:
                        return [{"normalized_id": ns}]
            return []
        elif "SELECT id, name FROM namespaces" in query:
            return [
                {"id": "legacy", "name": "Legacy Namespace"},
                {"id": "cogni-core", "name": "Cogni Core Namespace"},
            ]
        return []

    dummy_reader._execute_query = mock_execute_query

    # Configure create_memory_block to simulate namespace validation
    def mock_create_memory_block(block):
        """Mock create_memory_block with namespace validation."""
        if hasattr(block, "namespace_id"):
            # Normalize namespace_id for case-insensitive comparison
            normalized_namespace = block.namespace_id.lower().strip() if block.namespace_id else ""
            if normalized_namespace in ["legacy", "cogni-core"]:
                return (True, None)  # Success for valid namespace (any case)
            else:
                return (
                    False,
                    f"Namespace validation failed: Namespace does not exist: {block.namespace_id}",
                )
        return (True, None)  # Default success if no namespace_id

    dummy_bank.create_memory_block = mock_create_memory_block

    # Configure update_memory_block to simulate namespace validation
    def mock_update_memory_block(block):
        """Mock update_memory_block with namespace validation."""
        if hasattr(block, "namespace_id"):
            # Normalize namespace_id for case-insensitive comparison
            normalized_namespace = block.namespace_id.lower().strip() if block.namespace_id else ""
            if normalized_namespace in ["legacy", "cogni-core"]:
                return True  # Success for valid namespace (any case)
            else:
                return False  # Failure for invalid namespace
        return True  # Default success if no namespace_id

    dummy_bank.update_memory_block = mock_update_memory_block

    # Configure get_memory_block to return existing blocks
    def mock_get_memory_block(block_id):
        """Mock get_memory_block to return a sample block."""
        if block_id:
            # Create a simple mock object instead of importing MemoryBlock
            mock_block = MagicMock()
            mock_block.id = block_id
            mock_block.namespace_id = "legacy"
            mock_block.type = "knowledge"
            mock_block.text = "Sample block content"
            mock_block.state = "draft"
            mock_block.visibility = "internal"
            mock_block.tags = []
            mock_block.metadata = {}
            mock_block.created_by = "test_agent"
            mock_block.block_version = 1
            # Make the mock behave like a dict when accessed with dict methods
            mock_block.__getitem__ = lambda self, key: getattr(self, key, None)
            mock_block.get = lambda self, key, default=None: getattr(self, key, default)
            return mock_block
        return None

    dummy_bank.get_memory_block = mock_get_memory_block

    # Patch the constructors
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
def mcp_app():
    """Import and reload the MCP server so that our mocks apply at module-load time."""
    import services.mcp_server.app.mcp_server as app_module

    return importlib.reload(app_module)


# Test CreateMemoryBlock with namespace validation
@pytest.mark.xfail(
    reason="Legacy implementation now requires MCP integration test - manual tool functions removed in Phase 2A"
)
@pytest.mark.asyncio
async def test_create_memory_block_valid_namespace(mcp_app):
    """Test that CreateMemoryBlock succeeds with valid namespace."""
    input_data = {
        "type": "knowledge",
        "title": "Test Valid Namespace",
        "content": "Testing namespace validation with valid legacy namespace",
        "namespace_id": "legacy",
        "tags": ["test", "validation", "valid"],
    }

    result = await mcp_app.create_memory_block(input_data)

    # Should succeed with valid namespace
    assert result is not None
    if hasattr(result, "success"):
        assert result.success is True
        assert result.id is not None
        assert result.block_type == "knowledge"
    else:
        assert isinstance(result, dict)
        assert result.get("success") is True
        assert result.get("id") is not None


@pytest.mark.xfail(
    reason="Legacy implementation now requires MCP integration test - manual tool functions removed in Phase 2A"
)
@pytest.mark.asyncio
async def test_create_memory_block_invalid_namespace(mcp_app):
    """Test that CreateMemoryBlock fails with invalid namespace."""
    input_data = {
        "type": "knowledge",
        "title": "Test Invalid Namespace",
        "content": "Testing namespace validation with invalid namespace",
        "namespace_id": "invalid_namespace_test_123",
        "tags": ["test", "validation", "invalid"],
    }

    result = await mcp_app.create_memory_block(input_data)

    # Should fail with invalid namespace
    assert result is not None
    if hasattr(result, "success"):
        assert result.success is False
        assert result.id is None
        assert "Namespace validation failed" in result.error
    else:
        assert isinstance(result, dict)
        assert result.get("success") is False
        assert "error" in result


@pytest.mark.xfail(
    reason="Legacy implementation now requires MCP integration test - manual tool functions removed in Phase 2A"
)
@pytest.mark.asyncio
async def test_create_memory_block_default_namespace(mcp_app):
    """Test that CreateMemoryBlock uses default namespace when none specified."""
    input_data = {
        "type": "knowledge",
        "title": "Test Default Namespace",
        "content": "Testing default namespace behavior",
        "tags": ["test", "default"],
        # No namespace_id specified - should default to "legacy"
    }

    result = await mcp_app.create_memory_block(input_data)

    # Should succeed with default namespace
    assert result is not None
    if hasattr(result, "success"):
        assert result.success is True
        assert result.id is not None
        assert result.block_type == "knowledge"
    else:
        assert isinstance(result, dict)
        assert result.get("success") is True
        assert result.get("id") is not None


# Test CreateWorkItem with namespace validation
@pytest.mark.xfail(
    reason="Legacy implementation now requires MCP integration test - manual tool functions removed in Phase 2A"
)
@pytest.mark.asyncio
async def test_create_work_item_valid_namespace(mcp_app):
    """Test that CreateWorkItem succeeds with valid namespace."""
    input_data = {
        "type": "task",
        "title": "Test Work Item Valid Namespace",
        "description": "Testing work item creation with valid namespace",
        "namespace_id": "legacy",
        "owner": "test_agent",
        "acceptance_criteria": ["Test criteria 1", "Test criteria 2"],
    }

    result = await mcp_app.create_work_item(input_data)

    # Should succeed with valid namespace
    assert result is not None
    # Handle both Pydantic model and dict response formats
    if hasattr(result, "success"):
        assert result.success is True
        assert result.id is not None
        assert result.work_item_type == "task"
    elif isinstance(result, dict):
        assert result.get("success") is True
        assert result.get("id") is not None


@pytest.mark.xfail(
    reason="Legacy implementation now requires MCP integration test - manual tool functions removed in Phase 2A"
)
@pytest.mark.asyncio
async def test_create_work_item_invalid_namespace(mcp_app):
    """Test that CreateWorkItem fails with invalid namespace."""
    input_data = {
        "type": "task",
        "title": "Test Work Item Invalid Namespace",
        "description": "Testing work item creation with invalid namespace",
        "namespace_id": "invalid_work_namespace_456",
        "owner": "test_agent",
        "acceptance_criteria": ["Test criteria 1", "Test criteria 2"],
    }

    result = await mcp_app.create_work_item(input_data)

    # Should fail with invalid namespace
    assert result is not None
    # Handle both response formats
    if hasattr(result, "success"):
        assert result.success is False
        assert result.id is None
        assert "Namespace validation failed" in result.error
        assert "invalid_work_namespace_456" in result.error
    elif isinstance(result, dict):
        assert result.get("success") is False
        assert "error" in result


# Test UpdateMemoryBlock with namespace validation
@pytest.mark.xfail(
    reason="Legacy implementation now requires MCP integration test - manual tool functions removed in Phase 2A"
)
@pytest.mark.asyncio
async def test_update_memory_block_valid_namespace(mcp_app):
    """Test that UpdateMemoryBlock handles valid namespace correctly."""
    block_id = str(uuid.uuid4())
    input_data = {
        "block_id": block_id,
        "text": "Updated content with valid namespace",
        "namespace_id": "legacy",  # Valid namespace
        "tags": ["updated", "valid"],
        "change_note": "Testing namespace validation on update",
    }

    result = await mcp_app.update_memory_block(input_data)

    # Should handle the request (may fail due to mock limitations, but not due to namespace validation)
    assert result is not None
    # Check result format and handle accordingly
    if hasattr(result, "success"):
        # If it fails, it should not be due to namespace validation
        if not result.success:
            assert "Namespace validation failed" not in result.error
            assert "Namespace does not exist" not in result.error
    elif isinstance(result, dict):
        # For dict format, check success field
        if result.get("success") is False:
            error_msg = result.get("error", "")
            assert "Namespace validation failed" not in error_msg
            assert "Namespace does not exist" not in error_msg


@pytest.mark.xfail(
    reason="Legacy implementation now requires MCP integration test - manual tool functions removed in Phase 2A"
)
@pytest.mark.asyncio
async def test_update_memory_block_invalid_namespace(mcp_app):
    """Test that UpdateMemoryBlock fails with invalid namespace."""
    block_id = str(uuid.uuid4())
    input_data = {
        "block_id": block_id,
        "text": "Updated content with invalid namespace",
        "namespace_id": "invalid_update_namespace_789",  # Invalid namespace
        "tags": ["updated", "invalid"],
        "change_note": "Testing namespace validation failure on update",
    }

    result = await mcp_app.update_memory_block(input_data)

    # Should fail with invalid namespace
    assert result is not None
    if hasattr(result, "success"):
        assert result.success is False
        assert "VALIDATION_ERROR" in str(result.error_code) or "validation" in result.error.lower()
    elif isinstance(result, dict):
        assert result.get("success") is False
        error_msg = result.get("error", "")
        assert "validation" in error_msg.lower() or "error" in result


# Test namespace validation helper functions directly
def test_namespace_validation_helper_functions():
    """Test the namespace validation helper functions directly."""
    from infra_core.memory_system.tools.helpers.namespace_validation import (
        validate_namespace_exists,
        get_available_namespaces,
        clear_namespace_cache,
        invalidate_namespace_cache,
    )

    # Create a mock memory bank for testing (without autouse fixtures interfering)
    mock_bank = MagicMock()
    mock_reader = MagicMock()
    mock_bank.dolt_reader = mock_reader

    # Remove the namespace_exists method so it falls back to dolt_reader
    if hasattr(mock_bank, "namespace_exists"):
        delattr(mock_bank, "namespace_exists")

    def mock_execute_query(query, params=None):
        # Handle case-insensitive queries
        if "SELECT id FROM namespaces WHERE LOWER(id) = %s" in query:
            if params and params[0].lower() == "legacy":
                return [{"id": "legacy"}]
            else:
                return []
        # Handle legacy case-sensitive queries for backwards compatibility
        elif "SELECT id FROM namespaces WHERE id = %s" in query:
            if params and params[0] == "legacy":
                return [{"id": "legacy"}]
            else:
                return []
        elif "SELECT id, name FROM namespaces" in query:
            return [{"id": "legacy", "name": "Legacy Namespace"}]
        return []

    mock_reader._execute_query = mock_execute_query

    # Clear cache before testing
    clear_namespace_cache()

    # Test valid namespace (case-insensitive)
    assert validate_namespace_exists("legacy", mock_bank, raise_error=False) is True
    assert validate_namespace_exists("LEGACY", mock_bank, raise_error=False) is True
    assert validate_namespace_exists("Legacy", mock_bank, raise_error=False) is True

    # Test invalid namespace
    assert validate_namespace_exists("invalid", mock_bank, raise_error=False) is False

    # Test invalid namespace with raise_error=True
    with pytest.raises(KeyError, match="Namespace does not exist: invalid"):
        validate_namespace_exists("invalid", mock_bank, raise_error=True)

    # Test cache invalidation
    invalidate_namespace_cache("LEGACY")  # Should work with any case

    # Test get_available_namespaces
    namespaces = get_available_namespaces(mock_bank)
    assert isinstance(namespaces, dict)
    assert "legacy" in namespaces
    assert namespaces["legacy"] == "Legacy Namespace"


# Test edge cases and error conditions
@pytest.mark.xfail(
    reason="Legacy implementation now requires MCP integration test - manual tool functions removed in Phase 2A"
)
@pytest.mark.asyncio
async def test_namespace_validation_edge_cases(mcp_app):
    """Test edge cases for namespace validation."""

    # Test with empty namespace_id
    input_data = {
        "type": "knowledge",
        "title": "Test Empty Namespace",
        "content": "Testing with empty namespace",
        "namespace_id": "",  # Empty string
        "tags": ["test", "edge_case"],
    }

    result = await mcp_app.create_memory_block(input_data)

    # Should handle empty namespace gracefully
    assert result is not None
    if hasattr(result, "success"):
        assert result.success is False
    elif isinstance(result, dict):
        assert result.get("success") is False

    # Test with None namespace_id (should use default)
    input_data_none = {
        "type": "knowledge",
        "title": "Test None Namespace",
        "content": "Testing with None namespace",
        "namespace_id": None,
        "tags": ["test", "edge_case"],
    }

    result_none = await mcp_app.create_memory_block(input_data_none)

    # Should handle None namespace (likely defaults to legacy)
    assert result_none is not None


@pytest.mark.xfail(
    reason="Legacy implementation now requires MCP integration test - manual tool functions removed in Phase 2A"
)
@pytest.mark.asyncio
async def test_namespace_validation_case_insensitive(mcp_app):
    """Test that namespace validation is case-insensitive."""

    # Test various case combinations of "legacy" - all should succeed
    test_cases = ["legacy", "Legacy", "LEGACY", "LegAcY"]

    for namespace_case in test_cases:
        input_data = {
            "type": "knowledge",
            "title": f"Test Case Insensitive - {namespace_case}",
            "content": f"Testing case-insensitive validation with: {namespace_case}",
            "namespace_id": namespace_case,
            "tags": ["test", "case_insensitive"],
        }

        result = await mcp_app.create_memory_block(input_data)

        # All variations should succeed since they normalize to "legacy"
        assert result is not None
        if hasattr(result, "success"):
            assert result.success is True, f"Failed for namespace case: {namespace_case}"
        elif isinstance(result, dict):
            assert result.get("success") is True, f"Failed for namespace case: {namespace_case}"


@pytest.mark.xfail(
    reason="Legacy implementation now requires MCP integration test - manual tool functions removed in Phase 2A"
)
@pytest.mark.asyncio
async def test_multiple_tools_namespace_consistency(mcp_app):
    """Test that namespace validation is consistent across different tools."""

    # Test the same invalid namespace across multiple tools
    invalid_namespace = "consistent_invalid_namespace_test"

    # Test CreateMemoryBlock
    create_result = await mcp_app.create_memory_block(
        {
            "type": "knowledge",
            "title": "Consistency Test",
            "content": "Testing consistency",
            "namespace_id": invalid_namespace,
        }
    )

    # Test CreateWorkItem
    work_item_result = await mcp_app.create_work_item(
        {
            "type": "task",
            "title": "Consistency Test Work Item",
            "description": "Testing consistency",
            "namespace_id": invalid_namespace,
            "acceptance_criteria": ["Test criteria"],
        }
    )

    # Both should fail with namespace validation errors
    assert create_result is not None
    if hasattr(create_result, "success"):
        assert create_result.success is False
    elif isinstance(create_result, dict):
        assert create_result.get("success") is False

    assert work_item_result is not None
    if hasattr(work_item_result, "success"):
        assert work_item_result.success is False
    elif isinstance(work_item_result, dict):
        assert work_item_result.get("success") is False

    # CreateMemoryBlock should mention the invalid namespace
    if hasattr(create_result, "error"):
        assert invalid_namespace in create_result.error
    elif isinstance(create_result, dict):
        error_msg = create_result.get("error", "")
        assert invalid_namespace in error_msg

    # CreateWorkItem should also mention the invalid namespace
    if hasattr(work_item_result, "error"):
        assert invalid_namespace in work_item_result.error
    elif isinstance(work_item_result, dict):
        error_msg = work_item_result.get("error", "")
        assert invalid_namespace in error_msg


@pytest.mark.asyncio
async def test_namespace_cache_invalidation_smoke_test(mcp_app):
    """
    Smoke test: Create a new namespace in-process, invalidate cache,
    and immediately create a block in that namespace to confirm cache path works.

    Note: This is a mock-based test since we don't have actual namespace creation tools yet.
    """
    from infra_core.memory_system.tools.helpers.namespace_validation import (
        clear_namespace_cache,
        invalidate_namespace_cache,
        validate_namespace_exists,
    )
    from unittest.mock import MagicMock

    # Create a mock memory bank that will simulate a new namespace being created
    mock_bank = MagicMock()
    mock_reader = MagicMock()
    mock_bank.dolt_reader = mock_reader

    # Remove the namespace_exists attribute to force fallback to dolt_reader path
    del mock_bank.namespace_exists

    # Start with a fresh cache
    clear_namespace_cache()

    # First, simulate that "new_namespace" doesn't exist initially
    def mock_execute_query_initial(query, params=None):
        if "SELECT id FROM namespaces WHERE LOWER(id) = %s" in query:
            if params and params[0].lower() == "legacy":
                return [{"id": "legacy"}]
            else:
                return []  # new_namespace doesn't exist initially
        return []

    mock_reader._execute_query = mock_execute_query_initial

    # Verify the namespace doesn't exist initially
    assert validate_namespace_exists("new_namespace", mock_bank, raise_error=False) is False

    # Simulate creating the namespace (change the mock to return the new namespace)
    def mock_execute_query_after_creation(query, params=None):
        if "SELECT id FROM namespaces WHERE LOWER(id) = %s" in query:
            if params and params[0].lower() == "legacy":
                return [{"id": "legacy"}]
            elif params and params[0].lower() == "new_namespace":
                return [{"id": "new_namespace"}]  # Now it exists!
            else:
                return []
        return []

    mock_reader._execute_query = mock_execute_query_after_creation

    # Clear the cache to simulate what would happen after creating a namespace
    invalidate_namespace_cache("new_namespace")

    # Now verify the namespace exists (this should work due to cache invalidation)
    assert validate_namespace_exists("new_namespace", mock_bank, raise_error=False) is True

    # Test case-insensitive validation too
    assert validate_namespace_exists("NEW_NAMESPACE", mock_bank, raise_error=False) is True
    assert validate_namespace_exists("New_Namespace", mock_bank, raise_error=False) is True

    # This confirms the cache invalidation and namespace validation path works correctly
