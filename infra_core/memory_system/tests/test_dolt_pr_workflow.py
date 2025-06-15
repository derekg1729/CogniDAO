"""
Tests for Dolt PR workflow tools (CreatePullRequest, Merge, CompareBranches).

These tests specifically target the new PR functionality and expose known issues:
- @dolt_tool decorator error handling bugs
- Security validation gaps
- Integration issues between tools
"""

import pytest
from unittest.mock import MagicMock, patch, call

from infra_core.memory_system.tools.agent_facing.dolt_repo_tool import (
    dolt_create_pull_request_tool,
    DoltCreatePullRequestInput,
    dolt_merge_tool,
    DoltMergeInput,
    dolt_compare_branches_tool,
    DoltCompareBranchesInput,
    validate_branch_name,
    dolt_approve_pull_request_tool,
    DoltApprovePullRequestInput,
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


class TestDoltApprovePullRequestTool:
    """Test pull request approval functionality via DoltHub API."""

    def test_successful_pr_approval(self, mock_memory_bank):
        """Test successful PR approval and merge via DoltHub API."""
        memory_bank = mock_memory_bank

        # Mock DoltHub configuration
        memory_bank.dolt_writer.remote_url = "https://doltremoteapi.dolthub.com/testowner/testdb"
        memory_bank.dolt_writer.api_token = "test_token_123"
        memory_bank.dolt_writer.active_branch = "main"

        # Mock successful API response
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "operation_name": "merge_op_123",
                "merge_hash": "abc123def456",
            }
            mock_post.return_value = mock_response

            # Prepare input
            input_data = DoltApprovePullRequestInput(
                pr_id="pr-feature-main-123456789", approve_message="LGTM - approving this PR"
            )

            # Execute tool
            result = dolt_approve_pull_request_tool(input_data, memory_bank)

            # Verify results
            assert result.success is True
            assert result.pr_id == "pr-feature-main-123456789"
            assert result.merge_hash == "abc123def456"
            assert result.operation_name == "merge_op_123"
            assert "Successfully approved and merged" in result.message
            assert result.active_branch == "main"

            # Verify API call
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "testowner/testdb/pulls/pr-feature-main-123456789/merge" in call_args[0][0]
            assert call_args[1]["headers"]["authorization"] == "token test_token_123"

    def test_pr_approval_api_authentication_failure(self, mock_memory_bank):
        """Test PR approval with invalid API token."""
        memory_bank = mock_memory_bank

        # Mock DoltHub configuration with invalid token
        memory_bank.dolt_writer.remote_url = "https://doltremoteapi.dolthub.com/testowner/testdb"
        memory_bank.dolt_writer.api_token = "invalid_token"
        memory_bank.dolt_writer.active_branch = "main"

        # Mock 401 Unauthorized response
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized: Invalid token"
            mock_post.return_value = mock_response

            # Prepare input
            input_data = DoltApprovePullRequestInput(pr_id="pr-feature-main-123456789")

            # Execute tool
            result = dolt_approve_pull_request_tool(input_data, memory_bank)

            # Verify results
            assert result.success is False
            assert result.pr_id == "pr-feature-main-123456789"
            assert result.merge_hash is None
            assert "DoltHub API error: 401" in result.message
            assert "Unauthorized: Invalid token" in result.error
            assert result.error_code == "API_ERROR"

    def test_pr_approval_network_failure(self, mock_memory_bank):
        """Test PR approval with network connection failure."""
        memory_bank = mock_memory_bank

        # Mock DoltHub configuration
        memory_bank.dolt_writer.remote_url = "https://doltremoteapi.dolthub.com/testowner/testdb"
        memory_bank.dolt_writer.api_token = "test_token_123"
        memory_bank.dolt_writer.active_branch = "main"

        # Mock network failure
        with patch("requests.post") as mock_post:
            mock_post.side_effect = Exception("Connection timeout")

            # Prepare input
            input_data = DoltApprovePullRequestInput(pr_id="pr-feature-main-123456789")

            # Execute tool
            result = dolt_approve_pull_request_tool(input_data, memory_bank)

            # Verify results
            assert result.success is False
            assert result.pr_id == "pr-feature-main-123456789"
            assert "Failed to approve PR" in result.message
            assert "Connection timeout" in result.error
            assert result.error_code == "EXCEPTION"

    def test_pr_approval_invalid_pr_id(self, mock_memory_bank):
        """Test PR approval with non-existent PR ID."""
        memory_bank = mock_memory_bank

        # Mock DoltHub configuration
        memory_bank.dolt_writer.remote_url = "https://doltremoteapi.dolthub.com/testowner/testdb"
        memory_bank.dolt_writer.api_token = "test_token_123"
        memory_bank.dolt_writer.active_branch = "main"

        # Mock 404 Not Found response
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.text = "Pull request not found"
            mock_post.return_value = mock_response

            # Prepare input
            input_data = DoltApprovePullRequestInput(pr_id="pr-nonexistent-123")

            # Execute tool
            result = dolt_approve_pull_request_tool(input_data, memory_bank)

            # Verify results
            assert result.success is False
            assert result.pr_id == "pr-nonexistent-123"
            assert "DoltHub API error: 404" in result.message
            assert "Pull request not found" in result.error

    def test_pr_approval_missing_remote_url(self, mock_memory_bank):
        """Test PR approval when remote URL is not configured."""
        memory_bank = mock_memory_bank

        # Mock missing remote URL
        memory_bank.dolt_writer.remote_url = None
        memory_bank.dolt_writer.active_branch = "main"

        # Prepare input
        input_data = DoltApprovePullRequestInput(pr_id="pr-feature-main-123456789")

        # Execute tool
        result = dolt_approve_pull_request_tool(input_data, memory_bank)

        # Verify results
        assert result.success is False
        assert result.pr_id == "pr-feature-main-123456789"
        assert "No remote URL configured" in result.error
        assert result.error_code == "EXCEPTION"

    def test_pr_approval_missing_api_token(self, mock_memory_bank):
        """Test PR approval when API token is not configured."""
        memory_bank = mock_memory_bank

        # Mock missing API token
        memory_bank.dolt_writer.remote_url = "https://doltremoteapi.dolthub.com/testowner/testdb"
        memory_bank.dolt_writer.api_token = None
        memory_bank.dolt_writer.active_branch = "main"

        # Prepare input
        input_data = DoltApprovePullRequestInput(pr_id="pr-feature-main-123456789")

        # Execute tool
        result = dolt_approve_pull_request_tool(input_data, memory_bank)

        # Verify results
        assert result.success is False
        assert result.pr_id == "pr-feature-main-123456789"
        assert "No DoltHub API token configured" in result.error
        assert result.error_code == "EXCEPTION"

    def test_pr_approval_unsupported_remote_url(self, mock_memory_bank):
        """Test PR approval with unsupported remote URL format."""
        memory_bank = mock_memory_bank

        # Mock unsupported remote URL
        memory_bank.dolt_writer.remote_url = "https://github.com/user/repo.git"
        memory_bank.dolt_writer.api_token = "test_token_123"
        memory_bank.dolt_writer.active_branch = "main"

        # Prepare input
        input_data = DoltApprovePullRequestInput(pr_id="pr-feature-main-123456789")

        # Execute tool
        result = dolt_approve_pull_request_tool(input_data, memory_bank)

        # Verify results
        assert result.success is False
        assert result.pr_id == "pr-feature-main-123456789"
        assert "Unsupported remote URL format" in result.error
        assert result.error_code == "EXCEPTION"


