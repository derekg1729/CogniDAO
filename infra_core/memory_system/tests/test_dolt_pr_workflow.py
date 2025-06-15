"""
Tests for Dolt PR workflow tools (CreatePullRequest, Merge, CompareBranches).

These tests specifically target the new PR functionality and expose known issues:
- @dolt_tool decorator error handling bugs
- Security validation gaps
- Integration issues between tools
"""

import pytest
from unittest.mock import MagicMock, patch

from infra_core.memory_system.tools.agent_facing.dolt_repo_tool import (
    dolt_create_pull_request_tool,
    DoltCreatePullRequestInput,
    dolt_merge_tool,
    DoltMergeInput,
    dolt_compare_branches_tool,
    DoltCompareBranchesInput,
    validate_branch_name,
)


class TestDoltCompareBranchesTool:
    """Test branch comparison functionality."""

    def test_successful_branch_comparison_with_differences(self, mock_memory_bank):
        """Test successful branch comparison that finds differences."""
        # Use the mock_memory_bank fixture from conftest.py
        memory_bank = mock_memory_bank

        # Mock diff summary with differences
        mock_diff_data = [
            {
                "to_table_name": "memory_blocks",
                "diff_type": "modified",
                "data_change": True,
                "schema_change": False,
            },
            {
                "to_table_name": "block_properties",
                "diff_type": "modified",
                "data_change": True,
                "schema_change": False,
            },
        ]
        memory_bank.dolt_reader.get_diff_summary.return_value = mock_diff_data

        # Prepare input
        input_data = DoltCompareBranchesInput(source_branch="feature-branch", target_branch="main")

        # Execute tool
        result = dolt_compare_branches_tool(input_data, memory_bank)

        # Verify results
        assert result.success is True
        assert result.has_differences is True
        assert result.can_merge is True  # No schema conflicts
        assert len(result.diff_summary) == 2
        assert result.diff_summary[0].table_name == "memory_blocks"
        assert result.diff_summary[0].diff_type == "modified"
        assert "Found 2 table(s) with differences" in result.message

        # Verify mock calls
        memory_bank.dolt_reader.get_diff_summary.assert_called_once_with(
            from_revision="main", to_revision="feature-branch"
        )

    def test_successful_branch_comparison_no_differences(self, mock_memory_bank):
        """Test successful branch comparison with no differences."""
        memory_bank = mock_memory_bank

        # Mock empty diff summary
        memory_bank.dolt_reader.get_diff_summary.return_value = []

        # Prepare input
        input_data = DoltCompareBranchesInput(source_branch="feature-branch", target_branch="main")

        # Execute tool
        result = dolt_compare_branches_tool(input_data, memory_bank)

        # Verify results
        assert result.success is True
        assert result.has_differences is False
        assert result.can_merge is True
        assert len(result.diff_summary) == 0
        assert "No differences found" in result.message

    def test_branch_comparison_with_schema_conflicts(self, mock_memory_bank):
        """Test branch comparison that detects potential merge conflicts."""
        memory_bank = mock_memory_bank

        # Mock diff with schema changes (potential conflicts)
        mock_diff_data = [
            {
                "to_table_name": "memory_blocks",
                "diff_type": "modified",
                "data_change": True,
                "schema_change": True,  # This should trigger can_merge = False
            }
        ]
        memory_bank.dolt_reader.get_diff_summary.return_value = mock_diff_data

        # Prepare input
        input_data = DoltCompareBranchesInput(
            source_branch="breaking-changes", target_branch="main"
        )

        # Execute tool
        result = dolt_compare_branches_tool(input_data, memory_bank)

        # Verify results
        assert result.success is True
        assert result.has_differences is True
        assert result.can_merge is False  # Schema conflicts detected
        assert "potential merge conflicts detected" in result.message

    def test_branch_comparison_diff_failure(self, mock_memory_bank):
        """Test branch comparison when diff operation fails."""
        memory_bank = mock_memory_bank

        # Mock diff failure
        memory_bank.dolt_reader.get_diff_summary.side_effect = Exception("Branch not found")

        # Prepare input
        input_data = DoltCompareBranchesInput(
            source_branch="nonexistent-branch", target_branch="main"
        )

        # Execute tool
        result = dolt_compare_branches_tool(input_data, memory_bank)

        # Verify results
        assert result.success is False
        assert result.has_differences is False
        assert result.can_merge is False
        assert "Failed to get diff summary" in result.message
        assert "Branch not found" in result.error


