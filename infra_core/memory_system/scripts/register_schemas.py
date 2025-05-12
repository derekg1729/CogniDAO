#!/usr/bin/env python3
"""
Register all metadata schemas in the Dolt database.

Reads the Dolt DB path from:
1. --db-path command-line argument
2. DOLT_DB_PATH environment variable
3. Default path from services.web_api.app.DOLT_DB_PATH
"""

import os
import sys
import argparse
from pathlib import Path

# Project-specific imports - ensure they are at the top after standard library imports
from infra_core.memory_system.dolt_schema_manager import register_all_metadata_schemas

# from services.web_api.app import DOLT_DB_PATH as DEFAULT_DOLT_DB_PATH  # No longer used
from infra_core.constants import (
    MEMORY_DOLT_ROOT as DEFAULT_DOLT_DB_PATH,
)  # Use the central constant

# Add project root to path FIRST to ensure correct imports when script is run directly
# This needs to happen before functions that might use these modules are defined or called,
# but after the import statements themselves.
project_root = (
    Path(__file__).resolve().parent.parent.parent.parent
)  # Go up 4 levels from scripts/register_schemas.py
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def get_dolt_db_path():
    """Determines the Dolt DB path based on CLI args, env var, or default."""
    parser = argparse.ArgumentParser(description="Register metadata schemas in Dolt.")
    parser.add_argument("--db-path", type=str, help="Path to the Dolt database directory.")
    args = parser.parse_args()

    # 1. Check CLI argument
    if args.db_path:
        print(f"Using Dolt DB path from --db-path argument: {args.db_path}")
        # Convert to absolute path relative to project root if not already absolute
        db_path_obj = Path(args.db_path)
        if not db_path_obj.is_absolute():
            return str(project_root / db_path_obj)
        return args.db_path

    # 2. Check environment variable
    env_path = os.getenv("DOLT_DB_PATH")
    if env_path:
        print(f"Using Dolt DB path from DOLT_DB_PATH environment variable: {env_path}")
        # Convert to absolute path relative to project root if not already absolute
        db_path_obj = Path(env_path)
        if not db_path_obj.is_absolute():
            return str(project_root / db_path_obj)
        return env_path

    # 3. Use default path constant (already an absolute path object from constants.py)
    resolved_default_path = DEFAULT_DOLT_DB_PATH
    print(f"Using default Dolt DB path: {resolved_default_path}")
    return str(resolved_default_path)


if __name__ == "__main__":
    db_path = get_dolt_db_path()

    # Ensure the target directory exists before trying to register
    # register_all_metadata_schemas might handle this, but defensive check is good.
    db_path_obj = Path(db_path)
    if not db_path_obj.is_dir():
        print(f"Error: Dolt database directory not found: {db_path}")
        print("Please ensure the path is correct and the Dolt database is initialized.")
        sys.exit(1)

    # Register all schemas
    print(f"Registering schemas in Dolt DB: {db_path}...")
    results = register_all_metadata_schemas(db_path)

    # Print results
    print("\nRegistration results:")
    success_count = 0
    failure_count = 0
    for node_type, success in results.items():
        status = "Success" if success else "Failed"
        print(f"- {node_type}: {status}")
        if success:
            success_count += 1
        else:
            failure_count += 1

    print(f"\nSummary: {success_count} succeeded, {failure_count} failed.")
    # Exit with non-zero code if any registration failed
    if failure_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)
