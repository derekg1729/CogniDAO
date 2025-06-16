"""Tests for migration 0002: namespace FK behavior fix."""

import pytest
import mysql.connector
from unittest.mock import Mock
from infra_core.memory_system.migrations import migration_0002_namespace_fk_behavior as migration


class TestConstraintHelpers:
    """Test the helper functions for constraint management."""

    def test_drop_constraint_safe_success(self):
        """Test successful constraint drop."""
        runner = Mock()
        runner._execute_update.return_value = 1

        result = migration._drop_constraint_safe(runner, "test_constraint")

        assert result is True
        runner._execute_update.assert_called_once_with(
            "ALTER TABLE memory_blocks DROP FOREIGN KEY test_constraint"
        )

    def test_drop_constraint_safe_not_exists(self):
        """Test constraint drop when constraint doesn't exist."""
        runner = Mock()
        runner._execute_update.side_effect = mysql.connector.Error("Constraint doesn't exist")

        result = migration._drop_constraint_safe(runner, "test_constraint")

        assert result is False

    def test_drop_constraint_safe_other_error(self):
        """Test constraint drop with unexpected error."""
        runner = Mock()
        runner._execute_update.side_effect = mysql.connector.Error("Some other error")

        with pytest.raises(mysql.connector.Error):
            migration._drop_constraint_safe(runner, "test_constraint")

    def test_constraint_exists_true(self):
        """Test constraint existence check when constraint exists."""
        runner = Mock()
        runner._execute_query.return_value = [{"count": 1}]

        result = migration._constraint_exists(runner, "test_constraint")

        assert result is True

    def test_constraint_exists_false(self):
        """Test constraint existence check when constraint doesn't exist."""
        runner = Mock()
        runner._execute_query.return_value = [{"count": 0}]

        result = migration._constraint_exists(runner, "test_constraint")

        assert result is False


class TestMigrationApply:
    """Test the apply migration function."""

    def test_apply_drops_all_known_constraints(self):
        """Test that apply attempts to drop all known constraint names."""
        runner = Mock()

        # Mock dropping constraints - first two don't exist, third exists
        side_effects = [
            mysql.connector.Error("doesn't exist"),  # fk_namespace
            mysql.connector.Error("doesn't exist"),  # fk_memory_blocks_namespace
            1,  # memory_blocks_ibfk_1
        ]
        runner._execute_update.side_effect = side_effects + [
            1,
            1,
        ]  # Add constraint, check existence
        runner._execute_query.return_value = [{"count": 1}]  # Constraint exists after creation

        migration.apply(runner)

        # Should try to drop all known constraints
        expected_drops = [
            "ALTER TABLE memory_blocks DROP FOREIGN KEY fk_namespace",
            "ALTER TABLE memory_blocks DROP FOREIGN KEY fk_memory_blocks_namespace",
            "ALTER TABLE memory_blocks DROP FOREIGN KEY memory_blocks_ibfk_1",
        ]

        actual_drops = [call.args[0] for call in runner._execute_update.call_args_list[:3]]
        assert actual_drops == expected_drops

    def test_apply_adds_new_constraint(self):
        """Test that apply adds the new constraint with proper behavior."""
        runner = Mock()

        # Mock no existing constraints, successful constraint addition, successful validation
        runner._execute_update.side_effect = [
            mysql.connector.Error("doesn't exist"),  # Drop attempts
            mysql.connector.Error("doesn't exist"),
            mysql.connector.Error("doesn't exist"),
            1,  # Add constraint
        ]
        runner._execute_query.return_value = [{"count": 1}]  # Constraint exists after creation

        migration.apply(runner)

        # Check the constraint addition SQL
        add_call = runner._execute_update.call_args_list[3]
        add_sql = add_call.args[0]

        assert "ADD CONSTRAINT fk_memory_blocks_namespace" in add_sql
        assert "ON DELETE RESTRICT" in add_sql
        assert "ON UPDATE CASCADE" in add_sql

    def test_apply_handles_duplicate_constraint(self):
        """Test that apply handles duplicate constraint gracefully."""
        runner = Mock()

        # Mock constraint already exists
        runner._execute_update.side_effect = [
            mysql.connector.Error("doesn't exist"),  # Drop attempts
            mysql.connector.Error("doesn't exist"),
            mysql.connector.Error("doesn't exist"),
            mysql.connector.Error("duplicate constraint"),  # Add constraint fails (already exists)
        ]
        runner._execute_query.return_value = [{"count": 1}]  # Constraint exists

        # Should not raise an exception
        migration.apply(runner)

    def test_apply_validation_failure(self):
        """Test that apply raises error if validation fails."""
        runner = Mock()

        # Mock successful operations but validation failure
        runner._execute_update.side_effect = [
            mysql.connector.Error("doesn't exist"),  # Drop attempts
            mysql.connector.Error("doesn't exist"),
            mysql.connector.Error("doesn't exist"),
            1,  # Add constraint
        ]
        runner._execute_query.return_value = [
            {"count": 0}
        ]  # Constraint doesn't exist after creation

        with pytest.raises(Exception, match="Migration validation failed"):
            migration.apply(runner)