class TestDoltCreatePullRequestTool:
    """Test pull request creation functionality."""

    def test_successful_pr_creation_no_auto_merge(self, mock_memory_bank):
        """Test successful PR creation without auto-merge."""
        memory_bank = mock_memory_bank

        # Mock successful branch comparison
        with patch(
            "infra_core.memory_system.tools.agent_facing.dolt_repo_tool.dolt_compare_branches_tool"
        ) as mock_compare:
            mock_compare_result = MagicMock()
            mock_compare_result.success = True
            mock_compare_result.can_merge = True
            mock_compare.return_value = mock_compare_result

            # Prepare input
            input_data = DoltCreatePullRequestInput(
                source_branch="feature-branch",
                target_branch="main",
                title="Add new feature",
                description="This PR adds a new feature",
                auto_merge=False,
            )

            # Execute tool
            result = dolt_create_pull_request_tool(input_data, memory_bank)

            # Verify results
            assert result.success is True
            assert result.pr_id is not None
            assert result.pr_id.startswith("pr-feature-branch-main-")
            assert result.source_branch == "feature-branch"
            assert result.target_branch == "main"
            assert result.title == "Add new feature"
            assert result.can_auto_merge is True
            assert result.conflicts == 0
            assert "created successfully" in result.message

    def test_pr_creation_compare_failure(self, mock_memory_bank):
        """Test PR creation when branch comparison fails."""
        memory_bank = mock_memory_bank

        # Mock failed branch comparison
        with patch(
            "infra_core.memory_system.tools.agent_facing.dolt_repo_tool.dolt_compare_branches_tool"
        ) as mock_compare:
            mock_compare_result = MagicMock()
            mock_compare_result.success = False
            mock_compare_result.error = "Branch not found"
            mock_compare.return_value = mock_compare_result

            # Prepare input
            input_data = DoltCreatePullRequestInput(
                source_branch="nonexistent-branch", target_branch="main", title="This will fail"
            )

            # Execute tool
            result = dolt_create_pull_request_tool(input_data, memory_bank)

            # Verify results
            assert result.success is False
            assert result.can_auto_merge is False
            assert "Failed to compare branches" in result.message
            assert "Branch not found" in result.error


class TestDoltMergeTool:
    """Test merge functionality and expose decorator bugs."""

    def test_successful_merge_basic(self, mock_memory_bank):
        """Test successful basic merge operation."""
        memory_bank = mock_memory_bank

        # Mock successful merge via persistent connection
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"hash": "merge123abc", "fast_forward": 0, "conflicts": 0}
        ]
        memory_bank.dolt_writer._persistent_connection = MagicMock()
        memory_bank.dolt_writer._persistent_connection.cursor.return_value = mock_cursor
        memory_bank.dolt_writer._use_persistent = True

        # Prepare input
        input_data = DoltMergeInput(source_branch="feature-branch", target_branch="main")

        # Execute tool
        result = dolt_merge_tool(input_data, memory_bank)

        # Verify results
        assert result.success is True
        assert result.merge_hash == "merge123abc"
        assert result.source_branch == "feature-branch"
        assert result.target_branch == "main"
        assert result.fast_forward is False
        assert result.conflicts == 0
        assert "Successfully merged" in result.message

        # Verify SQL execution
        mock_cursor.execute.assert_called_once_with("CALL DOLT_MERGE(%s)", ("feature-branch",))

    def test_merge_with_conflicts(self, mock_memory_bank):
        """Test merge operation that results in conflicts."""
        memory_bank = mock_memory_bank

        # Mock merge with conflicts
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "hash": None,
                "fast_forward": 0,
                "conflicts": 3,  # Conflicts detected
            }
        ]
        memory_bank.dolt_writer._persistent_connection = MagicMock()
        memory_bank.dolt_writer._persistent_connection.cursor.return_value = mock_cursor
        memory_bank.dolt_writer._use_persistent = True

        # Prepare input
        input_data = DoltMergeInput(source_branch="conflicting-branch")

        # Execute tool
        result = dolt_merge_tool(input_data, memory_bank)

        # Verify results
        assert result.success is False
        assert result.conflicts == 3
        assert result.merge_hash is None
        assert "3 conflicts that need resolution" in result.message
        assert result.error_code == "MERGE_CONFLICTS"

    def test_merge_sql_exception_exposes_decorator_bug(self, mock_memory_bank):
        """Test merge when SQL execution fails - exposes decorator error handling bug."""
        memory_bank = mock_memory_bank

        # Mock SQL execution failure
        memory_bank.dolt_writer._persistent_connection = MagicMock()
        memory_bank.dolt_writer._persistent_connection.cursor.side_effect = Exception(
            "SQL connection failed"
        )
        memory_bank.dolt_writer._use_persistent = True

        # Prepare input
        input_data = DoltMergeInput(source_branch="feature-branch")

        # Execute tool - this should expose the decorator exception handling bug
        result = dolt_merge_tool(input_data, memory_bank)

        # The bug: @dolt_tool decorator tries to create DoltMergeOutput in exception handler
        # but doesn't provide required fields, causing Pydantic validation error
        # This test documents what SHOULD happen vs what actually happens
        assert result.success is False
        assert "SQL connection failed" in result.message or "SQL connection failed" in str(
            result.error
        )


