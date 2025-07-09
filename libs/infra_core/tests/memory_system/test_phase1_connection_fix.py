#!/usr/bin/env python3
"""
Simple test case for Phase 1 MCP connection bug fixes.

This test validates the specific changes made to fix the Docker connection drops:
1. Detection of "mysql connection not available" errors
2. Connection health checks preventing stale connection usage
3. Preservation of original exception types for proper detection

Run with: python -m pytest tests/memory_system/test_phase1_connection_fix.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
from mysql.connector.errors import Error, OperationalError

from infra_core.memory_system.dolt_mysql_base import (
    DoltConnectionConfig,
    DoltMySQLBase,
)


class TestPhase1ConnectionFix:
    """Test Phase 1 fixes for Docker connection drops."""

    @pytest.fixture
    def base_instance(self):
        """Create a DoltMySQLBase instance for testing."""
        config = DoltConnectionConfig()
        return DoltMySQLBase(config)

    def test_docker_error_detection(self, base_instance):
        """Test that Docker-specific 'MySQL Connection not available' error is detected."""
        # Test the exact error message from Docker logs
        docker_error = OperationalError("MySQL Connection not available")
        assert base_instance._is_connection_error(docker_error) is True

        # Test wrapped version (what happens after our fix)
        wrapped_error = Error("MySQL Connection not available")
        assert base_instance._is_connection_error(wrapped_error) is True

        # Test case insensitive detection
        case_error = Error("MYSQL CONNECTION NOT AVAILABLE")
        assert base_instance._is_connection_error(case_error) is True

        # Test partial match in longer message
        partial_error = Error("Query failed: MySQL Connection not available")
        assert base_instance._is_connection_error(partial_error) is True

    def test_connection_health_check(self, base_instance):
        """Test connection health check functionality."""
        # Test healthy connection
        healthy_connection = MagicMock()
        healthy_connection.is_connected.return_value = True
        healthy_cursor = MagicMock()
        healthy_connection.cursor.return_value = healthy_cursor

        result = base_instance._is_connection_healthy(healthy_connection)
        assert result is True

        # Verify the health check actually tests the connection
        healthy_connection.is_connected.assert_called_once()
        healthy_connection.cursor.assert_called_once()
        healthy_cursor.execute.assert_called_once_with("SELECT 1")
        healthy_cursor.fetchone.assert_called_once()
        healthy_cursor.close.assert_called_once()

    def test_unhealthy_connection_detection(self, base_instance):
        """Test detection of unhealthy connections."""
        # Test connection that reports as disconnected
        disconnected_connection = MagicMock()
        disconnected_connection.is_connected.return_value = False

        result = base_instance._is_connection_healthy(disconnected_connection)
        assert result is False

        # Test connection that fails on cursor creation
        failing_connection = MagicMock()
        failing_connection.is_connected.return_value = True
        failing_connection.cursor.side_effect = OperationalError("MySQL Connection not available")

        result = base_instance._is_connection_healthy(failing_connection)
        assert result is False

    def test_execute_query_with_health_check(self, base_instance):
        """Test that query execution uses health checks to prevent stale connections."""
        # Setup persistent connection mode
        base_instance._use_persistent = True
        stale_connection = MagicMock()
        base_instance._persistent_connection = stale_connection

        # Mock stale connection (reports connected but fails health check)
        stale_connection.is_connected.return_value = True
        stale_connection.cursor.side_effect = OperationalError("MySQL Connection not available")

        # Mock new connection creation
        new_connection = MagicMock()
        new_cursor = MagicMock()
        new_connection.cursor.return_value = new_cursor
        new_cursor.fetchall.return_value = [{"test": "result"}]

        with patch.object(base_instance, "_get_connection", return_value=new_connection):
            result = base_instance._execute_query_impl("SELECT 1")

            # Should have detected stale connection and created new one
            assert result == [{"test": "result"}]

            # Should have attempted health check on stale connection
            stale_connection.is_connected.assert_called()
            stale_connection.cursor.assert_called()

            # Should have created new connection when health check failed
            new_connection.cursor.assert_called_with(dictionary=True)
            new_cursor.execute.assert_called_with("SELECT 1", ())

    def test_error_preservation_no_wrapping(self, base_instance):
        """Test that original exceptions are preserved (no wrapping)."""
        # Setup connection that will fail
        failing_connection = MagicMock()
        failing_connection.cursor.side_effect = OperationalError("MySQL Connection not available")

        with patch.object(base_instance, "_get_connection", return_value=failing_connection):
            try:
                base_instance._execute_query_impl("SELECT 1")
                pytest.fail("Expected OperationalError to be raised")
            except OperationalError as e:
                # Should preserve original error type and message
                assert str(e) == "MySQL Connection not available"
                assert type(e) == OperationalError
                # Should NOT be wrapped in generic Exception

    def test_integration_with_retry_logic(self, base_instance):
        """Test integration with existing retry logic."""
        # Setup to simulate connection failure followed by successful retry
        base_instance._use_persistent = True
        base_instance._persistent_connection = MagicMock()
        base_instance._current_branch = "test-branch"

        call_count = 0

        def mock_execute_query_impl(query, params=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call fails with Docker error
                raise OperationalError("MySQL Connection not available")
            else:
                # Second call succeeds after reconnection
                return [{"success": True}]

        # Mock successful reconnection
        new_connection = MagicMock()
        with patch.object(
            base_instance, "_execute_query_impl", side_effect=mock_execute_query_impl
        ):
            with patch.object(base_instance, "_get_connection", return_value=new_connection):
                with patch.object(base_instance, "_ensure_branch"):
                    with patch.object(
                        base_instance, "_verify_current_branch", return_value="test-branch"
                    ):
                        # Should succeed after retry
                        result = base_instance._execute_query("SELECT 1")

                        assert result == [{"success": True}]
                        assert call_count == 2  # Called twice (original + retry)

    def test_non_docker_errors_still_work(self, base_instance):
        """Test that existing error detection still works."""
        # Test existing error patterns still work
        existing_errors = [
            OperationalError("Lost connection to MySQL server during query"),
            Error("MySQL server has gone away"),
            Error("Connection timeout"),
            Error("Connection refused"),
        ]

        for error in existing_errors:
            assert base_instance._is_connection_error(error) is True, f"Should detect: {error}"

        # Test non-connection errors are not detected
        non_connection_errors = [
            Error("Syntax error"),
            Error("Table doesn't exist"),
            Error("Duplicate key"),
        ]

        for error in non_connection_errors:
            assert base_instance._is_connection_error(error) is False, f"Should not detect: {error}"


def test_quick_validation():
    """Quick validation test that can be run standalone."""
    config = DoltConnectionConfig()
    base = DoltMySQLBase(config)

    # Test the specific Docker error from the bug report
    docker_error = OperationalError("MySQL Connection not available")
    assert base._is_connection_error(docker_error) is True

    # Test health check with mock connection
    healthy_connection = MagicMock()
    healthy_connection.is_connected.return_value = True
    healthy_cursor = MagicMock()
    healthy_connection.cursor.return_value = healthy_cursor

    assert base._is_connection_healthy(healthy_connection) is True

    print("✅ Phase 1 fixes validation passed!")


if __name__ == "__main__":
    test_quick_validation()
