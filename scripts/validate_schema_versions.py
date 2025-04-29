#!/usr/bin/env python3
"""
Pre-commit hook to validate metadata schema versions.

This script checks that any modified metadata schema files have corresponding
version entries in SCHEMA_VERSIONS in registry.py.
"""

import sys
import subprocess
import logging
from pathlib import Path

# Add project root to path before imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
# Must import after path modification but before other code
from experiments.src.memory_system.schemas.registry import SCHEMA_VERSIONS  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def get_modified_metadata_files() -> list[str]:
    """
    Get list of modified metadata schema files from git diff.

    Returns:
        list[str]: List of modified metadata schema file paths
    """
    try:
        # Get staged changes
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"], capture_output=True, text=True, check=True
        )

        # Filter for metadata schema files
        metadata_path = "experiments/src/memory_system/schemas/metadata/"
        return [
            f
            for f in result.stdout.splitlines()
            if f.startswith(metadata_path) and f.endswith(".py")
        ]
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get git diff: {e}")
        return []


def get_block_type_from_path(file_path: str) -> str:
    """
    Extract block type from metadata schema file path.

    Args:
        file_path: Path to metadata schema file

    Returns:
        str: Block type (e.g., 'task' from 'task.py')
    """
    return Path(file_path).stem


def validate_schema_versions() -> bool:
    """
    Validate that modified metadata schema files have version entries.

    Returns:
        bool: True if validation passes, False otherwise
    """
    validation_errors = []

    # Get modified metadata files
    modified_files = get_modified_metadata_files()
    if not modified_files:
        return True  # No metadata files modified, validation passes

    # Check each modified file
    for file_path in modified_files:
        block_type = get_block_type_from_path(file_path)
        if block_type not in SCHEMA_VERSIONS:
            error_msg = (
                f'Block type "{block_type}" modified but no version bump detected in SCHEMA_VERSIONS. '
                f"Please manually update registry.py."
            )
            validation_errors.append(error_msg)

    # Log any errors
    if validation_errors:
        logger.error("Schema version validation failed:")
        for error in validation_errors:
            logger.error(f"  - {error}")
        return False

    return True


if __name__ == "__main__":
    if not validate_schema_versions():
        sys.exit(1)
