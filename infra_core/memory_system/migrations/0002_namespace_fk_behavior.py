#!/usr/bin/env python3

"""
Migration 0002: Update foreign key constraint behavior for namespace_id

This migration addresses the feedback from the namespace implementation PR:
- Removes the existing FK constraint (which has unclear ON DELETE/UPDATE behavior)
- Adds a new FK constraint with explicit ON DELETE RESTRICT ON UPDATE CASCADE behavior
- Uses proper constraint naming for consistency

Design decisions:
1. Attempts to drop known constraint names without heavy discovery queries
2. Handles Dolt's lack of IF EXISTS support by catching specific errors
3. Uses direct approach since we know the possible constraint names
4. Provides proper rollback support
"""

from typing import TYPE_CHECKING
import mysql.connector
import logging

if TYPE_CHECKING:
    from infra_core.memory_system.migrations.runner import MigrationRunner

logger = logging.getLogger(__name__)

# Known possible constraint names from schema history
KNOWN_CONSTRAINT_NAMES = [
    "fk_namespace",  # Legacy constraint name
    "fk_memory_blocks_namespace",  # New standard name
    "memory_blocks_ibfk_1",  # MySQL auto-generated name
]

NEW_CONSTRAINT_NAME = "fk_memory_blocks_namespace"


def _drop_constraint_safe(runner: "MigrationRunner", constraint_name: str) -> bool:
    """
    Safely attempt to drop a foreign key constraint.

    Returns True if constraint was dropped, False if it didn't exist.
    Raises on other errors.
    """
    try:
        drop_sql = f"ALTER TABLE memory_blocks DROP FOREIGN KEY {constraint_name}"
        runner._execute_update(drop_sql)
        logger.info(f"Dropped constraint: {constraint_name}")
        return True
    except Exception as e:
        # Check if error is "constraint doesn't exist" vs other errors
        error_msg = str(e).lower()
        if any(
            phrase in error_msg
            for phrase in [
                "doesn't exist",
                "does not exist",
                "unknown constraint",
                "can't drop",
                "was not found",
            ]
        ):
            logger.debug(f"Constraint {constraint_name} doesn't exist, skipping")
            return False
        else:
            # Re-raise other errors
            logger.error(f"Error dropping constraint {constraint_name}: {e}")
            raise


def _constraint_exists(runner: "MigrationRunner", constraint_name: str) -> bool:
    """Check if a foreign key constraint exists."""
    try:
        check_sql = """
        SELECT COUNT(*) as count 
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = 'memory_blocks' 
        AND CONSTRAINT_NAME = %s 
        AND CONSTRAINT_TYPE = 'FOREIGN KEY'
        """
        results = runner._execute_query(check_sql, (constraint_name,))
        return results[0]["count"] > 0 if results else False
    except Exception as e:
        logger.warning(f"Error checking constraint existence: {e}")
        return False


def apply(runner):
    """
    Apply the FK constraint behavior fix.

    This migration:
    1. Drops any existing FK constraints on memory_blocks.namespace_id
    2. Adds a new FK constraint with explicit ON DELETE RESTRICT ON UPDATE CASCADE behavior
    3. Validates the result

    Args:
        runner: MigrationRunner instance with database connection
    """
    logger.info("Starting FK behavior migration - upgrading to explicit constraint behavior")

    # Step 1: Drop any existing constraints
    dropped_any = False
    for constraint_name in KNOWN_CONSTRAINT_NAMES:
        if _drop_constraint_safe(runner, constraint_name):
            dropped_any = True

    if not dropped_any:
        logger.info("No existing FK constraints found to drop")

    # Step 2: Add the new constraint with explicit behavior
    logger.info(f"Adding new FK constraint '{NEW_CONSTRAINT_NAME}' with explicit behavior")
    add_constraint_sql = f"""
    ALTER TABLE memory_blocks 
    ADD CONSTRAINT {NEW_CONSTRAINT_NAME} 
    FOREIGN KEY (namespace_id) 
    REFERENCES namespaces(id) 
    ON DELETE RESTRICT 
    ON UPDATE CASCADE
    """

    try:
        runner._execute_update(add_constraint_sql)
        logger.info(f"Successfully added constraint '{NEW_CONSTRAINT_NAME}'")
    except mysql.connector.Error as e:
        if "duplicate" in str(e).lower():
            logger.warning(f"Constraint '{NEW_CONSTRAINT_NAME}' already exists")
        else:
            raise

    # Step 3: Validate the result
    if _constraint_exists(runner, NEW_CONSTRAINT_NAME):
        logger.info("Migration completed successfully - FK constraint is properly configured")
    else:
        raise Exception("Migration validation failed - new constraint not found")


def rollback(runner):
    """
    Rollback the FK constraint behavior fix.

    This restores the basic FK constraint without explicit ON DELETE/UPDATE behavior.

    Args:
        runner: MigrationRunner instance with database connection
    """
    logger.info("Starting FK behavior migration rollback")

    # Step 1: Drop the new constraint
    _drop_constraint_safe(runner, NEW_CONSTRAINT_NAME)

    # Step 2: Restore basic constraint (MySQL will use default behavior)
    logger.info("Restoring basic FK constraint")
    restore_sql = """
    ALTER TABLE memory_blocks 
    ADD CONSTRAINT fk_namespace 
    FOREIGN KEY (namespace_id) 
    REFERENCES namespaces(id)
    """

    try:
        runner._execute_update(restore_sql)
        logger.info("Rollback completed - restored basic FK constraint")
    except mysql.connector.Error as e:
        if "duplicate" in str(e).lower():
            logger.warning("Basic FK constraint already exists")
        else:
            raise


# Required migration metadata
MIGRATION_ID = "0002_namespace_fk_behavior"
DESCRIPTION = "Update foreign key constraint behavior for namespace_id"
