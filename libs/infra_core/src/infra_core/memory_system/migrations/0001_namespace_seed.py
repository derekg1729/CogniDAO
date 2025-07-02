#!/usr/bin/env python3

"""Migration 0001: Seed default 'legacy' namespace and migrate existing memory blocks.

This migration implements the namespace seeding strategy:
1. INSERT the default 'legacy' namespace
2. UPDATE all existing memory_blocks to reference the legacy namespace
3. ALTER TABLE to add NOT NULL constraint on namespace_id

This migration is idempotent and can be safely re-run.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Default legacy namespace configuration
LEGACY_NAMESPACE_ID = "legacy"
LEGACY_NAMESPACE_NAME = "Legacy"
LEGACY_NAMESPACE_SLUG = "legacy"
LEGACY_NAMESPACE_OWNER_ID = "system"
LEGACY_NAMESPACE_DESCRIPTION = "Default legacy namespace for pre-migration memory blocks"


def apply(runner):
    """
    Apply the namespace seeding migration.

    Args:
        runner: MigrationRunner instance with database connection
    """
    logger.info("Starting namespace seeding migration")

    # Step 0: Create schema (tables and columns) if they don't exist
    _create_namespaces_table(runner)
    _add_namespace_id_column(runner)

    # Step 1: Insert the default 'legacy' namespace if it doesn't exist
    _ensure_legacy_namespace(runner)

    # Step 2: Update existing memory_blocks to reference legacy namespace
    _migrate_existing_blocks(runner)

    # Step 3: Add NOT NULL constraint to namespace_id (if not already present)
    _add_not_null_constraint(runner)

    # Step 4: Add explicit FK constraint with proper ON DELETE/UPDATE behavior
    _add_namespace_fk_constraint(runner)

    logger.info("Namespace seeding migration completed successfully")


def _create_namespaces_table(runner):
    """Create the namespaces table if it doesn't exist."""
    logger.info("Creating namespaces table if it doesn't exist")

    # Check if table already exists
    check_query = "SHOW TABLES LIKE 'namespaces'"
    existing = runner._execute_query(check_query)

    if existing:
        logger.info("Namespaces table already exists, skipping creation")
        return

    # Create namespaces table (without indexes first)
    create_query = """
    CREATE TABLE namespaces (
        id VARCHAR(255) PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        slug VARCHAR(255) NOT NULL,
        owner_id VARCHAR(255) NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        description TEXT,
        is_active BOOLEAN DEFAULT TRUE
    )
    """

    try:
        runner._execute_update(create_query)
        logger.info("Successfully created namespaces table")

        # Add unique constraint on slug
        runner._execute_update("ALTER TABLE namespaces ADD UNIQUE KEY uk_namespaces_slug (slug)")
        logger.info("Added unique constraint on slug")

        # Skip explicit index on owner_id for now - can be added later if needed
        logger.info("Skipping owner_id index to avoid Dolt duplicate index issues")

    except Exception as e:
        logger.error(f"Failed to create namespaces table: {e}")
        raise


def _add_namespace_id_column(runner):
    """Add namespace_id column to memory_blocks table if it doesn't exist."""
    logger.info("Adding namespace_id column to memory_blocks if it doesn't exist")

    # Check if column already exists
    describe_query = "DESCRIBE memory_blocks"
    columns = runner._execute_query(describe_query)

    # Check if namespace_id column exists
    namespace_id_exists = any(col["Field"] == "namespace_id" for col in columns)

    if namespace_id_exists:
        logger.info("namespace_id column already exists in memory_blocks, skipping creation")
        return

    # Add namespace_id column
    alter_query = """
    ALTER TABLE memory_blocks 
    ADD COLUMN namespace_id VARCHAR(255) NULL DEFAULT NULL,
    ADD INDEX idx_memory_blocks_namespace (namespace_id)
    """

    try:
        runner._execute_update(alter_query)
        logger.info("Successfully added namespace_id column to memory_blocks")
    except Exception as e:
        logger.error(f"Failed to add namespace_id column: {e}")
        raise


