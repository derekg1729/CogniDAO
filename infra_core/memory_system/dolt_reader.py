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
import os
from dataclasses import dataclass, field
import warnings

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

    def read_memory_blocks(self, branch: str = "main") -> List[MemoryBlock]:
        """Read all memory blocks from Dolt SQL server, returning MemoryBlock objects."""
        try:
            connection = self._get_connection()
            self._ensure_branch(connection, branch)

            query = """
            SELECT id, type, schema_version, text, state, visibility, block_version,
                   parent_id, has_children, tags, source_file, source_uri, confidence,
                   created_by, created_at, updated_at, embedding
            FROM memory_blocks
            """

            cursor = connection.cursor(dictionary=True)
            cursor.execute(query)
            rows = cursor.fetchall()
            cursor.close()
            connection.close()

            # Convert to MemoryBlock objects
            memory_blocks = []
            for row in rows:
                try:
                    # Parse JSON fields
                    if row.get("tags") and isinstance(row["tags"], str):
                        row["tags"] = json.loads(row["tags"])
                    if row.get("confidence") and isinstance(row["confidence"], str):
                        row["confidence"] = json.loads(row["confidence"])
                    if row.get("embedding") and isinstance(row["embedding"], str):
                        row["embedding"] = json.loads(row["embedding"])

                    # Get properties and compose metadata
                    try:
                        from infra_core.memory_system.property_mapper import PropertyMapper

                        properties = self.read_block_properties(row["id"], branch)
                        if properties:
                            # Convert dict properties to BlockProperty objects if needed
                            if properties and isinstance(properties[0], dict):
                                from infra_core.memory_system.schemas.common import BlockProperty

                                properties = [
                                    BlockProperty.model_validate(prop) for prop in properties
                                ]
                            metadata_dict = PropertyMapper.compose_metadata(properties)
                        else:
                            metadata_dict = {}
                        row["metadata"] = metadata_dict
                    except Exception as e:
                        logger.warning(f"Failed to compose metadata for block {row['id']}: {e}")
                        row["metadata"] = {}

                    # Remove None values and create MemoryBlock
                    cleaned_row = {k: v for k, v in row.items() if v is not None}
                    memory_block = MemoryBlock.model_validate(cleaned_row)
                    memory_blocks.append(memory_block)

                except Exception as e:
                    logger.error(f"Failed to parse memory block {row.get('id', 'unknown')}: {e}")
                    continue

            return memory_blocks

        except Exception as e:
            logger.error(f"Failed to read memory blocks: {e}")
            return []

    def read_memory_block(self, block_id: str, branch: str = "main") -> Optional[MemoryBlock]:
        """Read a single memory block by ID from Dolt SQL server, returning MemoryBlock object."""
        try:
            connection = self._get_connection()
            self._ensure_branch(connection, branch)

            query = """
            SELECT id, type, schema_version, text, state, visibility, block_version,
                   parent_id, has_children, tags, source_file, source_uri, confidence,
                   created_by, created_at, updated_at, embedding
            FROM memory_blocks
            WHERE id = %s
            LIMIT 1
            """

            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, (block_id,))
            row = cursor.fetchone()
            cursor.close()
            connection.close()

            if not row:
                return None

            try:
                # Parse JSON fields
                if row.get("tags") and isinstance(row["tags"], str):
                    row["tags"] = json.loads(row["tags"])
                if row.get("confidence") and isinstance(row["confidence"], str):
                    row["confidence"] = json.loads(row["confidence"])
                if row.get("embedding") and isinstance(row["embedding"], str):
                    row["embedding"] = json.loads(row["embedding"])

                # Get properties and compose metadata
                try:
                    from infra_core.memory_system.property_mapper import PropertyMapper

                    properties = self.read_block_properties(block_id, branch)
                    if properties:
                        # Convert dict properties to BlockProperty objects if needed
                        if properties and isinstance(properties[0], dict):
                            from infra_core.memory_system.schemas.common import BlockProperty

                            properties = [BlockProperty.model_validate(prop) for prop in properties]
                        metadata_dict = PropertyMapper.compose_metadata(properties)
                    else:
                        metadata_dict = {}
                    row["metadata"] = metadata_dict
                except Exception as e:
                    logger.warning(f"Failed to compose metadata for block {block_id}: {e}")
                    row["metadata"] = {}

                # Remove None values and create MemoryBlock
                cleaned_row = {k: v for k, v in row.items() if v is not None}
                return MemoryBlock.model_validate(cleaned_row)

            except Exception as e:
                logger.error(f"Failed to parse memory block {block_id}: {e}")
                return None

        except Exception as e:
            logger.error(f"Failed to read memory block {block_id}: {e}")
            return None

    def read_block_properties(self, block_id: str, branch: str = "main") -> List[BlockProperty]:
        """Read block properties for a specific block, returning BlockProperty objects."""
        try:
            connection = self._get_connection()
            self._ensure_branch(connection, branch)

            query = """
            SELECT block_id, property_name, property_value_text, property_value_number,
                   property_value_json, property_type, is_computed, created_at, updated_at
            FROM block_properties
            WHERE block_id = %s
            """

            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, (block_id,))
            rows = cursor.fetchall()
            cursor.close()
            connection.close()

            # Convert to BlockProperty objects
            properties = []
            for row in rows:
                try:
                    from infra_core.memory_system.schemas.common import BlockProperty

                    # Parse JSON field if it's a string
                    if row.get("property_value_json") and isinstance(
                        row["property_value_json"], str
                    ):
                        row["property_value_json"] = json.loads(row["property_value_json"])

                    property_obj = BlockProperty.model_validate(row)
                    properties.append(property_obj)
                except Exception as e:
                    logger.error(f"Failed to parse property for block {block_id}: {e}")
                    continue

            return properties

        except Exception as e:
            logger.error(f"Failed to read properties for block {block_id}: {e}")
            return []

    def batch_read_block_properties(
        self, block_ids: List[str], branch: str = "main"
    ) -> Dict[str, List[BlockProperty]]:
        """Read block properties for multiple blocks efficiently."""
        if not block_ids:
            return {}

        try:
            connection = self._get_connection()
            self._ensure_branch(connection, branch)

            placeholders = ",".join(["%s"] * len(block_ids))
            query = f"""
            SELECT block_id, property_name, property_value_text, property_value_number,
                   property_value_json, property_type, is_computed, created_at, updated_at
            FROM block_properties
            WHERE block_id IN ({placeholders})
            """

            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, block_ids)
            rows = cursor.fetchall()
            cursor.close()
            connection.close()

            # Group by block_id and convert to BlockProperty objects
            properties_by_block = {}
            for row in rows:
                try:
                    from infra_core.memory_system.schemas.common import BlockProperty

                    # Parse JSON field if it's a string
                    if row.get("property_value_json") and isinstance(
                        row["property_value_json"], str
                    ):
                        row["property_value_json"] = json.loads(row["property_value_json"])

                    property_obj = BlockProperty.model_validate(row)
                    block_id = row["block_id"]
                    if block_id not in properties_by_block:
                        properties_by_block[block_id] = []
                    properties_by_block[block_id].append(property_obj)
                except Exception as e:
                    logger.error(
                        f"Failed to parse property for block {row.get('block_id', 'unknown')}: {e}"
                    )
                    continue

            return properties_by_block

        except Exception as e:
            logger.error(f"Failed to batch read properties: {e}")
            return {}

    def read_memory_blocks_by_tags(
        self, tags: List[str], match_all: bool = True, branch: str = "main"
    ) -> List[MemoryBlock]:
        """Read memory blocks filtered by tags, returning MemoryBlock objects."""
        if not tags:
            return self.read_memory_blocks(branch)

        try:
            connection = self._get_connection()
            self._ensure_branch(connection, branch)

            # Build tag filter condition
            if match_all:
                # All tags must be present
                tag_conditions = []
                params = []
                for tag in tags:
                    tag_conditions.append("JSON_CONTAINS(tags, %s)")
                    params.append(json.dumps(tag))
                where_clause = " AND ".join(tag_conditions)
            else:
                # At least one tag must be present
                tag_conditions = []
                params = []
                for tag in tags:
                    tag_conditions.append("JSON_CONTAINS(tags, %s)")
                    params.append(json.dumps(tag))
                where_clause = " OR ".join(tag_conditions)

            query = f"""
            SELECT id, type, schema_version, text, state, visibility, block_version,
                   parent_id, has_children, tags, source_file, source_uri, confidence,
                   created_by, created_at, updated_at, embedding
            FROM memory_blocks
            WHERE {where_clause}
            """

            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            connection.close()

            # Convert to MemoryBlock objects (similar to read_memory_blocks)
            memory_blocks = []
            for row in rows:
                try:
                    # Parse JSON fields
                    if row.get("tags") and isinstance(row["tags"], str):
                        row["tags"] = json.loads(row["tags"])
                    if row.get("confidence") and isinstance(row["confidence"], str):
                        row["confidence"] = json.loads(row["confidence"])
                    if row.get("embedding") and isinstance(row["embedding"], str):
                        row["embedding"] = json.loads(row["embedding"])

                    # Get properties and compose metadata
                    try:
                        from infra_core.memory_system.property_mapper import PropertyMapper

                        properties = self.read_block_properties(row["id"], branch)
                        if properties:
                            metadata_dict = PropertyMapper.compose_metadata(properties)
                        else:
                            metadata_dict = {}
                        row["metadata"] = metadata_dict
                    except Exception as e:
                        logger.warning(f"Failed to compose metadata for block {row['id']}: {e}")
                        row["metadata"] = {}

                    # Remove None values and create MemoryBlock
                    cleaned_row = {k: v for k, v in row.items() if v is not None}
                    memory_block = MemoryBlock.model_validate(cleaned_row)
                    memory_blocks.append(memory_block)

                except Exception as e:
                    logger.error(f"Failed to parse memory block {row.get('id', 'unknown')}: {e}")
                    continue

            return memory_blocks

        except Exception as e:
            logger.error(f"Failed to read memory blocks by tags: {e}")
            return []