class TestEnhancedMergeGatingLogic:
    """Test the enhanced merge tool gating logic for multi-commit scenarios."""

    def test_single_commit_merge_allowed(self, mock_memory_bank):
        """Test that single-commit merges are allowed through gating logic."""
        memory_bank = mock_memory_bank

        # Mock single-commit scenario (only one table changed)
        with patch(
            "infra_core.memory_system.tools.agent_facing.dolt_repo_tool.dolt_compare_branches_tool"
        ) as mock_compare:
            mock_compare_result = MagicMock()
            mock_compare_result.success = True
            mock_compare_result.has_differences = True
            mock_compare_result.diff_summary = [{"table_name": "memory_blocks"}]  # Single table
            mock_compare.return_value = mock_compare_result

            # Mock successful merge execution
            memory_bank.dolt_writer._execute_query.return_value = [
                {"hash": "single123", "fast_forward": 1, "conflicts": 0}
            ]

            # Prepare input (without force_multi_commit flag)
            input_data = DoltMergeInput(source_branch="single-commit-branch", target_branch="main")

            # Execute tool
            result = dolt_merge_tool(input_data, memory_bank)

            # Verify merge was allowed and succeeded
            assert result.success is True
            assert result.merge_hash == "single123"
            assert result.fast_forward is True
            assert "Successfully merged" in result.message

    def test_multi_commit_merge_blocked(self, mock_memory_bank):
        """Test that multi-commit merges are blocked by gating logic."""
        memory_bank = mock_memory_bank

        # Mock multi-commit scenario (multiple tables changed)
        with patch(
            "infra_core.memory_system.tools.agent_facing.dolt_repo_tool.dolt_compare_branches_tool"
        ) as mock_compare:
            mock_compare_result = MagicMock()
            mock_compare_result.success = True
            mock_compare_result.has_differences = True
            mock_compare_result.diff_summary = [
                {"table_name": "memory_blocks"},
                {"table_name": "block_properties"},  # Multiple tables = multi-commit
            ]
            mock_compare.return_value = mock_compare_result

            # Prepare input (without force_multi_commit flag)
            input_data = DoltMergeInput(source_branch="multi-commit-branch", target_branch="main")

            # Execute tool
            result = dolt_merge_tool(input_data, memory_bank)

            # Verify merge was blocked
            assert result.success is False
            assert result.error_code == "MERGE_NOT_FAST_FORWARD"
            assert "Multi-commit merge detected" in result.message
            assert "Use dolt_approve_pull_request_tool" in result.message

    def test_gating_logic_compare_failure(self, mock_memory_bank):
        """Test gating logic when branch comparison fails."""
        memory_bank = mock_memory_bank

        # Mock failed branch comparison
        with patch(
            "infra_core.memory_system.tools.agent_facing.dolt_repo_tool.dolt_compare_branches_tool"
        ) as mock_compare:
            mock_compare_result = MagicMock()
            mock_compare_result.success = False
            mock_compare_result.error = "Branch comparison failed"
            mock_compare.return_value = mock_compare_result

            # Prepare input
            input_data = DoltMergeInput(source_branch="problematic-branch", target_branch="main")

            # Execute tool
            result = dolt_merge_tool(input_data, memory_bank)

            # Verify merge was blocked due to comparison failure
            assert result.success is False
            assert result.error_code == "MERGE_SAFETY_CHECK_FAILED"
            assert "Cannot compare branches for merge safety check" in result.message

    def test_force_multi_commit_bypasses_gating(self, mock_memory_bank):
        """Test that force_multi_commit flag bypasses gating logic."""
        memory_bank = mock_memory_bank

        # Mock successful merge execution (gating should be bypassed)
        memory_bank.dolt_writer._execute_query.return_value = [
            {"hash": "forced123", "fast_forward": 0, "conflicts": 0}
        ]

        # Prepare input with force flag
        input_data = DoltMergeInput(
            source_branch="multi-commit-branch",
            target_branch="main",
            force_multi_commit=True,  # This should bypass gating
        )

        # Execute tool
        result = dolt_merge_tool(input_data, memory_bank)

        # Verify merge proceeded without gating checks
        assert result.success is True
        assert result.merge_hash == "forced123"
        assert "Successfully merged" in result.message


