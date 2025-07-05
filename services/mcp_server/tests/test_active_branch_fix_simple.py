#!/usr/bin/env python3
"""
Simple test for Active Branch Bug Fix (Bug ID: ed079a77-445e-4c1e-8dbb-8027aba4e0b9)

Validates that MCP tool error handlers correctly report actual branch names
instead of hardcoded "unknown" values.
"""

import pytest
from unittest.mock import patch, MagicMock
from services.mcp_server.app.tool_registry import get_all_cogni_tools
from services.mcp_server.app.mcp_auto_generator import create_mcp_wrapper_from_cogni_tool
import sys
from pathlib import Path

# Fix path to point to the correct location of the MCP server
sys.path.insert(
    0, str(Path(__file__).parent.parent.parent.parent / "services" / "mcp_server" / "app")
)


class TestActiveBranchFixSimple:
    """Simple test suite for active_branch bug fix validation"""

    def create_mock_memory_bank(self, branch_name="test-branch"):
        """Create a properly mocked memory bank with branch property"""
        mock_memory_bank = MagicMock()
        mock_memory_bank.branch = branch_name
        return mock_memory_bank

    @pytest.mark.asyncio
    async def test_dolt_status_error_reports_actual_branch(self):
        """Test DoltStatus error handler reports actual branch instead of 'unknown'"""
        test_branch = "feature/test-branch"

        # Get DoltStatus auto-generated tool
        cogni_tools = get_all_cogni_tools()
        dolt_status_tool = None
        for tool in cogni_tools:
            if tool.name == "DoltStatus":
                dolt_status_tool = tool
                break
        
        assert dolt_status_tool is not None, "DoltStatus tool should be registered"

        # Create wrapper with mocked memory bank
        def mock_memory_bank_getter():
            return self.create_mock_memory_bank(test_branch)

        dolt_status_wrapper = create_mcp_wrapper_from_cogni_tool(dolt_status_tool, mock_memory_bank_getter)

        with patch("infra_core.memory_system.tools.agent_facing.dolt_repo_tool.dolt_status_tool") as mock_tool:
            mock_tool.side_effect = Exception("Simulated error")

            result = await dolt_status_wrapper(random_string="test")

            assert isinstance(result, dict)
            assert result["success"] is False
            assert result["current_branch"] == test_branch
            assert result["active_branch"] != "unknown"

    # NOTE: bulk_create_blocks_mcp was converted to auto-generated BulkCreateBlocks tool
    # in Phase 2A. The auto-generated tool uses individual parameters instead of
    # wrapped input objects, making the original test obsolete.

    @pytest.mark.asyncio
    async def test_dolt_list_branches_error_reports_actual_branch(self):
        """Test DoltListBranches error handler reports actual branch instead of 'unknown'"""
        test_branch = "main"

        # Get DoltListBranches auto-generated tool
        cogni_tools = get_all_cogni_tools()
        dolt_list_branches_tool = None
        for tool in cogni_tools:
            if tool.name == "DoltListBranches":
                dolt_list_branches_tool = tool
                break
        
        assert dolt_list_branches_tool is not None, "DoltListBranches tool should be registered"

        # Create wrapper with mocked memory bank
        def mock_memory_bank_getter():
            return self.create_mock_memory_bank(test_branch)

        dolt_list_branches_wrapper = create_mcp_wrapper_from_cogni_tool(dolt_list_branches_tool, mock_memory_bank_getter)

        with patch("infra_core.memory_system.tools.agent_facing.dolt_repo_tool.dolt_list_branches_tool") as mock_tool:
            mock_tool.side_effect = Exception("Simulated branch listing error")

            result = await dolt_list_branches_wrapper(random_string="test")

            assert isinstance(result, dict)
            assert result["success"] is False
            assert result["current_branch"] == test_branch
            assert result["active_branch"] != "unknown"

    def test_various_branch_name_formats(self):
        """Test that branch reporting works with different branch name formats"""
        test_branches = [
            "main",
            "develop",
            "feature/ai-education-team",
            "hotfix/critical-bug-fix",
            "release/v1.2.3",
        ]

        # Get DoltStatus auto-generated tool
        cogni_tools = get_all_cogni_tools()
        dolt_status_tool = None
        for tool in cogni_tools:
            if tool.name == "DoltStatus":
                dolt_status_tool = tool
                break
        
        assert dolt_status_tool is not None, "DoltStatus tool should be registered"

        for branch_name in test_branches:
            # Create wrapper with mocked memory bank for this branch
            def mock_memory_bank_getter():
                return self.create_mock_memory_bank(branch_name)

            dolt_status_wrapper = create_mcp_wrapper_from_cogni_tool(dolt_status_tool, mock_memory_bank_getter)

            with patch("infra_core.memory_system.tools.agent_facing.dolt_repo_tool.dolt_status_tool") as mock_tool:
                mock_tool.side_effect = Exception("Test error")

                import asyncio

                result = asyncio.run(dolt_status_wrapper(random_string="test"))

                assert result["active_branch"] == branch_name
                assert result["active_branch"] != "unknown"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
