#!/usr/bin/env python3

"""Migration runner for Dolt database schema and data migrations.

This module provides a MigrationRunner class that subclasses DoltMySQLBase
to execute migrations through the Dolt SQL server connection.

Following the DoltHub recommended "Schema Branch and Merge" pattern:
https://www.dolthub.com/blog/2024-04-18-dolt-schema-migrations/

Key features:
- Discovers migration files in the migrations directory
- Tracks applied migrations in a migrations table
- Executes migrations in order with proper error handling
- Restricts execution to schema-related branches only
- Provides transactional migration execution
- Provides idempotent migration execution
"""

import argparse
import importlib.util
import logging
import sys
from pathlib import Path
from typing import List, Optional

from infra_core.memory_system.dolt_mysql_base import DoltMySQLBase, DoltConnectionConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Schema branch prefix - must be exactly "schema-update" or start with "schema-update/"
SCHEMA_BRANCH_PREFIX = "schema-update"


class MigrationError(Exception):
    """Exception raised when migration operations fail."""

    pass


class MigrationRunner(DoltMySQLBase):
    """
    Migration runner that executes database migrations through Dolt SQL server.

    Subclasses DoltMySQLBase to leverage connection management and branch protection.
    Maintains a migrations table to track which migrations have been applied.

    Following DoltHub's "Schema Branch and Merge" pattern, this runner only
    operates on dedicated schema branches to isolate schema changes.
    """

    def __init__(self, config: DoltConnectionConfig):
        super().__init__(config)
        self.migrations_dir = Path(__file__).parent
        self._ensure_migrations_table()

    def _is_schema_branch(self, branch: str) -> bool:
        """
        Check if a branch is a valid schema branch for migrations.

        Only allows branches that are exactly "schema-update" or start with "schema-update/".

        Args:
            branch: Branch name to check

        Returns:
            True if branch is a valid schema branch
        """
        return branch == SCHEMA_BRANCH_PREFIX or branch.startswith(f"{SCHEMA_BRANCH_PREFIX}/")

    def _check_schema_branch_restriction(self, operation: str, target_branch: str) -> None:
        """
        Check if the operation is attempting to run on a non-schema branch.

        Args:
            operation: Description of the operation being attempted
            target_branch: The specific branch being targeted

        Raises:
            MigrationError: If attempting to run migrations on non-schema branch
        """
        if not self._is_schema_branch(target_branch):
            logger.error(
                f"Blocked {operation} on non-schema branch '{target_branch}' - "
                f"migrations must run on '{SCHEMA_BRANCH_PREFIX}' or branches starting with '{SCHEMA_BRANCH_PREFIX}/'"
            )
            raise MigrationError(
                f"Migration {operation} blocked: branch '{target_branch}' is not a valid schema branch. "
                f"Branch must be exactly '{SCHEMA_BRANCH_PREFIX}' or start with '{SCHEMA_BRANCH_PREFIX}/'"
            )

        logger.debug(f"Schema branch check passed: {operation} on branch '{target_branch}'")

    def _ensure_migrations_table(self) -> None:
        """Create the migrations tracking table if it doesn't exist."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS migrations (
            id VARCHAR(255) PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success BOOLEAN NOT NULL DEFAULT TRUE,
            error_message TEXT
        )
        """
        try:
            self._execute_update(create_table_sql)
            logger.debug("Migrations table ensured")
        except Exception as e:
            raise MigrationError(f"Failed to create migrations table: {e}")

    def _execute_in_transaction(self, operation_func, *args, **kwargs):
        """
        Execute an operation within a transaction for safety.

        Args:
            operation_func: Function to execute within transaction
            *args, **kwargs: Arguments to pass to operation_func

        Returns:
            Result of operation_func

        Raises:
            MigrationError: If transaction fails
        """
        # Store original persistent connection state
        original_use_persistent = self._use_persistent
        original_persistent_connection = self._persistent_connection

        # Use persistent connection if available, otherwise create new one
        if self._use_persistent and self._persistent_connection:
            connection = self._persistent_connection
            connection_is_persistent = True
        else:
            connection = self._get_connection()
            connection_is_persistent = False
            # Temporarily enable persistent mode to ensure all operations use this connection
            self._persistent_connection = connection
            self._use_persistent = True

        try:
            # Start transaction
            cursor = connection.cursor()
            cursor.execute("START TRANSACTION")

            # Debug check for autocommit status
            cursor.execute("SELECT @@autocommit")
            autocommit_result = cursor.fetchone()
            logger.debug(f"Autocommit status during transaction: {autocommit_result}")

            try:
                # Execute the operation
                result = operation_func(*args, **kwargs)

                # Commit transaction
                cursor.execute("COMMIT")
                logger.debug("Transaction committed successfully")
                return result

            except Exception as e:
                # Rollback on any error
                cursor.execute("ROLLBACK")
                logger.error(f"Transaction rolled back due to error: {e}")
                raise
            finally:
                cursor.close()

        except Exception as e:
            raise MigrationError(f"Transaction execution failed: {e}")
        finally:
            # Restore original persistent connection state
            if not connection_is_persistent:
                # We created a temporary connection, clean it up
                self._persistent_connection = original_persistent_connection
                self._use_persistent = original_use_persistent
                connection.close()
            # If it was already persistent, leave the state as-is

    def discover_migrations(self) -> List[str]:
        """
        Discover migration files in the migrations directory.

        Returns migration IDs sorted in execution order.
        Migration files should follow the pattern: NNNN_description.py
        """
        migration_files = []

        for file_path in self.migrations_dir.glob("*.py"):
            # Skip __init__.py, runner.py, and test files
            if file_path.name.startswith(("__", "runner", "test_")):
                continue

            # Extract migration ID from filename
            migration_id = file_path.stem
            migration_files.append(migration_id)

        # Sort by migration ID (assumes NNNN_ prefix for ordering)
        migration_files.sort()

        logger.debug(f"Discovered {len(migration_files)} migration files: {migration_files}")
        return migration_files

    def already_applied(self, migration_id: str) -> bool:
        """
        Check if a migration has already been successfully applied.

        Args:
            migration_id: The migration identifier to check

        Returns:
            True if migration was already applied successfully
        """
        query = "SELECT success FROM migrations WHERE id = %s"
        try:
            results = self._execute_query(query, (migration_id,))
            if results:
                return results[0]["success"]
            return False
        except Exception as e:
            logger.warning(f"Error checking migration status for {migration_id}: {e}")
            return False

    def _load_migration_module(self, migration_id: str):
        """
        Dynamically load a migration module.

        Args:
            migration_id: The migration identifier (filename without .py)

        Returns:
            The loaded migration module
        """
        migration_file = self.migrations_dir / f"{migration_id}.py"

        if not migration_file.exists():
            raise MigrationError(f"Migration file not found: {migration_file}")

        spec = importlib.util.spec_from_file_location(migration_id, migration_file)
        if spec is None or spec.loader is None:
            raise MigrationError(f"Could not load migration spec: {migration_file}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        return module

    def _apply_migration_unsafe(self, migration_id: str) -> bool:
        """
        Apply a single migration without transaction wrapper.

        This is the internal implementation called within a transaction.

        Args:
            migration_id: The migration identifier to apply

        Returns:
            True if migration was applied successfully
        """
        logger.info(f"Applying migration: {migration_id}")

        # Ensure migrations table exists on current branch (schema branches don't inherit it)
        self._ensure_migrations_table()

        # Load the migration module
        migration_module = self._load_migration_module(migration_id)

        # Check for required apply function
        if not hasattr(migration_module, "apply"):
            raise MigrationError(f"Migration {migration_id} missing apply() function")

        # Execute the migration
        migration_module.apply(self)

        # Record successful application
        insert_sql = "INSERT INTO migrations (id, success) VALUES (%s, %s)"
        self._execute_update(insert_sql, (migration_id, True))

        # Note: CREATE/ALTER statements return 0 affected rows, which is normal
        logger.info(f"Migration {migration_id} applied successfully")
        return True

    def apply(self, migration_id: str) -> bool:
        """
        Apply a single migration with transaction safety.

        Args:
            migration_id: The migration identifier to apply

        Returns:
            True if migration was applied successfully
        """
        if self.already_applied(migration_id):
            logger.info(f"Migration {migration_id} already applied, skipping")
            return True

        try:
            # Execute migration within transaction
            return self._execute_in_transaction(self._apply_migration_unsafe, migration_id)

        except Exception as e:
            error_msg = f"Migration {migration_id} failed: {e}"
            logger.error(error_msg)

            # Record failed application
            try:
                insert_sql = (
                    "INSERT INTO migrations (id, success, error_message) VALUES (%s, %s, %s)"
                )
                self._execute_update(insert_sql, (migration_id, False, str(e)))
            except Exception as record_error:
                logger.error(f"Failed to record migration failure: {record_error}")

            raise MigrationError(error_msg)

    def run_until(self, target_migration: Optional[str] = None, force: bool = False) -> bool:
        """
        Run migrations up to and including the target migration.

        Args:
            target_migration: Migration ID to run until (None = run all)
            force: Skip schema branch restriction (use with caution)

        Returns:
            True if all migrations were applied successfully
        """
        # Check branch protection (unless forced)
        current_branch = self.active_branch
        self._check_branch_protection("migration execution", current_branch)

        # Check schema branch restriction (unless forced)
        if not force:
            self._check_schema_branch_restriction("migration execution", current_branch)

        logger.info(f"Starting migration run on branch: {current_branch}")

        # Discover available migrations
        available_migrations = self.discover_migrations()

        if not available_migrations:
            logger.info("No migrations found")
            return True

        # Determine which migrations to run
        if target_migration:
            if target_migration not in available_migrations:
                raise MigrationError(f"Target migration not found: {target_migration}")

            # Find index of target migration
            target_index = available_migrations.index(target_migration)
            migrations_to_run = available_migrations[: target_index + 1]
        else:
            migrations_to_run = available_migrations

        logger.info(f"Planning to run {len(migrations_to_run)} migrations: {migrations_to_run}")

        # Apply migrations in order
        for migration_id in migrations_to_run:
            if not self.apply(migration_id):
                return False

        logger.info(
            f"Migration run completed successfully. Applied {len(migrations_to_run)} migrations."
        )
        return True


def main():
    """CLI entry point for the migration runner."""
    parser = argparse.ArgumentParser(
        description="Run Dolt database migrations on schema branches",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m infra_core.memory_system.migrations.runner --branch schema-update
  python -m infra_core.memory_system.migrations.runner --branch schema-update/feature-name --target 0001_namespace_seed
  python -m infra_core.memory_system.migrations.runner --branch main --force  # Use with caution!

Schema Branch Restriction:
  Migrations can only run on branches that are exactly "schema-update" or start with "schema-update/".
  Examples of valid branches: schema-update, schema-update/namespaces, schema-update/feature-xyz
  Examples of invalid branches: main, develop, feat/namespaces, schema, migrations
        """,
    )

    parser.add_argument(
        "--branch", required=True, help="Dolt branch to run migrations on (must be a schema branch)"
    )

    parser.add_argument("--target", help="Target migration to run until (default: run all)")

    parser.add_argument(
        "--force", action="store_true", help="Skip schema branch restriction (use with caution)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which migrations would be run without executing them",
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create configuration and runner
    config = DoltConnectionConfig()
    runner = MigrationRunner(config)

    try:
        # Use persistent connection for the migration run
        runner.use_persistent_connection(args.branch)

        if args.dry_run:
            # Show what would be run
            available_migrations = runner.discover_migrations()
            if args.target:
                if args.target not in available_migrations:
                    logger.error(f"Target migration not found: {args.target}")
                    sys.exit(1)
                target_index = available_migrations.index(args.target)
                migrations_to_run = available_migrations[: target_index + 1]
            else:
                migrations_to_run = available_migrations

            # Filter out already applied
            pending_migrations = [m for m in migrations_to_run if not runner.already_applied(m)]

            print(f"Would run {len(pending_migrations)} pending migrations:")
            for migration in pending_migrations:
                print(f"  - {migration}")

        else:
            # Run the migrations
            success = runner.run_until(args.target, force=args.force)
            if not success:
                logger.error("Migration run failed")
                sys.exit(1)

    except Exception as e:
        logger.error(f"Migration runner failed: {e}")
        sys.exit(1)
    finally:
        runner.close_persistent_connection()


if __name__ == "__main__":
    main()
