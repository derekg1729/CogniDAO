"""
Tests for the namespace_id fix in DoltMySQLWriter.write_memory_block method.

This test file specifically validates that the namespace_id field is properly
included in SQL INSERT statements and that blocks are created with the correct
namespace_id values.

Bug Fix: Previously, namespace_id was missing from the SQL INSERT statement,
causing all blocks to default to "legacy" namespace regardless of the specified
namespace_id parameter.
"""

import pytest
from unittest.mock import MagicMock, patch

from infra_core.memory_system.schemas.memory_block import MemoryBlock
from infra_core.memory_system.dolt_writer import DoltMySQLWriter
from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig


class TestDoltWriterNamespaceFix:
    """Test class for namespace_id fix in DoltMySQLWriter."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration for DoltMySQLWriter."""
        return DoltConnectionConfig(
            host="localhost",
            port=3306,
            user="test_user",
            password="test_password",
            database="test_db",
        )

    @pytest.fixture
    def sample_block_legacy_namespace(self):
        """Sample block with legacy namespace_id."""
        return MemoryBlock(
            id="test-block-legacy-001",
            namespace_id="legacy",
            type="knowledge",
            text="Test block in legacy namespace",
            tags=["test", "legacy"],
            metadata={"category": "testing"},
            created_by="test_user",
        )

    @pytest.fixture
    def sample_block_custom_namespace(self):
        """Sample block with custom namespace_id."""
        return MemoryBlock(
            id="test-block-custom-001",
            namespace_id="user-123",
            type="task",
            text="Test block in custom namespace",
            tags=["test", "custom"],
            metadata={"priority": "high"},
            created_by="test_user",
        )

    def _find_memory_blocks_insert_call(self, cursor_calls):
        """Helper to find the memory_blocks INSERT call among all SQL calls."""
        for call_args in cursor_calls:
            sql_query = call_args[0][0]
            if "REPLACE INTO memory_blocks" in sql_query:
                return call_args
        return None

    @patch("mysql.connector.connect")
    def test_namespace_id_included_in_sql_insert_legacy(
        self, mock_connect, mock_config, sample_block_legacy_namespace
    ):
        """Test that namespace_id is properly included in SQL INSERT for legacy namespace."""
        # Setup mock connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # Mock successful responses
        mock_cursor.fetchone.return_value = {"commit_hash": "test_commit_hash"}
        mock_cursor.fetchall.return_value = []

        # Create writer and execute operation
        writer = DoltMySQLWriter(mock_config)
        success, commit_hash = writer.write_memory_block(
            sample_block_legacy_namespace, branch="test-branch", auto_commit=True
        )

        # Verify success
        assert success is True
        assert commit_hash == "test_commit_hash"

        # Get the SQL query that was executed
        cursor_calls = mock_cursor.execute.call_args_list
        assert len(cursor_calls) > 0, "No SQL queries were executed"

        # Find the memory_blocks INSERT call
        memory_blocks_call = self._find_memory_blocks_insert_call(cursor_calls)
        assert memory_blocks_call is not None, "No memory_blocks INSERT call found"

        sql_query = memory_blocks_call[0][0]  # First argument is the SQL query
        sql_values = memory_blocks_call[0][1]  # Second argument is the values tuple

        # Verify namespace_id is in the SQL column list
        assert "namespace_id" in sql_query
        assert sql_query.count("namespace_id") == 1  # Should appear exactly once

        # Verify namespace_id is in the correct position (second column after id)
        expected_columns = [
            "id",
            "namespace_id",
            "type",
            "schema_version",
            "text",
            "state",
            "visibility",
            "block_version",
        ]
        for col in expected_columns:
            assert col in sql_query

        # Verify the values tuple includes namespace_id in correct position
        assert sql_values[0] == "test-block-legacy-001"  # id
        assert sql_values[1] == "legacy"  # namespace_id
        assert sql_values[2] == "knowledge"  # type

    @patch("mysql.connector.connect")
    def test_namespace_id_included_in_sql_insert_custom(
        self, mock_connect, mock_config, sample_block_custom_namespace
    ):
        """Test that namespace_id is properly included in SQL INSERT for custom namespace."""
        # Setup mock connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # Mock successful responses
        mock_cursor.fetchone.return_value = {"commit_hash": "test_commit_hash"}
        mock_cursor.fetchall.return_value = []

        # Create writer and execute operation
        writer = DoltMySQLWriter(mock_config)
        success, commit_hash = writer.write_memory_block(
            sample_block_custom_namespace, branch="test-branch", auto_commit=True
        )

        # Verify success
        assert success is True

        # Get the SQL values that were executed
        cursor_calls = mock_cursor.execute.call_args_list
        memory_blocks_call = self._find_memory_blocks_insert_call(cursor_calls)
        assert memory_blocks_call is not None, "No memory_blocks INSERT call found"

        sql_values = memory_blocks_call[0][1]

        # Verify the custom namespace_id is correctly passed
        assert sql_values[0] == "test-block-custom-001"  # id
        assert sql_values[1] == "user-123"  # namespace_id
        assert sql_values[2] == "task"  # type

    @patch("mysql.connector.connect")
    def test_sql_parameter_count_matches_placeholders(
        self, mock_connect, mock_config, sample_block_legacy_namespace
    ):
        """Test that the number of SQL parameters matches the number of placeholders."""
        # Setup mock connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # Mock successful responses
        mock_cursor.fetchone.return_value = {"commit_hash": "test_commit_hash"}
        mock_cursor.fetchall.return_value = []

        # Create writer and execute operation
        writer = DoltMySQLWriter(mock_config)
        writer.write_memory_block(
            sample_block_legacy_namespace, branch="test-branch", auto_commit=True
        )

        # Get the SQL query and values
        cursor_calls = mock_cursor.execute.call_args_list
        memory_blocks_call = self._find_memory_blocks_insert_call(cursor_calls)
        assert memory_blocks_call is not None, "No memory_blocks INSERT call found"

        sql_query = memory_blocks_call[0][0]
        sql_values = memory_blocks_call[0][1]

        # Count placeholders in SQL
        placeholder_count = sql_query.count("%s")

        # Count actual values provided
        values_count = len(sql_values)

        # They should match exactly
        assert placeholder_count == values_count, (
            f"SQL placeholder count ({placeholder_count}) doesn't match values count ({values_count}). "
            f"This indicates a mismatch in the SQL INSERT statement."
        )

    @patch("mysql.connector.connect")
    def test_namespace_id_position_in_values_tuple(
        self, mock_connect, mock_config, sample_block_custom_namespace
    ):
        """Test that namespace_id is in the correct position in the values tuple."""
        # Setup mock connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # Mock successful responses (no auto-commit)
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []

        # Create writer and execute operation
        writer = DoltMySQLWriter(mock_config)
        writer.write_memory_block(
            sample_block_custom_namespace,
            branch="test-branch",
            auto_commit=False,  # Don't auto-commit for this test
        )

        # Get the SQL values
        cursor_calls = mock_cursor.execute.call_args_list
        memory_blocks_call = self._find_memory_blocks_insert_call(cursor_calls)
        assert memory_blocks_call is not None, "No memory_blocks INSERT call found"

        sql_values = memory_blocks_call[0][1]

        # Verify key positions
        assert sql_values[0] == "test-block-custom-001"  # id (position 0)
        assert sql_values[1] == "user-123"  # namespace_id (position 1) - THIS IS THE FIX
        assert sql_values[2] == "task"  # type (position 2)
        assert sql_values[4] == "Test block in custom namespace"  # text (position 4)
        assert sql_values[14] == "test_user"  # created_by (position 14)

    @patch("mysql.connector.connect")
    def test_different_namespace_values_preserved(self, mock_connect, mock_config):
        """Test that different namespace_id values are correctly preserved."""
        test_cases = [
            ("legacy", "knowledge"),
            ("public", "doc"),
            ("user-123", "task"),
            ("org-456", "project"),
            ("team-789", "bug"),
            ("cognidao/memory-system", "epic"),
        ]

        for namespace_id, block_type in test_cases:
            # Setup fresh mock for each test case
            mock_connection = MagicMock()
            mock_cursor = MagicMock()
            mock_connection.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_connection

            # Mock successful responses
            mock_cursor.fetchone.return_value = None
            mock_cursor.fetchall.return_value = []

            # Create block with specific namespace
            block = MemoryBlock(
                id=f"test-{namespace_id}-{block_type}",
                namespace_id=namespace_id,
                type=block_type,
                text=f"Test block in {namespace_id} namespace",
                created_by="test_user",
            )

            # Create writer and execute operation
            writer = DoltMySQLWriter(mock_config)
            success, _ = writer.write_memory_block(block, branch="test-branch")
            assert success is True

            # Verify namespace_id was passed correctly
            cursor_calls = mock_cursor.execute.call_args_list
            memory_blocks_call = self._find_memory_blocks_insert_call(cursor_calls)
            assert memory_blocks_call is not None, (
                f"No memory_blocks INSERT call found for {namespace_id}"
            )

            sql_values = memory_blocks_call[0][1]

            assert sql_values[1] == namespace_id, (
                f"namespace_id not preserved for {namespace_id}. "
                f"Expected: {namespace_id}, Got: {sql_values[1]}"
            )

    @patch("mysql.connector.connect")
    def test_regression_namespace_id_not_missing(
        self, mock_connect, mock_config, sample_block_legacy_namespace
    ):
        """Regression test: Ensure namespace_id is not missing from SQL INSERT.

        This test specifically validates the bug fix where namespace_id was
        missing from the SQL INSERT statement, causing blocks to always
        default to 'legacy' namespace.
        """
        # Setup mock connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # Mock successful responses
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []

        # Create writer and execute operation
        writer = DoltMySQLWriter(mock_config)
        writer.write_memory_block(sample_block_legacy_namespace, branch="test-branch")

        # Get the executed SQL
        cursor_calls = mock_cursor.execute.call_args_list
        memory_blocks_call = self._find_memory_blocks_insert_call(cursor_calls)
        assert memory_blocks_call is not None, "No memory_blocks INSERT call found"

        sql_query = memory_blocks_call[0][0]

        # REGRESSION CHECK: namespace_id MUST be in the SQL
        assert "namespace_id" in sql_query, (
            "REGRESSION: namespace_id is missing from SQL INSERT statement. "
            "This was the original bug that caused all blocks to default to 'legacy' namespace."
        )

        # Verify it appears in the column list
        lines = sql_query.split("\n")
        column_line = None
        for line in lines:
            if "id, namespace_id" in line:
                column_line = line
                break

        assert column_line is not None, (
            "namespace_id should appear in the column list immediately after 'id'"
        )

        # Verify the column order is correct
        assert "id, namespace_id, type" in sql_query, (
            "namespace_id should be the second column after 'id' in the INSERT statement"
        )
