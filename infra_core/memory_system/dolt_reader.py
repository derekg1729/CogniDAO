"""
Dolt reader module for accessing memory blocks.

This module provides two approaches for reading data from Dolt:
1. Legacy file-based access using doltpy.cli.Dolt (will be deprecated)
2. Remote SQL server access using mysql.connector (recommended)

The DoltMySQLReader class provides MySQL connector-based access to a running
Dolt SQL server, supporting branch switching and using standard MySQL environment
variables for configuration.

Environment Variables (used by DoltConnectionConfig):
- MYSQL_HOST / DB_HOST: Database host (default: localhost)
- MYSQL_PORT / DB_PORT: Database port (default: 3306)
- MYSQL_USER / DB_USER: Database user (default: root)
- MYSQL_PASSWORD / DB_PASSWORD: Database password (default: empty)
- MYSQL_DATABASE / DB_NAME: Database name (default: memory_dolt)
"""

import logging
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
import json
from datetime import datetime
import os
from dataclasses import dataclass, field
import warnings

from doltpy.cli import Dolt
from pydantic import ValidationError
import mysql.connector
from mysql.connector import Error

# --- Path Setup --- START
# Must happen before importing local modules
script_dir = Path(__file__).parent
project_root_dir = script_dir.parent.parent.parent  # Navigate up THREE levels
if str(project_root_dir) not in sys.path:
    sys.path.insert(0, str(project_root_dir))
# --- Path Setup --- END

# Import schema using path relative to project root
try:
    from infra_core.memory_system.schemas.memory_block import MemoryBlock
    from infra_core.memory_system.schemas.common import BlockProperty
except ImportError as e:
    # Add more context to the error message
    raise ImportError(
        f"Could not import MemoryBlock schema from infra_core/memory_system. "
        f"Project root added to path: {project_root_dir}. Check structure. Error: {e}"
    )

# Setup standard Python logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@dataclass
class DoltConnectionConfig:
    """Configuration for connecting to a Dolt SQL server via MySQL connector.

    Uses standard MySQL environment variables with sensible defaults for Dolt.
    Environment variables checked (in order of precedence):
    - MYSQL_HOST / DB_HOST -> host
    - MYSQL_PORT / DB_PORT -> port
    - MYSQL_USER / DB_USER -> user
    - MYSQL_PASSWORD / DB_PASSWORD -> password
    - MYSQL_DATABASE / DB_NAME -> database
    """

    host: str = field(
        default_factory=lambda: os.getenv("MYSQL_HOST") or os.getenv("DB_HOST", "localhost")
    )
    port: int = field(
        default_factory=lambda: int(os.getenv("MYSQL_PORT") or os.getenv("DB_PORT", "3306"))
    )
    user: str = field(
        default_factory=lambda: os.getenv("MYSQL_USER") or os.getenv("DB_USER", "root")
    )
    password: str = field(
        default_factory=lambda: os.getenv("MYSQL_PASSWORD") or os.getenv("DB_PASSWORD", "")
    )
    database: str = field(
        default_factory=lambda: os.getenv("MYSQL_DATABASE") or os.getenv("DB_NAME", "memory_dolt")
    )


