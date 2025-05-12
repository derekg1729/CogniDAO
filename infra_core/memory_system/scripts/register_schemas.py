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
import logging
from pathlib import Path
from typing import Dict

# Project-specific imports - Imports should work now due to PYTHONPATH from hook
# Use __name__ for the DoltSchemaManager logger for better control
from infra_core.memory_system.dolt_schema_manager import (
    DoltSchemaManager,
    logger as schema_manager_logger,
)
from infra_core.constants import (
    MEMORY_DOLT_ROOT as DEFAULT_DOLT_DB_PATH,
)  # Use the central constant

# Import all schema definition files to ensure they are registered
# The act of importing these modules triggers their call to `register_metadata`
# Add any other schema modules here if they exist

# Now import the functions from registry.py that provide access to the populated registry
from infra_core.memory_system.schemas.registry import get_all_metadata_models, get_schema_version

# Setup logging
# Configure root logger initially - level will be adjusted based on args
logger = logging.getLogger(__name__)
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
# Reduce verbosity of doltpy logger always for this script
logging.getLogger("doltpy.cli.dolt").setLevel(logging.WARNING)

# Define project_root for path resolution if needed within the script
# (e.g., for resolving relative paths passed via args/env)
project_root = Path(__file__).resolve().parent.parent.parent.parent


def get_dolt_db_path_and_args():
    """Determines the Dolt DB path and parses other args."""
    parser = argparse.ArgumentParser(description="Register metadata schemas in Dolt.")
    parser.add_argument("--db-path", type=str, help="Path to the Dolt database directory.")
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress informational output, only show warnings/errors.",
    )
    args = parser.parse_args()

    # Set logging level based on quiet flag
    log_level = logging.WARNING if args.quiet else logging.INFO
    logger.setLevel(log_level)
    schema_manager_logger.setLevel(log_level)  # Control the schema manager's logger too

    # --- Resolve Dolt DB Path ---
    db_path = None
    source = "default"  # Track where the path came from for potential logging

    # 1. Check CLI argument
    if args.db_path:
        db_path = args.db_path
        source = "CLI --db-path"
    # 2. Check environment variable
    elif os.getenv("DOLT_DB_PATH"):
        db_path = os.getenv("DOLT_DB_PATH")
        source = "env DOLT_DB_PATH"
    # 3. Use default path constant
    else:
        db_path = str(DEFAULT_DOLT_DB_PATH)  # Use string representation
        source = "default constant"

    # Convert to absolute path relative to project root if not already absolute
    resolved_db_path = db_path
    db_path_obj = Path(db_path)
    if not db_path_obj.is_absolute():
        resolved_db_path = str(project_root / db_path_obj)  # Use project_root defined above

    # Log path source only if not quiet
    if not args.quiet:
        logger.info(f"Using Dolt DB path from {source}: {resolved_db_path}")

    return resolved_db_path, args


def main():
    dolt_db_path, args = get_dolt_db_path_and_args()

    # Ensure the target directory exists before trying to register
    db_path_obj = Path(dolt_db_path)
    if not db_path_obj.is_dir():
        # This is an error, should always be logged regardless of quiet flag
        logger.error(f"Error: Dolt database directory not found: {dolt_db_path}")
        logger.error("Please ensure the path is correct and the Dolt database is initialized.")
        sys.exit(1)

    # Register all schemas
    logger.info(
        f"Starting schema registration in Dolt DB: {dolt_db_path}..."
    )  # Log start if not quiet
    manager = DoltSchemaManager(str(dolt_db_path))
    registration_results: Dict[str, str] = {}

    # Get all registered models and their versions
    all_models = get_all_metadata_models()

    any_schema_updated = False  # Flag to track if any Dolt updates occurred

    for node_type, schema_model in all_models.items():
        schema_version = -1  # Initialize for error message
        try:
            schema_version = get_schema_version(node_type)
            # register_schema now returns True (changed), False (no change), or None (error)
            result = manager.register_schema(node_type, schema_version, schema_model)

            if result is True:
                registration_results[node_type] = "Success (Registered/Updated)"
                any_schema_updated = True  # Mark that an update happened
            elif result is False:
                registration_results[node_type] = "Success (Already up-to-date)"
            else:  # result is None
                registration_results[node_type] = "Failed (Check Logs)"

        except KeyError as e:
            # Log critical errors regardless of quiet flag
            logger.error(
                f"Schema version not found for {node_type} in SCHEMA_VERSIONS registry: {e}"
            )
            registration_results[node_type] = "Failed (Version Missing)"
        except Exception as e:
            # Log critical errors regardless of quiet flag
            logger.error(
                f"Unexpected error during registration process for {node_type} v{schema_version}: {e}",
                exc_info=True,
            )
            registration_results[node_type] = "Failed (Exception)"

    # Report results only if not quiet or if errors occurred
    succeeded_count = 0
    failed_count = 0
    already_up_to_date_count = 0

    for status in registration_results.values():
        if "Success" in status:
            succeeded_count += 1
            if "Already up-to-date" in status:
                already_up_to_date_count += 1
        else:
            failed_count += 1

    # Only print summary if not quiet OR if there were failures
    if not args.quiet or failed_count > 0:
        print("\nRegistration results:")  # Use print for summary table
        for node_type, status in registration_results.items():
            print(f"- {node_type}: {status}")
        print(
            f"\nSummary: {succeeded_count} succeeded ({already_up_to_date_count} already up-to-date), {failed_count} failed."
        )

    # Exit immediately if registration itself failed
    if failed_count > 0:
        sys.exit(1)

    # --- Final Check ---
    # If registration succeeded (failed_count==0) but Dolt was updated (any_schema_updated==True),
    # fail the hook and tell the user to stage the changes.
    if any_schema_updated:
        # Determine path to show in message (relative if possible)
        try:
            db_path_obj_for_msg = Path(dolt_db_path)
            relative_dolt_path_for_msg = db_path_obj_for_msg.relative_to(project_root)
            path_to_show = str(relative_dolt_path_for_msg)
        except ValueError:
            path_to_show = dolt_db_path  # Fallback to absolute path

        # This warning IS important, show regardless of quiet flag
        logger.warning("Schema registration updated the Dolt database.")
        logger.warning(
            f"You must STAGE these Dolt database changes (e.g., 'git add {path_to_show}') and then re-run your commit."
        )
        sys.exit(1)  # Exit with 1 because changes need staging
    else:
        # If failed_count > 0, we already exited.
        # If failed_count == 0 and any_schema_updated == False, then everything is up-to-date.
        # Log final success only if not quiet
        if not args.quiet:
            logger.info("Schema registration successful. No changes needed in Dolt database.")
        # Script will naturally exit with 0.


if __name__ == "__main__":
    main()