class TestSecurityValidation:
    """Test security validation functions."""

    def test_valid_branch_names(self):
        """Test that valid branch names pass validation."""
        valid_names = [
            "main",
            "feature-branch",
            "feature_branch",
            "feature/new-thing",
            "hotfix123",
            "release-v1.0.0",
            "user/derek/feature",
        ]

        for name in valid_names:
            # Should not raise exception
            result = validate_branch_name(name)
            assert result == name

    def test_invalid_branch_names(self):
        """Test that invalid branch names are rejected."""
        invalid_names = [
            "branch with spaces",
            "branch;DROP TABLE users;",
            "branch'OR'1'='1",
            "branch$(whoami)",
            "branch`rm -rf /`",
            "branch|cat /etc/passwd",
            "branch&& rm -rf /",
            "branch<script>alert('xss')</script>",
            "",  # Empty string
            "branch\nwith\nnewlines",
            "branch\twith\ttabs",
        ]

        for name in invalid_names:
            with pytest.raises(ValueError, match="Invalid branch name"):
                validate_branch_name(name)


class TestIntegrationIssues:
    """Test integration issues between tools."""

    def test_pr_workflow_integration(self, mock_memory_bank):
        """Test full PR workflow integration to expose coordination issues."""
        memory_bank = mock_memory_bank

        # Mock successful comparison
        with patch(
            "infra_core.memory_system.tools.agent_facing.dolt_repo_tool.dolt_compare_branches_tool"
        ) as mock_compare:
            mock_compare_result = MagicMock()
            mock_compare_result.success = True
            mock_compare_result.can_merge = True
            mock_compare.return_value = mock_compare_result

            # Mock successful merge for auto-merge PR
            with patch(
                "infra_core.memory_system.tools.agent_facing.dolt_repo_tool.dolt_merge_tool"
            ) as mock_merge:
                mock_merge_result = MagicMock()
                mock_merge_result.success = True
                mock_merge_result.merge_hash = "integration123"
                mock_merge.return_value = mock_merge_result

                # Create PR with auto-merge
                pr_input = DoltCreatePullRequestInput(
                    source_branch="test-integration",
                    target_branch="main",
                    title="Integration test PR",
                    auto_merge=True,
                )

                result = dolt_create_pull_request_tool(pr_input, memory_bank)

                # Verify the integration worked
                assert result.success is True
                assert "auto-merged successfully" in result.message

                # Verify both tools were called
                mock_compare.assert_called_once()
                mock_merge.assert_called_once()

    def test_concurrent_merge_operations_issue(self, mock_memory_bank):
        """Test that exposes the lack of concurrency controls."""
        memory_bank = mock_memory_bank

        # Mock successful merge
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [{"hash": "race123", "fast_forward": 0, "conflicts": 0}]
        memory_bank.dolt_writer._persistent_connection = MagicMock()
        memory_bank.dolt_writer._persistent_connection.cursor.return_value = mock_cursor
        memory_bank.dolt_writer._use_persistent = True

        # Simulate concurrent merge operations
        input1 = DoltMergeInput(source_branch="feature1")
        input2 = DoltMergeInput(source_branch="feature2")

        # Both should succeed but this exposes the race condition issue
        result1 = dolt_merge_tool(input1, memory_bank)
        result2 = dolt_merge_tool(input2, memory_bank)

        # Both succeed but in reality this could cause data corruption
        assert result1.success is True
        assert result2.success is True

        # This test documents that we need advisory locking or queuing
        # TODO: Add SELECT GET_LOCK() or similar mechanism