class DoltMySQLReader:
    """Dolt reader that connects to remote Dolt SQL server via MySQL connector.

    Provides the same interface as the original dolt_reader functions but
    connects to a running Dolt SQL server instead of local file access.
    """

    def __init__(self, config: DoltConnectionConfig):
        """Initialize with connection configuration."""
        self.config = config

    def _get_connection(self):
        """Get a new MySQL connection to the Dolt SQL server."""
        try:
            conn = mysql.connector.connect(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
                charset="utf8mb4",
                autocommit=True,
                connection_timeout=10,
                # Use dictionary cursor for consistent return format
                use_unicode=True,
                raise_on_warnings=True,
            )
            return conn
        except Error as e:
            raise Exception(f"Failed to connect to Dolt SQL server: {e}")

    def _ensure_branch(self, connection: mysql.connector.MySQLConnection, branch: str) -> None:
        """Ensure we're on the specified branch."""
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("CALL DOLT_CHECKOUT(%s)", (branch,))
            # Consume any results
            cursor.fetchall()
            cursor.close()
        except Error as e:
            raise Exception(f"Failed to checkout branch '{branch}': {e}")

    def _execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Execute a query and return results as list of dictionaries."""
        connection = self._get_connection()
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, params or ())
            results = cursor.fetchall()
            cursor.close()
            return results
        except Error as e:
            raise Exception(f"Query failed: {e}")
        finally:
            connection.close()

    def read_memory_blocks(self, branch: str = "main") -> List[Dict[str, Any]]:
        """Read all memory blocks from the specified branch."""
        connection = self._get_connection()
        try:
            self._ensure_branch(connection, branch)
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM memory_blocks")
            results = cursor.fetchall()
            cursor.close()
            return results
        except Error as e:
            raise Exception(f"Failed to read memory blocks: {e}")
        finally:
            connection.close()

    def read_memory_block(self, block_id: str, branch: str = "main") -> Optional[Dict[str, Any]]:
        """Read a specific memory block by ID from the specified branch."""
        connection = self._get_connection()
        try:
            self._ensure_branch(connection, branch)
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM memory_blocks WHERE id = %s", (block_id,))
            result = cursor.fetchone()
            cursor.close()
            return result
        except Error as e:
            raise Exception(f"Failed to read memory block {block_id}: {e}")
        finally:
            connection.close()

    def read_block_properties(
        self, block_id: str, branch: str = "main"
    ) -> Optional[Dict[str, Any]]:
        """Read properties for a specific block."""
        connection = self._get_connection()
        try:
            self._ensure_branch(connection, branch)
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT id, type, tags, metadata FROM memory_blocks WHERE id = %s", (block_id,)
            )
            result = cursor.fetchone()
            cursor.close()
            return result
        except Error as e:
            raise Exception(f"Failed to read block properties for {block_id}: {e}")
        finally:
            connection.close()

    def batch_read_block_properties(
        self, block_ids: List[str], branch: str = "main"
    ) -> List[Dict[str, Any]]:
        """Read properties for multiple blocks efficiently."""
        if not block_ids:
            return []

        connection = self._get_connection()
        try:
            self._ensure_branch(connection, branch)
            cursor = connection.cursor(dictionary=True)

            # Create placeholders for the IN clause
            placeholders = ",".join(["%s"] * len(block_ids))
            query = (
                f"SELECT id, type, tags, metadata FROM memory_blocks WHERE id IN ({placeholders})"
            )

            cursor.execute(query, block_ids)
            results = cursor.fetchall()
            cursor.close()
            return results
        except Error as e:
            raise Exception(f"Failed to batch read block properties: {e}")
        finally:
            connection.close()

    def read_memory_blocks_by_tags(
        self, tags: List[str], branch: str = "main"
    ) -> List[Dict[str, Any]]:
        """Read memory blocks that have all specified tags."""
        if not tags:
            return self.read_memory_blocks(branch)

        connection = self._get_connection()
        try:
            self._ensure_branch(connection, branch)
            cursor = connection.cursor(dictionary=True)

            # Build conditions for each tag
            conditions = []
            params = []
            for tag in tags:
                conditions.append("JSON_CONTAINS(tags, %s)")
                params.append(json.dumps(tag))

            where_clause = " AND ".join(conditions)
            query = f"SELECT * FROM memory_blocks WHERE {where_clause}"

            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()
            return results
        except Error as e:
            raise Exception(f"Failed to read memory blocks by tags {tags}: {e}")
        finally:
            connection.close()


# Helper function from dolt_writer for safe SQL formatting
def _escape_sql_string(value: Optional[str]) -> str:
    """Basic escaping for SQL strings to prevent simple injection issues."""
    if value is None:
        return "NULL"
    # Replace single quotes with two single quotes
    escaped_value = value.replace("'", "''")
    return f"'{escaped_value}'"


def batch_read_block_properties(
    db_path: str, block_ids: List[str], branch: str = "main"
) -> Dict[str, List[BlockProperty]]:
    """
    Read BlockProperty instances for multiple blocks in a single query to avoid N+1 performance issues.

    Args:
        db_path: Path to the Dolt database directory
        block_ids: List of block IDs to read properties for
        branch: The Dolt branch to read from (defaults to 'main')

    Returns:
        Dictionary mapping block_id to list of BlockProperty instances
    """
    if not block_ids:
        return {}

    logger.debug(f"Batch reading properties for {len(block_ids)} blocks from branch '{branch}'")
    repo = Dolt(db_path)

    # Escape all block IDs for SQL safety
    escaped_block_ids = [_escape_sql_string(block_id) for block_id in block_ids]
    in_clause = ", ".join(escaped_block_ids)

    query = f"""
    SELECT 
        block_id, property_name, property_value_text, property_value_number, 
        property_value_json, property_type, is_computed, created_at, updated_at
    FROM block_properties
    AS OF '{branch}'
    WHERE block_id IN ({in_clause})
    ORDER BY block_id, property_name
    """

    logger.debug(f"Executing batch properties query for {len(block_ids)} blocks:\n{query}")
    result = repo.sql(query=query, result_format="json")

    # Group properties by block_id
    properties_by_block: Dict[str, List[BlockProperty]] = {block_id: [] for block_id in block_ids}

    if result and "rows" in result and result["rows"]:
        logger.debug(f"Found {len(result['rows'])} total properties for {len(block_ids)} blocks")
        for row in result["rows"]:
            try:
                # Convert datetime strings back to datetime objects if needed
                if isinstance(row.get("created_at"), str):
                    row["created_at"] = datetime.fromisoformat(row["created_at"])
                if isinstance(row.get("updated_at"), str):
                    row["updated_at"] = datetime.fromisoformat(row["updated_at"])

                prop = BlockProperty.model_validate(row)
                block_id = prop.block_id
                if block_id in properties_by_block:
                    properties_by_block[block_id].append(prop)
                else:
                    # This shouldn't happen with proper WHERE clause, but handle gracefully
                    logger.warning(f"Found properties for unexpected block_id: {block_id}")
                    properties_by_block[block_id] = [prop]

            except ValidationError as e:
                logger.error(
                    f"Failed to validate property {row.get('property_name', 'unknown')} for block {row.get('block_id', 'unknown')}: {e}"
                )
            except Exception as e:
                logger.error(f"Error processing property row: {e}")
    else:
        logger.debug(f"No properties found for any of the {len(block_ids)} blocks")

    # Log summary stats
    total_properties = sum(len(props) for props in properties_by_block.values())
    blocks_with_properties = sum(1 for props in properties_by_block.values() if props)
    logger.debug(
        f"Batch read complete: {total_properties} properties across {blocks_with_properties}/{len(block_ids)} blocks"
    )

    return properties_by_block


def read_memory_blocks(db_path: str, branch: str = "main") -> List[MemoryBlock]:
    """
    Read MemoryBlocks from a Dolt database using file-based access.

    DEPRECATED: This function is deprecated and will be removed in a future version.
    Use DoltMySQLReader class with a running Dolt SQL server instead for better
    performance and scalability.

    Args:
        db_path: Path to the Dolt database directory
        branch: The Dolt branch to read from (defaults to 'main')

    Returns:
        List of MemoryBlock instances
    """
    warnings.warn(
        "read_memory_blocks() file-based access is deprecated. "
        "Use DoltMySQLReader with a Dolt SQL server instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    logger.info(f"Reading MemoryBlocks from branch '{branch}' using legacy file-based access")
    memory_blocks_list: List[MemoryBlock] = []
    repo: Optional[Dolt] = None

    try:
        # 1. Connect to Dolt repository
        repo = Dolt(db_path)

        # 2. Define the SQL Query (NO metadata column, include ALL mandatory columns - CR-01 & CR-02 fix)
        # Use AS OF syntax to query a specific branch/commit
        query = f"""
        SELECT 
            id, type, schema_version, text, state, visibility, block_version, 
            parent_id, has_children, tags, source_file, source_uri, confidence, 
            created_by, created_at, updated_at, embedding
        FROM memory_blocks 
        AS OF '{branch}'
        """
        logger.debug(f"Executing SQL query on branch '{branch}':\\n{query}")

        # 3. Execute the query
        result = repo.sql(query=query, result_format="json")

        # 4. Process Results
        if result and "rows" in result and result["rows"]:
            logger.info(f"Retrieved {len(result['rows'])} rows from Dolt.")

            # 5. PERFORMANCE OPTIMIZATION: Batch read all block properties in one query
            block_ids = [row["id"] for row in result["rows"]]
            properties_by_block = batch_read_block_properties(db_path, block_ids, branch)
            logger.info(
                f"Batch loaded properties for {len(block_ids)} blocks (performance optimization)"
            )

            for row in result["rows"]:
                try:
                    # 6. Compose metadata using PropertyMapper (CR-01 fix)
                    try:
                        # Import PropertyMapper here to avoid circular imports if needed
                        from infra_core.memory_system.property_mapper import PropertyMapper

                        # Get pre-loaded properties for this block
                        properties = properties_by_block.get(row["id"], [])

                        # Compose metadata from properties
                        metadata_dict = PropertyMapper.compose_metadata(properties)
                        logger.debug(
                            f"Composed metadata with {len(metadata_dict)} fields for block {row['id']} using {len(properties)} properties"
                        )

                        # Add metadata to the row data
                        row["metadata"] = metadata_dict

                    except Exception as prop_e:
                        logger.error(
                            f"Failed to compose metadata for block {row['id']}: {prop_e}",
                            exc_info=True,
                        )
                        # Use empty metadata as fallback
                        row["metadata"] = {}

                    # 7. Prepare row data for Pydantic model validation
                    # Filter out None values explicitly if needed, though Pydantic usually handles optional fields.
                    # Create a copy to avoid modifying the original result row if necessary.
                    parsed_row: Dict[str, Any] = {k: v for k, v in row.items() if v is not None}

                    # FIX-03: Parse embedding field if it comes as JSON string from Dolt
                    # (similar to the logic in read_memory_blocks_from_working_set)
                    for key, value in parsed_row.items():
                        if value is None:
                            continue

                        # Handle embedding field specifically
                        if key == "embedding" and isinstance(value, str):
                            try:
                                parsed_row[key] = json.loads(value)
                                logger.debug(
                                    f"Successfully parsed embedding JSON string for block {row['id']}"
                                )
                            except json.JSONDecodeError:
                                logger.warning(
                                    f"Failed to parse JSON string for embedding in block {row['id']}: {value}"
                                )
                                # Keep as string if parsing fails, Pydantic might handle or error
                                parsed_row[key] = value

                    # 8. Validate using Pydantic
                    memory_block = MemoryBlock.model_validate(parsed_row)
                    memory_blocks_list.append(memory_block)

                except ValidationError as e:
                    # Log Pydantic validation errors specifically
                    logger.error(
                        f"Pydantic validation failed for row (Block ID: {row.get('id', 'UNKNOWN')}): {e}"
                    )
                except Exception as parse_e:
                    # Log any other unexpected errors during processing of a row
                    logger.error(
                        f"Unexpected error processing row (Block ID: {row.get('id', 'UNKNOWN')}): {parse_e}",
                        exc_info=True,
                    )
        else:
            logger.info("No rows returned from the Dolt query.")

    except FileNotFoundError:
        logger.error(f"Dolt database path not found: {db_path}")
        # Re-raise or handle as appropriate for the application
        raise
    except Exception as e:
        # Log errors related to DB connection or SQL execution
        logger.error(
            f"Failed to read from Dolt DB at {db_path} on branch '{branch}': {e}", exc_info=True
        )
        # Depending on use case, might want to return partial list or empty list
        # Returning empty list on major error for now.
        return []  # Return empty list on error

    logger.info(
        f"Finished reading. Successfully parsed {len(memory_blocks_list)} MemoryBlocks using Property-Schema Split with batch property loading."
    )
    return memory_blocks_list


def read_memory_block(db_path: str, block_id: str, branch: str = "main") -> Optional[MemoryBlock]:
    """
    Reads a single MemoryBlock from the specified Dolt database using file-based access.

    DEPRECATED: This function is deprecated and will be removed in a future version.
    Use DoltMySQLReader class with a running Dolt SQL server instead for better
    performance and scalability.

    Args:
        db_path: Path to the Dolt database directory.
        block_id: The ID of the block to read.
        branch: The Dolt branch to read from (defaults to 'main').

    Returns:
        A validated MemoryBlock object if found, or None if not found/error.
    """
    warnings.warn(
        "read_memory_block() file-based access is deprecated. "
        "Use DoltMySQLReader with a Dolt SQL server instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    logger.info(f"Reading block {block_id} from branch '{branch}' using legacy file-based access")
    repo: Optional[Dolt] = None

    try:
        repo = Dolt(db_path)
        escaped_block_id = _escape_sql_string(block_id)

        # Step 1: Read from memory_blocks table (NO metadata column - Property-Schema Split)
        query = f"""
        SELECT
            id, type, schema_version, text, state, visibility, block_version, 
            parent_id, has_children, tags, source_file, source_uri, confidence, 
            created_by, created_at, updated_at, embedding
        FROM memory_blocks
        AS OF '{branch}'
        WHERE id = {escaped_block_id}
        LIMIT 1
        """
        logger.debug(
            f"Executing SQL query for block {escaped_block_id} on branch '{branch}':\n{query}"
        )

        # Execute query without the 'args' parameter
        result = repo.sql(query=query, result_format="json")

        if result and "rows" in result and result["rows"]:
            row = result["rows"][0]
            logger.info(f"Retrieved row for block ID: {block_id}")

            # Step 2: Read properties and compose metadata using PropertyMapper
            try:
                # Import PropertyMapper here to avoid circular imports if needed
                from infra_core.memory_system.property_mapper import PropertyMapper

                # Read properties from block_properties table
                properties = read_block_properties(db_path, block_id, branch)

                # Compose metadata from properties
                metadata_dict = PropertyMapper.compose_metadata(properties)
                logger.debug(
                    f"Composed metadata with {len(metadata_dict)} fields for block {block_id}"
                )

                # Add metadata to the row data
                row["metadata"] = metadata_dict

            except Exception as prop_e:
                logger.error(
                    f"Failed to compose metadata for block {block_id}: {prop_e}", exc_info=True
                )
                # Use empty metadata as fallback
                row["metadata"] = {}

            try:
                # Prepare row data for Pydantic model validation
                parsed_row: Dict[str, Any] = {k: v for k, v in row.items() if v is not None}

                # FIX-03: Parse embedding field if it comes as JSON string from Dolt
                for key, value in parsed_row.items():
                    if value is None:
                        continue

                    # Handle embedding field specifically
                    if key == "embedding" and isinstance(value, str):
                        try:
                            parsed_row[key] = json.loads(value)
                            logger.debug(
                                f"Successfully parsed embedding JSON string for block {block_id}"
                            )
                        except json.JSONDecodeError:
                            logger.warning(
                                f"Failed to parse JSON string for embedding in block {block_id}: {value}"
                            )
                            # Keep as string if parsing fails, Pydantic might handle or error
                            parsed_row[key] = value

                memory_block = MemoryBlock.model_validate(parsed_row)
                logger.info(
                    f"Successfully parsed MemoryBlock {block_id} using Property-Schema Split."
                )
                return memory_block

            except ValidationError as e:
                logger.error(f"Pydantic validation failed for row (Block ID: {block_id}): {e}")
                return None
            except Exception as parse_e:
                logger.error(
                    f"Unexpected error processing row (Block ID: {block_id}): {parse_e}",
                    exc_info=True,
                )
                return None
        else:
            logger.info(f"No row found for MemoryBlock ID: {block_id}")
            return None

    except FileNotFoundError:
        logger.error(f"Dolt database path not found: {db_path}")
        raise  # Re-raise critical error
    except Exception as e:
        logger.error(
            f"Failed to read block {block_id} from Dolt DB at {db_path} on branch '{branch}': {e}",
            exc_info=True,
        )
        return None


def read_memory_blocks_by_tags(
    db_path: str, tags: List[str], match_all: bool = True, branch: str = "main"
) -> List[MemoryBlock]:
    """
    Reads MemoryBlocks from Dolt filtered by tags using file-based access.

    DEPRECATED: This function is deprecated and will be removed in a future version.
    Use DoltMySQLReader class with a running Dolt SQL server instead for better
    performance and scalability.

    Args:
        db_path: Path to the Dolt database directory.
        tags: A list of tags to filter by.
        match_all: If True, blocks must contain ALL tags. If False, blocks must contain AT LEAST ONE tag.
        branch: The Dolt branch to read from (defaults to 'main').

    Returns:
        A list of validated MemoryBlock objects matching the tag criteria.
    """
    warnings.warn(
        "read_memory_blocks_by_tags() file-based access is deprecated. "
        "Use DoltMySQLReader with a Dolt SQL server instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    if not tags:
        logger.warning("read_memory_blocks_by_tags called with empty tags list.")
        return []

    logger.info(
        f"Reading MemoryBlocks by tags {tags} (match_all={match_all}) from branch '{branch}' using legacy file-based access"
    )
    memory_blocks_list: List[MemoryBlock] = []
    repo: Optional[Dolt] = None

    try:
        repo = Dolt(db_path)

        # Build tag filter conditions using JSON operations
        tag_conditions = []
        for tag in tags:
            # Convert tag to proper JSON string format first, then SQL-escape it
            # This ensures JSON_CONTAINS gets a valid JSON string like '"core-document"'
            json_tag = json.dumps(tag)  # Creates proper JSON string with quotes
            escaped_json_tag = _escape_sql_string(json_tag)
            # Use JSON_CONTAINS to check if the tag is in the JSON array
            tag_conditions.append(f"JSON_CONTAINS(tags, {escaped_json_tag})")

        if match_all:
            # All tags must be present (AND condition)
            where_clause = " AND ".join(tag_conditions)
        else:
            # At least one tag must be present (OR condition)
            where_clause = " OR ".join(tag_conditions)

        # Define the SQL Query with tag filtering
        query = f"""
        SELECT 
            id, type, schema_version, text, state, visibility, block_version, 
            parent_id, has_children, tags, source_file, source_uri, confidence, 
            created_by, created_at, updated_at, embedding
        FROM memory_blocks 
        AS OF '{branch}'
        WHERE {where_clause}
        """
        logger.debug(f"Executing tag filter SQL query on branch '{branch}':\\n{query}")

        result = repo.sql(query=query, result_format="json")

        if result and "rows" in result and result["rows"]:
            logger.info(f"Retrieved {len(result['rows'])} rows matching tags from Dolt.")

            # PERFORMANCE OPTIMIZATION: Batch read all block properties in one query
            block_ids = [row["id"] for row in result["rows"]]
            properties_by_block = batch_read_block_properties(db_path, block_ids, branch)
            logger.info(
                f"Batch loaded properties for {len(block_ids)} blocks matching tags (performance optimization)"
            )

            for row in result["rows"]:
                try:
                    # Compose metadata using PropertyMapper (CR-01 fix)
                    try:
                        # Import PropertyMapper here to avoid circular imports if needed
                        from infra_core.memory_system.property_mapper import PropertyMapper

                        # Get pre-loaded properties for this block
                        properties = properties_by_block.get(row["id"], [])

                        # Compose metadata from properties
                        metadata_dict = PropertyMapper.compose_metadata(properties)
                        logger.debug(
                            f"Composed metadata with {len(metadata_dict)} fields for block {row['id']} using {len(properties)} properties"
                        )

                        # Add metadata to the row data
                        row["metadata"] = metadata_dict

                    except Exception as prop_e:
                        logger.error(
                            f"Failed to compose metadata for block {row['id']}: {prop_e}",
                            exc_info=True,
                        )
                        # Use empty metadata as fallback
                        row["metadata"] = {}

                    parsed_row: Dict[str, Any] = {k: v for k, v in row.items() if v is not None}

                    # FIX-03: Parse embedding field if it comes as JSON string from Dolt
                    for key, value in parsed_row.items():
                        if value is None:
                            continue

                        # Handle embedding field specifically
                        if key == "embedding" and isinstance(value, str):
                            try:
                                parsed_row[key] = json.loads(value)
                                logger.debug(
                                    f"Successfully parsed embedding JSON string for block {row['id']}"
                                )
                            except json.JSONDecodeError:
                                logger.warning(
                                    f"Failed to parse JSON string for embedding in block {row['id']}: {value}"
                                )
                                # Keep as string if parsing fails, Pydantic might handle or error
                                parsed_row[key] = value

                    memory_block = MemoryBlock.model_validate(parsed_row)
                    memory_blocks_list.append(memory_block)
                except ValidationError as e:
                    logger.error(
                        f"Pydantic validation failed for row (Block ID: {row.get('id', 'UNKNOWN')}): {e}"
                    )
                except Exception as parse_e:
                    logger.error(
                        f"Unexpected error processing row (Block ID: {row.get('id', 'UNKNOWN')}): {parse_e}",
                        exc_info=True,
                    )
        else:
            logger.info("No rows returned from the Dolt tag query.")

    except FileNotFoundError:
        logger.error(f"Dolt database path not found: {db_path}")
        raise
    except Exception as e:
        logger.error(
            f"Failed to read by tags from Dolt DB at {db_path} on branch '{branch}': {e}",
            exc_info=True,
        )
        return []  # Return empty list on error

    logger.info(
        f"Finished reading by tags. Successfully parsed {len(memory_blocks_list)} MemoryBlocks using Property-Schema Split with batch property loading."
    )
    return memory_blocks_list


def read_memory_blocks_from_working_set(db_path: str) -> List[MemoryBlock]:
    """
    Reads MemoryBlocks from the working set of the specified Dolt database using Property-Schema Split approach.

    Uses PropertyMapper to compose metadata from the block_properties table instead of reading
    from a metadata JSON column (CR-01 fix).

    PERFORMANCE: Uses batch_read_block_properties() to avoid N+1 query performance issues.
    """
    logger.info(
        f"Attempting to read MemoryBlocks from Dolt DB working set at {db_path} using Property-Schema Split"
    )
    memory_blocks_list: List[MemoryBlock] = []
    repo: Optional[Dolt] = None

    try:
        repo = Dolt(db_path)

        # Query to select all relevant columns from memory_blocks in the working set.
        # No 'AS OF' clause is used, so it queries the working tables.
        # NO metadata column, include ALL mandatory columns (CR-01 & CR-02 fix)
        query = """
        SELECT
            id, type, schema_version, text, state, visibility, block_version, 
            parent_id, has_children, tags, source_file, source_uri, confidence, 
            created_by, created_at, updated_at, embedding
        FROM memory_blocks
        """

        logger.debug(f"Executing SQL query on working set:\\n{query}")

        result = repo.sql(query=query, result_format="json")

        if result and "rows" in result and result["rows"]:
            logger.info(f"Retrieved {len(result['rows'])} rows from Dolt working set.")

            # PERFORMANCE OPTIMIZATION: Batch read all block properties in one query
            block_ids = [row_data["id"] for row_data in result["rows"]]
            properties_by_block = batch_read_block_properties(
                db_path, block_ids, "main"
            )  # Working set uses main branch
            logger.info(
                f"Batch loaded properties for {len(block_ids)} blocks from working set (performance optimization)"
            )

            for row_data in result["rows"]:
                try:
                    # Compose metadata using PropertyMapper (CR-01 fix)
                    try:
                        # Import PropertyMapper here to avoid circular imports if needed
                        from infra_core.memory_system.property_mapper import PropertyMapper

                        # Get pre-loaded properties for this block
                        properties = properties_by_block.get(row_data["id"], [])

                        # Compose metadata from properties
                        metadata_dict = PropertyMapper.compose_metadata(properties)
                        logger.debug(
                            f"Composed metadata with {len(metadata_dict)} fields for block {row_data['id']} using {len(properties)} properties"
                        )

                        # Add metadata to the row data
                        row_data["metadata"] = metadata_dict

                    except Exception as prop_e:
                        logger.error(
                            f"Failed to compose metadata for block {row_data['id']}: {prop_e}",
                            exc_info=True,
                        )
                        # Use empty metadata as fallback
                        row_data["metadata"] = {}

                    # Prepare row data for Pydantic model validation.
                    parsed_row = {}
                    for key, value in row_data.items():
                        if value is None:  # Pydantic handles optional fields being None
                            parsed_row[key] = None
                            continue

                        # Explicitly parse potential JSON string fields if not auto-parsed
                        if key in ["tags", "metadata", "confidence"]:
                            if isinstance(value, str):
                                try:
                                    parsed_row[key] = json.loads(value)
                                except json.JSONDecodeError:
                                    logger.warning(
                                        f"Failed to parse JSON string for field '{key}' in block ID {row_data.get('id', 'UNKNOWN')}: {value}"
                                    )
                                    parsed_row[key] = (
                                        value  # Keep as string if parsing fails, Pydantic might handle or error
                                    )
                            else:
                                parsed_row[key] = value  # Assume already parsed by doltpy
                        else:
                            parsed_row[key] = value

                    memory_block = MemoryBlock.model_validate(parsed_row)
                    memory_blocks_list.append(memory_block)

                except ValidationError as e:
                    logger.error(
                        f"Pydantic validation failed for row (Block ID: {row_data.get('id', 'UNKNOWN')}): {e}"
                    )
                except Exception as parse_e:
                    logger.error(
                        f"Unexpected error processing row (Block ID: {row_data.get('id', 'UNKNOWN')}): {parse_e}",
                        exc_info=True,
                    )
        else:
            logger.info("No rows returned from the Dolt working set query.")

    except FileNotFoundError:
        logger.error(f"Dolt database path not found: {db_path}")
        raise
    except Exception as e:
        logger.error(f"Failed to read from Dolt DB working set at {db_path}: {e}", exc_info=True)
        return []

    logger.info(
        f"Finished reading. Successfully parsed {len(memory_blocks_list)} MemoryBlocks from working set using Property-Schema Split with batch property loading."
    )
    return memory_blocks_list


def read_block_properties(db_path: str, block_id: str, branch: str = "main") -> List[BlockProperty]:
    """
    Read BlockProperty instances for a specific block from the block_properties table using file-based access.

    DEPRECATED: This function is deprecated and will be removed in a future version.
    Use DoltMySQLReader class with a running Dolt SQL server instead for better
    performance and scalability.

    Args:
        db_path: Path to the Dolt database directory
        block_id: ID of the block to read properties for
        branch: The Dolt branch to read from (defaults to 'main')

    Returns:
        List of BlockProperty instances
    """
    warnings.warn(
        "read_block_properties() file-based access is deprecated. "
        "Use DoltMySQLReader with a Dolt SQL server instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    logger.debug(
        f"Reading properties for block {block_id} from branch '{branch}' using legacy file-based access"
    )
    repo = Dolt(db_path)
    escaped_block_id = _escape_sql_string(block_id)

    query = f"""
    SELECT 
        block_id, property_name, property_value_text, property_value_number, 
        property_value_json, property_type, is_computed, created_at, updated_at
    FROM block_properties
    AS OF '{branch}'
    WHERE block_id = {escaped_block_id}
    """

    logger.debug(f"Executing properties query:\n{query}")
    result = repo.sql(query=query, result_format="json")

    properties = []
    if result and "rows" in result and result["rows"]:
        logger.debug(f"Found {len(result['rows'])} properties for block {block_id}")
        for row in result["rows"]:
            try:
                # Convert datetime strings back to datetime objects if needed
                if isinstance(row.get("created_at"), str):
                    row["created_at"] = datetime.fromisoformat(row["created_at"])
                if isinstance(row.get("updated_at"), str):
                    row["updated_at"] = datetime.fromisoformat(row["updated_at"])

                prop = BlockProperty.model_validate(row)
                properties.append(prop)
            except ValidationError as e:
                logger.error(
                    f"Failed to validate property {row.get('property_name', 'unknown')}: {e}"
                )
            except Exception as e:
                logger.error(f"Error processing property row: {e}")
    else:
        logger.debug(f"No properties found for block {block_id}")

    return properties


# Example Usage (can be run as a script for testing)
if __name__ == "__main__":
    logger.info("Running Dolt reader example...")

    # Define the path to your experimental Dolt database
    # Assumes script is run from project root or PYTHONPATH is set
    dolt_db_dir = project_root_dir / "experiments" / "dolt_data" / "memory_db"

    if not dolt_db_dir.exists() or not (dolt_db_dir / ".dolt").exists():
        logger.error(f"Dolt database not found at {dolt_db_dir}. Please run Task 1.2 setup.")
    else:
        logger.info(f"Using Dolt DB at: {dolt_db_dir}")

        # Read blocks from the 'main' branch
        try:
            blocks = read_memory_blocks(str(dolt_db_dir), branch="main")
            if blocks:
                logger.info(f"Successfully read {len(blocks)} MemoryBlocks from main branch:")
                # Print summary of first few blocks for verification
                for i, block in enumerate(blocks[:3]):
                    logger.info(
                        f"  Block {i + 1}: ID={block.id}, Type={block.type}, Text='{block.text[:50]}...' Tags={block.tags}"
                    )
                if len(blocks) > 3:
                    logger.info(f"  ... and {len(blocks) - 3} more.")
            else:
                logger.info("No MemoryBlocks found in the main branch.")
        except Exception as e:
            logger.error(f"Failed to read blocks during example run: {e}", exc_info=True)
