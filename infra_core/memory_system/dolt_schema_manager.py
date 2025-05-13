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
from typing import Dict, Any, Optional, List, Type
from pydantic import BaseModel
from infra_core.memory_system.schemas.registry import get_all_metadata_models, get_schema_version

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


class DoltSchemaManager:
    """Manages registration and retrieval of Pydantic schemas in a Dolt database."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.dolt = Dolt(db_path)

    def _get_current_branch_name(self) -> str:
        """Gets the name of the current active Dolt branch using dolt.active_branch. Raises Exception on failure."""
        try:
            # Try accessing the active_branch attribute directly
            active_branch = self.dolt.active_branch
            if active_branch:
                # logger.debug(f"Current active branch from dolt.active_branch: {active_branch}")
                return active_branch.name  # Assuming it's a Branch object with a .name
            else:
                raise Exception("dolt.active_branch did not return a value.")
        except AttributeError:
            logger.warning(
                "dolt.active_branch attribute not found. Falling back to status parsing."
            )
            # Fallback to status parsing if active_branch attribute doesn't exist
            try:
                status = self.dolt.status()
                if status and hasattr(status, "message") and status.message:
                    first_line = status.message.splitlines()[0]
                    if first_line.startswith("On branch "):
                        branch_name = first_line.split(" ", 2)[2]
                        return branch_name
                    else:
                        raise Exception(
                            f"Could not parse branch name from status message: {first_line}"
                        )
                else:
                    raise Exception(
                        "Could not get status message from Dolt or status object lacks 'message' attribute."
                    )
            except Exception as e_parse:
                logger.error(f"Error determining current branch name via status parsing: {e_parse}")
                raise Exception(
                    f"Failed to determine current branch via status parsing: {e_parse}"
                ) from e_parse
        except Exception as e_direct:
            logger.error(
                f"Error determining current branch name via dolt.active_branch: {e_direct}"
            )
            raise Exception(
                f"Failed to determine current branch via dolt.active_branch: {e_direct}"
            ) from e_direct

    def _get_existing_schema_json(
        self, node_type: str, schema_version: int
    ) -> Optional[Dict[str, Any]]:
        """Retrieve the existing JSON schema object (as dict) from Dolt for a given type and version."""
        select_query = f"""
        SELECT json_schema
        FROM node_schemas
        WHERE node_type = '{node_type}' AND schema_version = {schema_version}
        """
        try:
            result = self.dolt.sql(query=select_query, result_format="json")
            if result and "rows" in result and len(result["rows"]) > 0:
                # Assuming json_schema is the first column if selected explicitly
                # result_format="json" should return a dict directly for the JSON column
                schema_data = result["rows"][0].get("json_schema")
                # Dolt might return it as a string if it wasn't stored as JSON type, or dict if it was.
                # Handle both cases for robustness.
                if isinstance(schema_data, str):
                    try:
                        return json.loads(schema_data)
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Failed to parse existing schema string for {node_type} v{schema_version} from DB."
                        )
                        return None  # Treat unparseable string as non-existent
                elif isinstance(schema_data, dict):
                    return schema_data
                else:
                    # Handle unexpected types if necessary
                    logger.warning(
                        f"Unexpected type {type(schema_data)} for existing schema {node_type} v{schema_version} from DB."
                    )
                    return None
            return None
        except Exception as e:
            logger.error(f"Error checking for existing schema {node_type} v{schema_version}: {e}")
            # Decide if this error should prevent registration or just be logged
            # For now, let's assume we should proceed with registration attempt if check fails
            return None  # Indicate we couldn't confirm existence/content

    def register_schema(
        self, node_type: str, schema_version: int, schema_model: Type[BaseModel]
    ) -> Optional[bool]:
        """
        Registers a Pydantic schema in the Dolt database.
        Checks if the schema already exists and is identical before performing write operations.
        Ensures operation happens on the 'main' branch.
        Returns:
            bool: True if a change was made and committed.
            bool: False if schema exists and is identical (no change needed).
            None: If an error occurred during the process (e.g., cannot checkout main).
        """
        logger.info(
            f"Registering schema for {node_type} version {schema_version} to Dolt at {self.db_path}"
        )

        # Ensure we are on the main branch for registration consistency
        try:
            # Attempt checkout; doltpy handles 'Already on branch' gracefully
            self.dolt.checkout("main")
            logger.info("Ensured on branch 'main' (or checkout succeeded).")
        except Exception as e:
            logger.error(f"Failed to checkout 'main' branch: {e}. Aborting registration.")
            return None  # Indicate failure

        # Generate JSON schema from the Pydantic model
        try:
            # Add generation timestamp metadata *before* generating the schema dict
            timestamp_str = datetime.utcnow().isoformat()
            schema_dict = schema_model.model_json_schema()
            # Add custom metadata directly expected by the MemoryBlock structure or registry
            schema_dict["x_node_type"] = node_type
            schema_dict["x_schema_version"] = schema_version
            schema_dict["x_generated_at"] = timestamp_str  # Add generation time
            json_schema_str = json.dumps(schema_dict, separators=(",", ":"))  # Use compact encoding
        except Exception as e:
            logger.error(f"Failed to generate JSON schema for {node_type} v{schema_version}: {e}")
            return None

        # Check if an identical schema already exists
        existing_schema_dict = self._get_existing_schema_json(node_type, schema_version)

        if existing_schema_dict:
            try:
                # Compare parsed JSON objects for semantic equality, ignoring formatting differences
                current_schema = json.loads(json_schema_str)
                # Remove generation timestamp before comparison as it changes every time
                existing_schema_dict.pop("x_generated_at", None)
                current_schema.pop("x_generated_at", None)

                if existing_schema_dict == current_schema:
                    logger.info(
                        f"Schema {node_type} v{schema_version} already exists and is identical. Skipping registration."
                    )
                    return False  # No changes made
                else:
                    logger.info(
                        f"Schema {node_type} v{schema_version} exists but differs. Proceeding with update."
                    )
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Could not parse existing schema {node_type} v{schema_version} for comparison: {e}. Proceeding with update."
                )
            except Exception as e:
                logger.warning(
                    f"Error comparing schemas for {node_type} v{schema_version}: {e}. Proceeding with update."
                )
        else:
            logger.info(
                f"Schema {node_type} v{schema_version} not found or check failed. Proceeding with registration."
            )

        # Prepare SQL query for insertion or update
        created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        # Escape backslashes and single quotes in the JSON string for SQL compatibility
        escaped_json_schema = json_schema_str.replace("\\", "\\\\").replace("'", "''")

        sql_query = f"""
        INSERT INTO node_schemas (node_type, schema_version, json_schema, created_at)
        VALUES ('{node_type}', {schema_version}, '{escaped_json_schema}', '{created_at}')
        ON DUPLICATE KEY UPDATE
            json_schema = VALUES(json_schema),
            created_at = VALUES(created_at)
        """

        try:
            # Execute the SQL query
            self.dolt.sql(query=sql_query)
            logger.info(f"Successfully executed SQL for {node_type} schema registration")

            # Stage the changes in Dolt
            self.dolt.add("node_schemas")
            logger.info(f"Staged 'node_schemas' for {node_type} v{schema_version}")

            # Attempt to commit the changes
            # Assume success if commit doesn't raise an exception.
            # Dolt CLI might print "nothing to commit", but doltpy might not signal this easily.
            # If the SQL INSERT/UPDATE truly changed nothing, this commit *might* do nothing,
            # but the earlier schema comparison should ideally prevent this path.
            commit_message = f"Register schema for {node_type} version {schema_version}"
            self.dolt.commit(message=commit_message)
            logger.info(f"Successfully committed schema for {node_type} version {schema_version}")
            return True  # Changes were made and committed

        except Exception as e:
            logger.error(
                f"Failed to register or commit schema for {node_type} v{schema_version}: {e}"
            )
            return None  # Indicate failure

    def get_schema(
        self, node_type: str, version: Optional[int] = None
    ) -> Optional[Type[BaseModel]]:
        """
        Retrieves a schema definition from the node_schemas table.

        Args:
            node_type: The type of node to get the schema for
            version: Optional specific version to retrieve (defaults to latest)

        Returns:
            The schema definition as a dict, or None if not found
        """
        try:
            # Build the query string
            if version is not None:
                query = f"""
                SELECT json_schema, schema_version, created_at
                FROM node_schemas
                WHERE node_type = '{node_type}'
                AND schema_version = {version}
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
            result = self.dolt.sql(query=query, result_format="json")

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

    def list_available_schemas(self, branch: str = "main") -> List[Dict[str, Any]]:
        """
        Lists all available schemas in the node_schemas table.

        Args:
            branch: Dolt branch to read from (defaults to 'main')

        Returns:
            List of dicts with node_type, schema_version, and created_at
        """
        logger.info(f"Listing available schemas from Dolt at {self.db_path}")

        try:
            # Query for all schemas
            query = f"""
            SELECT node_type, schema_version, created_at
            FROM node_schemas AS OF '{branch}'
            ORDER BY node_type, schema_version DESC
            """

            # Execute the query
            result = self.dolt.sql(query=query, result_format="json")

            if result and result.get("rows"):
                return result["rows"]
            else:
                return []

        except Exception as e:
            logger.error(f"Failed to list schemas: {e}", exc_info=True)
            return []


