"""
Tests for the migration runner tool.

This module tests:
1. Schema branch validation logic (schema-update restriction)
2. Migration discovery and loading
3. Migration tracking and idempotency
4. Transaction safety
5. CLI argument parsing
6. Error handling and edge cases
"""

import pytest
import tempfile
import unittest.mock
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

from infra_core.memory_system.migrations.runner import (
    MigrationRunner,
    MigrationError,
    SCHEMA_BRANCH_PREFIX,
    main,
)
from infra_core.memory_system.dolt_mysql_base import (
    DoltConnectionConfig,
    MainBranchProtectionError,
)


@pytest.fixture
def mock_config():
    """Create a mock connection config."""
    return DoltConnectionConfig(
        host="localhost", port=3306, user="root", password="", database="test_db"
    )


@pytest.fixture
def mock_runner(mock_config):
    """Create a mock MigrationRunner with mocked database operations."""
    with (
        patch.object(MigrationRunner, "_ensure_migrations_table"),
        patch.object(
            MigrationRunner, "active_branch", new_callable=PropertyMock
        ) as mock_active_branch,
    ):
        mock_active_branch.return_value = "schema-update"
        runner = MigrationRunner(mock_config)
        runner._execute_query = MagicMock(return_value=[])
        runner._execute_update = MagicMock(return_value=1)
        return runner


class TestSchemaBranchValidation:
    """Test the schema branch validation logic."""

    def test_valid_schema_branches(self, mock_runner):
        """Test that valid schema branches are accepted."""
        valid_branches = [
            "schema-update",
            "schema-update/namespaces",
            "schema-update/feature-xyz",
            "schema-update/fix-migration",
            "schema-update/v2.0",
        ]

        for branch in valid_branches:
            assert mock_runner._is_schema_branch(branch), f"Branch '{branch}' should be valid"

    def test_invalid_schema_branches(self, mock_runner):
        """Test that invalid schema branches are rejected."""
        invalid_branches = [
            "schema",
            "schema-migration",
            "migrations",
            "schema-dev",
            "main",
            "develop",
            "feat/namespaces",
            "feat/schema-update",  # Doesn't start with schema-update
            "schema-update-feature",  # No slash separator
            "my-schema-update",  # Doesn't start with schema-update
            "",
        ]

        for branch in invalid_branches:
            assert not mock_runner._is_schema_branch(branch), f"Branch '{branch}' should be invalid"

    def test_schema_branch_restriction_enforcement(self, mock_runner):
        """Test that schema branch restriction is enforced."""
        # Should pass for valid branch
        mock_runner._check_schema_branch_restriction("test operation", "schema-update")

        # Should raise error for invalid branch
        with pytest.raises(MigrationError) as exc_info:
            mock_runner._check_schema_branch_restriction("test operation", "main")

        assert "not a valid schema branch" in str(exc_info.value)
        assert "schema-update" in str(exc_info.value)

    def test_schema_branch_case_sensitivity(self, mock_runner):
        """Test that schema branch validation is case sensitive."""
        # These should be invalid (case mismatch)
        invalid_case_branches = [
            "Schema-Update",
            "SCHEMA-UPDATE",
            "Schema-update/feature",
        ]

        for branch in invalid_case_branches:
            assert not mock_runner._is_schema_branch(branch), (
                f"Branch '{branch}' should be invalid (case sensitive)"
            )


class TestMigrationDiscovery:
    """Test migration file discovery."""

    def test_discover_migrations_empty_directory(self, mock_runner):
        """Test migration discovery in empty directory."""
        with patch.object(Path, "glob", return_value=[]):
            migrations = mock_runner.discover_migrations()
            assert migrations == []

    def test_discover_migrations_with_files(self, mock_runner):
        """Test migration discovery with actual migration files."""
        # Create mock file objects with proper stem attributes
        mock_files = []
        file_names = [
            "0001_initial.py",
            "0002_add_users.py",
            "0003_add_indexes.py",
            "runner.py",  # Should be excluded
            "test_migrations.py",  # Should be excluded
            "__init__.py",  # Should be excluded
        ]

        for name in file_names:
            mock_file = MagicMock()
            mock_file.name = name
            mock_file.stem = name.replace(".py", "")
            mock_files.append(mock_file)

        with patch.object(Path, "glob", return_value=mock_files):
            migrations = mock_runner.discover_migrations()

            expected = ["0001_initial", "0002_add_users", "0003_add_indexes"]
            assert migrations == expected

    def test_discover_migrations_sorting(self, mock_runner):
        """Test that migrations are sorted correctly."""
        # Create mock file objects with proper stem attributes
        mock_files = []
        file_names = [
            "0003_third.py",
            "0001_first.py",
            "0002_second.py",
            "0010_tenth.py",
        ]

        for name in file_names:
            mock_file = MagicMock()
            mock_file.name = name
            mock_file.stem = name.replace(".py", "")
            mock_files.append(mock_file)

        with patch.object(Path, "glob", return_value=mock_files):
            migrations = mock_runner.discover_migrations()

            expected = ["0001_first", "0002_second", "0003_third", "0010_tenth"]
            assert migrations == expected


