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

# --- Configure logging --- #
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
"""

def run_command(command: list[str], cwd: str, description: str) -> bool:
    """Runs a subprocess command, logs output, and handles errors."""
    logger.info(f"{description} in {cwd}...")
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=True,        # Raise exception on non-zero exit code
            capture_output=True, # Capture stdout/stderr
            text=True          # Decode stdout/stderr as text
        )
        logger.debug(f"{description} output:\n{result.stdout}")
        logger.info(f"{description} successful.")
        return True
    except FileNotFoundError:
        logger.error(f"Command '{command[0]}' not found. Ensure Dolt CLI (or required tool) is installed and in PATH.")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"{description} failed with exit code {e.returncode}")
        logger.error(f"Command: {' '.join(e.cmd)}")
        logger.error(f"Stderr:\n{e.stderr}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during '{description}': {e}")
        return False

def initialize_dolt_db(db_path_str: str) -> bool:
    """
    Initializes Dolt repo and creates memory_blocks table if they don't exist.

    Args:
        db_path_str: The path to the target Dolt database directory.

    Returns:
        True if initialization is successful or already done, False otherwise.
    """
    db_path = Path(db_path_str).resolve() # Ensure absolute path

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

    # 2. Initialize Dolt if .dolt directory doesn't exist
    dolt_dir_path = db_path / ".dolt"
    if not dolt_dir_path.exists():
        if not run_command(['dolt', 'init'], cwd=str(db_path), description="Dolt init"):
            return False
    else:
        logger.info(f"Dolt repository already initialized in {db_path}")

    # 3. Create memory_blocks table if it doesn't exist
    if not run_command(['dolt', 'sql', '-q', CREATE_TABLE_SQL], cwd=str(db_path), description="Create memory_blocks table"):
        return False

    logger.info(f"Dolt database at {db_path} is ready.")
    return True


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Initialize a Dolt database and create the 'memory_blocks' table."
    )
    parser.add_argument(
        "db_path",
        type=str,
        help="Path to the target Dolt database directory."
    )
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
