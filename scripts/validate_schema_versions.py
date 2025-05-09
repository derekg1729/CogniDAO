#!/usr/bin/env python3
"""
Pre-commit hook to validate metadata schema versions.

This script checks that any modified metadata schema files have corresponding
version entries in SCHEMA_VERSIONS in registry.py.
"""

import sys
import subprocess
import logging
import re
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Baseline versions that require incrementing if files are modified
# Update this whenever SCHEMA_VERSIONS in registry.py is appropriately updated
# TODO: This is a cheap and brittle way to do this, but it's good enough for now.
BASELINE_VERSIONS = {
    "base": 2,
    "project": 2,
    "task": 2,
    "doc": 2,
    "knowledge": 2,
    "log": 2,
}


def get_staged_schema_versions() -> dict:
    """
    Get the SCHEMA_VERSIONS dict from staged registry.py.

    This reads the actual staged content instead of importing, which
    ensures we're looking at the version that's about to be committed.

    Returns:
        dict: The SCHEMA_VERSIONS from the staged registry.py
    """
    try:
        registry_path = "infra_core/memory_system/schemas/registry.py"

        # Get the staged content of registry.py
        result = subprocess.run(
            ["git", "show", f":0:{registry_path}"], capture_output=True, text=True, check=True
        )

        content = result.stdout

        # Find the SCHEMA_VERSIONS dictionary using regex
        schema_versions_pattern = r"SCHEMA_VERSIONS\s*:\s*Dict\[str,\s*int\]\s*=\s*\{([^}]+)\}"
        match = re.search(schema_versions_pattern, content, re.DOTALL)

        if not match:
            logger.error(f"Couldn't find SCHEMA_VERSIONS in {registry_path}")
            return {}

        # Parse the dictionary entries
        schema_dict_str = match.group(1)
        version_entries = {}

        # Extract key-value pairs using regex for more robustness
        pair_pattern = r'"([^"]+)"\s*:\s*(\d+)'
        for key, value in re.findall(pair_pattern, schema_dict_str):
            version_entries[key] = int(value)

        return version_entries
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get staged registry.py: {e}")
        return {}
    except Exception as e:
        logger.error(f"Error parsing SCHEMA_VERSIONS: {e}")
        return {}


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
        metadata_path = "infra_core/memory_system/schemas/metadata/"
        modified_files = [
            f
            for f in result.stdout.splitlines()
            if f.startswith(metadata_path)
            and f.endswith(".py")
            and not Path(f).name.startswith("__init__")
            # Exclude test files from schema version validation
            and not Path(f).name.startswith("test_")
        ]

        return modified_files
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

    # Get current schema versions from staged registry.py
    schema_versions = get_staged_schema_versions()
    if not schema_versions:
        logger.error("Couldn't retrieve schema versions, skipping validation")
        return True  # Skip validation if we can't get versions

    # Check each modified file
    for file_path in modified_files:
        block_type = get_block_type_from_path(file_path)

        if block_type not in schema_versions:
            error_msg = (
                f'Block type "{block_type}" modified but no version entry found in SCHEMA_VERSIONS. '
                f"Please add an entry in registry.py."
            )
            validation_errors.append(error_msg)
        elif (
            block_type in BASELINE_VERSIONS
            and schema_versions[block_type] <= BASELINE_VERSIONS[block_type]
        ):
            error_msg = (
                f'Schema file "{block_type}.py" modified but version still at {schema_versions[block_type]}. '
                f"Please increment the version in SCHEMA_VERSIONS in registry.py."
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
