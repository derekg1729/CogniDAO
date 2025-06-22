#!/usr/bin/env python3
"""
Test for DoltStatus MCP Tool Validation Error Fix

This test validates that the DoltStatus tool error handlers use the correct
field names and don't cause Pydantic validation errors.

Before the fix: Error handlers used 'current_branch' causing validation errors
After the fix: Error handlers use 'active_branch' matching the Pydantic model
"""

import pytest
from unittest.mock import patch
from pydantic import ValidationError

# Import the MCP server components
import sys
from pathlib import Path

# Fix path to point to the correct location of the MCP server
sys.path.insert(
    0, str(Path(__file__).parent.parent.parent.parent / "services" / "mcp_server" / "app")
)

from mcp_server import dolt_status
from infra_core.memory_system.tools.agent_facing.dolt_repo_tool import DoltStatusOutput


class TestDoltStatusValidationFix:
    """Test suite for DoltStatus MCP tool validation error fix"""

    @pytest.mark.asyncio
    async def test_dolt_status_error_handler_uses_correct_field_names(self):
        """
        Test that DoltStatus error handler uses 'active_branch' not 'current_branch'

        This test would have FAILED before the fix due to validation error:
        "1 validation error for DoltStatusOutput active_branch Field required"
        """
        # Mock input that will cause an exception in the tool
        mock_input = {}

        # Patch the dolt_status_tool to raise an exception
        with patch("mcp_server.dolt_status_tool") as mock_tool:
            mock_tool.side_effect = Exception("Simulated database error")

            # Call the MCP tool - this should handle the error gracefully
            result = await dolt_status(mock_input)

            # The result should be a valid JSON dict, not raise a validation error
            assert isinstance(result, dict)
            assert result["success"] is False
            assert "active_branch" in result  # This is the key fix!
            # After our bug fix, active_branch should be the actual branch, not "unknown"
            assert result["active_branch"] != "unknown"  # Should be actual branch name
            assert isinstance(result["active_branch"], str)  # Should be a valid string
            assert "Status check failed" in result["message"]
            assert result["error"] is not None

    def test_dolt_status_output_model_validation(self):
        """
        Test that DoltStatusOutput model requires 'active_branch' field

        This demonstrates what the error was before the fix.
        """
        # This should work - all required fields present
        valid_output = DoltStatusOutput(
            success=True,
            active_branch="main",
            is_clean=True,
            total_changes=0,
            message="Working tree clean",
        )
        assert valid_output.active_branch == "main"

        # This should fail - missing required 'active_branch' field
        with pytest.raises(ValidationError) as exc_info:
            DoltStatusOutput(
                success=False,
                # active_branch missing!
                is_clean=False,
                total_changes=0,
                message="Status check failed",
            )

        # Verify the validation error mentions 'active_branch'
        error_str = str(exc_info.value)
        assert "active_branch" in error_str
        assert "Field required" in error_str

    def test_error_response_structure_matches_success_response(self):
        """
        Test that error responses have the same structure as success responses

        This ensures consistency in the API contract.
        """
        # Create a success response
        success_response = DoltStatusOutput(
            success=True,
            active_branch="main",
            is_clean=True,
            total_changes=0,
            message="Working tree clean",
        )

        # Create an error response (like our fixed error handler does)
        error_response = DoltStatusOutput(
            success=False,
            active_branch="test-branch",  # After fix: uses actual branch name
            is_clean=False,
            total_changes=0,
            message="Status check failed: simulated error",
            error="simulated error",
        )

        # Both should have the same required fields
        success_dict = success_response.model_dump()
        error_dict = error_response.model_dump()

        # Key fields should be present in both
        required_fields = ["success", "active_branch", "is_clean", "total_changes", "message"]
        for field in required_fields:
            assert field in success_dict
            assert field in error_dict

    @pytest.mark.asyncio
    async def test_multiple_dolt_tools_error_consistency(self):
        """
        Test that all Dolt MCP tools use consistent error field names

        This prevents regression of the same issue in other tools.
        """
        # Import other Dolt MCP tools
        from mcp_server import dolt_auto_commit_and_push, dolt_list_branches, dolt_diff

        mock_input = {}

        # Test DoltAutoCommitAndPush error handler
        with patch("mcp_server.dolt_auto_commit_and_push_tool") as mock_tool:
            mock_tool.side_effect = Exception("Simulated error")
            result = await dolt_auto_commit_and_push(mock_input)
            assert isinstance(result, dict)
            assert "active_branch" in result
            # After bug fix: should be actual branch name, not "unknown"
            assert result["active_branch"] != "unknown"
            assert isinstance(result["active_branch"], str)

        # Test DoltListBranches error handler
        with patch("mcp_server.dolt_list_branches_tool") as mock_tool:
            mock_tool.side_effect = Exception("Simulated error")
            result = await dolt_list_branches(mock_input)
            assert isinstance(result, dict)
            assert "active_branch" in result
            # After bug fix: should be actual branch name, not "unknown"
            assert result["active_branch"] != "unknown"
            assert isinstance(result["active_branch"], str)

        # Test DoltDiff error handler
        with patch("mcp_server.dolt_diff_tool") as mock_tool:
            mock_tool.side_effect = Exception("Simulated error")
            result = await dolt_diff(mock_input)
            assert isinstance(result, dict)
            assert "active_branch" in result
            # After bug fix: should be actual branch name, not "unknown"
            assert result["active_branch"] != "unknown"
            assert isinstance(result["active_branch"], str)


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
