"""
Tests for MCP parameter handling fix.

This test file specifically validates that MCP tools handle empty parameters correctly
and don't fail when called with empty dictionaries instead of strings.

Bug: MCP tools were failing when called with empty strings because they try to unpack
the input with **input into Pydantic model constructors.
"""

import pytest
from unittest.mock import MagicMock, patch

from services.mcp_server.app.mcp_server import (
    dolt_status,
    dolt_list_branches,
    get_active_work_items,
    query_memory_blocks_semantic,
    health_check,
)


class TestMCPParameterFix:
    """Test class for MCP parameter handling fix."""

    @pytest.mark.asyncio
    async def test_dolt_status_with_empty_dict(self):
        """Test that DoltStatus works with empty dictionary input."""
        with patch("services.mcp_server.app.mcp_server.get_memory_bank") as mock_bank:
            mock_bank.return_value = MagicMock()
            mock_bank.return_value.dolt_reader._execute_query.return_value = []
            mock_bank.return_value.dolt_writer.active_branch = "main"

            # This should work (empty dict)
            result = await dolt_status({})
            assert result is not None
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_dolt_status_with_empty_string_fails(self):
        """Test that DoltStatus fails gracefully with empty string input."""
        with patch("services.mcp_server.app.mcp_server.get_memory_bank") as mock_bank:
            mock_bank.return_value = MagicMock()

            # This should fail but handle gracefully (empty string)
            result = await dolt_status("")
            assert result is not None
            assert isinstance(result, dict)
            assert "success" in result
            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_dolt_list_branches_with_empty_dict(self):
        """Test that DoltListBranches works with empty dictionary input."""
        with patch("services.mcp_server.app.mcp_server.get_memory_bank") as mock_bank:
            mock_bank.return_value = MagicMock()
            mock_bank.return_value.dolt_reader._execute_query.return_value = []
            mock_bank.return_value.dolt_writer.active_branch = "main"

            # This should work (empty dict)
            result = await dolt_list_branches({})
            assert result is not None
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_active_work_items_with_empty_dict(self):
        """Test that GetActiveWorkItems works with empty dictionary input."""
        with patch("services.mcp_server.app.mcp_server.get_memory_bank") as mock_bank:
            mock_bank.return_value = MagicMock()
            mock_bank.return_value.dolt_reader._execute_query.return_value = []

            # This should work (empty dict)
            result = await get_active_work_items({})
            assert result is not None
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_query_memory_blocks_semantic_with_required_param(self):
        """Test that QueryMemoryBlocksSemantic works with required query_text parameter."""
        with patch("services.mcp_server.app.mcp_server.get_memory_bank") as mock_bank:
            mock_bank.return_value = MagicMock()
            mock_bank.return_value.dolt_reader._execute_query.return_value = []

            # This should work (dict with required param)
            result = await query_memory_blocks_semantic({"query_text": "test query"})
            assert result is not None
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_health_check_no_params(self):
        """Test that HealthCheck works without any parameters."""
        with (
            patch("services.mcp_server.app.mcp_server.get_memory_bank") as mock_get_memory_bank,
            patch("services.mcp_server.app.mcp_server.get_link_manager") as mock_get_link_manager,
            patch("services.mcp_server.app.mcp_server.get_pm_links") as mock_get_pm_links,
        ):
            # Mock all the memory system components
            mock_memory_bank = MagicMock()
            mock_get_memory_bank.return_value = mock_memory_bank

            mock_link_manager = MagicMock()
            mock_get_link_manager.return_value = mock_link_manager

            mock_pm_links = MagicMock()
            mock_get_pm_links.return_value = mock_pm_links

            # HealthCheck doesn't take any parameters
            result = await health_check()
            assert result is not None
            assert isinstance(result, dict)
            assert "healthy" in result

    @pytest.mark.asyncio
    async def test_parameter_type_validation(self):
        """Test that various parameter types are handled correctly."""
        with patch("services.mcp_server.app.mcp_server.get_memory_bank") as mock_bank:
            mock_bank.return_value = MagicMock()
            mock_bank.return_value.dolt_reader._execute_query.return_value = []
            mock_bank.return_value.dolt_writer.active_branch = "main"

            # Test various input types that should be handled gracefully
            test_cases = [
                {},  # Empty dict (should work)
                {"invalid_param": "value"},  # Dict with invalid params (should work with defaults)
            ]

            for input_data in test_cases:
                result = await dolt_status(input_data)
                assert result is not None
                assert isinstance(result, dict)

            # Test invalid input types that should fail gracefully
            invalid_cases = [
                "",  # Empty string (should fail gracefully)
                "string",  # Non-empty string (should fail gracefully)
                123,  # Number (should fail gracefully)
                [],  # List (should fail gracefully)
            ]

            for invalid_input in invalid_cases:
                result = await dolt_status(invalid_input)
                assert result is not None
                assert isinstance(result, dict)
                assert "success" in result
                assert result["success"] is False
