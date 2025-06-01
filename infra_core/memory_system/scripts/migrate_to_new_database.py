#!/usr/bin/env python3
"""
Migration script to copy all data from old database (data/memory_dolt)
to new database (data/blocks/memory_dolt).

This script handles the database path transition where we moved from:
- Old path: data/memory_dolt (legacy)
- New path: data/blocks/memory_dolt (current)

The new database has the enhanced schema with block_properties table.
"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Tuple

# Add the project root to sys.path so we can import PropertyMapper
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


# --- Configure logging --- #
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- Database Paths --- #
DEFAULT_OLD_DB_PATH = Path("data/memory_dolt")
DEFAULT_NEW_DB_PATH = Path("data/blocks/memory_dolt")

# --- Tables to migrate --- #
TABLES_TO_MIGRATE = ["memory_blocks", "block_links", "block_proofs", "node_schemas"]


def run_dolt_sql(db_path: Path, query: str, description: str) -> Tuple[bool, str]:
    """
    Execute a Dolt SQL query and return success status and output.

    Args:
        db_path: Path to the Dolt database directory
        query: SQL query to execute
        description: Description for logging

    Returns:
        Tuple of (success: bool, output: str)
    """
    logger.info(f"Running: {description}")
    logger.debug(f"SQL Query: {query}")

    try:
        result = subprocess.run(
            ["dolt", "sql", "-q", query],
            cwd=str(db_path),
            capture_output=True,
            text=True,
            check=True,
        )
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"SQL failed: {description}")
        logger.error(f"Error: {e.stderr}")
        return False, e.stderr


def get_table_count(db_path: Path, table_name: str) -> int:
    """Get the number of records in a table."""
    success, output = run_dolt_sql(
        db_path, f"SELECT COUNT(*) as count FROM {table_name}", f"Getting count for {table_name}"
    )
    if not success:
        return -1

    # Parse the count from the output
    # Dolt SQL output format is:
    # +-------+
    # | count |
    # +-------+
    # | 85    |
    # +-------+
    lines = [line.strip() for line in output.split("\n") if line.strip()]
    for line in lines:
        # Look for lines that contain just a number (the actual count)
        if line.startswith("|") and line.endswith("|"):
            # Extract content between the pipes
            content = line.strip("|").strip()
            # Skip header lines and separator lines
            if content != "count" and not content.startswith("-") and content.isdigit():
                return int(content)
    return 0


def check_table_exists(db_path: Path, table_name: str) -> bool:
    """Check if a table exists in the database."""
    success, output = run_dolt_sql(
        db_path, f"SHOW TABLES LIKE '{table_name}'", f"Checking if {table_name} exists"
    )
    return success and table_name in output


def create_node_schemas_table(new_db_path: Path) -> bool:
    """Create the node_schemas table in the new database if it doesn't exist."""
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS node_schemas (
        node_type VARCHAR(255) NOT NULL,
        schema_version INT NOT NULL,
        json_schema JSON NOT NULL,
        created_at VARCHAR(255) NOT NULL
    )
    """

    success, _ = run_dolt_sql(
        new_db_path, create_table_sql, "Creating node_schemas table in new database"
    )
    return success


def migrate_table_data(old_db_path: Path, new_db_path: Path, table_name: str) -> bool:
    """
    Migrate all data from a table in the old database to the new database.

    Args:
        old_db_path: Path to the old database
        new_db_path: Path to the new database
        table_name: Name of the table to migrate

    Returns:
        True if migration successful, False otherwise
    """
    logger.info(f"Migrating table: {table_name}")

    # Check if table exists in old database
    if not check_table_exists(old_db_path, table_name):
        logger.warning(f"Table {table_name} does not exist in old database, skipping")
        return True

    # Get count of records to migrate
    old_count = get_table_count(old_db_path, table_name)
    if old_count == -1:
        logger.error(f"Failed to get count for {table_name} in old database")
        return False
    elif old_count == 0:
        logger.info(f"Table {table_name} is empty in old database, skipping")
        return True

    logger.info(f"Found {old_count} records in {table_name} to migrate")

    # Special handling for node_schemas table which may not exist in new DB
    if table_name == "node_schemas":
        if not check_table_exists(new_db_path, table_name):
            logger.info("node_schemas table does not exist in new database, creating it")
            if not create_node_schemas_table(new_db_path):
                logger.error("Failed to create node_schemas table in new database")
                return False

    # Clear existing data in new database table (if any)
    success, _ = run_dolt_sql(
        new_db_path,
        f"DELETE FROM {table_name}",
        f"Clearing existing data from {table_name} in new database",
    )
    if not success:
        logger.error(f"Failed to clear {table_name} in new database")
        return False

    try:
        # Get all data from the old table as JSON
        result = subprocess.run(
            ["dolt", "sql", "-q", f"SELECT * FROM {table_name}", "--result-format", "json"],
            cwd=old_db_path,
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse JSON and create INSERT statements
        data = json.loads(result.stdout)
        rows = data.get("rows", [])

        if not rows:
            logger.info(f"No data to migrate for {table_name}")
            return True

        logger.info(f"Found {len(rows)} rows to migrate for {table_name}")

        # Get column names from the first row
        if rows:
            columns = list(rows[0].keys())
            logger.info(f"Columns for {table_name}: {columns}")
            columns_str = ", ".join(f"`{col}`" for col in columns)
        else:
            logger.warning(f"No rows found for {table_name}")
            return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to export data from {table_name}: {e}")
        logger.error(f"Stderr: {e.stderr}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON for {table_name}: {e}")
        logger.error(f"Raw output: {result.stdout}")
        return False

    # Process rows in batches to avoid huge SQL statements
    batch_size = 50
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]

        # Build VALUES clause
        values_parts = []
        for row in batch:
            row_values = []
            for col in columns:
                # Use safe column access to handle missing columns
                value = row.get(col)
                if value is None:
                    row_values.append("NULL")
                elif isinstance(value, str):
                    # Escape single quotes, backslashes, and control characters for SQL
                    escaped_value = (
                        value.replace("\\", "\\\\")
                        .replace("'", "''")
                        .replace("\n", "\\n")
                        .replace("\r", "\\r")
                        .replace("\t", "\\t")
                    )
                    row_values.append(f"'{escaped_value}'")
                elif isinstance(value, (dict, list)):
                    # JSON fields - need comprehensive escaping
                    json_str = json.dumps(value)
                    # Escape for SQL: single quotes, backslashes, and newlines
                    escaped_json = (
                        json_str.replace("\\", "\\\\")
                        .replace("'", "''")
                        .replace("\n", "\\n")
                        .replace("\r", "\\r")
                        .replace("\t", "\\t")
                    )
                    row_values.append(f"'{escaped_json}'")
                else:
                    row_values.append(str(value))

            values_parts.append("(" + ", ".join(row_values) + ")")

        values_clause = ", ".join(values_parts)
        insert_query = f"INSERT INTO {table_name} ({columns_str}) VALUES {values_clause}"

        # Execute the batch INSERT
        success, _ = run_dolt_sql(
            new_db_path, insert_query, f"Inserting batch {i // batch_size + 1} for {table_name}"
        )

        if not success:
            logger.error(f"Failed to insert batch {i // batch_size + 1} for {table_name}")
            return False

    # Verify the migration
    new_count = get_table_count(new_db_path, table_name)
    if new_count == old_count:
        logger.info(f"✅ Successfully migrated {new_count} records for {table_name}")
        return True
    else:
        logger.error(
            f"❌ Migration verification failed for {table_name}: expected {old_count}, got {new_count}"
        )
        return False


def commit_migration(new_db_path: Path) -> bool:
    """Commit the migration changes to the new database."""
    logger.info("Committing migration changes...")

    try:
        # Add all changes
        subprocess.run(
            ["dolt", "add", "."], cwd=str(new_db_path), check=True, capture_output=True, text=True
        )

        # Commit with descriptive message
        subprocess.run(
            [
                "dolt",
                "commit",
                "-m",
                "Data migration from legacy database path (data/memory_dolt) to new path (data/blocks/memory_dolt)",
            ],
            cwd=str(new_db_path),
            check=True,
            capture_output=True,
            text=True,
        )

        logger.info("✅ Migration changes committed successfully")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to commit migration: {e.stderr}")
        return False


def validate_databases(old_db_path: Path, new_db_path: Path) -> bool:
    """Validate that both databases exist and are accessible."""
    # Check old database
    if not old_db_path.exists():
        logger.error(f"Old database path does not exist: {old_db_path}")
        return False

    if not (old_db_path / ".dolt").exists():
        logger.error(f"Old path is not a Dolt repository: {old_db_path}")
        return False

    # Check new database
    if not new_db_path.exists():
        logger.error(f"New database path does not exist: {new_db_path}")
        return False

    if not (new_db_path / ".dolt").exists():
        logger.error(f"New path is not a Dolt repository: {new_db_path}")
        return False

    logger.info("✅ Both databases validated successfully")
    return True


def print_migration_summary(old_db_path: Path, new_db_path: Path):
    """Print a summary of the migration."""
    logger.info("=== MIGRATION SUMMARY ===")
    logger.info(f"Old database: {old_db_path}")
    logger.info(f"New database: {new_db_path}")
    logger.info("")

    for table_name in TABLES_TO_MIGRATE:
        old_count = (
            get_table_count(old_db_path, table_name)
            if check_table_exists(old_db_path, table_name)
            else 0
        )
        new_count = (
            get_table_count(new_db_path, table_name)
            if check_table_exists(new_db_path, table_name)
            else 0
        )

        status = "✅" if old_count == new_count else "❌"
        logger.info(f"{status} {table_name}: {old_count} → {new_count}")


def migrate_metadata_to_properties(old_db_path: Path, new_db_path: Path) -> bool:
    """
    Decompose metadata from migrated memory_blocks and populate block_properties table.

    This function reads the metadata JSON from memory_blocks and uses PropertyMapper
    to decompose it into individual property rows in the block_properties table.

    Args:
        old_db_path: Path to the old database (not used, kept for consistency)
        new_db_path: Path to the new database where properties will be inserted

    Returns:
        True if migration successful, False otherwise
    """
    logger.info("Decomposing metadata into block_properties table...")

    # Import PropertyMapper here to avoid module-level import issues
    from infra_core.memory_system.property_mapper import PropertyMapper

    try:
        # Get all memory blocks with their metadata from the new database
        result = subprocess.run(
            [
                "dolt",
                "sql",
                "-q",
                "SELECT id, metadata FROM memory_blocks WHERE JSON_LENGTH(metadata) > 0",
                "--result-format",
                "json",
            ],
            cwd=new_db_path,
            capture_output=True,
            text=True,
            check=True,
        )

        data = json.loads(result.stdout)
        rows = data.get("rows", [])

        if not rows:
            logger.info("No blocks with metadata found, skipping property decomposition")
            return True

        logger.info(f"Found {len(rows)} blocks with metadata to decompose")

        total_properties = 0
        successful_blocks = 0

        for row in rows:
            block_id = row["id"]
            metadata_json = row["metadata"]

            try:
                # Parse the metadata JSON
                if isinstance(metadata_json, str):
                    metadata_dict = json.loads(metadata_json)
                else:
                    metadata_dict = metadata_json

                # Use PropertyMapper to decompose metadata
                properties = PropertyMapper.decompose_metadata(block_id, metadata_dict)

                if not properties:
                    logger.debug(f"No properties to insert for block {block_id}")
                    successful_blocks += 1
                    continue

                # Convert properties to SQL INSERT statements
                for prop in properties:
                    # Prepare values for INSERT with proper escaping
                    def escape_sql_string(value):
                        if value is None:
                            return "NULL"
                        # Escape single quotes and backslashes for SQL
                        escaped = str(value).replace("\\", "\\\\").replace("'", "''")
                        return f"'{escaped}'"

                    def escape_sql_json(value):
                        if value is None:
                            return "NULL"
                        json_str = json.dumps(value)
                        # Escape single quotes and backslashes for SQL
                        escaped = json_str.replace("\\", "\\\\").replace("'", "''")
                        return f"'{escaped}'"

                    values = [
                        escape_sql_string(prop.block_id),
                        escape_sql_string(prop.property_name),
                        escape_sql_string(prop.property_value_text),
                        str(prop.property_value_number)
                        if prop.property_value_number is not None
                        else "NULL",
                        escape_sql_json(prop.property_value_json),
                        escape_sql_string(prop.property_type),
                        "1" if prop.is_computed else "0",
                        escape_sql_string(prop.created_at.strftime("%Y-%m-%d %H:%M:%S")),
                        escape_sql_string(prop.updated_at.strftime("%Y-%m-%d %H:%M:%S")),
                    ]

                    insert_sql = f"""
                    INSERT INTO block_properties (
                        block_id, property_name, property_value_text, property_value_number, 
                        property_value_json, property_type, is_computed, created_at, updated_at
                    ) VALUES ({", ".join(values)})
                    """

                    # Execute the INSERT
                    success, output = run_dolt_sql(
                        new_db_path,
                        insert_sql,
                        f"Inserting property {prop.property_name} for block {block_id}",
                    )

                    if not success:
                        logger.error(
                            f"Failed to insert property {prop.property_name} for block {block_id}: {output}"
                        )
                        return False

                    total_properties += 1

                successful_blocks += 1
                logger.debug(
                    f"Successfully decomposed {len(properties)} properties for block {block_id}"
                )

            except Exception as e:
                logger.error(f"Failed to decompose metadata for block {block_id}: {e}")
                return False

        logger.info(
            f"✅ Successfully decomposed metadata for {successful_blocks} blocks into {total_properties} properties"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to decompose metadata to properties: {e}")
        return False


def main():
    """Main migration function."""
    parser = argparse.ArgumentParser(
        description="Migrate data from old database path to new database path"
    )
    parser.add_argument(
        "--old-db-path",
        type=str,
        default=str(DEFAULT_OLD_DB_PATH),
        help=f"Path to the old database (default: {DEFAULT_OLD_DB_PATH})",
    )
    parser.add_argument(
        "--new-db-path",
        type=str,
        default=str(DEFAULT_NEW_DB_PATH),
        help=f"Path to the new database (default: {DEFAULT_NEW_DB_PATH})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without actually doing it",
    )
    parser.add_argument(
        "--no-commit", action="store_true", help="Don't commit the changes after migration"
    )

    args = parser.parse_args()

    # Convert to Path objects and make absolute
    old_db_path = Path(args.old_db_path).resolve()
    new_db_path = Path(args.new_db_path).resolve()

    logger.info(f"Starting migration from {old_db_path} to {new_db_path}")

    # Validate databases
    if not validate_databases(old_db_path, new_db_path):
        logger.error("Database validation failed")
        sys.exit(1)

    # Show migration plan
    logger.info("=== MIGRATION PLAN ===")
    for table_name in TABLES_TO_MIGRATE:
        if check_table_exists(old_db_path, table_name):
            count = get_table_count(old_db_path, table_name)
            logger.info(f"📋 {table_name}: {count} records")
        else:
            logger.info(f"📋 {table_name}: table does not exist (will skip)")

    if args.dry_run:
        logger.info("Dry run mode - no changes will be made")
        return

    # Migrate data for all tables
    migration_success = True

    for table_name in TABLES_TO_MIGRATE:
        if not migrate_table_data(old_db_path, new_db_path, table_name):
            migration_success = False
            break

    if not migration_success:
        logger.error("❌ Migration failed")
        sys.exit(1)

    # Decompose metadata into block_properties table (Critical fix for property-schema split)
    logger.info("=== DECOMPOSING METADATA TO PROPERTIES ===")
    if not migrate_metadata_to_properties(old_db_path, new_db_path):
        logger.error("❌ Failed to decompose metadata into properties")
        sys.exit(1)

    # Commit changes (unless --no-commit specified)
    if not args.no_commit:
        if not commit_migration(new_db_path):
            logger.error("❌ Failed to commit migration")
            sys.exit(1)
    else:
        logger.info("Skipping commit due to --no-commit flag")

    # Print final summary
    print_migration_summary(old_db_path, new_db_path)
    logger.info("🎉 Migration completed successfully!")


if __name__ == "__main__":
    main()