class TestMigrationTracking:
    """Test migration application tracking."""

    def test_already_applied_true(self, mock_runner):
        """Test checking if migration is already applied (true case)."""
        mock_runner._execute_query.return_value = [{"success": True}]

        result = mock_runner.already_applied("0001_test_migration")

        assert result is True
        mock_runner._execute_query.assert_called_once_with(
            "SELECT success FROM migrations WHERE id = %s", ("0001_test_migration",)
        )

    def test_already_applied_false_not_found(self, mock_runner):
        """Test checking if migration is already applied (not found)."""
        mock_runner._execute_query.return_value = []

        result = mock_runner.already_applied("0001_test_migration")

        assert result is False

    def test_already_applied_false_failed(self, mock_runner):
        """Test checking if migration is already applied (failed previously)."""
        mock_runner._execute_query.return_value = [{"success": False}]

        result = mock_runner.already_applied("0001_test_migration")

        assert result is False

    def test_already_applied_query_error(self, mock_runner):
        """Test handling of query errors when checking migration status."""
        mock_runner._execute_query.side_effect = Exception("Database error")

        result = mock_runner.already_applied("0001_test_migration")

        assert result is False  # Should default to False on error


class TestMigrationLoading:
    """Test migration module loading."""

    def test_load_migration_module_success(self, mock_runner):
        """Test successful migration module loading."""
        # Create a temporary migration file
        with tempfile.TemporaryDirectory() as temp_dir:
            migration_file = Path(temp_dir) / "0001_test.py"
            migration_file.write_text("""
def apply(runner):
    pass

def rollback(runner):
    pass
""")

            # Mock the migrations directory
            mock_runner.migrations_dir = Path(temp_dir)

            module = mock_runner._load_migration_module("0001_test")

            assert hasattr(module, "apply")
            assert hasattr(module, "rollback")

    def test_load_migration_module_file_not_found(self, mock_runner):
        """Test error when migration file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_runner.migrations_dir = Path(temp_dir)

            with pytest.raises(MigrationError) as exc_info:
                mock_runner._load_migration_module("nonexistent_migration")

            assert "Migration file not found" in str(exc_info.value)

    def test_load_migration_module_invalid_python(self, mock_runner):
        """Test error when migration file has invalid Python syntax."""
        with tempfile.TemporaryDirectory() as temp_dir:
            migration_file = Path(temp_dir) / "0001_invalid.py"
            migration_file.write_text("invalid python syntax !!!")

            mock_runner.migrations_dir = Path(temp_dir)

            with pytest.raises(Exception):  # Should raise some kind of syntax error
                mock_runner._load_migration_module("0001_invalid")


class TestMigrationApplication:
    """Test migration application logic."""

    def test_apply_migration_already_applied(self, mock_runner):
        """Test applying a migration that's already been applied."""
        mock_runner.already_applied = MagicMock(return_value=True)

        result = mock_runner.apply("0001_test")

        assert result is True
        mock_runner.already_applied.assert_called_once_with("0001_test")

    def test_apply_migration_missing_apply_function(self, mock_runner):
        """Test error when migration module is missing apply function."""
        # Create a migration module without apply function
        with tempfile.TemporaryDirectory() as temp_dir:
            migration_file = Path(temp_dir) / "0001_no_apply.py"
            migration_file.write_text("# No apply function here")

            mock_runner.migrations_dir = Path(temp_dir)
            mock_runner.already_applied = MagicMock(return_value=False)

            with pytest.raises(MigrationError) as exc_info:
                mock_runner.apply("0001_no_apply")

            assert "missing apply() function" in str(exc_info.value)

    def test_apply_migration_records_failure(self, mock_runner):
        """Test that migration failures are recorded in the database."""
        # Create a migration that will fail
        with tempfile.TemporaryDirectory() as temp_dir:
            migration_file = Path(temp_dir) / "0001_failing.py"
            migration_file.write_text("""
def apply(runner):
    raise Exception("Migration failed!")
""")

            mock_runner.migrations_dir = Path(temp_dir)
            mock_runner.already_applied = MagicMock(return_value=False)

            with pytest.raises(MigrationError):
                mock_runner.apply("0001_failing")

            # Verify failure was recorded
            calls = mock_runner._execute_update.call_args_list
            failure_call = None
            for call in calls:
                if "INSERT INTO migrations" in call[0][0] and "error_message" in call[0][0]:
                    failure_call = call
                    break

            assert failure_call is not None
            assert "0001_failing" in failure_call[0][1]
            assert False in failure_call[0][1]  # success = False