def _ensure_legacy_namespace(runner):
    """Insert the legacy namespace if it doesn't already exist."""
    logger.info("Ensuring legacy namespace exists")

    # Check if legacy namespace already exists
    check_query = "SELECT id FROM namespaces WHERE id = %s"
    existing = runner._execute_query(check_query, (LEGACY_NAMESPACE_ID,))

    if existing:
        logger.info("Legacy namespace already exists, skipping creation")
        return

    # Insert the legacy namespace
    insert_query = """
    INSERT INTO namespaces (id, name, slug, owner_id, created_at, description)
    VALUES (%s, %s, %s, %s, %s, %s)
    """

    current_time = datetime.utcnow()
    params = (
        LEGACY_NAMESPACE_ID,
        LEGACY_NAMESPACE_NAME,
        LEGACY_NAMESPACE_SLUG,
        LEGACY_NAMESPACE_OWNER_ID,
        current_time,
        LEGACY_NAMESPACE_DESCRIPTION,
    )

    try:
        runner._execute_update(insert_query, params)
        logger.info(f"Created legacy namespace with ID: {LEGACY_NAMESPACE_ID}")
    except Exception as e:
        # Check if this is a duplicate key error (race condition)
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            logger.info("Legacy namespace was created by another process, continuing")
        else:
            raise


def _migrate_existing_blocks(runner):
    """Update existing memory_blocks to reference the legacy namespace."""
    logger.info("Migrating existing memory blocks to legacy namespace")

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

    logger.info(f"Found {blocks_to_migrate} memory blocks to migrate to legacy namespace")

    # Update blocks to reference legacy namespace
    update_query = """
    UPDATE memory_blocks 
    SET namespace_id = %s 
    WHERE COALESCE(NULLIF(TRIM(namespace_id),''),NULL) IS NULL
    """

    try:
        rows_updated = runner._execute_update(update_query, (LEGACY_NAMESPACE_ID,))
        logger.info(f"Successfully migrated {rows_updated} memory blocks to legacy namespace")
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
    # Keep VARCHAR(255) to match existing schema and add DEFAULT 'legacy'
    alter_query = """
    ALTER TABLE memory_blocks 
    MODIFY COLUMN namespace_id VARCHAR(255) NOT NULL DEFAULT 'legacy'
    """

    try:
        runner._execute_update(alter_query)
        logger.info("Successfully added NOT NULL constraint to namespace_id column")
    except Exception as e:
        logger.error(f"Failed to add NOT NULL constraint: {e}")
        raise


def _add_namespace_fk_constraint(runner):
    """Ensure memory_blocks.namespace_id has explicit FK with RESTRICT/CASCADE."""
    logger.info("Adding explicit FK constraint with proper ON DELETE/UPDATE behavior")

    # First, drop any existing FK constraints that might exist (safe approach)
    # We'll attempt to drop known constraint names and ignore if they don't exist
    potential_constraint_names = [
        "fk_namespace",
        "fk_memory_blocks_namespace",
        "memory_blocks_ibfk_1",
    ]

    for constraint_name in potential_constraint_names:
        try:
            drop_sql = f"ALTER TABLE memory_blocks DROP FOREIGN KEY {constraint_name}"
            runner._execute_update(drop_sql)
            logger.info(f"Dropped existing FK constraint: {constraint_name}")
        except Exception as e:
            # Expected if constraint doesn't exist - this is safe to ignore
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
                logger.debug(f"FK constraint {constraint_name} doesn't exist, skipping")
            else:
                logger.warning(f"Unexpected error dropping FK constraint {constraint_name}: {e}")

    # Now add the new FK constraint with explicit behavior
    try:
        add_constraint_sql = """
        ALTER TABLE memory_blocks
        ADD CONSTRAINT fk_memory_blocks_namespace
        FOREIGN KEY (namespace_id) REFERENCES namespaces(id)
        ON DELETE RESTRICT ON UPDATE CASCADE
        """
        runner._execute_update(add_constraint_sql)
        logger.info(
            "Successfully added FK constraint with explicit ON DELETE RESTRICT ON UPDATE CASCADE behavior"
        )
    except Exception as e:
        # Check if constraint already exists (idempotency)
        if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
            logger.info("FK constraint already exists with proper behavior")
        else:
            logger.error(f"Failed to add FK constraint: {e}")
            raise


def rollback(runner):
    """
    Rollback the namespace seeding migration.

    WARNING: This will remove the legacy namespace and reset all memory_blocks
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
        rows_updated = runner._execute_update(update_query, (LEGACY_NAMESPACE_ID,))
        logger.info(f"Reset {rows_updated} memory blocks to NULL namespace_id")
    except Exception as e:
        logger.warning(f"Failed to reset memory blocks: {e}")

    # Step 3: Delete legacy namespace
    try:
        delete_query = "DELETE FROM namespaces WHERE id = %s"
        runner._execute_update(delete_query, (LEGACY_NAMESPACE_ID,))
        logger.info("Deleted legacy namespace")
    except Exception as e:
        logger.warning(f"Failed to delete legacy namespace: {e}")

    logger.warning("Namespace seeding migration rollback completed")
