#!/usr/bin/env python3

"""Migration script for P-04: Parent/Children Hierarchy Support.

- Adds parent_id UUID column (NULLable with foreign key constraint)
- Adds has_children BOOLEAN column (default FALSE)
- Adds foreign key constraint with ON DELETE CASCADE
- Commits changes cleanly to Dolt
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

# SQL statements for adding parent/child hierarchy columns
MEMORY_BLOCKS_HIERARCHY_ALTERS = [
    # Add new columns with proper defaults
    "ALTER TABLE memory_blocks ADD COLUMN parent_id VARCHAR(255)",
    "ALTER TABLE memory_blocks ADD COLUMN has_children BOOLEAN NOT NULL DEFAULT FALSE",
    # Add foreign key constraint with cascade delete
    "ALTER TABLE memory_blocks ADD CONSTRAINT fk_memory_blocks_parent FOREIGN KEY (parent_id) REFERENCES memory_blocks(id) ON DELETE CASCADE",
    # Create index for efficient parent lookups
    "CREATE INDEX idx_memory_blocks_parent_id ON memory_blocks (parent_id)",
    # Create index for efficient children queries
    "CREATE INDEX idx_memory_blocks_has_children ON memory_blocks (has_children)",
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


def migrate_schema(db_path: Path) -> bool:
    """Apply parent/child hierarchy schema changes."""
    logger.info("Starting parent/child hierarchy migration...")

    # Apply memory_blocks hierarchy changes
    for sql in MEMORY_BLOCKS_HIERARCHY_ALTERS:
        if not run_sql(db_path, sql, f"Hierarchy: {sql[:60]}"):
            return False

    logger.info("All hierarchy schema updates applied successfully.")

    # Commit the migration
    try:
        subprocess.run(
            ["dolt", "add", "."], cwd=str(db_path), check=True, capture_output=True, text=True
        )
        subprocess.run(
            [
                "dolt",
                "commit",
                "-m",
                "P-04: Add parent_id and has_children columns for hierarchy support",
            ],
            cwd=str(db_path),
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("Hierarchy migration committed to Dolt.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Dolt commit failed: {e.stderr}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate Dolt schema for P-04 Parent/Child Hierarchy"
    )
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
