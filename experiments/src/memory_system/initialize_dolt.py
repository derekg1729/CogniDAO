#!/usr/bin/env python3
"""
Initializes a Dolt database directory if it doesn't exist,
and ensures the 'memory_blocks' table is created.
"""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path
from experiments.src.memory_system.schemas.registry import (
    get_all_metadata_models,
    SCHEMA_VERSIONS,
)

# --- Configure logging --- #
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- Define Table Schema --- #
# Matches the schema expected by dolt_writer and tested in integration tests
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS memory_blocks (
    id VARCHAR(255) PRIMARY KEY,
    type VARCHAR(50),
    schema_version INT,
    text LONGTEXT,
    tags JSON,
    metadata JSON,
    links JSON,
    source_file VARCHAR(1024),
    source_uri VARCHAR(2048),
    confidence JSON,
    created_by VARCHAR(255),
    created_at DATETIME(6),
    updated_at DATETIME(6),
    embedding LONGTEXT
);

CREATE TABLE IF NOT EXISTS node_schemas (
    node_type VARCHAR(255) NOT NULL,
    schema_version INT NOT NULL,
    json_schema JSON NOT NULL,
    created_at VARCHAR(255) NOT NULL
);
"""


def run_command(command: list[str], cwd: str, description: str) -> bool:
    """Runs a subprocess command, logs output, and handles errors."""
    logger.info(f"{description} in {cwd}...")
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=True,  # Raise exception on non-zero exit code
            capture_output=True,  # Capture stdout/stderr
            text=True,  # Decode stdout/stderr as text
        )
        logger.debug(f"{description} output:\n{result.stdout}")
        logger.info(f"{description} successful.")
        return True
    except FileNotFoundError:
        logger.error(
            f"Command '{command[0]}' not found. Ensure Dolt CLI (or required tool) is installed and in PATH."
        )
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"{description} failed with exit code {e.returncode}")
        logger.error(f"Command: {' '.join(e.cmd)}")
        logger.error(f"Stderr:\n{e.stderr}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during '{description}': {e}")
        return False


def validate_schema_versions(db_path: Path) -> bool:
    """
    Validates that all registered block types have schema versions defined
    and match what's in the database (if any).

    Args:
        db_path: Path to the Dolt database directory

    Returns:
        True if validation passes, False otherwise
    """
    validation_errors = []

    # Get all registered metadata models
    metadata_models = get_all_metadata_models()
    logger.debug(f"Registered metadata models: {list(metadata_models.keys())}")
    logger.debug(f"SCHEMA_VERSIONS: {SCHEMA_VERSIONS}")

    # Check that all registered types have version entries
    for block_type in metadata_models:
        logger.debug(f"Checking schema version for block type: {block_type}")
        if block_type not in SCHEMA_VERSIONS:
            error_msg = f"Block type '{block_type}' is registered but has no schema version defined in SCHEMA_VERSIONS"
            logger.debug(f"Found error: {error_msg}")
            validation_errors.append(error_msg)
            continue

    # If we already have errors, log them and return False
    if validation_errors:
        logger.error("Schema version validation failed:")
        for error in validation_errors:
            logger.error(f"  - {error}")
        return False

    # Check if node_schemas table exists
    try:
        result = subprocess.run(
            ["dolt", "sql", "-q", "SHOW TABLES LIKE 'node_schemas'"],
            cwd=str(db_path),
            capture_output=True,
            text=True,
            check=True,
        )
        if "node_schemas" not in result.stdout:
            # Table doesn't exist yet, which is fine
            return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to check if node_schemas table exists: {e}")
        return False

    # Check database for existing schemas and validate versions
    try:
        result = subprocess.run(
            ["dolt", "sql", "-q", "SELECT node_type, schema_version FROM node_schemas"],
            cwd=str(db_path),
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse the output to get existing schemas
        # Skip header row and empty lines
        lines = [line.strip() for line in result.stdout.split("\n") if line.strip()]
        if len(lines) > 1:  # If we have any schemas in the database
            for line in lines[1:]:  # Skip header
                node_type, version = line.split("\t")
                if node_type in SCHEMA_VERSIONS:
                    db_version = int(version)
                    code_version = SCHEMA_VERSIONS[node_type]
                    if db_version != code_version:
                        validation_errors.append(
                            f"Schema version mismatch for '{node_type}': "
                            f"database has version {db_version}, code has version {code_version}"
                        )

            # If we found any mismatches, log them and return False
            if validation_errors:
                logger.error("Schema version validation failed:")
                for error in validation_errors:
                    logger.error(f"  - {error}")
                return False

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to check schema versions in database: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during schema version validation: {e}")
        return False

    return True


def initialize_dolt_db(db_path_str: str) -> bool:
    """
    Initializes Dolt repo and creates memory_blocks table if they don't exist.

    Args:
        db_path_str: The path to the target Dolt database directory.

    Returns:
        True if initialization is successful or already done, False otherwise.
    """
    db_path = Path(db_path_str).resolve()  # Ensure absolute path

    # 1. Create directory if it doesn't exist
    if not db_path.exists():
        logger.info(f"Directory not found. Creating directory: {db_path}")
        try:
            os.makedirs(db_path, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create directory {db_path}: {e}")
            return False
    elif not db_path.is_dir():
        logger.error(f"Path exists but is not a directory: {db_path}")
        return False

    # 2. Initialize Dolt repo if not already initialized
    if not (db_path / ".dolt").exists():
        if not run_command(["dolt", "init"], str(db_path), "Initializing Dolt repository"):
            return False
        logger.info("Dolt repository initialized.")
    else:
        logger.info("Dolt repository already initialized.")

    # 3. Create tables using SQL
    try:
        with open(db_path / "create_tables.sql", "w") as f:
            f.write(CREATE_TABLE_SQL)
        if not run_command(
            ["dolt", "sql", "--file", "create_tables.sql"],
            str(db_path),
            "Creating tables",
        ):
            return False
        os.unlink(db_path / "create_tables.sql")  # Clean up SQL file
        logger.info("Tables created successfully.")
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        return False

    # 4. Validate schema versions after tables are created
    if not validate_schema_versions(db_path):
        logger.error("Schema version validation failed")
        return False

    return True


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Initialize a Dolt database and create the 'memory_blocks' table."
    )
    parser.add_argument("db_path", type=str, help="Path to the target Dolt database directory.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    logger.info(f"Attempting to initialize Dolt DB at: {args.db_path}")
    if initialize_dolt_db(args.db_path):
        logger.info("Initialization process completed successfully.")
        sys.exit(0)
    else:
        logger.error("Initialization process failed.")
        sys.exit(1)
