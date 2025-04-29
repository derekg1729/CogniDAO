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
    "CREATE INDEX idx_memory_blocks_type_state_visibility ON memory_blocks (type, state, visibility)",
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


def run_command(command: list[str], cwd: str, description: str) -> bool:
    """Runs a subprocess command, logs output, and handles errors."""
    logger.info(f"{description} in {cwd}...")
    try:
        result = subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)
        logger.debug(f"{description} output:\n{result.stdout}")
        logger.info(f"{description} successful.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"{description} failed with exit code {e.returncode}")
        logger.error(f"Command: {' '.join(e.cmd)}")
        logger.error(f"Stderr:\n{e.stderr}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during '{description}': {e}")
        return False


def migrate_schema(db_path: str) -> bool:
    """
    Execute the schema migration for Task 3.6.

    Args:
        db_path: Path to the Dolt database directory

    Returns:
        True if migration was successful, False otherwise
    """
    db_path = Path(db_path).resolve()

    # 1. Apply memory_blocks table changes
    for sql in MEMORY_BLOCKS_ALTERS:
        if not run_command(
            ["dolt", "sql", "-q", sql], str(db_path), f"Executing memory_blocks ALTER: {sql}"
        ):
            return False

    # 2. Apply block_links table changes
    for sql in BLOCK_LINKS_ALTERS:
        if not run_command(
            ["dolt", "sql", "-q", sql], str(db_path), f"Executing block_links ALTER: {sql}"
        ):
            return False

    # 3. Commit the changes
    commit_message = "Task 3.6: Schema updates for MemoryBlock and BlockLink"
    if not run_command(
        ["dolt", "commit", "-m", commit_message], str(db_path), "Committing schema changes"
    ):
        return False

    logger.info("Schema migration completed successfully.")
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

    if migrate_schema(args.db_path):
        logger.info("Migration completed successfully.")
        sys.exit(0)
    else:
        logger.error("Migration failed.")
        sys.exit(1)
