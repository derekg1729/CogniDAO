"""
Test suite to expose and verify fix for block_proofs table blind spot in Dolt MCP tools.

This test demonstrates the critical bug where DoltStatus, DoltAdd, and DoltReset
tools ignore the block_proofs table, creating dangerous disconnects between
reported state and actual repository state.
"""

import pytest
from unittest.mock import Mock

from infra_core.memory_system.tools.agent_facing.dolt_repo_tool import (
    dolt_status_tool,
    dolt_add_tool,
    dolt_reset_tool,
    DoltStatusInput,
    DoltAddInput,
    DoltResetInput,
)


class TestDoltToolsBlockProofsBug:
    """Test suite exposing the block_proofs table blind spot bug."""

    def test_dolt_status_detects_block_proofs_changes(self):
        """
        FAILING TEST: DoltStatus should detect block_proofs table changes.

        This test exposes the bug where block_proofs changes are invisible
        to the MCP status tool, causing 'clean' reports when dirty.
        """
        # Mock memory bank with block_proofs changes
        mock_memory_bank = Mock()
        mock_writer = Mock()
        mock_memory_bank.dolt_writer = mock_writer
        mock_writer.active_branch = "test-branch"

        # Mock status query to return block_proofs as modified
        def mock_execute_query(query):
            if "SELECT 1 as test" in query:
                return [{"test": 1}]
            elif "active_branch()" in query:
                return [{"branch": "test-branch"}]
            elif "dolt_status" in query:
                return [{"table_name": "block_proofs", "staged": 0, "status": "modified"}]
            else:
                return []

        mock_writer._execute_query.side_effect = mock_execute_query

        input_data = DoltStatusInput()
        result = dolt_status_tool(input_data, mock_memory_bank)

        # BUG: This assertion SHOULD pass but currently FAILS
        # because block_proofs changes are detected but not processed properly
        assert not result.is_clean, "Status should show dirty when block_proofs is modified"
        assert "block_proofs" in result.unstaged_tables, "block_proofs should be in unstaged tables"
        assert result.total_changes > 0, "Should report changes when block_proofs is modified"

    def test_dolt_add_can_stage_block_proofs(self):
        """
        FAILING TEST: DoltAdd should be able to stage block_proofs table.

        This test verifies that when block_proofs is specified in tables,
        it gets properly staged.
        """
        mock_memory_bank = Mock()
        mock_writer = Mock()
        mock_memory_bank.dolt_writer = mock_writer
        mock_writer.active_branch = "test-branch"

        # Mock successful staging
        mock_writer.add_to_staging.return_value = (True, "Successfully staged block_proofs")

        # Try to add block_proofs specifically
        input_data = DoltAddInput(tables=["block_proofs"])
        result = dolt_add_tool(input_data, mock_memory_bank)

        # This should work if block_proofs is properly supported
        assert result.success, "Adding block_proofs should succeed"
        mock_writer.add_to_staging.assert_called_once_with(tables=["block_proofs"])

    def test_dolt_reset_can_reset_block_proofs(self):
        """
        FAILING TEST: DoltReset should be able to reset block_proofs table.

        This test verifies that block_proofs changes can be discarded.
        """
        mock_memory_bank = Mock()
        mock_writer = Mock()
        mock_memory_bank.dolt_writer = mock_writer
        mock_writer.active_branch = "test-branch"

        # Mock successful reset
        mock_writer.reset.return_value = (True, "Successfully reset block_proofs")

        # Try to reset block_proofs specifically
        input_data = DoltResetInput(tables=["block_proofs"], hard=True)
        result = dolt_reset_tool(input_data, mock_memory_bank)

        # This should work if block_proofs is properly supported
        assert result.success, "Resetting block_proofs should succeed"
        mock_writer.reset.assert_called_once_with(hard=True, tables=["block_proofs"])

    def test_persisted_tables_includes_block_proofs(self):
        """
        FAILING TEST: PERSISTED_TABLES should include block_proofs.

        This test exposes the root cause - block_proofs is missing
        from the PERSISTED_TABLES constant.
        """
        from infra_core.memory_system.dolt_writer import PERSISTED_TABLES

        # BUG: This assertion FAILS because block_proofs is missing
        assert "block_proofs" in PERSISTED_TABLES, (
            "block_proofs table should be included in PERSISTED_TABLES constant"
        )

        # Verify all expected tables are present
        expected_tables = ["memory_blocks", "block_properties", "block_links", "block_proofs"]
        for table in expected_tables:
            assert table in PERSISTED_TABLES, f"Table {table} should be in PERSISTED_TABLES"

    def test_dolt_commit_default_tables_includes_block_proofs(self):
        """
        FAILING TEST: Default commit should include block_proofs table.

        When no tables are specified, dolt_repo_tool uses PERSISTED_TABLES
        as the default, which should include block_proofs.
        """
        from infra_core.memory_system.tools.agent_facing.dolt_repo_tool import (
            dolt_repo_tool,
            DoltCommitInput,
        )

        mock_memory_bank = Mock()
        mock_writer = Mock()
        mock_memory_bank.dolt_writer = mock_writer
        mock_writer.active_branch = "test-branch"

        # Mock successful commit
        mock_writer.commit_changes.return_value = (True, "abc123")

        # Commit with no tables specified (should use PERSISTED_TABLES default)
        input_data = DoltCommitInput(commit_message="Test commit")
        dolt_repo_tool(input_data, mock_memory_bank)

        # Verify commit was called with PERSISTED_TABLES (which should include block_proofs)
        mock_writer.commit_changes.assert_called_once()
        call_args = mock_writer.commit_changes.call_args
        tables_committed = call_args[1]["tables"]  # keyword argument

        # BUG: This assertion FAILS because block_proofs is not in PERSISTED_TABLES
        assert "block_proofs" in tables_committed, (
            "block_proofs should be included in default commit tables"
        )

    @pytest.mark.integration
    def test_real_scenario_block_proofs_invisible(self):
        """
        Integration test demonstrating the real-world impact of the bug.

        This test simulates the exact scenario we discovered:
        - block_proofs has uncommitted changes
        - MCP tools report 'clean'
        - Pull operations fail mysteriously
        """
        # This test would require actual Dolt setup, so we'll mock it
        # but document the real scenario that led to the bug discovery

        mock_memory_bank = Mock()
        mock_writer = Mock()
        mock_memory_bank.dolt_writer = mock_writer
        mock_writer.active_branch = "ai-education-team"

        # Simulate the exact scenario: block_proofs modified, other tables clean
        def mock_execute_query_real_scenario(query):
            if "SELECT 1 as test" in query:
                return [{"test": 1}]
            elif "active_branch()" in query:
                return [{"branch": "ai-education-team"}]
            elif "dolt_status" in query:
                return [{"table_name": "block_proofs", "staged": 0, "status": "modified"}]
            else:
                return []

        mock_writer._execute_query.side_effect = mock_execute_query_real_scenario

        input_data = DoltStatusInput()
        result = dolt_status_tool(input_data, mock_memory_bank)

        # The bug: This reports clean when it should report dirty
        # Leading to failed pull operations with "cannot merge with uncommitted changes"
        assert not result.is_clean, (
            "CRITICAL BUG: Status reports clean when block_proofs has uncommitted changes, "
            "causing mysterious pull failures"
        )
