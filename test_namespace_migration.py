#!/usr/bin/env python3
"""Test namespace migration on schema branch."""

import os
from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig
from infra_core.memory_system.migrations.runner import MigrationRunner


def test_namespace_migration():
    """Test creating schema branch and running namespace migration."""

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
        print(f"✅ Migration runner ready on branch: {runner.active_branch}")

        # Create and checkout schema branch
        import time

        schema_branch = f"schema-update/namespace-test-{int(time.time())}"
        print(f"🔄 Creating schema branch: {schema_branch}")

        # Create branch from main - use _execute_query to handle stored procedure results
        try:
            result = runner._execute_query("CALL DOLT_BRANCH(%s)", (schema_branch,))
            print(f"✅ Created branch: {schema_branch} (result: {result})")
        except Exception as e:
            if "already exists" in str(e):
                print(f"ℹ️ Branch {schema_branch} already exists, continuing...")
            else:
                raise

        # Switch to schema branch
        runner.use_persistent_connection(schema_branch)
        current_branch = runner.active_branch
        print(f"✅ Switched to branch: {current_branch}")

        # Check if namespace migration has been applied
        already_applied = runner.already_applied("0001_namespace_seed")
        print(f"✅ Migration 0001_namespace_seed already applied: {already_applied}")

        if not already_applied:
            print("🔄 Applying namespace migration...")
            success = runner.apply("0001_namespace_seed")
            print(f"✅ Migration applied successfully: {success}")

            # Verify namespaces table was created
            tables_result = runner._execute_query("SHOW TABLES LIKE 'namespaces'")
            if tables_result:
                print("✅ Namespaces table created successfully")

                # Check if legacy namespace was seeded
                legacy_ns = runner._execute_query("SELECT * FROM namespaces WHERE id = 'legacy'")
                if legacy_ns:
                    print(f"✅ Legacy namespace seeded: {legacy_ns[0]}")
                else:
                    print("❌ Legacy namespace not found")
            else:
                print("❌ Namespaces table not found")
        else:
            print("ℹ️ Migration already applied, checking existing state...")

            # Check existing namespaces table
            tables_result = runner._execute_query("SHOW TABLES LIKE 'namespaces'")
            if tables_result:
                print("✅ Namespaces table exists")
                namespaces = runner._execute_query("SELECT * FROM namespaces")
                print(f"✅ Existing namespaces: {len(namespaces)} found")
                for ns in namespaces:
                    print(f"  - {ns}")

        # Clean up - close persistent connection
        runner.close_persistent_connection()
        print("✅ Test completed successfully")
        return True

    except Exception as e:
        print(f"❌ Namespace migration test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_namespace_migration()