# Helper function from dolt_writer for safe SQL formatting
def _escape_sql_string(value: Optional[str]) -> str:
    """
    DEPRECATED: Basic escaping for SQL strings.
    Use parameterized queries in DoltMySQLReader instead.
    """
    warnings.warn("_escape_sql_string is deprecated", DeprecationWarning)
    from infra_core.memory_system.legacy_file_dolt_access import _escape_sql_string as legacy_escape

    return legacy_escape(value)


def batch_read_block_properties(
    db_path: str, block_ids: List[str], branch: str = "main"
) -> Dict[str, List[BlockProperty]]:
    """
    DEPRECATED: Legacy file-based function.
    Use DoltMySQLReader.batch_read_block_properties() instead.
    """
    from infra_core.memory_system.legacy_file_dolt_access import (
        batch_read_block_properties as legacy_func,
    )

    return legacy_func(db_path, block_ids, branch)


def read_memory_blocks(db_path: str, branch: str = "main") -> List[MemoryBlock]:
    """
    DEPRECATED: Legacy file-based function.
    Use DoltMySQLReader.read_memory_blocks() instead.
    """
    from infra_core.memory_system.legacy_file_dolt_access import read_memory_blocks as legacy_func

    return legacy_func(db_path, branch)


def read_memory_block(db_path: str, block_id: str, branch: str = "main") -> Optional[MemoryBlock]:
    """
    DEPRECATED: Legacy file-based function.
    Use DoltMySQLReader.read_memory_block() instead.
    """
    from infra_core.memory_system.legacy_file_dolt_access import read_memory_block as legacy_func

    return legacy_func(db_path, block_id, branch)


def read_memory_blocks_by_tags(
    db_path: str, tags: List[str], match_all: bool = True, branch: str = "main"
) -> List[MemoryBlock]:
    """
    DEPRECATED: Legacy file-based function.
    Use DoltMySQLReader.read_memory_blocks_by_tags() instead.
    """
    from infra_core.memory_system.legacy_file_dolt_access import (
        read_memory_blocks_by_tags as legacy_func,
    )

    return legacy_func(db_path, tags, match_all, branch)


def read_memory_blocks_from_working_set(db_path: str) -> List[MemoryBlock]:
    """
    DEPRECATED: Legacy file-based function.
    Use DoltMySQLReader with appropriate branch instead.
    """
    from infra_core.memory_system.legacy_file_dolt_access import (
        read_memory_blocks_from_working_set as legacy_func,
    )

    return legacy_func(db_path)


def read_block_properties(db_path: str, block_id: str, branch: str = "main") -> List[BlockProperty]:
    """
    DEPRECATED: Legacy file-based function.
    Use DoltMySQLReader.read_block_properties() instead.
    """
    from infra_core.memory_system.legacy_file_dolt_access import (
        read_block_properties as legacy_func,
    )

    return legacy_func(db_path, block_id, branch)


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
