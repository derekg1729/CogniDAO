#!/usr/bin/env python3
"""
Unit Test for DoltStatus Validation Error Fix

This test validates that the Pydantic models work correctly and demonstrates
the validation error that would have occurred before the fix.

Before the fix: Error handlers used 'current_branch' causing validation errors
After the fix: Error handlers use 'active_branch' matching the Pydantic model
"""

import pytest
from pydantic import ValidationError
from datetime import datetime

# Import the Pydantic models directly
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from infra_core.memory_system.tools.agent_facing.dolt_repo_tool import (
    DoltStatusOutput,
    DoltAutoCommitOutput,
    DoltListBranchesOutput,
    DoltDiffOutput,
)


class TestDoltValidationFix:
    """Test suite for Dolt tool validation error fix"""

    def test_dolt_status_output_requires_active_branch(self):
        """
        Test that DoltStatusOutput model requires 'active_branch' field

        This demonstrates the validation error that occurred before the fix.
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
        # This is exactly what was happening in the error handlers before the fix
        with pytest.raises(ValidationError) as exc_info:
            DoltStatusOutput(
                success=False,
                # active_branch missing! (error handlers used 'current_branch')
                is_clean=False,
                total_changes=0,
                message="Status check failed",
            )

        # Verify the validation error mentions 'active_branch'
        error_str = str(exc_info.value)
        assert "active_branch" in error_str
        assert "Field required" in error_str

    def test_dolt_status_error_response_structure(self):
        """
        Test that error responses can be created with correct field names

        This simulates what our fixed error handlers now do.
        """
        # This is what our FIXED error handler creates
        error_response = DoltStatusOutput(
            success=False,
            active_branch="unknown",  # This is the fix!
            is_clean=False,
            total_changes=0,
            message="Status check failed: simulated error",
            error="simulated error",
        )

        # Should serialize to JSON without issues
        json_data = error_response.model_dump()
        assert json_data["success"] is False
        assert json_data["active_branch"] == "unknown"
        assert "Status check failed" in json_data["message"]

    def test_all_dolt_outputs_have_active_branch_field(self):
        """
        Test that all Dolt output models have the active_branch field

        This ensures consistency across all Dolt tools.
        """
        # Test DoltAutoCommitOutput
        auto_commit_output = DoltAutoCommitOutput(
            success=False,
            message="Auto commit failed",
            operations_performed=["failed"],
            was_clean=False,
            active_branch="unknown",  # This field was also fixed
            error="simulated error",
        )
        assert auto_commit_output.active_branch == "unknown"

        # Test DoltListBranchesOutput
        list_branches_output = DoltListBranchesOutput(
            success=False,
            active_branch="unknown",  # This field was also fixed
            message="Branch listing failed",
            error="simulated error",
        )
        assert list_branches_output.active_branch == "unknown"

        # Test DoltDiffOutput
        diff_output = DoltDiffOutput(
            success=False,
            diff_summary=[],
            message="Diff failed",
            active_branch="unknown",  # This field was also fixed
            error="simulated error",
        )
        assert diff_output.active_branch == "unknown"

    def test_validation_error_reproduction(self):
        """
        Reproduce the exact validation error from the flow logs

        This test reproduces the error message:
        "1 validation error for DoltStatusOutput active_branch Field required"
        """
        # This reproduces the exact error that was happening
        with pytest.raises(ValidationError) as exc_info:
            # Simulate what the error handler was doing before the fix
            error_data = {
                "success": False,
                "current_branch": "unknown",  # WRONG FIELD NAME!
                "is_clean": False,
                "total_changes": 0,
                "message": "Status check failed",
                "error": "simulated error",
                "timestamp": datetime.now(),
            }

            # Try to create DoltStatusOutput with wrong field name
            DoltStatusOutput(**error_data)

        # Verify this is the exact error from the logs
        error_str = str(exc_info.value)
        assert "1 validation error for DoltStatusOutput" in error_str
        assert "active_branch" in error_str
        assert "Field required" in error_str

    def test_fixed_error_handler_simulation(self):
        """
        Test that the fixed error handler approach works

        This simulates what our fixed MCP tools now do.
        """
        # Simulate what the FIXED error handler does
        try:
            # Simulate an exception in the tool
            raise Exception("Simulated database error")
        except Exception as e:
            # This is what our FIXED error handler creates
            error_response = DoltStatusOutput(
                success=False,
                active_branch="unknown",  # CORRECT FIELD NAME!
                is_clean=False,
                total_changes=0,
                message=f"Status check failed: {str(e)}",
                error=str(e),
            )

            # Should work without validation errors
            json_result = error_response.model_dump(mode="json")
            assert json_result["success"] is False
            assert json_result["active_branch"] == "unknown"
            assert "Simulated database error" in json_result["message"]


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