# Minimal wrapper functions
def register_schema(db_path, node_type, schema_version, json_schema):
    """Register a schema definition for a node type."""
    try:
        manager = DoltSchemaManager(db_path)
        # Handle both Pydantic models and direct JSON schema dictionaries
        if hasattr(json_schema, "model_json_schema"):  # It's a Pydantic model
            return manager.register_schema(node_type, schema_version, json_schema)
        else:  # It's a JSON schema dictionary
            # Just use the schema directly
            timestamp_str = datetime.utcnow().isoformat()
            schema_dict = json_schema.copy()
            schema_dict["x_node_type"] = node_type
            schema_dict["x_schema_version"] = schema_version
            schema_dict["x_generated_at"] = timestamp_str

            created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
            escaped_json_schema = json.dumps(schema_dict).replace("\\", "\\\\").replace("'", "''")

            sql_query = f"""
            INSERT INTO node_schemas (node_type, schema_version, json_schema, created_at)
            VALUES ('{node_type}', {schema_version}, '{escaped_json_schema}', '{created_at}')
            ON DUPLICATE KEY UPDATE
                json_schema = VALUES(json_schema),
                created_at = VALUES(created_at)
            """

            manager.dolt.sql(query=sql_query)
            manager.dolt.add("node_schemas")
            manager.dolt.commit(message=f"Register schema for {node_type} version {schema_version}")
            return True
    except Exception as e:
        logger.error(f"Failed to register schema for {node_type} v{schema_version}: {e}")
        return False


