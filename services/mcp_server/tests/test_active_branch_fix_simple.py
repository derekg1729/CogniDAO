#!/usr/bin/env python3
"""
Simple test for Active Branch Bug Fix (Bug ID: ed079a77-445e-4c1e-8dbb-8027aba4e0b9)

Validates that MCP tool error handlers correctly report actual branch names
instead of hardcoded "unknown" values.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Fix path to point to the correct location of the MCP server
sys.path.insert(
    0, str(Path(__file__).parent.parent.parent.parent / "services" / "mcp_server" / "app")
)

from mcp_server import dolt_status, dolt_list_branches


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

        with patch("mcp_server.get_memory_bank") as mock_get_bank:
            mock_get_bank.return_value = self.create_mock_memory_bank(test_branch)

            with patch("mcp_server.dolt_status_tool") as mock_tool:
                mock_tool.side_effect = Exception("Simulated error")

                result = await dolt_status({})

                assert isinstance(result, dict)
                assert result["success"] is False
                assert result["active_branch"] == test_branch
                assert result["active_branch"] != "unknown"

    # NOTE: bulk_create_blocks_mcp was converted to auto-generated BulkCreateBlocks tool
    # in Phase 2A. The auto-generated tool uses individual parameters instead of
    # wrapped input objects, making the original test obsolete.

    @pytest.mark.asyncio
    async def test_dolt_list_branches_error_reports_actual_branch(self):
        """Test DoltListBranches error handler reports actual branch instead of 'unknown'"""
        test_branch = "main"

        with patch("mcp_server.get_memory_bank") as mock_get_bank:
            mock_get_bank.return_value = self.create_mock_memory_bank(test_branch)

            with patch("mcp_server.dolt_list_branches_tool") as mock_tool:
                mock_tool.side_effect = Exception("Simulated branch listing error")

                result = await dolt_list_branches({})

                assert isinstance(result, dict)
                assert result["success"] is False
                assert result["active_branch"] == test_branch
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

        for branch_name in test_branches:
            mock_memory_bank = self.create_mock_memory_bank(branch_name)

            with patch("mcp_server.get_memory_bank") as mock_get_bank:
                mock_get_bank.return_value = mock_memory_bank

                with patch("mcp_server.dolt_status_tool") as mock_tool:
                    mock_tool.side_effect = Exception("Test error")

                    import asyncio

                    result = asyncio.run(dolt_status({}))

                    assert result["active_branch"] == branch_name
                    assert result["active_branch"] != "unknown"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
