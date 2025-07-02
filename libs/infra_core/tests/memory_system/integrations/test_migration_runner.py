#!/usr/bin/env python3

"""Integration tests for the migration runner and namespace seeding migration.

These tests exercise the actual Dolt/MySQL runtime behavior including:
- FK constraint enforcement
- Migration tracking table functionality
- Namespace seeding migration execution
- Idempotent migration behavior
- Branch protection

NOTE: These tests are currently skipped due to test infrastructure issue where
global mysql.connector.connect mocks interfere with integration tests that need
real database connections. See bug: 099c655a-fc6e-4475-a9eb-9b802c9643c8
"""

import pytest
import uuid

from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig, MainBranchProtectionError
from infra_core.memory_system.migrations.runner import MigrationRunner


@pytest.mark.skip(
    reason="Integration tests skipped due to global mysql.connector.connect mock interference. See bug: 099c655a-fc6e-4475-a9eb-9b802c9643c8"
)
class TestMigrationRunner:
    """Integration tests for MigrationRunner class."""

    @pytest.fixture
    def config(self):
        """Create test database configuration."""
        return DoltConnectionConfig()

    @pytest.fixture
    def runner(self, config):
        """Create migration runner instance."""
        return MigrationRunner(config)

    def test_migrations_table_creation(self, runner):
        """Test that migrations table is created automatically."""
        # The table should be created during runner initialization
        query = "SHOW TABLES LIKE 'migrations'"
        result = runner._execute_query(query)
        assert len(result) == 1
        assert result[0]["Tables_in_memory_dolt (migrations)"] == "migrations"

        # Check table structure
        describe_result = runner._execute_query("DESCRIBE migrations")
        columns = {row["Field"]: row for row in describe_result}

        assert "id" in columns
        assert "applied_at" in columns
        assert "success" in columns
        assert "error_message" in columns
        assert columns["id"]["Key"] == "PRI"

    def test_discover_migrations(self, runner):
        """Test migration file discovery."""
        migrations = runner.discover_migrations()

        # Should find existing migration files but exclude runner.py and test files
        assert isinstance(migrations, list)

        # Should include our new namespace migration
        assert "0001_namespace_seed" in migrations

        # Should exclude runner and test files
        assert "runner" not in migrations
        assert "test_migration_runner" not in migrations

    def test_already_applied_tracking(self, runner):
        """Test migration application tracking."""
        test_migration_id = f"test_migration_{uuid.uuid4().hex[:8]}"

        # Initially should not be applied
        assert not runner.already_applied(test_migration_id)

        # Record as applied
        insert_sql = "INSERT INTO migrations (id, success) VALUES (%s, %s)"
        runner._execute_update(insert_sql, (test_migration_id, True))

        # Should now be marked as applied
        assert runner.already_applied(test_migration_id)

    def test_branch_protection(self, runner):
        """Test that migration runner respects branch protection."""
        # Try to run migrations on main branch (should fail)
        runner.use_persistent_connection("main")

        with pytest.raises(MainBranchProtectionError):
            runner.run_until()

        runner.close_persistent_connection()

    def test_migration_runner_on_safe_branch(self, runner):
        """Test migration runner works on non-protected branches."""
        # Use feat/namespaces branch (should work)
        runner.use_persistent_connection("feat/namespaces")

        try:
            # This should not raise branch protection error
            # (though it may fail for other reasons if migrations don't exist)
            result = runner.run_until()
            # We expect this to succeed or fail gracefully
            assert isinstance(result, bool)
        finally:
            runner.close_persistent_connection()


