"""
Purpose: Manage dynamic node type metadata schemas (Pydantic models) stored in the node_schemas Dolt table.

This module handles the storage, retrieval, and versioning of schema definitions for different node types
(e.g., 'task', 'project', 'doc') in the Dolt node_schemas table. It works with the in-memory registry system
to persist schemas for long-term storage and version tracking.

Note: This module does NOT modify the base Dolt table layouts. For table initialization and structure,
see generate_dolt_schema.py instead.

Key Functions:
- register_schema: Register or update a schema definition
- register_all_metadata_schemas: Register all defined metadata schemas
- get_schema: Retrieve a schema definition
- list_available_schemas: List all available schemas
"""

import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from infra_core.memory_system.schemas.registry import (
    get_all_metadata_models,
    get_schema_version,
)

# Use the correct import path for doltpy v2+
try:
    from doltpy.cli import Dolt
except ImportError:
    raise ImportError("doltpy not found. Please install it: pip install doltpy")

# --- Path Setup --- START
# Ensure the project root is in the Python path for schema imports
script_dir = Path(__file__).parent
project_root_dir = script_dir.parent.parent.parent  # Adjust if structure changes
if str(project_root_dir) not in sys.path:
    sys.path.insert(0, str(project_root_dir))
# --- Path Setup --- END

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def register_schema(
    db_path: str,
    node_type: str,
    schema_version: int,
    json_schema: Dict[str, Any],
    branch: str = "main",
) -> bool:
    """
    Registers or updates a schema definition in the node_schemas Dolt table.

    Args:
        db_path: Path to the Dolt database directory
        node_type: Type of node/block (e.g., 'task', 'project')
        schema_version: Version number for this schema
        json_schema: The JSON schema output from Pydantic model.model_json_schema()
        branch: Dolt branch to write to (defaults to 'main')

    Returns:
        bool: True if successful, False otherwise
    """
    logger.info(f"Registering schema for {node_type} version {schema_version} to Dolt at {db_path}")

    try:
        # Connect to Dolt repository
        repo = Dolt(db_path)

        # Get current branch from the tuple returned by branch()
        current_branch = repo.branch()[0]  # First element of the tuple is the branch name
        if current_branch != branch:
            logger.info(f"Switching from branch '{current_branch}' to '{branch}'")
            repo.checkout(branch)

        # Convert JSON schema to string and properly escape for SQL
        schema_json_str = json.dumps(json_schema).replace("'", "''").replace("\\", "\\\\")

        # Use current timestamp
        now = datetime.now().isoformat()

        # Prepare the INSERT SQL with ON DUPLICATE KEY UPDATE
        # This will insert a new record or update an existing one
        insert_sql = f"""
        INSERT INTO node_schemas (node_type, schema_version, json_schema, created_at)
        VALUES ('{node_type}', {schema_version}, '{schema_json_str}', '{now}')
        ON DUPLICATE KEY UPDATE 
            json_schema = VALUES(json_schema),
            created_at = VALUES(created_at)
        """

        # Execute the query
        try:
            repo.sql(query=insert_sql)
            logger.info(f"Successfully executed SQL for {node_type} schema registration")
        except Exception as e:
            logger.error(f"Failed to execute SQL for {node_type} schema registration: {e}")
            return False

        # Commit the changes
        try:
            commit_message = f"Register schema for {node_type} version {schema_version}"
            repo.add("node_schemas")
            repo.commit(commit_message)
            logger.info(f"Successfully committed schema for {node_type} version {schema_version}")
            return True
        except Exception as e:
            logger.error(f"Failed to commit schema for {node_type}: {e}")
            return False

    except Exception as e:
        logger.error(f"Failed to register schema: {e}", exc_info=True)
        return False


