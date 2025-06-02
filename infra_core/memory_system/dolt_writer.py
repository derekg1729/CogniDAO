"""
Contains functions for writing MemoryBlock objects to a Dolt database.

This module provides secure MySQL connector-based write access to a running
Dolt SQL server, supporting branch switching and using parameterized queries
for security.

The DoltMySQLWriter class uses the same DoltConnectionConfig as the reader
for consistent configuration.

This version uses the Property-Schema Split approach, writing metadata as typed
properties to the block_properties table instead of JSON metadata column.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional, Tuple, List

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
    from infra_core.memory_system.property_mapper import PropertyMapper
    from infra_core.memory_system.dolt_reader import DoltConnectionConfig
except ImportError as e:
    # Add more context to the error message
    raise ImportError(
        f"Could not import required schemas or configs from infra_core/memory_system. "
        f"Project root added to path: {project_root_dir}. Check structure. Error: {e}"
    )

# Setup standard Python logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


class DoltMySQLWriter:
    """Dolt writer that connects to remote Dolt SQL server via MySQL connector.

    Provides write operations using parameterized queries for better security.
    Works with the same DoltConnectionConfig as DoltMySQLReader.
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
                autocommit=False,  # We want transaction control for writes
                connection_timeout=10,
                use_unicode=True,
                raise_on_warnings=True,
            )
            return conn
        except Error as e:
            raise Exception(f"Failed to connect to Dolt SQL server: {e}")

    def _ensure_branch(self, connection: mysql.connector.MySQLConnection, branch: str) -> None:
        """Ensure we're on the specified branch."""
        try:
            cursor = connection.cursor()
            cursor.execute("CALL DOLT_CHECKOUT(%s)", (branch,))
            # Consume any results
            cursor.fetchall()
            cursor.close()
        except Error as e:
            raise Exception(f"Failed to checkout branch '{branch}': {e}")

    def write_memory_block(
        self,
        block: MemoryBlock,
        branch: str = "main",
        auto_commit: bool = False,
        preserve_nulls: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """Write a memory block to the Dolt SQL server."""
        connection = self._get_connection()
        commit_hash = None

        try:
            self._ensure_branch(connection, branch)
            cursor = connection.cursor(dictionary=True)

            # Step 1: Write to memory_blocks table using REPLACE INTO for idempotency
            memory_blocks_query = """
            REPLACE INTO memory_blocks (
                id, type, schema_version, text, state, visibility, block_version,
                parent_id, has_children, tags, source_file, source_uri, confidence,
                created_by, created_at, updated_at, embedding
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """

            # Prepare values, handling JSON serialization
            values = (
                block.id,
                block.type,
                getattr(block, "schema_version", None),
                block.text,
                getattr(block, "state", "draft"),
                getattr(block, "visibility", "internal"),
                getattr(block, "block_version", 1),
                getattr(block, "parent_id", None),
                getattr(block, "has_children", False),
                json.dumps(block.tags) if block.tags else None,
                block.source_file,
                block.source_uri,
                json.dumps(block.confidence.model_dump()) if block.confidence else None,
                block.created_by,
                block.created_at,
                block.updated_at,
                json.dumps(block.embedding) if block.embedding else None,
            )

            cursor.execute(memory_blocks_query, values)

            # Step 2: Handle metadata properties using PropertyMapper
            if hasattr(block, "metadata") and block.metadata:
                # Decompose metadata into properties
                properties = PropertyMapper.decompose_metadata(
                    block_id=block.id, metadata_dict=block.metadata, preserve_nulls=preserve_nulls
                )

                # Clear existing properties for this block
                cursor.execute("DELETE FROM block_properties WHERE block_id = %s", (block.id,))

                # Insert new properties
                if properties:
                    property_query = """
                    INSERT INTO block_properties (
                        block_id, property_name, property_value_text, property_value_number,
                        property_value_json, property_type, is_computed, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """

                    for prop in properties:
                        property_values = (
                            prop.block_id,
                            prop.property_name,
                            prop.property_value_text,
                            prop.property_value_number,
                            json.dumps(prop.property_value_json)
                            if prop.property_value_json
                            else None,
                            prop.property_type,
                            prop.is_computed,
                            prop.created_at,
                            prop.updated_at,
                        )
                        cursor.execute(property_query, property_values)

            if auto_commit:
                # Use Dolt SQL functions to add and commit
                cursor.execute("CALL DOLT_ADD('memory_blocks', 'block_properties')")
                cursor.execute("CALL DOLT_COMMIT('-m', %s)", (f"Write memory block {block.id}",))

                # Get commit hash
                cursor.execute("SELECT DOLT_HASHOF_DB('HEAD') AS commit_hash")
                result = cursor.fetchone()
                if result:
                    commit_hash = result["commit_hash"]
            else:
                # Just commit the MySQL transaction, don't commit to Dolt
                connection.commit()

            cursor.close()
            logger.info(f"Successfully wrote block {block.id} via MySQL connection")
            return True, commit_hash

        except Exception as e:
            connection.rollback()
            logger.error(f"Failed to write block {block.id}: {e}", exc_info=True)
            return False, None
        finally:
            connection.close()

    def delete_memory_block(
        self, block_id: str, branch: str = "main", auto_commit: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """Delete a memory block from the Dolt SQL server."""
        connection = self._get_connection()
        commit_hash = None

        try:
            self._ensure_branch(connection, branch)
            cursor = connection.cursor(dictionary=True)

            # Delete from both tables
            cursor.execute("DELETE FROM block_properties WHERE block_id = %s", (block_id,))
            cursor.execute("DELETE FROM memory_blocks WHERE id = %s", (block_id,))

            if auto_commit:
                # Use Dolt SQL functions to add and commit
                cursor.execute("CALL DOLT_ADD('memory_blocks', 'block_properties')")
                cursor.execute("CALL DOLT_COMMIT('-m', %s)", (f"Delete memory block {block_id}",))

                # Get commit hash
                cursor.execute("SELECT DOLT_HASHOF_DB('HEAD') AS commit_hash")
                result = cursor.fetchone()
                if result:
                    commit_hash = result["commit_hash"]
            else:
                # Just commit the MySQL transaction, don't commit to Dolt
                connection.commit()

            cursor.close()
            logger.info(f"Successfully deleted block {block_id} via MySQL connection")
            return True, commit_hash

        except Exception as e:
            connection.rollback()
            logger.error(f"Failed to delete block {block_id}: {e}", exc_info=True)
            return False, None
        finally:
            connection.close()

    def commit_changes(
        self, commit_msg: str, tables: List[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """Commit working changes to Dolt via MySQL connection."""
        connection = self._get_connection()
        commit_hash = None

        try:
            cursor = connection.cursor(dictionary=True)

            # Add specified tables or default ones
            if tables:
                cursor.execute("CALL DOLT_ADD(%s)", (",".join(tables),))
            else:
                cursor.execute("CALL DOLT_ADD('memory_blocks', 'block_properties', 'block_links')")

            # Commit changes
            cursor.execute("CALL DOLT_COMMIT('-m', %s)", (commit_msg,))

            # Get commit hash
            cursor.execute("SELECT DOLT_HASHOF_DB('HEAD') AS commit_hash")
            result = cursor.fetchone()
            if result:
                commit_hash = result["commit_hash"]

            cursor.close()
            logger.info(f"Successfully committed changes: {commit_msg}")
            return True, commit_hash

        except Exception as e:
            logger.error(f"Failed to commit changes: {e}", exc_info=True)
            return False, None
        finally:
            connection.close()

    def discard_changes(self, tables: List[str] = None) -> bool:
        """Discard working changes in Dolt via MySQL connection."""
        connection = self._get_connection()

        try:
            cursor = connection.cursor()

            # Reset specified tables or all
            if tables:
                for table in tables:
                    cursor.execute("CALL DOLT_RESET('--hard', %s)", (table,))
            else:
                cursor.execute("CALL DOLT_RESET('--hard')")

            cursor.close()
            logger.info("Successfully discarded working changes")
            return True

        except Exception as e:
            logger.error(f"Failed to discard changes: {e}", exc_info=True)
            return False
        finally:
            connection.close()
