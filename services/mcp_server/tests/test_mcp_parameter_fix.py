"""
Tests for MCP parameter handling with auto-generated tools.

This test file validates that auto-generated MCP tools handle empty parameters correctly
and work properly with the new CogniTool wrapper system.

Updated for Phase 2A migration: Now uses auto-generated tools instead of manual functions.
"""

import pytest
from unittest.mock import MagicMock

from services.mcp_server.app.tool_registry import get_all_cogni_tools
from services.mcp_server.app.mcp_auto_generator import create_mcp_wrapper_from_cogni_tool
from services.mcp_server.app.mcp_server import health_check  # Keep this as it's not converted


class TestMCPParameterFix:
    """Test class for MCP parameter handling with auto-generated tools."""

    @pytest.mark.asyncio
    async def test_dolt_status_with_empty_dict(self):
        """Test that DoltStatus auto-generated tool works with empty dictionary input."""
        # Get DoltStatus auto-generated tool
        cogni_tools = get_all_cogni_tools()
        dolt_status_tool = None
        for tool in cogni_tools:
            if tool.name == "DoltStatus":
                dolt_status_tool = tool
                break
        
        if dolt_status_tool is None:
            pytest.skip("DoltStatus tool not found in auto-generated tools")
        
        # Mock memory bank getter
        def mock_memory_bank_getter():
            mock_bank = MagicMock()
            mock_bank.branch = "test-branch"
            mock_bank.dolt_writer.active_branch = "test-branch"
            mock_bank.dolt_reader._execute_query.return_value = []
            return mock_bank
        
        # Create wrapper and test
        wrapper = create_mcp_wrapper_from_cogni_tool(dolt_status_tool, mock_memory_bank_getter)
        result = await wrapper()
        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_dolt_status_handles_errors_gracefully(self):
        """Test that DoltStatus auto-generated tool handles errors gracefully."""
        # Get DoltStatus auto-generated tool
        cogni_tools = get_all_cogni_tools()
        dolt_status_tool = None
        for tool in cogni_tools:
            if tool.name == "DoltStatus":
                dolt_status_tool = tool
                break
        
        if dolt_status_tool is None:
            pytest.skip("DoltStatus tool not found in auto-generated tools")
        
        # Mock memory bank getter that will cause an error
        def mock_memory_bank_getter():
            mock_bank = MagicMock()
            mock_bank.branch = "test-branch"
            # Simulate an error in dolt operations
            mock_bank.dolt_reader._execute_query.side_effect = Exception("Database error")
            return mock_bank
        
        # Create wrapper and test error handling
        wrapper = create_mcp_wrapper_from_cogni_tool(dolt_status_tool, mock_memory_bank_getter)
        result = await wrapper()
        assert result is not None
        assert isinstance(result, dict)
        assert "success" in result
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_dolt_list_branches_with_empty_dict(self):
        """Test that DoltListBranches auto-generated tool works with empty dictionary input."""
        # Get DoltListBranches auto-generated tool
        cogni_tools = get_all_cogni_tools()
        dolt_list_branches_tool = None
        for tool in cogni_tools:
            if tool.name == "DoltListBranches":
                dolt_list_branches_tool = tool
                break
        
        if dolt_list_branches_tool is None:
            pytest.skip("DoltListBranches tool not found in auto-generated tools")
        
        # Mock memory bank getter
        def mock_memory_bank_getter():
            mock_bank = MagicMock()
            mock_bank.branch = "main"
            mock_bank.dolt_reader._execute_query.return_value = []
            mock_bank.dolt_writer.active_branch = "main"
            return mock_bank
        
        # Create wrapper and test
        wrapper = create_mcp_wrapper_from_cogni_tool(dolt_list_branches_tool, mock_memory_bank_getter)
        result = await wrapper()
        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_active_work_items_with_empty_dict(self):
        """Test that GetActiveWorkItems auto-generated tool works with empty dictionary input."""
        # Get GetActiveWorkItems auto-generated tool
        cogni_tools = get_all_cogni_tools()
        get_active_work_items_tool = None
        for tool in cogni_tools:
            if tool.name == "GetActiveWorkItems":
                get_active_work_items_tool = tool
                break
        
        if get_active_work_items_tool is None:
            pytest.skip("GetActiveWorkItems tool not found in auto-generated tools")
        
        # Mock memory bank getter
        def mock_memory_bank_getter():
            mock_bank = MagicMock()
            mock_bank.branch = "main"
            mock_bank.dolt_reader._execute_query.return_value = []
            return mock_bank
        
        # Create wrapper and test
        wrapper = create_mcp_wrapper_from_cogni_tool(get_active_work_items_tool, mock_memory_bank_getter)
        result = await wrapper()
        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_parameter_type_validation(self):
        """Test that auto-generated tools handle various parameter types correctly."""
        # Get DoltStatus auto-generated tool
        cogni_tools = get_all_cogni_tools()
        dolt_status_tool = None
        for tool in cogni_tools:
            if tool.name == "DoltStatus":
                dolt_status_tool = tool
                break
        
        if dolt_status_tool is None:
            pytest.skip("DoltStatus tool not found in auto-generated tools")
        
        # Mock memory bank getter
        def mock_memory_bank_getter():
            mock_bank = MagicMock()
            mock_bank.branch = "test-branch"
            mock_bank.dolt_reader._execute_query.return_value = []
            mock_bank.dolt_writer.active_branch = "test-branch"
            return mock_bank
        
        # Create wrapper and test various parameter handling
        wrapper = create_mcp_wrapper_from_cogni_tool(dolt_status_tool, mock_memory_bank_getter)
        
        # Test with no parameters (should work)
        result = await wrapper()
        assert result is not None
        assert isinstance(result, dict)
        
        # Test with random parameters (should be ignored gracefully)
        result = await wrapper(random_param="ignored")
        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_health_check_still_works(self):
        """Test that non-converted tools like health_check still work."""
        result = await health_check()
        assert result is not None
        assert isinstance(result, dict)
        assert "healthy" in result