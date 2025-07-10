"""
Tests for connection pooling functionality in DoltMySQLBase.

These tests focus on the feature flag logic, deprecation warnings,
and basic pooling configuration without requiring a live database.
"""

import os
import warnings
from unittest.mock import patch, MagicMock

from infra_core.memory_system.dolt_mysql_base import DoltMySQLBase, DoltConnectionConfig


class TestDoltMySQLBasePooling:
    """Test connection pooling functionality in DoltMySQLBase."""

    def test_legacy_mode_by_default(self):
        """Test that pooling is disabled by default."""
        # Ensure no pool env var
        if "USE_DOLT_POOL" in os.environ:
            del os.environ["USE_DOLT_POOL"]

        config = DoltConnectionConfig()
        base = DoltMySQLBase(config)

        assert base._use_pool is False
        assert base._pool is None
        assert base._pool_size == 10  # Default size

    def test_pooling_enabled_with_env_var(self):
        """Test that pooling is enabled when USE_DOLT_POOL=true."""
        with patch.dict(os.environ, {"USE_DOLT_POOL": "true"}):
            config = DoltConnectionConfig()

            # Mock the pool initialization to avoid DB connection
            with patch.object(DoltMySQLBase, "_initialize_connection_pool") as mock_init:
                base = DoltMySQLBase(config)

                assert base._use_pool is True
                assert base._pool_size == 10
                mock_init.assert_called_once()

    def test_custom_pool_size(self):
        """Test custom pool size configuration."""
        with patch.dict(os.environ, {"USE_DOLT_POOL": "true", "DOLT_POOL_SIZE": "5"}):
            config = DoltConnectionConfig()

            with patch.object(DoltMySQLBase, "_initialize_connection_pool"):
                base = DoltMySQLBase(config)

                assert base._pool_size == 5

    def test_feature_flag_case_insensitive(self):
        """Test that feature flag works with different cases."""
        test_values = ["true", "True", "TRUE", "false", "False", "FALSE"]

        for value in test_values:
            with patch.dict(os.environ, {"USE_DOLT_POOL": value}):
                config = DoltConnectionConfig()

                with patch.object(DoltMySQLBase, "_initialize_connection_pool"):
                    base = DoltMySQLBase(config)

                    expected = value.lower() == "true"
                    assert base._use_pool is expected

    def test_deprecated_persistent_connection_warning(self):
        """Test deprecation warning when using persistent connections with pooling enabled."""
        with patch.dict(os.environ, {"USE_DOLT_POOL": "true"}):
            config = DoltConnectionConfig()

            with patch.object(DoltMySQLBase, "_initialize_connection_pool"):
                base = DoltMySQLBase(config)

                # Test use_persistent_connection deprecation
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    base.use_persistent_connection("main")

                    assert len(w) == 1
                    assert issubclass(w[0].category, DeprecationWarning)
                    assert "use_persistent_connection() is deprecated" in str(w[0].message)

    def test_deprecated_close_persistent_connection_warning(self):
        """Test deprecation warning when closing persistent connections with pooling enabled."""
        with patch.dict(os.environ, {"USE_DOLT_POOL": "true"}):
            config = DoltConnectionConfig()

            with patch.object(DoltMySQLBase, "_initialize_connection_pool"):
                base = DoltMySQLBase(config)

                # Test close_persistent_connection deprecation
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    base.close_persistent_connection()

                    assert len(w) == 1
                    assert issubclass(w[0].category, DeprecationWarning)
                    assert "close_persistent_connection() is deprecated" in str(w[0].message)

    def test_legacy_persistent_connection_still_works(self):
        """Test that persistent connections still work when pooling is disabled."""
        with patch.dict(os.environ, {"USE_DOLT_POOL": "false"}):
            config = DoltConnectionConfig()
            base = DoltMySQLBase(config)

            # Mock the connection methods to avoid DB calls
            mock_connection = MagicMock()
            with patch.object(base, "_get_connection", return_value=mock_connection):
                with patch.object(base, "_ensure_branch"):
                    with patch.object(base, "_verify_current_branch", return_value="main"):
                        # Should work without warnings
                        with warnings.catch_warnings(record=True) as w:
                            warnings.simplefilter("always")
                            base.use_persistent_connection("main")

                            assert len(w) == 0  # No deprecation warnings
                            assert base._use_persistent is True

    @patch("infra_core.memory_system.dolt_mysql_base.MySQLConnectionPool")
    def test_pool_configuration(self, mock_pool_class):
        """Test that connection pool is configured correctly."""
        with patch.dict(os.environ, {"USE_DOLT_POOL": "true", "DOLT_POOL_SIZE": "15"}):
            config = DoltConnectionConfig(
                host="test-host",
                port=3307,
                user="test-user",
                password="test-pass",
                database="test-db",
            )

            base = DoltMySQLBase(config)

            # Verify pool was assigned
            assert base._pool == mock_pool_class.return_value

            # Verify pool was created with correct config
            mock_pool_class.assert_called_once()
            call_kwargs = mock_pool_class.call_args[1]

            assert call_kwargs["pool_name"] == "dolt_pool_test-db"
            assert call_kwargs["pool_size"] == 15
            assert call_kwargs["host"] == "test-host"
            assert call_kwargs["port"] == 3307
            assert call_kwargs["user"] == "test-user"
            assert call_kwargs["password"] == "test-pass"
            assert call_kwargs["database"] == "test-db"
            assert call_kwargs["autocommit"] is False  # Default for transaction control
            assert call_kwargs["pool_reset_session"] is True

    def test_get_connection_method_exists(self):
        """Test that get_connection context manager method exists."""
        config = DoltConnectionConfig()
        base = DoltMySQLBase(config)

        assert hasattr(base, "get_connection")
        assert callable(getattr(base, "get_connection"))

    def test_health_check_method_exists(self):
        """Test that pooled health check method exists."""
        config = DoltConnectionConfig()
        base = DoltMySQLBase(config)

        assert hasattr(base, "_ensure_connection_healthy_pooled")
        assert callable(getattr(base, "_ensure_connection_healthy_pooled"))

    def test_pool_timeout_configuration(self):
        """Test that pool timeout is configured correctly."""
        with patch.dict(os.environ, {"USE_DOLT_POOL": "true", "DOLT_POOL_TIMEOUT": "45"}):
            config = DoltConnectionConfig()

            with patch.object(DoltMySQLBase, "_initialize_connection_pool"):
                base = DoltMySQLBase(config)

                assert base._pool_timeout == 45

    def test_pool_timeout_default(self):
        """Test that pool timeout has correct default."""
        with patch.dict(os.environ, {"USE_DOLT_POOL": "true"}):
            # Remove timeout env var if present
            if "DOLT_POOL_TIMEOUT" in os.environ:
                del os.environ["DOLT_POOL_TIMEOUT"]

            config = DoltConnectionConfig()

            with patch.object(DoltMySQLBase, "_initialize_connection_pool"):
                base = DoltMySQLBase(config)

                assert base._pool_timeout == 30  # Default value

    @patch("infra_core.memory_system.dolt_mysql_base.MySQLConnectionPool")
    def test_pool_get_connection_with_timeout(self, mock_pool_class):
        """Test that pool.get_connection() is called with timeout parameter."""
        with patch.dict(os.environ, {"USE_DOLT_POOL": "true", "DOLT_POOL_TIMEOUT": "20"}):
            config = DoltConnectionConfig()
            base = DoltMySQLBase(config)

            # Mock pool and connection
            mock_pool = mock_pool_class.return_value
            mock_connection = MagicMock()
            mock_pool.get_connection.return_value = mock_connection

            # Mock health check and branch methods
            with patch.object(base, "_ensure_connection_healthy_pooled"):
                with patch.object(base, "_ensure_branch"):
                    with patch.object(base, "_verify_current_branch", return_value="test-branch"):
                        # Use context manager
                        with base.get_connection("test-branch", autocommit=True) as conn:
                            assert conn == mock_connection

                        # Verify timeout was passed to get_connection
                        mock_pool.get_connection.assert_called_once_with(timeout=20)

    def test_branch_consistency_verification_exists(self):
        """Test that branch consistency verification methods exist."""
        config = DoltConnectionConfig()
        base = DoltMySQLBase(config)

        # These methods should exist for branch verification
        assert hasattr(base, "_verify_current_branch")
        assert callable(getattr(base, "_verify_current_branch"))

        # BranchConsistencyError should be importable
        from infra_core.memory_system.dolt_mysql_base import BranchConsistencyError

        assert BranchConsistencyError