def register_all_metadata_schemas(db_path):
    """Register all metadata schemas defined in the system."""
    # Create manager once to reuse the same Dolt connection
    dolt_instance = Dolt(db_path)
    results = {}

    # Get all metadata models from registry
    metadata_models = get_all_metadata_models()

    for node_type, model_cls in metadata_models.items():
        try:
            # Get schema version for this node type
            version = get_schema_version(node_type)

            # Generate JSON schema from the Pydantic model
            schema_dict = model_cls.model_json_schema()
            # Add custom metadata expected by the MemoryBlock structure or registry
            schema_dict["x_node_type"] = node_type
            schema_dict["x_schema_version"] = version
            schema_dict["x_generated_at"] = datetime.utcnow().isoformat()
            json_schema_str = json.dumps(schema_dict, separators=(",", ":"))

            # Escape for SQL
            escaped_json_schema = json_schema_str.replace("\\", "\\\\").replace("'", "''")
            created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")

            # SQL query with VALUES clause as expected by the test
            sql_query = f"""
            INSERT INTO node_schemas (node_type, schema_version, json_schema, created_at)
            VALUES ('{node_type}', {version}, '{escaped_json_schema}', '{created_at}')
            ON DUPLICATE KEY UPDATE
                json_schema = VALUES(json_schema),
                created_at = VALUES(created_at)
            """

            # Execute the SQL query
            dolt_instance.sql(query=sql_query)

            # Stage the changes in Dolt
            dolt_instance.add("node_schemas")

            # Commit the changes
            commit_message = f"Register schema for {node_type} version {version}"
            dolt_instance.commit(message=commit_message)

            results[node_type] = True
        except KeyError as ke:
            # Handle case where no schema version is defined for this type
            logger.error(f"Error registering schema for {node_type}: {str(ke)}")
            results[node_type] = False
        except Exception as e:
            logger.error(f"Error registering schema for {node_type}: {str(e)}")
            results[node_type] = False

    return results


def get_schema(db_path, node_type, version=None, schema_version=None):
    """Retrieve a schema definition for a node type."""
    # Allow schema_version as an alternative parameter name for backward compatibility
    v = schema_version if schema_version is not None else version
    return DoltSchemaManager(db_path).get_schema(node_type, v)


def list_available_schemas(db_path, branch="main"):
    """List all available schemas in the database."""
    return DoltSchemaManager(db_path).list_available_schemas(branch)


# Example usage
if __name__ == "__main__":
    # Path to the Dolt database
    dolt_db_dir = project_root_dir / "experiments" / "dolt_data" / "memory_db"

    # Register all schemas
    if dolt_db_dir.exists():
        manager = DoltSchemaManager(str(dolt_db_dir))
        results = manager.register_all_metadata_schemas()

        # Report results
        for node_type, success in results.items():
            status = "Success" if success else "Failed"
            print(f"{node_type}: {status}")

        # List all available schemas
        schemas = manager.list_available_schemas()
        print("\nAvailable schemas:")
        for schema in schemas:
            print(
                f"- {schema['node_type']} (v{schema['schema_version']}) created at {schema['created_at']}"
            )
    else:
        print(f"Dolt database not found at {dolt_db_dir}")
