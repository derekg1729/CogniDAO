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
from typing import List, Optional, Dict, Any, Tuple
import json
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
    from infra_core.memory_system.dolt_mysql_base import DoltMySQLBase
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


class DoltMySQLReader(DoltMySQLBase):
    """Dolt reader that connects to remote Dolt SQL server via MySQL connector.

    Provides the same interface as the original dolt_reader functions but
    connects to a running Dolt SQL server instead of local file access.

    Uses autocommit=True connections optimized for read operations.
    """

    def _get_connection(self):
        """Get a new MySQL connection optimized for reading with autocommit=True."""
        try:
            conn = mysql.connector.connect(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
                charset="utf8mb4",
                autocommit=True,  # Optimized for read operations
                connection_timeout=10,
                use_unicode=True,
                raise_on_warnings=True,
            )
            return conn
        except mysql.connector.Error as e:
            raise Exception(f"Failed to connect to Dolt SQL server: {e}")

    def read_memory_blocks(self, branch: str = "main") -> List[MemoryBlock]:
        """Read all memory blocks from Dolt SQL server, returning MemoryBlock objects."""
        try:
            connection = self._get_connection()
            self._ensure_branch(connection, branch)

            query = """
            SELECT id, namespace_id, type, schema_version, text, state, visibility, block_version,
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
            SELECT id, namespace_id, type, schema_version, text, state, visibility, block_version,
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
            SELECT id, namespace_id, type, schema_version, text, state, visibility, block_version,
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

    def read_block_proofs(self, block_id: str, branch: str = "main") -> List[Dict[str, Any]]:
        """
        Read block operation proofs for a specific block from block_proofs table.

        Args:
            block_id: The ID of the block to get proofs for
            branch: The Dolt branch to read from

        Returns:
            List of dictionaries containing operation, commit_hash, timestamp info.
            Ordered newest first (most recent operation first).
        """
        try:
            connection = self._get_connection()
            self._ensure_branch(connection, branch)

            query = """
            SELECT block_id, commit_hash, operation, timestamp
            FROM block_proofs 
            WHERE block_id = %s
            ORDER BY timestamp DESC
            """

            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, (block_id,))
            rows = cursor.fetchall()
            cursor.close()
            connection.close()

            return rows

        except Error as e:
            logger.error(f"Failed to read block proofs for {block_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error reading block proofs for {block_id}: {e}")
            return []

    def read_latest_schema_version(self, node_type: str, branch: str = "main") -> Optional[int]:
        """
        Read the latest schema version for a given node type from node_schemas table.

        Args:
            node_type: The type of node/block (e.g., 'knowledge', 'task', 'project', 'doc')
            branch: The Dolt branch to read from

        Returns:
            The latest schema version as an integer, or None if no schema is found
        """
        try:
            connection = self._get_connection()
            self._ensure_branch(connection, branch)

            query = """
            SELECT MAX(schema_version) as latest_version
            FROM node_schemas 
            WHERE node_type = %s
            """

            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, (node_type,))
            result = cursor.fetchone()
            cursor.close()
            connection.close()

            if result and result.get("latest_version") is not None:
                return int(result["latest_version"])
            else:
                return None

        except Error as e:
            logger.error(f"Failed to read latest schema version for {node_type}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading schema version for {node_type}: {e}")
            return None

    def read_forward_links(
        self, block_id: str, relation: Optional[str] = None, branch: str = "main"
    ) -> List[Dict[str, Any]]:
        """
        Read outgoing links from a specific block from block_links table.

        Args:
            block_id: The ID of the source block
            relation: Optional relation type to filter by
            branch: The Dolt branch to read from

        Returns:
            List of dictionaries containing link information
        """
        try:
            connection = self._get_connection()
            self._ensure_branch(connection, branch)

            if relation:
                query = """
                SELECT from_block_id, to_block_id, relation, priority, created_at, updated_at, metadata
                FROM block_links 
                WHERE from_block_id = %s AND relation = %s
                ORDER BY priority DESC, created_at ASC
                """
                params = (block_id, relation)
            else:
                query = """
                SELECT from_block_id, to_block_id, relation, priority, created_at, updated_at, metadata
                FROM block_links 
                WHERE from_block_id = %s
                ORDER BY priority DESC, created_at ASC
                """
                params = (block_id,)

            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            connection.close()

            # Parse JSON metadata if present
            for row in rows:
                if row.get("metadata") and isinstance(row["metadata"], str):
                    try:
                        row["metadata"] = json.loads(row["metadata"])
                    except json.JSONDecodeError:
                        row["metadata"] = {}

            return rows

        except Error as e:
            logger.error(f"Failed to read forward links for {block_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error reading forward links for {block_id}: {e}")
            return []

    def read_backlinks(
        self, block_id: str, relation: Optional[str] = None, branch: str = "main"
    ) -> List[Dict[str, Any]]:
        """
        Read incoming links to a specific block from block_links table.

        Args:
            block_id: The ID of the target block
            relation: Optional relation type to filter by
            branch: The Dolt branch to read from

        Returns:
            List of dictionaries containing link information
        """
        try:
            connection = self._get_connection()
            self._ensure_branch(connection, branch)

            if relation:
                query = """
                SELECT from_block_id, to_block_id, relation, priority, created_at, updated_at, metadata
                FROM block_links 
                WHERE to_block_id = %s AND relation = %s
                ORDER BY priority DESC, created_at ASC
                """
                params = (block_id, relation)
            else:
                query = """
                SELECT from_block_id, to_block_id, relation, priority, created_at, updated_at, metadata
                FROM block_links 
                WHERE to_block_id = %s
                ORDER BY priority DESC, created_at ASC
                """
                params = (block_id,)

            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            connection.close()

            # Parse JSON metadata if present
            for row in rows:
                if row.get("metadata") and isinstance(row["metadata"], str):
                    try:
                        row["metadata"] = json.loads(row["metadata"])
                    except json.JSONDecodeError:
                        row["metadata"] = {}

            return rows

        except Error as e:
            logger.error(f"Failed to read backlinks for {block_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error reading backlinks for {block_id}: {e}")
            return []

    def read_work_items_core_view(self, limit: int = 5, branch: str = "main") -> list:
        """
        Read work items from the core view with limit.
        """
        connection = self._get_connection()
        try:
            self._ensure_branch(connection, branch)
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM work_items_core_view LIMIT %s", (limit,))
            results = cursor.fetchall()
            cursor.close()
            return results
        except Exception as e:
            logger.error(f"Failed to read work items core view: {e}")
            return []
        finally:
            connection.close()

    def list_branches(self) -> Tuple[List[Dict[str, Any]], str]:
        """
        List all Dolt branches with their information.

        Returns:
            Tuple of (branches_list, current_branch) where:
            - branches_list: List of dictionaries containing branch information
            - current_branch: Name of the currently active branch
        """
        # Use persistent connection if available, otherwise create new one
        if self._use_persistent and self._persistent_connection:
            connection = self._persistent_connection
            connection_is_persistent = True
        else:
            connection = self._get_connection()
            connection_is_persistent = False

        try:
            cursor = connection.cursor(dictionary=True)

            # Get current branch
            cursor.execute("SELECT active_branch() as current_branch")
            current_result = cursor.fetchone()
            current_branch = current_result["current_branch"] if current_result else "unknown"

            # Get all branches from dolt_branches system table
            cursor.execute("""
                SELECT 
                    name,
                    hash,
                    latest_committer,
                    latest_committer_email,
                    latest_commit_date,
                    latest_commit_message,
                    remote,
                    branch,
                    dirty
                FROM dolt_branches
                ORDER BY name
            """)

            branches_data = cursor.fetchall()

            # Convert to the expected format
            branches_list = []
            for branch_row in branches_data:
                branch_info = {
                    "name": branch_row["name"],
                    "hash": branch_row["hash"],
                    "latest_committer": branch_row["latest_committer"],
                    "latest_committer_email": branch_row["latest_committer_email"],
                    "latest_commit_date": branch_row["latest_commit_date"],
                    "latest_commit_message": branch_row["latest_commit_message"],
                    "remote": branch_row["remote"] or "",
                    "branch": branch_row["branch"] or "",
                    "dirty": bool(branch_row["dirty"]),
                }
                branches_list.append(branch_info)

            cursor.close()
            logger.info(
                f"Successfully listed {len(branches_list)} branches. Current branch: {current_branch}"
            )
            return branches_list, current_branch

        except Exception as e:
            error_msg = f"Failed to list branches: {e}"
            logger.error(error_msg, exc_info=True)
            return [], "unknown"
        finally:
            # Only close if it's not a persistent connection
            if not connection_is_persistent:
                connection.close()

    def get_diff_summary(self, from_revision: str, to_revision: str) -> List[dict]:
        """
        Gets a summary of differences between two revisions using DOLT_DIFF_SUMMARY.

        Args:
            from_revision: The starting revision (e.g., 'HEAD', 'main').
            to_revision: The ending revision (e.g., 'WORKING', 'STAGED').

        Returns:
            A list of dictionaries, where each dictionary represents a changed table.
        """
        # Use persistent connection if available, otherwise create a new one
        if self._use_persistent and self._persistent_connection:
            connection = self._persistent_connection
            connection_is_persistent = True
        else:
            connection = self._get_connection()
            connection_is_persistent = False

        try:
            cursor = connection.cursor(dictionary=True)

            query = "SELECT * FROM DOLT_DIFF_SUMMARY(%s, %s)"
            cursor.execute(query, (from_revision, to_revision))

            diff_summary = cursor.fetchall()

            cursor.close()
            logger.info(
                f"Successfully retrieved diff summary from {from_revision} to {to_revision}"
            )
            return diff_summary

        except Exception as e:
            logger.error(f"Failed to get diff summary: {e}", exc_info=True)
            raise
        finally:
            if not connection_is_persistent:
                connection.close()

    def get_diff_details(
        self, from_revision: str, to_revision: str, table_name: str = None
    ) -> List[dict]:
        """
        Gets detailed row-level differences using DOLT_DIFF table function.

        This is much simpler than the previous approach - just returns the raw DOLT_DIFF results.

        Args:
            from_revision: The starting revision (e.g., 'HEAD', 'main').
            to_revision: The ending revision (e.g., 'WORKING', 'STAGED').
            table_name: Specific table to diff (optional, if None gets all changed tables).

        Returns:
            A list of dictionaries with raw DOLT_DIFF results for all tables or specific table.
        """
        # Use persistent connection if available, otherwise create a new one
        if self._use_persistent and self._persistent_connection:
            connection = self._persistent_connection
            connection_is_persistent = True
        else:
            connection = self._get_connection()
            connection_is_persistent = False

        try:
            cursor = connection.cursor(dictionary=True)
            all_changes = []

            if table_name:
                # Get diff for specific table
                query = "SELECT * FROM DOLT_DIFF(%s, %s, %s)"
                cursor.execute(query, (from_revision, to_revision, table_name))
                changes = cursor.fetchall()
                all_changes.extend(changes)
            else:
                # Get list of changed tables first
                summary_query = (
                    "SELECT to_table_name FROM DOLT_DIFF_SUMMARY(%s, %s) WHERE data_change = 1"
                )
                cursor.execute(summary_query, (from_revision, to_revision))
                changed_tables = cursor.fetchall()

                # Get detailed diff for each changed table
                for table_info in changed_tables:
                    table_name = table_info["to_table_name"]
                    try:
                        detail_query = "SELECT * FROM DOLT_DIFF(%s, %s, %s)"
                        cursor.execute(detail_query, (from_revision, to_revision, table_name))
                        table_changes = cursor.fetchall()
                        # Add table_name to each change for context
                        for change in table_changes:
                            change["_table_name"] = table_name
                        all_changes.extend(table_changes)
                    except Exception as table_error:
                        logger.warning(f"Failed to get diff for table {table_name}: {table_error}")
                        continue

            cursor.close()
            logger.info(
                f"Successfully retrieved {len(all_changes)} detailed changes from {from_revision} to {to_revision}"
            )
            return all_changes

        except Exception as e:
            logger.error(f"Failed to get detailed diff: {e}", exc_info=True)
            return []
        finally:
            if not connection_is_persistent:
                connection.close()


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
    warnings.warn(
        "batch_read_block_properties() legacy function is deprecated. "
        "Use DoltMySQLReader.batch_read_block_properties() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Use DoltMySQLReader for MySQL-based access
    from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

    config = DoltConnectionConfig()
    reader = DoltMySQLReader(config)
    return reader.batch_read_block_properties(block_ids, branch)


def read_memory_blocks(db_path: str, branch: str = "main") -> List[MemoryBlock]:
    """
    DEPRECATED: Legacy file-based function.
    Use DoltMySQLReader.read_memory_blocks() instead.
    """
    warnings.warn(
        "read_memory_blocks() legacy function is deprecated. "
        "Use DoltMySQLReader.read_memory_blocks() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Use DoltMySQLReader for MySQL-based access
    from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

    config = DoltConnectionConfig()
    reader = DoltMySQLReader(config)
    return reader.read_memory_blocks(branch)


def read_memory_block(db_path: str, block_id: str, branch: str = "main") -> Optional[MemoryBlock]:
    """
    DEPRECATED: Legacy file-based function.
    Use DoltMySQLReader.read_memory_block() instead.
    """
    warnings.warn(
        "read_memory_block() legacy function is deprecated. "
        "Use DoltMySQLReader.read_memory_block() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Use DoltMySQLReader for MySQL-based access
    from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

    config = DoltConnectionConfig()
    reader = DoltMySQLReader(config)
    return reader.read_memory_block(block_id, branch)


def read_memory_blocks_by_tags(
    db_path: str, tags: List[str], match_all: bool = True, branch: str = "main"
) -> List[MemoryBlock]:
    """
    DEPRECATED: Legacy file-based function.
    Use DoltMySQLReader.read_memory_blocks_by_tags() instead.
    """
    warnings.warn(
        "read_memory_blocks_by_tags() legacy function is deprecated. "
        "Use DoltMySQLReader.read_memory_blocks_by_tags() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Use DoltMySQLReader for MySQL-based access
    from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

    config = DoltConnectionConfig()
    reader = DoltMySQLReader(config)
    return reader.read_memory_blocks_by_tags(tags, match_all, branch)


def read_memory_blocks_from_working_set(db_path: str) -> List[MemoryBlock]:
    """
    DEPRECATED: Legacy file-based function.
    Use DoltMySQLReader with appropriate branch instead.
    """
    warnings.warn(
        "read_memory_blocks_from_working_set() legacy function is deprecated. "
        "Use DoltMySQLReader.read_memory_blocks() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Use DoltMySQLReader for MySQL-based access (working set = current branch)
    from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

    config = DoltConnectionConfig()
    reader = DoltMySQLReader(config)
    return reader.read_memory_blocks("main")  # Working set approximated as main branch


def read_block_properties(db_path: str, block_id: str, branch: str = "main") -> List[BlockProperty]:
    """
    DEPRECATED: Legacy file-based function.
    Use DoltMySQLReader.read_block_properties() instead.
    """
    warnings.warn(
        "read_block_properties() legacy function is deprecated. "
        "Use DoltMySQLReader.read_block_properties() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Use DoltMySQLReader for MySQL-based access
    from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

    config = DoltConnectionConfig()
    reader = DoltMySQLReader(config)
    return reader.read_block_properties(block_id, branch)


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
