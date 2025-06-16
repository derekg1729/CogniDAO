#!/usr/bin/env python3

"""Migration runner for Dolt database schema and data migrations.

This module provides a MigrationRunner class that subclasses DoltMySQLBase
to execute migrations through the Dolt SQL server connection.

Key features:
- Discovers migration files in the migrations directory
- Tracks applied migrations in a migrations table
- Executes migrations in order with proper error handling
- Refuses to run on protected branches (main, master)
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


class MigrationError(Exception):
    """Exception raised when migration operations fail."""

    pass


class MigrationRunner(DoltMySQLBase):
    """
    Migration runner that executes database migrations through Dolt SQL server.

    Subclasses DoltMySQLBase to leverage connection management and branch protection.
    Maintains a migrations table to track which migrations have been applied.
    """

    def __init__(self, config: DoltConnectionConfig):
        super().__init__(config)
        self.migrations_dir = Path(__file__).parent
        self._ensure_migrations_table()

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

        logger.info(f"Discovered {len(migration_files)} migration files: {migration_files}")
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

    def apply(self, migration_id: str) -> bool:
        """
        Apply a single migration.

        Args:
            migration_id: The migration identifier to apply

        Returns:
            True if migration was applied successfully
        """
        if self.already_applied(migration_id):
            logger.info(f"Migration {migration_id} already applied, skipping")
            return True

        logger.info(f"Applying migration: {migration_id}")

        try:
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

            logger.info(f"Migration {migration_id} applied successfully")
            return True

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

    def run_until(self, target_migration: Optional[str] = None) -> bool:
        """
        Run migrations up to and including the target migration.

        Args:
            target_migration: Migration ID to run until (None = run all)

        Returns:
            True if all migrations were applied successfully
        """
        # Check branch protection
        current_branch = self.active_branch
        self._check_branch_protection("migration execution", current_branch)

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
        description="Run Dolt database migrations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m infra_core.migrations.runner --branch schema-update
  python -m infra_core.migrations.runner --branch feat/namespaces --target 0001_namespace_seed
        """,
    )

    parser.add_argument(
        "--branch", required=True, help="Dolt branch to run migrations on (required for safety)"
    )

    parser.add_argument("--target", help="Target migration to run until (default: run all)")

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
            success = runner.run_until(args.target)
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
