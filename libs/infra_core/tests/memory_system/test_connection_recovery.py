#!/usr/bin/env python3
"""
Unit tests for MySQL connection recovery functionality in DoltMySQLBase.

Tests the automatic reconnection logic that detects connection failures
and attempts to restore persistent connections while preserving branch state.
"""

import pytest
from unittest.mock import MagicMock, patch
from mysql.connector import Error, OperationalError, InterfaceError

from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig, DoltMySQLBase


class TestConnectionRecovery:
    """Test connection recovery functionality in DoltMySQLBase."""

    @pytest.fixture
    def base_instance(self):
        """Create a DoltMySQLBase instance for testing."""
        config = DoltConnectionConfig()
        return DoltMySQLBase(config)

    @pytest.fixture
    def mock_connection(self):
        """Create a mock MySQL connection."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        return mock_conn, mock_cursor

    # Test _is_connection_error method
    def test_is_connection_error_operational_error(self, base_instance):
        """Test that OperationalError is detected as a connection error."""
        error = OperationalError("Lost connection to MySQL server during query")
        assert base_instance._is_connection_error(error) is True

    def test_is_connection_error_interface_error(self, base_instance):
        """Test that InterfaceError is detected as a connection error."""
        error = InterfaceError("Connection timeout")
        assert base_instance._is_connection_error(error) is True

    def test_is_connection_error_mysql_error_with_connection_keywords(self, base_instance):
        """Test that MySQL Error with connection keywords is detected."""
        test_cases = [
            "Lost connection to MySQL server",
            "Connection was killed",
            "Connection timeout exceeded",
            "Connection refused by server",
            "Broken pipe during query",
            "Network error occurred",
            "Connection reset by peer",
            "Connection aborted",
            "Host is unreachable",
            "Connection closed unexpectedly",
        ]

        for msg in test_cases:
            error = Error(msg)
            assert base_instance._is_connection_error(error) is True, f"Should detect: {msg}"

    def test_is_connection_error_mysql_error_case_insensitive(self, base_instance):
        """Test that error detection is case-insensitive."""
        error = Error("LOST CONNECTION to MySQL server")
        assert base_instance._is_connection_error(error) is True

    def test_is_connection_error_non_connection_error(self, base_instance):
        """Test that non-connection errors are not detected as connection errors."""
        test_cases = [
            Error("Syntax error in SQL statement"),
            Error("Table 'test.nonexistent' doesn't exist"),
            Error("Duplicate entry 'test' for key 'PRIMARY'"),
            ValueError("Invalid parameter"),
            RuntimeError("General runtime error"),
        ]

        for error in test_cases:
            assert base_instance._is_connection_error(error) is False

    # Test _attempt_reconnection method
    def test_attempt_reconnection_not_using_persistent(self, base_instance):
        """Test that reconnection returns False when not using persistent connections."""
        # Ensure not using persistent connections
        base_instance._use_persistent = False

        result = base_instance._attempt_reconnection()
        assert result is False

    @patch("infra_core.memory_system.dolt_mysql_base.logger")
    def test_attempt_reconnection_success(self, mock_logger, base_instance, mock_connection):
        """Test successful reconnection with branch restoration."""
        mock_conn, mock_cursor = mock_connection

        # Setup persistent connection state
        base_instance._use_persistent = True
        base_instance._current_branch = "feat/test-branch"
        base_instance._persistent_connection = MagicMock()  # Old broken connection

        # Mock _get_connection to return new connection
        with patch.object(base_instance, "_get_connection", return_value=mock_conn):
            # Mock _ensure_branch and _verify_current_branch
            with patch.object(base_instance, "_ensure_branch") as mock_ensure:
                with patch.object(
                    base_instance, "_verify_current_branch", return_value="feat/test-branch"
                ) as mock_verify:
                    result = base_instance._attempt_reconnection()

                    # Verify success
                    assert result is True
                    assert base_instance._persistent_connection == mock_conn
                    assert base_instance._current_branch == "feat/test-branch"

                    # Verify methods were called correctly
                    mock_ensure.assert_called_once_with(mock_conn, "feat/test-branch")
                    mock_verify.assert_called_once_with(mock_conn)

                    # Verify logging
                    mock_logger.warning.assert_called_once()
                    mock_logger.info.assert_called_once()

    @patch("infra_core.memory_system.dolt_mysql_base.logger")
    def test_attempt_reconnection_branch_mismatch(
        self, mock_logger, base_instance, mock_connection
    ):
        """Test reconnection handles branch mismatch after restoration."""
        mock_conn, mock_cursor = mock_connection

        # Setup persistent connection state
        base_instance._use_persistent = True
        base_instance._current_branch = "feat/test-branch"
        base_instance._persistent_connection = MagicMock()

        with patch.object(base_instance, "_get_connection", return_value=mock_conn):
            with patch.object(base_instance, "_ensure_branch"):
                # Mock branch verification returning different branch
                with patch.object(
                    base_instance, "_verify_current_branch", return_value="different-branch"
                ):
                    result = base_instance._attempt_reconnection()

                    # Should still succeed but update current branch
                    assert result is True
                    assert base_instance._current_branch == "different-branch"

                    # Should log warning about mismatch
                    warning_calls = [
                        call
                        for call in mock_logger.warning.call_args_list
                        if "Branch mismatch" in str(call)
                    ]
                    assert len(warning_calls) == 1

    @patch("infra_core.memory_system.dolt_mysql_base.logger")
    def test_attempt_reconnection_failure(self, mock_logger, base_instance):
        """Test reconnection failure handling."""
        # Setup persistent connection state
        base_instance._use_persistent = True
        base_instance._current_branch = "feat/test-branch"
        base_instance._persistent_connection = MagicMock()

        # Mock _get_connection to raise exception
        with patch.object(base_instance, "_get_connection", side_effect=Error("Connection failed")):
            result = base_instance._attempt_reconnection()

            # Verify failure
            assert result is False
            assert base_instance._persistent_connection is None
            assert base_instance._current_branch is None
            assert base_instance._use_persistent is False

            # Verify error logging
            mock_logger.error.assert_called_once()

    # Test _execute_with_retry method
    def test_execute_with_retry_success_first_attempt(self, base_instance):
        """Test successful execution on first attempt."""
        mock_operation = MagicMock(return_value="success")

        result = base_instance._execute_with_retry(mock_operation, "SELECT 1", ())

        assert result == "success"
        mock_operation.assert_called_once_with("SELECT 1", ())

    @patch("infra_core.memory_system.dolt_mysql_base.logger")
    def test_execute_with_retry_non_connection_error(self, mock_logger, base_instance):
        """Test that non-connection errors are re-raised without retry."""
        mock_operation = MagicMock(side_effect=Error("Syntax error"))

        with pytest.raises(Error, match="Syntax error"):
            base_instance._execute_with_retry(mock_operation, "INVALID SQL", ())

        # Should only be called once (no retry)
        mock_operation.assert_called_once()

    @patch("infra_core.memory_system.dolt_mysql_base.logger")
    def test_execute_with_retry_connection_error_reconnect_success(
        self, mock_logger, base_instance
    ):
        """Test successful retry after connection error and reconnection."""
        # First call fails with connection error, second succeeds
        mock_operation = MagicMock(
            side_effect=[OperationalError("Lost connection"), "success_after_retry"]
        )

        with patch.object(base_instance, "_attempt_reconnection", return_value=True):
            result = base_instance._execute_with_retry(mock_operation, "SELECT 1", ())

            assert result == "success_after_retry"
            assert mock_operation.call_count == 2

    @patch("infra_core.memory_system.dolt_mysql_base.logger")
    def test_execute_with_retry_connection_error_reconnect_fails(self, mock_logger, base_instance):
        """Test that original error is raised when reconnection fails."""
        original_error = OperationalError("Lost connection")
        mock_operation = MagicMock(side_effect=original_error)

        with patch.object(base_instance, "_attempt_reconnection", return_value=False):
            with pytest.raises(OperationalError, match="Lost connection"):
                base_instance._execute_with_retry(mock_operation, "SELECT 1", ())

        # Should only be called once since reconnection failed
        mock_operation.assert_called_once()

    @patch("infra_core.memory_system.dolt_mysql_base.logger")
    def test_execute_with_retry_connection_error_retry_fails(self, mock_logger, base_instance):
        """Test that retry failure is properly handled."""
        mock_operation = MagicMock(
            side_effect=[OperationalError("Lost connection"), Error("Retry failed")]
        )

        with patch.object(base_instance, "_attempt_reconnection", return_value=True):
            with pytest.raises(Exception, match="Operation failed after reconnection attempt"):
                base_instance._execute_with_retry(mock_operation, "SELECT 1", ())

            assert mock_operation.call_count == 2

    # Test integration with _execute_query and _execute_update
    def test_execute_query_uses_retry_mechanism(self, base_instance):
        """Test that _execute_query uses the retry mechanism."""
        with patch.object(base_instance, "_execute_with_retry") as mock_retry:
            with patch.object(base_instance, "_execute_query_impl") as mock_impl:
                mock_retry.return_value = [{"test": "result"}]

                result = base_instance._execute_query("SELECT 1", ())

                assert result == [{"test": "result"}]
                mock_retry.assert_called_once_with(mock_impl, "SELECT 1", ())

    def test_execute_update_uses_retry_mechanism(self, base_instance):
        """Test that _execute_update uses the retry mechanism."""
        with patch.object(base_instance, "_execute_with_retry") as mock_retry:
            with patch.object(base_instance, "_execute_update_impl") as mock_impl:
                mock_retry.return_value = 1

                result = base_instance._execute_update("UPDATE test SET x=1", ())

                assert result == 1
                mock_retry.assert_called_once_with(mock_impl, "UPDATE test SET x=1", ())

    # Test real-world scenario simulation
    @patch("infra_core.memory_system.dolt_mysql_base.logger")
    def test_real_world_scenario_persistent_connection_recovery(
        self, mock_logger, base_instance, mock_connection
    ):
        """Test a realistic scenario where persistent connection is lost and recovered."""
        # Setup persistent connection
        base_instance._use_persistent = True
        base_instance._current_branch = "feat/development"
        base_instance._persistent_connection = MagicMock()

        # Mock the implementation methods to simulate first failure, then success
        first_call = True

        def mock_execute_query_impl(query, params=None):
            nonlocal first_call
            if first_call:
                first_call = False
                raise OperationalError("MySQL server has gone away")
            else:
                return [{"result": "success"}]

        # Mock successful reconnection
        with patch.object(
            base_instance, "_execute_query_impl", side_effect=mock_execute_query_impl
        ):
            with patch.object(base_instance, "_get_connection", return_value=MagicMock()):
                with patch.object(base_instance, "_ensure_branch"):
                    with patch.object(
                        base_instance, "_verify_current_branch", return_value="feat/development"
                    ):
                        # This should succeed after reconnection
                        result = base_instance._execute_query("SELECT 1")

                        assert result == [{"result": "success"}]

                        # Verify reconnection happened
                        assert base_instance._persistent_connection is not None
                        assert base_instance._current_branch == "feat/development"

                        # Verify logging shows the recovery process
                        warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
                        info_calls = [str(call) for call in mock_logger.info.call_args_list]

                        assert any("Connection error detected" in call for call in warning_calls)
                        assert any(
                            "Retrying operation after reconnection" in call for call in info_calls
                        )


class TestConnectionRecoveryEdgeCases:
    """Test edge cases and error conditions for connection recovery."""

    @pytest.fixture
    def base_instance(self):
        """Create a DoltMySQLBase instance for testing."""
        config = DoltConnectionConfig()
        return DoltMySQLBase(config)

    def test_reconnection_with_no_previous_branch(self, base_instance):
        """Test reconnection when no previous branch was set."""
        base_instance._use_persistent = True
        base_instance._current_branch = None  # No previous branch
        base_instance._persistent_connection = MagicMock()

        mock_conn = MagicMock()
        with patch.object(base_instance, "_get_connection", return_value=mock_conn):
            result = base_instance._attempt_reconnection()

            assert result is True
            assert base_instance._persistent_connection == mock_conn
            # Should not call _ensure_branch if no previous branch

    def test_error_detection_with_complex_error_messages(self, base_instance):
        """Test error detection with complex, realistic error messages."""
        # Test the specific error patterns that should be detected
        complex_errors = [
            "ERROR 2013 (HY000): Lost connection to MySQL server during query",
            "MySQL server has gone away",  # This should be detected
            "Can't connect to MySQL server on 'localhost' (10061)",
            "Server shutdown in progress",  # This should be detected
            "Can't connect to MySQL server on 'host' (110)",
        ]

        for error_msg in complex_errors:
            error = Error(error_msg)
            is_detected = base_instance._is_connection_error(error)
            print(f"Testing: '{error_msg}' -> {is_detected}")  # Debug output
            assert base_instance._is_connection_error(error) is True, f"Should detect: {error_msg}"

    def test_partial_connection_close_failure(self, base_instance):
        """Test that reconnection handles old connection close failures gracefully."""
        base_instance._use_persistent = True
        base_instance._current_branch = "test-branch"

        # Mock old connection that fails to close
        old_conn = MagicMock()
        old_conn.close.side_effect = Error("Connection already closed")
        base_instance._persistent_connection = old_conn

        new_conn = MagicMock()
        with patch.object(base_instance, "_get_connection", return_value=new_conn):
            with patch.object(base_instance, "_ensure_branch"):
                with patch.object(
                    base_instance, "_verify_current_branch", return_value="test-branch"
                ):
                    # Should succeed despite old connection close failure
                    result = base_instance._attempt_reconnection()
                    assert result is True
                    assert base_instance._persistent_connection == new_conn
