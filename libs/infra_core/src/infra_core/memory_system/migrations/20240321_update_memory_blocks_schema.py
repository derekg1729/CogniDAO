#!/usr/bin/env python3

"""Migration script for Task 3.6: Enhanced Memory System Schema (Production Ready).

- Updates memory_blocks table (state, visibility, block_version fields, constraints, indexes)
- Updates block_links table (priority, metadata fields, constraints, indexes)
- Commits changes cleanly to Dolt
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# SQL statements for memory_blocks
MEMORY_BLOCKS_ALTERS = [
    # Update existing columns
    "ALTER TABLE memory_blocks MODIFY COLUMN state VARCHAR(50) NOT NULL DEFAULT 'draft'",
    "ALTER TABLE memory_blocks MODIFY COLUMN visibility VARCHAR(50) NOT NULL DEFAULT 'internal'",
    "ALTER TABLE memory_blocks MODIFY COLUMN block_version INT NOT NULL DEFAULT 1",
    # Create index if it doesn't exist - Dolt requires key lengths for VARCHAR columns
    "CREATE INDEX idx_memory_blocks_type_state_visibility ON memory_blocks (type(50), state(50), visibility(50))",
]

# SQL statements for block_links
BLOCK_LINKS_ALTERS = [
    # Add new columns
    "ALTER TABLE block_links ADD COLUMN from_id VARCHAR(255) NOT NULL DEFAULT ''",
    "ALTER TABLE block_links ADD COLUMN priority INT DEFAULT 0",
    "ALTER TABLE block_links ADD COLUMN link_metadata JSON",
    "ALTER TABLE block_links ADD COLUMN created_by VARCHAR(255)",
    "ALTER TABLE block_links ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    # Drop existing primary key
    "ALTER TABLE block_links DROP PRIMARY KEY",
    # Add new PRIMARY KEY
    "ALTER TABLE block_links ADD PRIMARY KEY (from_id, to_id, relation)",
    # Add constraints
    "ALTER TABLE block_links ADD CONSTRAINT chk_priority_non_negative CHECK (priority >= 0)",
    "ALTER TABLE block_links ADD CONSTRAINT chk_valid_relation CHECK (relation IN ('related_to', 'subtask_of', 'depends_on', 'child_of', 'mentions'))",
    # Create index
    "CREATE INDEX idx_block_links_to_id ON block_links (to_id)",
]


def run_sql(db_path: Path, sql: str, description: str) -> bool:
    """Run a SQL command in Dolt and handle errors."""
    logger.info(f"Running: {description}")
    try:
        subprocess.run(
            ["dolt", "sql", "-q", sql], cwd=str(db_path), check=True, capture_output=True, text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        # Only ignore "already exists" errors for indexes and columns
        if ("already exists" in e.stderr.lower() or "duplicate" in e.stderr.lower()) and (
            "CREATE INDEX" in sql or "ADD COLUMN" in sql
        ):
            logger.info(f"Object already exists, continuing: {description}")
            return True
        # All other errors should fail the migration
        logger.error(f"SQL failed: {description}")
        logger.error(f"Error: {e.stderr}")
        return False


def check_field_values(
    db_path: Path, field: str, allowed_values: List[str]
) -> Tuple[bool, List[str]]:
    """Check if a field contains only allowed values."""
    try:
        result = subprocess.run(
            ["dolt", "sql", "-q", f"SELECT DISTINCT {field} FROM memory_blocks"],
            cwd=str(db_path),
            check=True,
            capture_output=True,
            text=True,
        )
        # Parse the output, skipping header and footer lines
        lines = result.stdout.strip().split("\n")
        if len(lines) <= 3:  # No data
            return True, []

        # Extract values, skipping header and separator lines
        current_values = []
        for line in lines[2:-1]:  # Skip first two lines (header) and last line (footer)
            value = line.strip().strip("|").strip()
            if value and not value.startswith("+"):
                current_values.append(value)

        invalid_values = [v for v in current_values if v not in allowed_values]
        return len(invalid_values) == 0, invalid_values
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to check {field} values: {e.stderr}")
        return False, []


def update_invalid_values(db_path: Path) -> bool:
    """Update any invalid values in state and visibility fields."""
    # Check state values
    state_valid, invalid_states = check_field_values(
        db_path, "state", ["draft", "published", "archived"]
    )
    if not state_valid:
        logger.warning(f"Found invalid state values: {invalid_states}")
        try:
            # Update invalid states to 'draft'
            subprocess.run(
                [
                    "dolt",
                    "sql",
                    "-q",
                    "UPDATE memory_blocks SET state = 'draft' WHERE state NOT IN ('draft', 'published', 'archived')",
                ],
                cwd=str(db_path),
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info("Updated invalid state values to 'draft'")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to update invalid states: {e.stderr}")
            return False

    # Check visibility values
    visibility_valid, invalid_visibilities = check_field_values(
        db_path, "visibility", ["internal", "public", "restricted"]
    )
    if not visibility_valid:
        logger.warning(f"Found invalid visibility values: {invalid_visibilities}")
        try:
            # Update invalid visibility to 'internal'
            subprocess.run(
                [
                    "dolt",
                    "sql",
                    "-q",
                    "UPDATE memory_blocks SET visibility = 'internal' WHERE visibility NOT IN ('internal', 'public', 'restricted')",
                ],
                cwd=str(db_path),
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info("Updated invalid visibility values to 'internal'")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to update invalid visibilities: {e.stderr}")
            return False

    return True


def migrate_schema(db_path: Path) -> bool:
    """Apply all schema changes."""
    logger.info("Starting migration...")

    # First, check and update any invalid values
    logger.info("Checking for invalid field values...")
    if not update_invalid_values(db_path):
        return False

    # Apply memory_blocks changes
    for sql in MEMORY_BLOCKS_ALTERS:
        if not run_sql(db_path, sql, f"MemoryBlocks: {sql[:60]}"):
            return False

    # Apply block_links changes
    for sql in BLOCK_LINKS_ALTERS:
        if not run_sql(db_path, sql, f"BlockLinks: {sql[:60]}"):
            return False

    logger.info("All schema updates applied successfully.")

    # Commit the migration
    try:
        subprocess.run(
            ["dolt", "add", "."], cwd=str(db_path), check=True, capture_output=True, text=True
        )
        subprocess.run(
            ["dolt", "commit", "-m", "Task 3.6: Schema migration for enhanced memory system."],
            cwd=str(db_path),
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("Schema migration committed to Dolt.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Dolt commit failed: {e.stderr}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Migrate Dolt schema for Task 3.6")
    parser.add_argument("db_path", help="Path to the Dolt database directory")
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        logger.error(f"Provided db_path does not exist: {db_path}")
        sys.exit(1)

    if not migrate_schema(db_path):
        logger.error("Migration failed.")
        sys.exit(1)

    logger.info("Migration completed successfully.")


if __name__ == "__main__":
    main()