class TestEndToEndWorkflows:
    """Test complete end-to-end PR workflows."""

    def test_complete_pr_workflow_success(self, mock_memory_bank):
        """Test complete PR workflow: Create → Approve → Success."""
        memory_bank = mock_memory_bank

        # Setup DoltHub configuration
        memory_bank.dolt_writer.remote_url = "https://doltremoteapi.dolthub.com/testowner/testdb"
        memory_bank.dolt_writer.api_token = "test_token_123"
        memory_bank.dolt_writer.active_branch = "main"

        # Step 1: Create PR
        with patch(
            "infra_core.memory_system.tools.agent_facing.dolt_repo_tool.dolt_compare_branches_tool"
        ) as mock_compare:
            mock_compare_result = MagicMock()
            mock_compare_result.success = True
            mock_compare_result.can_merge = True
            mock_compare.return_value = mock_compare_result

            pr_input = DoltCreatePullRequestInput(
                source_branch="feature-complete-workflow",
                target_branch="main",
                title="Complete workflow test",
                auto_merge=False,
            )

            pr_result = dolt_create_pull_request_tool(pr_input, memory_bank)

            # Verify PR creation
            assert pr_result.success is True
            pr_id = pr_result.pr_id

        # Step 2: Approve PR
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "operation_name": "workflow_merge_123",
                "merge_hash": "workflow123abc",
            }
            mock_post.return_value = mock_response

            approve_input = DoltApprovePullRequestInput(
                pr_id=pr_id, approve_message="End-to-end workflow test approval"
            )

            approve_result = dolt_approve_pull_request_tool(approve_input, memory_bank)

            # Verify PR approval
            assert approve_result.success is True
            assert approve_result.pr_id == pr_id
            assert approve_result.merge_hash == "workflow123abc"

        # Verify complete workflow success
        assert pr_result.success and approve_result.success

    def test_pr_workflow_with_approval_failure_recovery(self, mock_memory_bank):
        """Test PR workflow recovery when approval fails."""
        memory_bank = mock_memory_bank

        # Setup DoltHub configuration
        memory_bank.dolt_writer.remote_url = "https://doltremoteapi.dolthub.com/testowner/testdb"
        memory_bank.dolt_writer.api_token = "test_token_123"
        memory_bank.dolt_writer.active_branch = "main"

        # Step 1: Create PR successfully
        with patch(
            "infra_core.memory_system.tools.agent_facing.dolt_repo_tool.dolt_compare_branches_tool"
        ) as mock_compare:
            mock_compare_result = MagicMock()
            mock_compare_result.success = True
            mock_compare_result.can_merge = True
            mock_compare.return_value = mock_compare_result

            pr_input = DoltCreatePullRequestInput(
                source_branch="feature-recovery-test",
                target_branch="main",
                title="Recovery workflow test",
            )

            pr_result = dolt_create_pull_request_tool(pr_input, memory_bank)
            assert pr_result.success is True
            pr_id = pr_result.pr_id

        # Step 2: Approval fails (network error)
        with patch("requests.post") as mock_post:
            mock_post.side_effect = Exception("Network timeout")

            approve_input = DoltApprovePullRequestInput(pr_id=pr_id)
            approve_result = dolt_approve_pull_request_tool(approve_input, memory_bank)

            # Verify approval failed
            assert approve_result.success is False
            assert "Network timeout" in approve_result.error

        # Step 3: Retry approval (simulating recovery)
        with patch("requests.post") as mock_post_retry:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "operation_name": "recovery_merge_123",
                "merge_hash": "recovery123abc",
            }
            mock_post_retry.return_value = mock_response

            retry_result = dolt_approve_pull_request_tool(approve_input, memory_bank)

            # Verify recovery succeeded
            assert retry_result.success is True
            assert retry_result.merge_hash == "recovery123abc"


