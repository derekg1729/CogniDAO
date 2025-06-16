#!/usr/bin/env python3
"""Debug script to check branch state."""

import os
from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig
from infra_core.memory_system.migrations.runner import MigrationRunner


def debug_branch_state():
    """Debug what's on the current schema branch."""

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

        # Create a fresh schema branch
        import time

        schema_branch = f"debug-schema-{int(time.time())}"
        print(f"🔄 Creating fresh schema branch: {schema_branch}")

        # Create branch from main
        try:
            runner._execute_query("CALL DOLT_BRANCH(%s)", (schema_branch,))
            print(f"✅ Created branch: {schema_branch}")
        except Exception as e:
            print(f"❌ Failed to create branch: {e}")
            return False

        # Switch to schema branch
        runner.use_persistent_connection(schema_branch)
        current_branch = runner.active_branch
        print(f"✅ Switched to branch: {current_branch}")

        # Check what tables exist
        tables = runner._execute_query("SHOW TABLES")
        if tables:
            table_names = [list(table.values())[0] for table in tables]
            print(f"✅ Tables on {current_branch}: {table_names}")
        else:
            print(f"✅ No tables on {current_branch}")

        # Check if namespaces table exists
        namespaces_check = runner._execute_query("SHOW TABLES LIKE 'namespaces'")
        print(f"✅ Namespaces table exists: {bool(namespaces_check)}")

        if namespaces_check:
            # Show the table structure
            describe = runner._execute_query("DESCRIBE namespaces")
            print("✅ Namespaces table structure:")
            for col in describe:
                print(f"  - {col}")

            # Show indexes
            indexes = runner._execute_query("SHOW INDEX FROM namespaces")
            print("✅ Namespaces table indexes:")
            for idx in indexes:
                print(f"  - {idx}")

        # Clean up
        runner.close_persistent_connection()
        return True

    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    debug_branch_state()