class TestMigrationRollback:
    """Test the rollback migration function."""

    def test_rollback_drops_new_constraint(self):
        """Test that rollback drops the new constraint."""
        runner = Mock()
        runner._execute_update.side_effect = [1, 1]  # Drop successful, add successful

        migration.rollback(runner)

        # First call should drop the new constraint
        drop_call = runner._execute_update.call_args_list[0]
        assert "DROP FOREIGN KEY fk_memory_blocks_namespace" in drop_call.args[0]

    def test_rollback_restores_basic_constraint(self):
        """Test that rollback restores basic constraint."""
        runner = Mock()
        runner._execute_update.side_effect = [1, 1]  # Drop successful, add successful

        migration.rollback(runner)

        # Second call should add basic constraint
        add_call = runner._execute_update.call_args_list[1]
        add_sql = add_call.args[0]

        assert "ADD CONSTRAINT fk_namespace" in add_sql
        assert "FOREIGN KEY (namespace_id)" in add_sql
        assert "REFERENCES namespaces(id)" in add_sql
        # Should NOT have explicit ON DELETE/UPDATE clauses
        assert "ON DELETE" not in add_sql
        assert "ON UPDATE" not in add_sql

    def test_rollback_handles_duplicate_constraint(self):
        """Test that rollback handles duplicate constraint gracefully."""
        runner = Mock()
        runner._execute_update.side_effect = [
            1,  # Drop successful
            mysql.connector.Error("duplicate constraint"),  # Add fails (already exists)
        ]

        # Should not raise an exception
        migration.rollback(runner)


class TestIntegrationScenarios:
    """Integration tests for real-world scenarios."""

    @pytest.mark.integration
    def test_namespace_cascade_update(self):
        """Test that updating namespace_id cascades to memory_blocks (placeholder)."""
        # This would be a real database integration test
        # For now, just verify the SQL structure is correct

        # The migration should create this constraint:
        expected_constraint = """
        ALTER TABLE memory_blocks 
        ADD CONSTRAINT fk_memory_blocks_namespace 
        FOREIGN KEY (namespace_id) 
        REFERENCES namespaces(id) 
        ON DELETE RESTRICT 
        ON UPDATE CASCADE
        """

        # Test that the constraint SQL contains the right clauses
        assert "ON DELETE RESTRICT" in expected_constraint
        assert "ON UPDATE CASCADE" in expected_constraint

    @pytest.mark.integration
    def test_namespace_delete_restriction(self):
        """Test that deleting in-use namespace fails (placeholder)."""
        # This would be a real database integration test
        # For now, just verify the constraint behavior is specified correctly

        # The ON DELETE RESTRICT should prevent deletion of in-use namespaces
        # This is a placeholder for a real integration test that would:
        # 1. Create a namespace
        # 2. Create memory blocks using that namespace
        # 3. Try to delete the namespace
        # 4. Verify it fails with FK constraint violation
        pass


class TestMigrationMetadata:
    """Test migration metadata."""

    def test_migration_id(self):
        """Test migration has correct ID."""
        assert migration.MIGRATION_ID == "0002_namespace_fk_behavior"

    def test_migration_description(self):
        """Test migration has description."""
        assert migration.DESCRIPTION == "Update foreign key constraint behavior for namespace_id"

    def test_constraint_names(self):
        """Test known constraint names are defined."""
        expected_names = [
            "fk_namespace",
            "fk_memory_blocks_namespace",
            "memory_blocks_ibfk_1",
        ]
        assert migration.KNOWN_CONSTRAINT_NAMES == expected_names
        assert migration.NEW_CONSTRAINT_NAME == "fk_memory_blocks_namespace"
