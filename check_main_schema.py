#!/usr/bin/env python3
"""Check schema on main branch."""

import os
from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig
from infra_core.memory_system.migrations.runner import MigrationRunner


def check_main_schema():
    """Check what tables exist on main branch."""

    # Set environment variables for Docker Dolt connection
    os.environ["MYSQL_HOST"] = "localhost"
    os.environ["MYSQL_PORT"] = "3306"
    os.environ["MYSQL_USER"] = "root"
    os.environ["MYSQL_PASSWORD"] = "kXMnM6firYohXzK+2r0E0DmSjOl6g3A2SmXc6ALDOlA="
    os.environ["MYSQL_DATABASE"] = "cogni-dao-memory"

    try:
        # Create configuration and runner
        config = DoltConnectionConfig()
        runner = MigrationRunner(config)
        print(f"✅ Connected to branch: {runner.active_branch}")

        # List all tables
        tables = runner._execute_query("SHOW TABLES")
        print(f"✅ Tables result format: {tables[:2] if tables else 'No tables'}")

        # Extract table names based on actual format
        if tables:
            if isinstance(tables[0], dict):
                table_names = [list(table.values())[0] for table in tables]
            else:
                table_names = [table[0] for table in tables]
            print(f"✅ Tables on main branch: {table_names}")
        else:
            print("✅ No tables found")

        # Check if namespaces table exists
        namespaces_check = runner._execute_query("SHOW TABLES LIKE 'namespaces'")
        print(f"✅ Namespaces table exists: {bool(namespaces_check)}")

        # Check memory_blocks schema
        memory_blocks_schema = runner._execute_query("DESCRIBE memory_blocks")
        print("✅ memory_blocks schema:")
        for column in memory_blocks_schema:
            print(
                f"  - {column['Field']}: {column['Type']} {'NOT NULL' if column['Null'] == 'NO' else 'NULL'}"
            )

        # Check if namespace_id column exists in memory_blocks
        namespace_id_exists = any(col["Field"] == "namespace_id" for col in memory_blocks_schema)
        print(f"✅ namespace_id column exists in memory_blocks: {namespace_id_exists}")

        return True

    except Exception as e:
        print(f"❌ Schema check failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    check_main_schema()