class TestTransactionSafety:
    """Test transaction safety features."""

    def test_execute_in_transaction_success(self, mock_runner):
        """Test successful transaction execution."""
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        mock_runner._get_connection = MagicMock(return_value=mock_connection)
        mock_runner._use_persistent = False

        def test_operation():
            return "success"

        result = mock_runner._execute_in_transaction(test_operation)

        assert result == "success"
        mock_cursor.execute.assert_any_call("START TRANSACTION")
        mock_cursor.execute.assert_any_call("COMMIT")

    def test_execute_in_transaction_rollback_on_error(self, mock_runner):
        """Test that transaction is rolled back on error."""
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        mock_runner._get_connection = MagicMock(return_value=mock_connection)
        mock_runner._use_persistent = False

        def failing_operation():
            raise Exception("Operation failed")

        with pytest.raises(MigrationError):
            mock_runner._execute_in_transaction(failing_operation)

        mock_cursor.execute.assert_any_call("START TRANSACTION")
        mock_cursor.execute.assert_any_call("ROLLBACK")

    def test_execute_in_transaction_connection_scoping(self, mock_runner):
        """Test that transaction properly scopes connections for non-persistent mode."""
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        # Start in non-persistent mode
        mock_runner._use_persistent = False
        mock_runner._persistent_connection = None
        mock_runner._get_connection = MagicMock(return_value=mock_connection)

        # Track calls to _execute_update to ensure it uses the transaction connection
        original_execute_update = mock_runner._execute_update
        execute_update_calls = []

        def track_execute_update(*args, **kwargs):
            # Verify we're in persistent mode during the operation
            execute_update_calls.append(
                {
                    "use_persistent": mock_runner._use_persistent,
                    "persistent_connection": mock_runner._persistent_connection,
                }
            )
            return original_execute_update(*args, **kwargs)

        mock_runner._execute_update = track_execute_update

        def test_operation():
            # This simulates what happens inside _apply_migration_unsafe
            mock_runner._execute_update(
                "INSERT INTO migrations (id, success) VALUES (%s, %s)", ("test", True)
            )
            return "success"

        result = mock_runner._execute_in_transaction(test_operation)

        assert result == "success"
        # Verify the operation was called with persistent mode enabled
        assert len(execute_update_calls) == 1
        assert execute_update_calls[0]["use_persistent"] is True
        assert execute_update_calls[0]["persistent_connection"] == mock_connection

        # Verify persistent mode was restored after transaction
        assert mock_runner._use_persistent is False
        assert mock_runner._persistent_connection is None


