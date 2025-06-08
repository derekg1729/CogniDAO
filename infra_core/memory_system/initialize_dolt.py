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
from infra_core.memory_system.schemas.registry import (
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
    type VARCHAR(50) NOT NULL,
    schema_version INT NULL,
    text LONGTEXT NOT NULL,
    state VARCHAR(50) NULL DEFAULT 'draft',
    visibility VARCHAR(50) NULL DEFAULT 'internal',
    block_version INT NULL DEFAULT 1,
    parent_id VARCHAR(255) NULL,
    has_children BOOLEAN NOT NULL DEFAULT False,
    tags JSON NOT NULL,
    source_file VARCHAR(255) NULL,
    source_uri VARCHAR(255) NULL,
    confidence JSON NULL,
    created_by VARCHAR(255) NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    embedding LONGTEXT NULL,
    CONSTRAINT chk_valid_state CHECK (state IN ('draft', 'published', 'archived')),
    CONSTRAINT chk_valid_visibility CHECK (visibility IN ('internal', 'public', 'restricted')),
    CONSTRAINT chk_block_version_positive CHECK (block_version > 0)
);

CREATE INDEX idx_memory_blocks_type_state_visibility ON memory_blocks (type, state, visibility);

CREATE TABLE IF NOT EXISTS block_links (
    to_id VARCHAR(255) NOT NULL,
    from_id VARCHAR(255) NOT NULL,
    relation VARCHAR(50) NOT NULL,
    priority INT NULL DEFAULT 0,
    link_metadata JSON NULL,
    created_by VARCHAR(255) NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (from_id, to_id, relation)
);

CREATE INDEX idx_block_links_to_id ON block_links (to_id);

CREATE TABLE IF NOT EXISTS node_schemas (
    node_type VARCHAR(255) NOT NULL,
    schema_version INT NOT NULL,
    json_schema JSON NOT NULL,
    created_at VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS block_properties (
    block_id VARCHAR(255) NOT NULL,
    property_name VARCHAR(255) NOT NULL,
    property_value_text TEXT NULL,
    property_value_number DOUBLE NULL,
    property_value_json JSON NULL,
    property_type VARCHAR(50) NOT NULL,
    is_computed BOOLEAN NOT NULL DEFAULT False,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (block_id, property_name),
    CONSTRAINT chk_exactly_one_value_nonnull CHECK ( (CASE WHEN property_value_text IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN property_value_number IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN property_value_json IS NOT NULL THEN 1 ELSE 0 END) <= 1 )
);

CREATE TABLE IF NOT EXISTS block_proofs (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    block_id VARCHAR(255) NOT NULL,
    commit_hash VARCHAR(255) NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('create', 'update', 'delete')),
    timestamp DATETIME NOT NULL,
    INDEX block_id_idx (block_id)
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


def check_schema_nullability(db_path: Path) -> bool:
    """
    Checks that the actual Dolt column nullability matches the MemoryBlock field definitions.

    Args:
        db_path: Path to the Dolt database directory

    Returns:
        True if validation passes, False otherwise
    """
    from typing import get_args, get_origin, Union
    from infra_core.memory_system.schemas.memory_block import MemoryBlock

    logger.info("Checking Dolt schema column nullability against Pydantic model...")

    try:
        # Get column information from Dolt
        result = subprocess.run(
            ["dolt", "sql", "-q", "DESCRIBE memory_blocks"],
            cwd=str(db_path),
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse the output to get column information
        # Format: Field | Type | Null | Default | Extra
        lines = [line.strip() for line in result.stdout.split("\n") if line.strip()]
        if len(lines) < 2:  # Need at least header + 1 row
            logger.error("Failed to get column information from Dolt")
            return False

        # Extract column information
        column_info = {}
        for line in lines[1:]:  # Skip header
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                column_name = parts[0].strip().lower()
                nullable = parts[2].strip().lower() == "yes"
                column_info[column_name] = nullable

        # Check against Pydantic model fields
        for field_name, field in MemoryBlock.model_fields.items():
            field_name = field_name.lower()
            if field_name in column_info:
                # Determine if field is optional in Pydantic
                field_type = field.annotation
                is_optional = (
                    get_origin(field_type) is Union and type(None) in get_args(field_type)
                ) or field_name in [
                    "state",
                    "visibility",
                    "block_version",
                    "source_file",
                    "source_uri",
                    "confidence",
                    "embedding",
                    "created_by",
                    "schema_version",
                ]

                # Check if Dolt nullable setting matches Pydantic
                if is_optional and not column_info[field_name]:
                    logger.warning(
                        f"Column '{field_name}' is Optional in Pydantic but NOT NULL in Dolt"
                    )
                elif not is_optional and column_info[field_name]:
                    logger.warning(
                        f"Column '{field_name}' is required in Pydantic but nullable in Dolt"
                    )

        logger.info("Schema nullability check completed")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to check schema nullability: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during schema nullability check: {e}")
        return False


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

    # 5. Check schema nullability
    if not check_schema_nullability(db_path):
        logger.warning("Schema nullability check failed, but continuing...")
        # We continue despite failures to avoid breaking existing installations

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