def register_all_metadata_schemas(db_path: str, branch: str = "main") -> Dict[str, bool]:
    """
    Registers all defined metadata schemas in the node_schemas table.
    Uses schema versions from SCHEMA_VERSIONS in registry.py.

    Args:
        db_path: Path to the Dolt database directory
        branch: Dolt branch to write to (defaults to 'main')

    Returns:
        Dict mapping node_type to registration success (True/False)
    """
    results = {}

    # Get metadata models from registry
    models_map = get_all_metadata_models()

    # Register each metadata type
    for node_type, model_cls in models_map.items():
        if model_cls is None:
            logger.warning(f"No schema defined for {node_type}, skipping")
            results[node_type] = False
            continue

        try:
            # Get schema version from registry
            try:
                version = get_schema_version(node_type)
            except KeyError as e:
                logger.error(f"Failed to get schema version for {node_type}: {e}")
                results[node_type] = False
                continue

            # Generate JSON schema from the model
            json_schema = model_cls.model_json_schema()

            # Add additional metadata
            json_schema["x_node_type"] = node_type
            json_schema["x_schema_version"] = version
            json_schema["x_generated_at"] = datetime.now().isoformat()

            # Register the schema
            success = register_schema(
                db_path=db_path,
                node_type=node_type,
                schema_version=version,
                json_schema=json_schema,
                branch=branch,
            )

            results[node_type] = success

        except Exception as e:
            logger.error(f"Failed to register schema for {node_type}: {e}", exc_info=True)
            results[node_type] = False

    return results


def get_schema(
    db_path: str, node_type: str, schema_version: Optional[int] = None, branch: str = "main"
) -> Optional[Dict]:
    """
    Retrieves a schema definition from the node_schemas table.

    Args:
        db_path: Path to the Dolt database directory
        node_type: The type of node to get the schema for
        schema_version: Optional specific version to retrieve (defaults to latest)
        branch: Dolt branch to read from (defaults to 'main')

    Returns:
        The schema definition as a dict, or None if not found
    """
    try:
        repo = Dolt(db_path)

        # Build the query string
        if schema_version is not None:
            query = f"""
            SELECT json_schema, schema_version, created_at
            FROM node_schemas
            WHERE node_type = '{node_type}'
            AND schema_version = {schema_version}
            ORDER BY created_at DESC
            LIMIT 1
            """
        else:
            query = f"""
            SELECT json_schema, schema_version, created_at
            FROM node_schemas
            WHERE node_type = '{node_type}'
            ORDER BY created_at DESC
            LIMIT 1
            """

        # Execute query with result_format
        result = repo.sql(query=query, result_format="json")

        if not result or "rows" not in result or not result["rows"]:
            return None

        row = result["rows"][0]
        schema = row["json_schema"]

        # Add metadata
        schema["x_schema_version"] = row["schema_version"]
        schema["x_created_at"] = row["created_at"]

        return schema

    except Exception as e:
        logger.error(f"Failed to retrieve schema: {e}", exc_info=True)
        return None


def list_available_schemas(db_path: str, branch: str = "main") -> List[Dict[str, Any]]:
    """
    Lists all available schemas in the node_schemas table.

    Args:
        db_path: Path to the Dolt database directory
        branch: Dolt branch to read from (defaults to 'main')

    Returns:
        List of dicts with node_type, schema_version, and created_at
    """
    logger.info(f"Listing available schemas from Dolt at {db_path}")

    try:
        # Connect to Dolt repository
        repo = Dolt(db_path)

        # Query for all schemas
        query = f"""
        SELECT node_type, schema_version, created_at
        FROM node_schemas AS OF '{branch}'
        ORDER BY node_type, schema_version DESC
        """

        # Execute the query
        result = repo.sql(query=query, result_format="json")

        if result and result.get("rows"):
            return result["rows"]
        else:
            return []

    except Exception as e:
        logger.error(f"Failed to list schemas: {e}", exc_info=True)
        return []


# Example usage
if __name__ == "__main__":
    # Path to the Dolt database
    dolt_db_dir = project_root_dir / "experiments" / "dolt_data" / "memory_db"

    # Register all schemas
    if dolt_db_dir.exists():
        results = register_all_metadata_schemas(str(dolt_db_dir))

        # Report results
        for node_type, success in results.items():
            status = "Success" if success else "Failed"
            print(f"{node_type}: {status}")

        # List all available schemas
        schemas = list_available_schemas(str(dolt_db_dir))
        print("\nAvailable schemas:")
        for schema in schemas:
            print(
                f"- {schema['node_type']} (v{schema['schema_version']}) created at {schema['created_at']}"
            )
    else:
        print(f"Dolt database not found at {dolt_db_dir}")
