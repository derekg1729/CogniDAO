#!/usr/bin/env python3

"""Migration 0001: Seed default 'public' namespace and migrate existing memory blocks.

This migration implements the namespace seeding strategy:
1. INSERT the default 'public' namespace
2. UPDATE all existing memory_blocks to reference the public namespace
3. ALTER TABLE to add NOT NULL constraint on namespace_id

This migration is idempotent and can be safely re-run.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Default public namespace configuration
PUBLIC_NAMESPACE_ID = "public"
PUBLIC_NAMESPACE_NAME = "Public"
PUBLIC_NAMESPACE_SLUG = "public"
PUBLIC_NAMESPACE_OWNER_ID = "system"
PUBLIC_NAMESPACE_DESCRIPTION = "Default public namespace for shared memory blocks"


def apply(runner):
    """
    Apply the namespace seeding migration.

    Args:
        runner: MigrationRunner instance with database connection
    """
    logger.info("Starting namespace seeding migration")

    # Step 1: Insert the default 'public' namespace if it doesn't exist
    _ensure_public_namespace(runner)

    # Step 2: Update existing memory_blocks to reference public namespace
    _migrate_existing_blocks(runner)

    # Step 3: Add NOT NULL constraint to namespace_id (if not already present)
    _add_not_null_constraint(runner)

    logger.info("Namespace seeding migration completed successfully")


def _ensure_public_namespace(runner):
    """Insert the public namespace if it doesn't already exist."""
    logger.info("Ensuring public namespace exists")

    # Check if public namespace already exists
    check_query = "SELECT id FROM namespaces WHERE id = %s"
    existing = runner._execute_query(check_query, (PUBLIC_NAMESPACE_ID,))

    if existing:
        logger.info("Public namespace already exists, skipping creation")
        return

    # Insert the public namespace
    insert_query = """
    INSERT INTO namespaces (id, name, slug, owner_id, created_at, description)
    VALUES (%s, %s, %s, %s, %s, %s)
    """

    current_time = datetime.utcnow()
    params = (
        PUBLIC_NAMESPACE_ID,
        PUBLIC_NAMESPACE_NAME,
        PUBLIC_NAMESPACE_SLUG,
        PUBLIC_NAMESPACE_OWNER_ID,
        current_time,
        PUBLIC_NAMESPACE_DESCRIPTION,
    )

    try:
        runner._execute_update(insert_query, params)
        logger.info(f"Created public namespace with ID: {PUBLIC_NAMESPACE_ID}")
    except Exception as e:
        # Check if this is a duplicate key error (race condition)
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            logger.info("Public namespace was created by another process, continuing")
        else:
            raise


def _migrate_existing_blocks(runner):
    """Update existing memory_blocks to reference the public namespace."""
    logger.info("Migrating existing memory blocks to public namespace")

    # Count blocks that need migration (where namespace_id is NULL or empty/whitespace)
    count_query = """
    SELECT COUNT(*) as count 
    FROM memory_blocks 
    WHERE COALESCE(NULLIF(TRIM(namespace_id),''),NULL) IS NULL
    """

    count_result = runner._execute_query(count_query)
    blocks_to_migrate = count_result[0]["count"] if count_result else 0

    if blocks_to_migrate == 0:
        logger.info("No memory blocks need namespace migration")
        return

    logger.info(f"Found {blocks_to_migrate} memory blocks to migrate to public namespace")

    # Update blocks to reference public namespace
    update_query = """
    UPDATE memory_blocks 
    SET namespace_id = %s 
    WHERE COALESCE(NULLIF(TRIM(namespace_id),''),NULL) IS NULL
    """

    try:
        rows_updated = runner._execute_update(update_query, (PUBLIC_NAMESPACE_ID,))
        logger.info(f"Successfully migrated {rows_updated} memory blocks to public namespace")
    except Exception as e:
        logger.error(f"Failed to migrate memory blocks: {e}")
        raise


def _add_not_null_constraint(runner):
    """Add NOT NULL constraint to namespace_id column if not already present."""
    logger.info("Adding NOT NULL constraint to namespace_id column")

    # Check current column definition
    describe_query = "DESCRIBE memory_blocks"
    columns = runner._execute_query(describe_query)

    # Find namespace_id column
    namespace_column = None
    for column in columns:
        if column["Field"] == "namespace_id":
            namespace_column = column
            break

    if not namespace_column:
        logger.warning("namespace_id column not found in memory_blocks table")
        return

    # Check if column is already NOT NULL
    if namespace_column["Null"] == "NO":
        logger.info("namespace_id column already has NOT NULL constraint")
        return

    # Add NOT NULL constraint with DEFAULT value
    # Note: In MySQL/Dolt, we need to use MODIFY COLUMN to change nullability
    # Keep VARCHAR(255) to match existing schema and add DEFAULT 'public'
    alter_query = """
    ALTER TABLE memory_blocks 
    MODIFY COLUMN namespace_id VARCHAR(255) NOT NULL DEFAULT 'public'
    """

    try:
        runner._execute_update(alter_query)
        logger.info("Successfully added NOT NULL constraint to namespace_id column")
    except Exception as e:
        logger.error(f"Failed to add NOT NULL constraint: {e}")
        raise


def rollback(runner):
    """
    Rollback the namespace seeding migration.

    WARNING: This will remove the public namespace and reset all memory_blocks
    to have NULL namespace_id. Use with extreme caution.

    Args:
        runner: MigrationRunner instance with database connection
    """
    logger.warning("Rolling back namespace seeding migration")

    # Step 1: Remove NOT NULL constraint
    try:
        alter_query = """
        ALTER TABLE memory_blocks 
        MODIFY COLUMN namespace_id VARCHAR(255) NULL
        """
        runner._execute_update(alter_query)
        logger.info("Removed NOT NULL constraint from namespace_id")
    except Exception as e:
        logger.warning(f"Failed to remove NOT NULL constraint: {e}")

    # Step 2: Reset memory_blocks namespace_id to NULL
    try:
        update_query = "UPDATE memory_blocks SET namespace_id = NULL WHERE namespace_id = %s"
        rows_updated = runner._execute_update(update_query, (PUBLIC_NAMESPACE_ID,))
        logger.info(f"Reset {rows_updated} memory blocks to NULL namespace_id")
    except Exception as e:
        logger.warning(f"Failed to reset memory blocks: {e}")

    # Step 3: Delete public namespace
    try:
        delete_query = "DELETE FROM namespaces WHERE id = %s"
        runner._execute_update(delete_query, (PUBLIC_NAMESPACE_ID,))
        logger.info("Deleted public namespace")
    except Exception as e:
        logger.warning(f"Failed to delete public namespace: {e}")

    logger.warning("Namespace seeding migration rollback completed")