class TestRunUntilMethod:
    """Test the run_until method."""

    def test_run_until_branch_protection(self, mock_runner):
        """Test that branch protection is enforced."""
        mock_runner._check_branch_protection = MagicMock(
            side_effect=MainBranchProtectionError("test", "main", [])
        )

        with pytest.raises(MainBranchProtectionError):
            mock_runner.run_until()

    def test_run_until_schema_branch_restriction(self, mock_runner):
        """Test that schema branch restriction is enforced."""
        mock_runner._check_branch_protection = MagicMock()  # Pass branch protection

        # Mock active_branch to return invalid branch
        with patch.object(
            type(mock_runner), "active_branch", new_callable=PropertyMock
        ) as mock_active_branch:
            mock_active_branch.return_value = "main"  # Invalid schema branch

            with pytest.raises(MigrationError) as exc_info:
                mock_runner.run_until()

            assert "not a valid schema branch" in str(exc_info.value)

    def test_run_until_force_bypasses_schema_restriction(self, mock_runner):
        """Test that --force flag bypasses schema branch restriction."""
        mock_runner._check_branch_protection = MagicMock()
        mock_runner.discover_migrations = MagicMock(return_value=[])

        # Mock active_branch to return invalid branch
        with patch.object(
            type(mock_runner), "active_branch", new_callable=PropertyMock
        ) as mock_active_branch:
            mock_active_branch.return_value = "main"  # Invalid schema branch

            # Should not raise error with force=True
            result = mock_runner.run_until(force=True)
            assert result is True

    def test_run_until_no_migrations(self, mock_runner):
        """Test run_until with no migrations found."""
        mock_runner._check_branch_protection = MagicMock()
        mock_runner._check_schema_branch_restriction = MagicMock()
        mock_runner.discover_migrations = MagicMock(return_value=[])

        result = mock_runner.run_until()

        assert result is True

    def test_run_until_target_migration_not_found(self, mock_runner):
        """Test error when target migration is not found."""
        mock_runner._check_branch_protection = MagicMock()
        mock_runner._check_schema_branch_restriction = MagicMock()
        mock_runner.discover_migrations = MagicMock(return_value=["0001_first", "0002_second"])

        with pytest.raises(MigrationError) as exc_info:
            mock_runner.run_until(target_migration="0003_nonexistent")

        assert "Target migration not found" in str(exc_info.value)

    def test_run_until_with_target_migration(self, mock_runner):
        """Test run_until with a specific target migration."""
        mock_runner._check_branch_protection = MagicMock()
        mock_runner._check_schema_branch_restriction = MagicMock()
        mock_runner.discover_migrations = MagicMock(
            return_value=["0001_first", "0002_second", "0003_third"]
        )
        mock_runner.apply = MagicMock(return_value=True)

        result = mock_runner.run_until(target_migration="0002_second")

        assert result is True
        # Should only apply migrations up to and including the target
        expected_calls = [
            unittest.mock.call("0001_first"),
            unittest.mock.call("0002_second"),
        ]
        mock_runner.apply.assert_has_calls(expected_calls)
        assert mock_runner.apply.call_count == 2


class TestCLIInterface:
    """Test the CLI interface."""

    @patch("sys.argv", ["runner.py", "--branch", "schema-update"])
    @patch("infra_core.memory_system.migrations.runner.MigrationRunner")
    def test_cli_basic_usage(self, mock_runner_class):
        """Test basic CLI usage."""
        mock_runner = MagicMock()
        mock_runner_class.return_value = mock_runner
        mock_runner.run_until.return_value = True

        with patch("sys.exit") as mock_exit:
            main()
            mock_exit.assert_not_called()

        mock_runner.use_persistent_connection.assert_called_once_with("schema-update")
        mock_runner.run_until.assert_called_once_with(None, force=False)

    @patch("sys.argv", ["runner.py", "--branch", "schema-update", "--dry-run"])
    @patch("infra_core.memory_system.migrations.runner.MigrationRunner")
    @patch("builtins.print")
    def test_cli_dry_run(self, mock_print, mock_runner_class):
        """Test CLI dry-run functionality."""
        mock_runner = MagicMock()
        mock_runner_class.return_value = mock_runner
        mock_runner.discover_migrations.return_value = ["0001_test", "0002_test"]
        mock_runner.already_applied.return_value = False

        with patch("sys.exit") as mock_exit:
            main()
            mock_exit.assert_not_called()

        # Should not call run_until in dry-run mode
        mock_runner.run_until.assert_not_called()

        # Should print dry-run information
        mock_print.assert_called()

    @patch("sys.argv", ["runner.py", "--branch", "main", "--force"])
    @patch("infra_core.memory_system.migrations.runner.MigrationRunner")
    def test_cli_force_flag(self, mock_runner_class):
        """Test CLI --force flag."""
        mock_runner = MagicMock()
        mock_runner_class.return_value = mock_runner
        mock_runner.run_until.return_value = True

        with patch("sys.exit") as mock_exit:
            main()
            mock_exit.assert_not_called()

        mock_runner.run_until.assert_called_once_with(None, force=True)


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_migration_error_inheritance(self):
        """Test that MigrationError is properly defined."""
        error = MigrationError("test error")
        assert isinstance(error, Exception)
        assert str(error) == "test error"

    def test_schema_branch_prefix_constant(self):
        """Test that SCHEMA_BRANCH_PREFIX constant is correctly defined."""
        assert SCHEMA_BRANCH_PREFIX == "schema-update"

    def test_runner_initialization_with_config(self, mock_config):
        """Test MigrationRunner initialization with config."""
        with patch.object(MigrationRunner, "_ensure_migrations_table"):
            runner = MigrationRunner(mock_config)
            assert runner.config == mock_config
            assert isinstance(runner.migrations_dir, Path)