@pytest.mark.skip(
    reason="Integration tests skipped due to global mysql.connector.connect mock interference. See bug: 099c655a-fc6e-4475-a9eb-9b802c9643c8"
)
class TestNamespaceSeedingMigration:
    """Integration tests for the namespace seeding migration."""

    @pytest.fixture
    def config(self):
        """Create test database configuration."""
        return DoltConnectionConfig()

    @pytest.fixture
    def runner(self, config):
        """Create migration runner instance on safe branch."""
        runner = MigrationRunner(config)
        runner.use_persistent_connection("feat/namespaces")
        return runner

    @pytest.fixture(autouse=True)
    def cleanup_test_data(self, runner):
        """Clean up test data before and after each test."""
        yield
        # Cleanup after test
        try:
            # Remove any test namespaces
            runner._execute_update("DELETE FROM namespaces WHERE id LIKE 'test_%'")
            # Remove test migration records
            runner._execute_update("DELETE FROM migrations WHERE id LIKE 'test_%'")
        except Exception:
            pass  # Ignore cleanup errors
        finally:
            runner.close_persistent_connection()

    def test_namespace_seeding_migration_exists(self, runner):
        """Test that the namespace seeding migration file exists and is discoverable."""
        migrations = runner.discover_migrations()
        assert "0001_namespace_seed" in migrations

    def test_public_namespace_creation(self, runner):
        """Test that the migration creates the public namespace."""
        # Ensure public namespace doesn't exist
        runner._execute_update("DELETE FROM namespaces WHERE id = 'public'")

        # Apply the migration
        success = runner.apply("0001_namespace_seed")
        assert success

        # Verify public namespace was created
        query = "SELECT * FROM namespaces WHERE id = 'public'"
        result = runner._execute_query(query)
        assert len(result) == 1

        namespace = result[0]
        assert namespace["id"] == "public"
        assert namespace["name"] == "Public"
        assert namespace["slug"] == "public"
        assert namespace["owner_id"] == "system"

    def test_memory_blocks_migration(self, runner):
        """Test that existing memory blocks are migrated to public namespace."""
        # Create a test memory block without namespace_id
        test_block_id = f"test_block_{uuid.uuid4().hex[:8]}"

        # First ensure the memory_blocks table allows NULL namespace_id
        try:
            runner._execute_update(
                "ALTER TABLE memory_blocks MODIFY COLUMN namespace_id CHAR(36) NULL"
            )
        except Exception:
            pass  # May already be nullable

        # Insert test block with NULL namespace_id
        insert_block_sql = """
        INSERT INTO memory_blocks (id, type, text, state, visibility, created_at, updated_at)
        VALUES (%s, 'test', 'test content', 'draft', 'internal', NOW(), NOW())
        """
        runner._execute_update(insert_block_sql, (test_block_id,))

        # Verify block has NULL namespace_id
        check_query = "SELECT namespace_id FROM memory_blocks WHERE id = %s"
        result = runner._execute_query(check_query, (test_block_id,))
        assert result[0]["namespace_id"] is None

        # Apply the migration
        success = runner.apply("0001_namespace_seed")
        assert success

        # Verify block now has public namespace_id
        result = runner._execute_query(check_query, (test_block_id,))
        assert result[0]["namespace_id"] == "public"

        # Cleanup
        runner._execute_update("DELETE FROM memory_blocks WHERE id = %s", (test_block_id,))

    def test_foreign_key_constraint_enforcement(self, runner):
        """Test that FK constraints are properly enforced after migration."""
        # Apply the migration to ensure FK constraints are in place
        runner.apply("0001_namespace_seed")

        # Try to insert a memory block with invalid namespace_id
        test_block_id = f"test_block_{uuid.uuid4().hex[:8]}"
        invalid_namespace_id = "nonexistent_namespace"

        insert_sql = """
        INSERT INTO memory_blocks (id, type, text, state, visibility, namespace_id, created_at, updated_at)
        VALUES (%s, 'test', 'test content', 'draft', 'internal', %s, NOW(), NOW())
        """

        # This should fail due to FK constraint
        with pytest.raises(Exception) as exc_info:
            runner._execute_update(insert_sql, (test_block_id, invalid_namespace_id))

        # Should be a foreign key constraint violation
        error_msg = str(exc_info.value).lower()
        assert any(keyword in error_msg for keyword in ["foreign key", "constraint", "reference"])

    def test_migration_idempotency(self, runner):
        """Test that the migration can be run multiple times safely."""
        # Apply migration first time
        success1 = runner.apply("0001_namespace_seed")
        assert success1

        # Verify public namespace exists
        query = "SELECT COUNT(*) as count FROM namespaces WHERE id = 'public'"
        result = runner._execute_query(query)
        assert result[0]["count"] == 1

        # Apply migration second time (should be idempotent)
        success2 = runner.apply("0001_namespace_seed")
        assert success2

        # Should still have exactly one public namespace
        result = runner._execute_query(query)
        assert result[0]["count"] == 1

    def test_not_null_constraint_addition(self, runner):
        """Test that NOT NULL constraint is properly added to namespace_id."""
        # Apply the migration
        success = runner.apply("0001_namespace_seed")
        assert success

        # Check that namespace_id column is NOT NULL
        describe_result = runner._execute_query("DESCRIBE memory_blocks")
        namespace_column = None
        for column in describe_result:
            if column["Field"] == "namespace_id":
                namespace_column = column
                break

        assert namespace_column is not None
        assert namespace_column["Null"] == "NO"

        # Try to insert a memory block with NULL namespace_id (should fail)
        test_block_id = f"test_block_{uuid.uuid4().hex[:8]}"
        insert_sql = """
        INSERT INTO memory_blocks (id, type, text, state, visibility, namespace_id, created_at, updated_at)
        VALUES (%s, 'test', 'test content', 'draft', 'internal', NULL, NOW(), NOW())
        """

        with pytest.raises(Exception) as exc_info:
            runner._execute_update(insert_sql, (test_block_id,))

        # Should be a NOT NULL constraint violation
        error_msg = str(exc_info.value).lower()
        assert any(keyword in error_msg for keyword in ["null", "cannot be null"])

    def test_migration_tracking(self, runner):
        """Test that migration application is properly tracked."""
        # Apply the migration
        success = runner.apply("0001_namespace_seed")
        assert success

        # Check that migration is recorded as applied
        query = "SELECT * FROM migrations WHERE id = '0001_namespace_seed'"
        result = runner._execute_query(query)
        assert len(result) == 1

        migration_record = result[0]
        assert migration_record["id"] == "0001_namespace_seed"
        assert migration_record["success"] is True
        assert migration_record["applied_at"] is not None
        assert migration_record["error_message"] is None

    def test_concurrent_migration_safety(self, runner):
        """Test that concurrent migration attempts are handled safely."""
        # This test simulates what happens if two processes try to run
        # the same migration simultaneously

        # First, ensure migration hasn't been applied
        runner._execute_update("DELETE FROM migrations WHERE id = '0001_namespace_seed'")
        runner._execute_update("DELETE FROM namespaces WHERE id = 'public'")

        # Apply migration first time
        success1 = runner.apply("0001_namespace_seed")
        assert success1

        # Simulate second process checking if already applied
        already_applied = runner.already_applied("0001_namespace_seed")
        assert already_applied

        # Second application should be skipped
        success2 = runner.apply("0001_namespace_seed")
        assert success2  # Should succeed (skipped)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
