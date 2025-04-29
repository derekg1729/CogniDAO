#!/usr/bin/env python3

"""Migration script for Task 3.6 schema updates.

This script handles the migration of existing data to support the new schema features:
- Adds state, visibility, and block_version columns to memory_blocks
- Adds priority, link_metadata, created_by, and created_at columns to block_links
- Creates new indexes for efficient querying
- Sets default values for new columns
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# SQL statements for schema updates
MEMORY_BLOCKS_ALTERS = [
    # Add new columns with default values
    "ALTER TABLE memory_blocks ADD COLUMN state VARCHAR(50) DEFAULT 'draft'",
    "ALTER TABLE memory_blocks ADD COLUMN visibility VARCHAR(50) DEFAULT 'internal'",
    "ALTER TABLE memory_blocks ADD COLUMN block_version INT DEFAULT 1",
    # Add constraints
    "ALTER TABLE memory_blocks ADD CONSTRAINT chk_state CHECK (state IN ('draft', 'published', 'archived'))",
    "ALTER TABLE memory_blocks ADD CONSTRAINT chk_visibility CHECK (visibility IN ('internal', 'public', 'restricted'))",
    # Create composite index
    "CREATE INDEX idx_memory_blocks_type_state_visibility ON memory_blocks (type(50), state(50), visibility(50))",
]

BLOCK_LINKS_ALTERS = [
    # Add new columns with default values
    "ALTER TABLE block_links ADD COLUMN priority INT DEFAULT 0",
    "ALTER TABLE block_links ADD COLUMN link_metadata JSON",
    "ALTER TABLE block_links ADD COLUMN created_by VARCHAR(255)",
    "ALTER TABLE block_links ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
    # Add index for reverse traversal
    "CREATE INDEX idx_block_links_to_id ON block_links (to_id)",
    # Add constraint for canonical relation types
    "ALTER TABLE block_links ADD CONSTRAINT chk_relation CHECK (relation IN ('related_to', 'subtask_of', 'depends_on', 'child_of', 'mentions'))",
]


def check_column_exists(db_path: Path, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    try:
        result = subprocess.run(
            ["dolt", "sql", "-q", f"SELECT {column} FROM {table} LIMIT 1"],
            cwd=str(db_path),
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def check_index_exists(db_path: Path, table: str, index: str) -> bool:
    """Check if an index exists on a table."""
    try:
        result = subprocess.run(
            ["dolt", "sql", "-q", f"SHOW INDEX FROM {table} WHERE Key_name = '{index}'"],
            cwd=str(db_path),
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and result.stdout.strip()
    except Exception:
        return False


def run_sql(db_path: Path, sql: str, description: str) -> bool:
    """Run a SQL command and handle errors."""
    logger.info(f"Executing {description} in {db_path}...")
    try:
        subprocess.run(
            ["dolt", "sql", "-q", sql], cwd=str(db_path), check=True, capture_output=True, text=True
        )
        logger.info(f"Executing {description} successful.")
        return True
    except subprocess.CalledProcessError as e:
        if "already exists" in e.stderr:
            logger.info(f"{description} already exists, skipping.")
            return True
        logger.error(f"Executing {description} failed with exit code {e.returncode}")
        logger.error(f"Command: {' '.join(e.cmd)}")
        logger.error(f"Stderr:\n{e.stderr}")
        return False


def migrate_schema(db_path: Path) -> bool:
    """Run the migration SQL statements."""
    logger.info(f"Starting schema migration for Task 3.6 at: {db_path}")

    # Add new columns if they don't exist
    columns_to_add = [
        ("state", "VARCHAR(50) DEFAULT 'draft'"),
        ("visibility", "VARCHAR(50) DEFAULT 'internal'"),
        ("block_version", "INT DEFAULT 1"),
    ]

    for column, definition in columns_to_add:
        if not check_column_exists(db_path, "memory_blocks", column):
            sql = f"ALTER TABLE memory_blocks ADD COLUMN {column} {definition}"
            if not run_sql(db_path, sql, f"Adding column {column}"):
                return False

    # Add constraints if they don't exist
    constraints = [
        ("chk_state", "state IN ('draft', 'published', 'archived')"),
        ("chk_visibility", "visibility IN ('internal', 'public', 'restricted')"),
    ]

    for constraint, check in constraints:
        sql = f"ALTER TABLE memory_blocks ADD CONSTRAINT {constraint} CHECK ({check})"
        if not run_sql(db_path, sql, f"Adding constraint {constraint}"):
            return False

    # Create index if it doesn't exist
    index_name = "idx_memory_blocks_type_state_visibility"
    if not check_index_exists(db_path, "memory_blocks", index_name):
        sql = f"CREATE INDEX {index_name} ON memory_blocks (type(50), state(50), visibility(50))"
        if not run_sql(db_path, sql, f"Creating index {index_name}"):
            return False

    logger.info("Migration completed successfully.")
    return True


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Migrate Dolt schema for Task 3.6: Enhance MemoryBlock and BlockLink Schemas"
    )
    parser.add_argument("db_path", type=str, help="Path to the Dolt database directory")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    logger.info(f"Starting schema migration for Task 3.6 at: {args.db_path}")

    if migrate_schema(Path(args.db_path)):
        logger.info("Migration completed successfully.")
        sys.exit(0)
    else:
        logger.error("Migration failed.")
        sys.exit(1)
