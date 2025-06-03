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
    from infra_core.memory_system.dolt_mysql_base import DoltMySQLBase
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


class DoltMySQLWriter(DoltMySQLBase):
    """Dolt writer that connects to remote Dolt SQL server via MySQL connector.

    Provides write operations using parameterized queries for better security.
    Works with the same DoltConnectionConfig as DoltMySQLReader.
    """

    def _get_connection(self):
        """Get a new MySQL connection to the Dolt SQL server with transaction control."""
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
                json.dumps(block.tags) if block.tags is not None else json.dumps([]),
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
                            if prop.property_value_json is not None
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
                cursor.fetchall()  # Consume any results from DOLT_ADD
                cursor.execute("CALL DOLT_COMMIT('-m', %s)", (f"Write memory block {block.id}",))
                cursor.fetchall()  # Consume any results from DOLT_COMMIT

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
                cursor.fetchall()  # Consume any results from DOLT_ADD
                cursor.execute("CALL DOLT_COMMIT('-m', %s)", (f"Delete memory block {block_id}",))
                cursor.fetchall()  # Consume any results from DOLT_COMMIT

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
            self._ensure_branch(connection, "main")
            cursor = connection.cursor(dictionary=True)

            # Add specified tables or default ones
            if tables:
                # Build the DOLT_ADD call with proper argument placeholders
                placeholders = ", ".join(["%s"] * len(tables))
                cursor.execute(f"CALL DOLT_ADD({placeholders})", tuple(tables))
                cursor.fetchall()  # Consume any results from DOLT_ADD
            else:
                cursor.execute("CALL DOLT_ADD('memory_blocks', 'block_properties', 'block_links')")
                cursor.fetchall()  # Consume any results from DOLT_ADD

            # Commit changes
            cursor.execute("CALL DOLT_COMMIT('-m', %s)", (commit_msg,))
            cursor.fetchall()  # Consume any results from DOLT_COMMIT

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
        """
        Discard uncommitted changes in Dolt working set.

        Args:
            tables: List of table names to discard changes for. If None, discards all changes.

        Returns:
            True if discard was successful, False otherwise.
        """
        connection = self._get_connection()

        try:
            self._ensure_branch(connection, "main")
            cursor = connection.cursor()

            if tables:
                # Discard changes for specific tables
                for table in tables:
                    cursor.execute("CALL DOLT_RESET('--hard', %s)", (table,))
                    cursor.fetchall()  # Consume any results
            else:
                # Discard all changes
                cursor.execute("CALL DOLT_RESET('--hard')")
                cursor.fetchall()  # Consume any results

            cursor.close()
            logger.info("Successfully discarded Dolt working changes")
            return True

        except Exception as e:
            logger.error(f"Failed to discard Dolt changes: {e}", exc_info=True)
            return False
        finally:
            connection.close()

    def write_block_proof(
        self, block_id: str, operation: str, commit_hash: str, branch: str = "main"
    ) -> bool:
        """
        Write a block operation proof to the block_proofs table.

        Args:
            block_id: The ID of the block
            operation: The operation type ('create', 'update', 'delete')
            commit_hash: The Dolt commit hash for this operation
            branch: The Dolt branch to write to

        Returns:
            True if proof was stored successfully, False otherwise
        """
        connection = self._get_connection()

        try:
            self._ensure_branch(connection, branch)
            cursor = connection.cursor()

            # Insert proof record with current timestamp
            insert_query = """
            INSERT INTO block_proofs (block_id, commit_hash, operation, timestamp)
            VALUES (%s, %s, %s, NOW())
            """

            cursor.execute(insert_query, (block_id, commit_hash, operation))
            connection.commit()

            cursor.close()
            logger.info(
                f"Stored block proof: {operation} operation for block {block_id} with commit {commit_hash}"
            )
            return True

        except Exception as e:
            connection.rollback()
            logger.error(f"Failed to store block proof for {block_id}: {e}", exc_info=True)
            return False
        finally:
            connection.close()


# --- Backward Compatibility Stubs (DO NOT USE) ---


def write_memory_block_to_dolt(
    block: MemoryBlock, db_path: str, auto_commit: bool = False, preserve_nulls: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    DEPRECATED STUB: This function has been replaced by DoltMySQLWriter.write_memory_block().

    The old file-based API is no longer supported for security reasons.
    Use DoltMySQLWriter with a DoltConnectionConfig instead.
    """
    raise NotImplementedError(
        "write_memory_block_to_dolt() is deprecated. Use DoltMySQLWriter.write_memory_block() instead."
    )


def delete_memory_block_from_dolt(
    block_id: str, db_path: str, auto_commit: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    DEPRECATED STUB: This function has been replaced by DoltMySQLWriter.delete_memory_block().
    """
    raise NotImplementedError(
        "delete_memory_block_from_dolt() is deprecated. Use DoltMySQLWriter.delete_memory_block() instead."
    )


def commit_working_changes(
    db_path: str, commit_msg: str, tables: List[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    DEPRECATED STUB: This function has been replaced by DoltMySQLWriter.commit_changes().
    """
    raise NotImplementedError(
        "commit_working_changes() is deprecated. Use DoltMySQLWriter.commit_changes() instead."
    )


def discard_working_changes(db_path: str, tables: List[str] = None) -> bool:
    """
    DEPRECATED STUB: This function has been replaced by DoltMySQLWriter.discard_changes().
    """
    raise NotImplementedError(
        "discard_working_changes() is deprecated. Use DoltMySQLWriter.discard_changes() instead."
    )
