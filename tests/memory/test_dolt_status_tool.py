"""
Test for DoltStatus tool - specifically testing the bug where status changes are not properly detected.

This test file follows TDD approach to expose and fix the bug where dolt_status_tool
always reports clean state even when database has uncommitted changes.
"""

import pytest
from unittest.mock import MagicMock, patch

from infra_core.memory_system.tools.agent_facing.dolt_repo_tool import (
    dolt_status_tool,
    DoltStatusInput,
)
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

# Mock data paths
MOCK_CHROMA_PATH = "/mock/chroma/path"
MOCK_COLLECTION = "mock_collection"


@pytest.fixture
def mock_memory_bank():
    """Create a mock StructuredMemoryBank with mocked DoltMySQLWriter."""
    with (
        patch("infra_core.memory_system.structured_memory_bank.LlamaMemory"),
        patch(
            "infra_core.memory_system.structured_memory_bank.DoltMySQLWriter"
        ) as mock_writer_class,
        patch("infra_core.memory_system.structured_memory_bank.DoltMySQLReader"),
    ):
        # Create mock writer instance
        mock_writer = MagicMock()
        mock_writer_class.return_value = mock_writer

        # Create mock config
        mock_config = DoltConnectionConfig(
            host="localhost", port=3306, user="root", password="", database="test_db"
        )

        # Create memory bank instance
        memory_bank = StructuredMemoryBank(
            chroma_path=MOCK_CHROMA_PATH,
            chroma_collection=MOCK_COLLECTION,
            dolt_connection_config=mock_config,
            auto_commit=False,
        )

        yield memory_bank, mock_writer


class TestDoltStatusToolBugFix:
    """TDD test class for DoltStatus tool bug - status changes not detected."""

    def test_status_detects_unstaged_changes(self, mock_memory_bank):
        """
        TDD TEST: DoltStatus should detect unstaged changes and report them correctly.

        This test exposes the bug where dolt_status_tool ignores actual database status.
        Currently FAILS because status processing logic is incomplete.
        Should PASS after implementation is fixed.
        """
        memory_bank, mock_writer = mock_memory_bank

        # Mock all queries with correct return values for each call sequence
        def mock_execute_query(query):
            if "active_branch()" in query:
                return [{"branch": "main"}]
            elif "dolt_status" in query:
                return [
                    {"table_name": "block_proofs", "staged": 0, "status": "modified"},
                    {"table_name": "memory_blocks", "staged": 1, "status": "modified"},
                ]
            else:
                return [{"test": 1}]  # Default test query result

        mock_writer._execute_query.side_effect = mock_execute_query

        # Execute status tool
        input_data = DoltStatusInput()
        result = dolt_status_tool(input_data, memory_bank)

        # CRITICAL ASSERTIONS - These should pass but currently FAIL due to bug
        assert result.success is True, "Status tool should execute successfully"

        # This is the main bug - these assertions FAIL because processing logic is missing
        assert result.is_clean is False, "Should detect changes exist"
        assert "block_proofs" in result.unstaged_tables, (
            "Should detect unstaged block_proofs changes"
        )
        assert "memory_blocks" in result.staged_tables, "Should detect staged memory_blocks changes"
        assert result.total_changes == 2, "Should count 2 total changes"

        # Status message should reflect changes
        assert "2 changes" in result.message, "Message should indicate number of changes"

    def test_status_detects_clean_state(self, mock_memory_bank):
        """
        TDD TEST: DoltStatus should correctly detect truly clean state.

        This test verifies the tool works correctly when there are no changes.
        """
        memory_bank, mock_writer = mock_memory_bank

        # Mock current branch query and empty status
        mock_writer._execute_query.side_effect = [
            [{"branch": "main"}],  # Current branch query
            [],  # Empty dolt_status query result - no changes
        ]

        # Execute status tool
        input_data = DoltStatusInput()
        result = dolt_status_tool(input_data, memory_bank)

        # These should pass - clean state detection should work
        assert result.success is True
        assert result.is_clean is True
        assert len(result.unstaged_tables) == 0
        assert len(result.staged_tables) == 0
        assert result.total_changes == 0
        assert "Working tree clean" in result.message

    def test_status_handles_different_change_types(self, mock_memory_bank):
        """
        TDD TEST: DoltStatus should handle various types of changes correctly.

        Tests the tool's ability to categorize different status types.
        """
        memory_bank, mock_writer = mock_memory_bank

        # Mock complex status result with various change types
        def mock_execute_query(query):
            if "active_branch()" in query:
                return [{"branch": "feature-branch"}]
            elif "dolt_status" in query:
                return [
                    {
                        "table_name": "table1",
                        "staged": 1,
                        "status": "modified",
                    },  # Staged modification
                    {
                        "table_name": "table2",
                        "staged": 0,
                        "status": "modified",
                    },  # Unstaged modification
                    {"table_name": "table3", "staged": 1, "status": "added"},  # Staged addition
                    {"table_name": "table4", "staged": 0, "status": "deleted"},  # Unstaged deletion
                ]
            else:
                return [{"test": 1}]

        mock_writer._execute_query.side_effect = mock_execute_query

        # Execute status tool
        input_data = DoltStatusInput()
        result = dolt_status_tool(input_data, memory_bank)

        # Verify correct categorization
        assert result.active_branch == "feature-branch"
        assert result.is_clean is False

        # Verify staged changes
        expected_staged = ["table1", "table3"]
        assert set(result.staged_tables) == set(expected_staged), (
            f"Expected staged: {expected_staged}, got: {result.staged_tables}"
        )

        # Verify unstaged changes
        expected_unstaged = ["table2", "table4"]
        assert set(result.unstaged_tables) == set(expected_unstaged), (
            f"Expected unstaged: {expected_unstaged}, got: {result.unstaged_tables}"
        )

        assert result.total_changes == 4
