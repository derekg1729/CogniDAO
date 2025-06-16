#!/usr/bin/env python3
"""Test migration runner with Docker Dolt SQL server."""

import os
from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig
from infra_core.memory_system.migrations.runner import MigrationRunner


def test_migration_runner():
    """Test migration runner connection and basic operations."""

    # Set environment variables for Docker Dolt connection
    os.environ["MYSQL_HOST"] = "localhost"
    os.environ["MYSQL_PORT"] = "3306"
    os.environ["MYSQL_USER"] = "root"
    os.environ["MYSQL_PASSWORD"] = "kXMnM6firYohXzK+2r0E0DmSjOl6g3A2SmXc6ALDOlA="
    os.environ["MYSQL_DATABASE"] = "cogni-dao-memory"

    try:
        # Create configuration
        config = DoltConnectionConfig()
        print(f"✅ Configuration created: {config.host}:{config.port}/{config.database}")

        # Create migration runner
        runner = MigrationRunner(config)
        print("✅ Migration runner created")

        # Test basic connection by checking current branch
        current_branch = runner.active_branch
        print(f"✅ Current branch: {current_branch}")

        # Test migration discovery
        migrations = runner.discover_migrations()
        print(f"✅ Discovered migrations: {migrations}")

        # Test migrations table creation (should already exist)
        runner._ensure_migrations_table()
        print("✅ Migrations table ensured")

        return True

    except Exception as e:
        print(f"❌ Migration runner test failed: {e}")
        return False


if __name__ == "__main__":
    test_migration_runner()