class TestDoltMergeTool:
    """Test merge functionality and expose decorator bugs."""

    def test_successful_merge_basic(self, mock_memory_bank):
        """Test successful basic merge operation."""
        memory_bank = mock_memory_bank

        # Mock successful merge via _execute_query method directly
        memory_bank.dolt_writer._execute_query.return_value = [
            {"hash": "merge123abc", "fast_forward": 0, "conflicts": 0}
        ]

        # Prepare input
        input_data = DoltMergeInput(
            source_branch="feature-branch", target_branch="main", force_multi_commit=True
        )

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

        # Verify SQL execution - check that both calls were made
        calls = memory_bank.dolt_writer._execute_query.call_args_list
        assert len(calls) == 2
        assert calls[0] == call("CALL DOLT_MERGE(?)", ("feature-branch",))
        assert calls[1] == call("SELECT HASHOF('HEAD') as hash")

    def test_merge_with_conflicts(self, mock_memory_bank):
        """Test merge operation that results in conflicts."""
        memory_bank = mock_memory_bank

        # Mock merge with conflicts via _execute_query method directly
        memory_bank.dolt_writer._execute_query.return_value = [
            {
                "hash": None,
                "fast_forward": 0,
                "conflicts": 3,  # Conflicts detected
            }
        ]

        # Prepare input
        input_data = DoltMergeInput(source_branch="conflicting-branch", force_multi_commit=True)

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

        # Mock SQL execution failure via _execute_query method directly
        memory_bank.dolt_writer._execute_query.side_effect = Exception("SQL connection failed")

        # Prepare input
        input_data = DoltMergeInput(source_branch="feature-branch", force_multi_commit=True)

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

        # Mock successful merge via _execute_query method directly
        memory_bank.dolt_writer._execute_query.return_value = [
            {"hash": "race123", "fast_forward": 0, "conflicts": 0}
        ]

        # Simulate concurrent merge operations
        input1 = DoltMergeInput(source_branch="feature1", force_multi_commit=True)
        input2 = DoltMergeInput(source_branch="feature2", force_multi_commit=True)

        # Both should succeed but this exposes the race condition issue
        result1 = dolt_merge_tool(input1, memory_bank)
        result2 = dolt_merge_tool(input2, memory_bank)

        # Both succeed but in reality this could cause data corruption
        assert result1.success is True
        assert result2.success is True

        # This test documents that we need advisory locking or queuing
        # TODO: Add SELECT GET_LOCK() or similar mechanism
