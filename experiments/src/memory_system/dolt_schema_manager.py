"""
Functions for managing schema persistence in the Dolt database.

This module handles the storage, retrieval, and versioning of schema definitions
in the Dolt node_schemas table. It works with the in-memory registry system to
persist schemas for long-term storage and version tracking.
"""

import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from experiments.src.memory_system.schemas.registry import get_all_metadata_models

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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def register_schema(
    db_path: str,
    node_type: str,
    schema_version: int,
    json_schema: Dict[str, Any],
    branch: str = 'main'
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
        
        # Check if we're on the right branch
        current_branch = repo.branch(r=True).strip()
        if current_branch != branch:
            logger.info(f"Switching from branch '{current_branch}' to '{branch}'")
            repo.checkout(branch)
        
        # Prepare the INSERT SQL with ON DUPLICATE KEY UPDATE
        # This will insert a new record or update an existing one
        insert_sql = """
        INSERT INTO node_schemas (node_type, schema_version, json_schema, created_at)
        VALUES (?, ?, ?, ?)
        ON DUPLICATE KEY UPDATE 
            json_schema = VALUES(json_schema),
            created_at = VALUES(created_at)
        """
        
        # Convert JSON schema to string
        schema_json_str = json.dumps(json_schema)
        
        # Use current timestamp
        now = datetime.now()
        
        # Execute the query with parameters
        repo.sql(
            query=insert_sql,
            args=[node_type, schema_version, schema_json_str, now.isoformat()],
        )
        
        # Commit the changes
        commit_message = f"Register schema for {node_type} version {schema_version}"
        repo.add("node_schemas")
        repo.commit(commit_message)
        
        logger.info(f"Successfully registered schema for {node_type} version {schema_version}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to register schema: {e}", exc_info=True)
        return False

def register_all_metadata_schemas(
    db_path: str, 
    version: int = 1,
    branch: str = 'main'
) -> Dict[str, bool]:
    """
    Registers all defined metadata schemas in the node_schemas table.
    
    Args:
        db_path: Path to the Dolt database directory
        version: Version number to assign to all schemas (defaults to 1)
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
                branch=branch
            )
            
            results[node_type] = success
            
        except Exception as e:
            logger.error(f"Failed to register schema for {node_type}: {e}", exc_info=True)
            results[node_type] = False
    
    return results

def get_schema(
    db_path: str,
    node_type: str,
    schema_version: Optional[int] = None,
    branch: str = 'main'
) -> Optional[Dict[str, Any]]:
    """
    Retrieves a schema definition from the node_schemas Dolt table.
    
    Args:
        db_path: Path to the Dolt database directory
        node_type: Type of node to retrieve schema for
        schema_version: Specific version to retrieve (if None, gets latest)
        branch: Dolt branch to read from (defaults to 'main')
        
    Returns:
        The JSON schema as a dict, or None if not found
    """
    logger.info(f"Retrieving schema for {node_type} from Dolt at {db_path}")
    
    try:
        # Connect to Dolt repository
        repo = Dolt(db_path)
        
        # Prepare the query
        if schema_version is not None:
            # Get specific version
            query = f"""
            SELECT json_schema, schema_version, created_at
            FROM node_schemas AS OF '{branch}'
            WHERE node_type = ? AND schema_version = ?
            """
            args = [node_type, schema_version]
        else:
            # Get latest version
            query = f"""
            SELECT json_schema, schema_version, created_at
            FROM node_schemas AS OF '{branch}'
            WHERE node_type = ?
            ORDER BY schema_version DESC
            LIMIT 1
            """
            args = [node_type]
        
        # Execute the query
        result = repo.sql(query=query, args=args, result_format='json')
        
        if result and result.get('rows') and len(result['rows']) > 0:
            row = result['rows'][0]
            
            # Parse the JSON string back to a dict
            schema_dict = json.loads(row['json_schema'])
            
            # Add metadata from query
            schema_dict['x_schema_version'] = row['schema_version']
            schema_dict['x_created_at'] = row['created_at']
            
            return schema_dict
        else:
            logger.warning(f"No schema found for {node_type}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to retrieve schema: {e}", exc_info=True)
        return None

def list_available_schemas(
    db_path: str,
    branch: str = 'main'
) -> List[Dict[str, Any]]:
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
        result = repo.sql(query=query, result_format='json')
        
        if result and result.get('rows'):
            return result['rows']
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
            print(f"- {schema['node_type']} (v{schema['schema_version']}) created at {schema['created_at']}")
    else:
        print(f"Dolt database not found at {dolt_db_dir}") 