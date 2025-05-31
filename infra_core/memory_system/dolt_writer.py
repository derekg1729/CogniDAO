"""
Contains functions for writing MemoryBlock objects to a Dolt database.

This version uses the Property-Schema Split approach, writing metadata as typed
properties to the block_properties table instead of JSON metadata column.

!!! IMPORTANT SECURITY WARNING !!!
The current Dolt interaction relies on `doltpy.cli.Dolt.sql()`, which
DOES NOT SUPPORT parameterized queries (the `args` parameter).
Therefore, this module MUST manually format SQL strings using the
_escape_sql_string and _format_sql_value helper functions.

This approach carries an INHERENT RISK OF SQL INJECTION if the escaping
functions are flawed or if data contains unexpected characters not handled
by the basic escaping.

This is a necessary workaround due to library limitations. Prioritize migrating
to a safer database interaction method (e.g., using `doltpy.core` with a
standard DB-API connector like `mysql-connector-python` or `psycopg2` if Dolt
supports those interfaces, or a dedicated ORM) as soon as possible.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional, Tuple, Any, List
from datetime import datetime  # Import datetime directly

# Use the correct import path for doltpy v2+
from doltpy.cli import Dolt

# --- Path Setup --- START
# Must happen before importing local modules
script_dir = Path(__file__).parent
project_root_dir = script_dir.parent.parent.parent  # Navigate up THREE levels
if str(project_root_dir) not in sys.path:
    sys.path.insert(0, str(project_root_dir))
# --- Path Setup --- END

# Import schema using path relative to project root
try:
    from infra_core.memory_system.schemas.memory_block import MemoryBlock, ConfidenceScore
    from infra_core.memory_system.property_mapper import PropertyMapper
except ImportError as e:
    # Add more context to the error message
    raise ImportError(
        f"Could not import MemoryBlock/ConfidenceScore schemas or PropertyMapper from infra_core/memory_system. "
        f"Project root added to path: {project_root_dir}. Check structure. Error: {e}"
    )

# Setup standard Python logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# --- Manual Escaping ---
# WARNING: Due to lack of parameterized query support in doltpy.cli.Dolt.sql(),
# we must manually escape values. This is inherently risky.


def _escape_sql_string(value: Optional[str]) -> str:
    """
    Manually escape a string for SQL inclusion by wrapping in single quotes and escaping internal quotes.

    WARNING: This is NOT as robust as parameterized queries and carries SQL injection risks.

    Args:
        value: The string value to escape.

    Returns:
        A single-quoted, escaped string suitable for SQL inclusion.
    """
    if value is None:
        return "NULL"

    # CR-05 fix: Block control characters to prevent injection attacks
    # Check for dangerous control characters that could be used in attacks
    import re

    if re.search(r"[\x00\x08\x0a\x0d\x09\x1a]", value):
        raise ValueError(
            f"String contains dangerous control characters (null, backspace, newline, "
            f"carriage return, tab, or substitute): {repr(value)}"
        )

    # Escape single quotes by doubling them (SQL standard)
    escaped_value = value.replace("'", "''")
    return f"'{escaped_value}'"


def _format_sql_value(value: Optional[Any]) -> str:
    """
    Formats a Python value for safe inclusion in a SQL query string.

    WARNING: This is NOT as robust as parameterized queries and carries SQL injection risks.

    Args:
        value: The value to format for SQL.

    Returns:
        A string representation suitable for insertion into a SQL query.
    """
    if value is None:
        return "NULL"
    elif isinstance(value, str):
        return _escape_sql_string(value)
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, bool):
        return "1" if value else "0"
    elif isinstance(value, (list, dict)):
        # Serialize to JSON string and then escape
        def json_serializer(obj):
            """Handle non-serializable objects like datetime."""
            if isinstance(obj, datetime):
                return obj.isoformat()
            # Add other type handlers as needed
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        json_str = json.dumps(value, default=json_serializer, ensure_ascii=True)

        # CR-03 fix: Check JSON length to avoid silent truncation
        # MySQL max_packet_size is typically 1MB (1048576 bytes), but we use a conservative limit
        MAX_JSON_LENGTH = 1048576  # 1MB
        if len(json_str) > MAX_JSON_LENGTH:
            logger.warning(
                f"JSON value exceeds {MAX_JSON_LENGTH} bytes ({len(json_str)} bytes). "
                f"This may hit Dolt/MySQL JSON length limits. Consider using property_value_text fallback."
            )
            # For now, we'll still try to insert it, but log the warning
            # In the future, PropertyMapper could automatically use property_value_text for large values

        return _escape_sql_string(json_str)
    elif isinstance(value, datetime):
        # Format datetime as MySQL-compatible string
        return _escape_sql_string(value.strftime("%Y-%m-%d %H:%M:%S"))
    else:
        # Fallback: convert to string and escape
        return _escape_sql_string(str(value))


# --- End Manual Escaping ---


def write_memory_block_to_dolt(
    block: MemoryBlock, db_path: str, auto_commit: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Writes a single MemoryBlock object to the specified Dolt database using the Property-Schema Split approach.
    Uses PropertyMapper to decompose metadata into typed properties in the block_properties table.
    Uses REPLACE INTO for idempotency.

    WARNING: This function uses manual SQL string formatting due to limitations
    in doltpy.cli.Dolt.sql() (lack of parameterized query support).
    This carries an inherent SQL injection risk.

    Args:
        block: The MemoryBlock object to write.
        db_path: Path to the Dolt database directory.
        auto_commit: If True, automatically runs `dolt add` and `dolt commit` after writing.
                    If False, the changes are only in the working set and need to be committed later.

    Returns:
        Tuple[bool, Optional[str]]: A tuple containing:
            - bool: True if the write was successful, False otherwise.
            - Optional[str]: The Dolt commit hash if auto_commit was True and successful, else None.
    """
    commit_hash: Optional[str] = None
    repo: Optional[Dolt] = None
    memory_blocks_query = ""

    try:
        repo = Dolt(db_path)
        logger.info(
            f"Attempting to write block {block.id} to Dolt DB at {db_path} using Property-Schema Split approach."
        )

        # Step 1: Decompose metadata into properties using PropertyMapper
        try:
            # Use the actual metadata from the block for Property-Schema Split approach
            metadata_dict = (
                block.metadata if hasattr(block, "metadata") and block.metadata is not None else {}
            )

            properties = PropertyMapper.decompose_metadata(
                block_id=block.id,
                metadata_dict=metadata_dict,
            )
            logger.debug(
                f"Decomposed metadata into {len(properties)} properties for block {block.id}"
            )
        except Exception as prop_e:
            logger.error(
                f"Failed to decompose metadata for block {block.id}: {prop_e}", exc_info=True
            )
            return False, None

        # Step 2: Write to memory_blocks table (NO metadata column - Property-Schema Split)
        # Manually format values for SQL insertion using the helper function
        values = {
            "id": _format_sql_value(block.id),
            "type": _format_sql_value(block.type),
            "schema_version": _format_sql_value(block.schema_version)
            if hasattr(block, "schema_version") and block.schema_version is not None
            else "NULL",
            "text": _format_sql_value(block.text),
            "state": _format_sql_value(getattr(block, "state", "draft")),
            "visibility": _format_sql_value(getattr(block, "visibility", "internal")),
            "block_version": _format_sql_value(getattr(block, "block_version", 1)),
            "parent_id": _format_sql_value(getattr(block, "parent_id", None)),
            "has_children": _format_sql_value(getattr(block, "has_children", False)),
            "tags": _format_sql_value(block.tags if block.tags is not None else []),
            "source_file": _format_sql_value(block.source_file),
            "source_uri": _format_sql_value(block.source_uri),
            "confidence": _format_sql_value(block.confidence.model_dump())
            if block.confidence
            else "NULL",
            "created_by": _format_sql_value(block.created_by),
            "created_at": _format_sql_value(block.created_at),
            "updated_at": _format_sql_value(block.updated_at),
            "embedding": _format_sql_value(block.embedding)
            if block.embedding is not None
            else "NULL",
        }

        # Construct the memory_blocks SQL query (NO metadata column)
        memory_blocks_query = f"""
        REPLACE INTO memory_blocks (id, type, schema_version, text, state, visibility, 
                                   block_version, parent_id, has_children, tags, 
                                   source_file, source_uri, confidence, created_by, created_at,
                                   updated_at, embedding)
        VALUES ({values["id"]}, {values["type"]}, {values["schema_version"]}, {values["text"]}, 
                {values["state"]}, {values["visibility"]}, {values["block_version"]}, 
                {values["parent_id"]}, {values["has_children"]}, {values["tags"]}, 
                {values["source_file"]}, {values["source_uri"]}, {values["confidence"]}, {values["created_by"]}, 
                {values["created_at"]}, {values["updated_at"]}, {values["embedding"]});
        """

        logger.debug(f"Executing memory_blocks SQL (WARNING: Risk of SQLi):\n{memory_blocks_query}")

        # Execute the memory_blocks query
        repo.sql(query=memory_blocks_query)
        logger.info(
            f"Successfully wrote block {block.id} to memory_blocks table (Property-Schema Split)."
        )

        # Step 3: Delete existing properties for this block to ensure clean state
        # This ensures REPLACE-like behavior for properties
        delete_properties_query = (
            f"DELETE FROM block_properties WHERE block_id = {_format_sql_value(block.id)};"
        )
        logger.debug(f"Executing property cleanup SQL: {delete_properties_query}")
        repo.sql(query=delete_properties_query)
        logger.debug(f"Cleaned up existing properties for block {block.id}")

        # Step 4: Write properties to block_properties table
        if properties:
            # Build batch INSERT for all properties
            property_values = []
            for prop in properties:
                prop_value = {
                    "block_id": _format_sql_value(prop.block_id),
                    "property_name": _format_sql_value(prop.property_name),
                    "property_value_text": _format_sql_value(prop.property_value_text),
                    "property_value_number": _format_sql_value(prop.property_value_number),
                    "property_value_json": _format_sql_value(prop.property_value_json),
                    "property_type": _format_sql_value(prop.property_type),
                    "is_computed": _format_sql_value(prop.is_computed),
                    "created_at": _format_sql_value(prop.created_at),
                    "updated_at": _format_sql_value(prop.updated_at),
                }

                value_tuple = f"""({prop_value["block_id"]}, {prop_value["property_name"]}, 
                                   {prop_value["property_value_text"]}, {prop_value["property_value_number"]}, 
                                   {prop_value["property_value_json"]}, {prop_value["property_type"]}, 
                                   {prop_value["is_computed"]}, {prop_value["created_at"]}, 
                                   {prop_value["updated_at"]})"""
                property_values.append(value_tuple)

            # Create batch INSERT statement
            properties_query = f"""
            INSERT INTO block_properties (block_id, property_name, property_value_text, 
                                        property_value_number, property_value_json, property_type, 
                                        is_computed, created_at, updated_at)
            VALUES {", ".join(property_values)};
            """

            logger.debug(
                f"Executing properties batch INSERT SQL (WARNING: Risk of SQLi):\n{properties_query}"
            )
            repo.sql(query=properties_query)
            logger.info(
                f"Successfully wrote {len(properties)} properties for block {block.id} to block_properties table."
            )
        else:
            logger.info(f"No properties to write for block {block.id} (empty metadata)")

        # Note: Links are now managed through the LinkManager and block_links table
        # They are no longer written as part of the MemoryBlock write operation

        if auto_commit:
            try:
                logger.info(f"Auto-committing changes for block {block.id}...")
                repo.add(["memory_blocks", "block_properties"])  # Add both tables

                # Check if there are changes that need to be committed
                status = repo.status()
                is_clean = status.is_clean and not status.staged_tables

                if is_clean:
                    logger.info("No changes staged for commit.")
                    # Get current commit hash if working set is clean
                    try:
                        result = repo.sql(
                            query="SELECT DOLT_HASHOF_DB('HEAD') AS commit_hash",
                            result_format="json",
                        )
                        if (
                            result
                            and "rows" in result
                            and len(result["rows"]) > 0
                            and "commit_hash" in result["rows"][0]
                        ):
                            commit_hash = result["rows"][0]["commit_hash"]
                            logger.info(f"Working set clean. Current HEAD hash: {commit_hash}")
                        else:
                            logger.warning(
                                "Could not parse commit hash from DOLT_HASHOF_DB('HEAD') query result."
                            )
                            commit_hash = None
                    except Exception as hash_e:
                        logger.error(
                            f"Error retrieving commit hash using DOLT_HASHOF_DB('HEAD'): {hash_e}"
                        )
                        commit_hash = None
                else:
                    # Changes need to be committed
                    commit_msg = f"Write memory block {block.id} with properties"
                    repo.commit(commit_msg)

                    # Get the commit hash after successful commit
                    try:
                        result = repo.sql(
                            query="SELECT DOLT_HASHOF_DB('HEAD') AS commit_hash",
                            result_format="json",
                        )
                        if (
                            result
                            and "rows" in result
                            and len(result["rows"]) > 0
                            and "commit_hash" in result["rows"][0]
                        ):
                            commit_hash = result["rows"][0]["commit_hash"]
                            logger.info(f"Committed changes. Hash: {commit_hash}")
                        else:
                            logger.warning(
                                "Could not parse commit hash from DOLT_HASHOF_DB('HEAD') query result after commit."
                            )
                            commit_hash = None
                    except Exception as hash_e:
                        logger.error(
                            f"Error retrieving commit hash using DOLT_HASHOF_DB('HEAD') after commit: {hash_e}"
                        )
                        commit_hash = None
            except Exception as commit_e:
                logger.error(
                    f"Failed to auto-commit changes for block {block.id}: {commit_e}", exc_info=True
                )
                # Return True for write success, but None for commit hash
                return True, None
        else:
            # If auto_commit is False, log that changes are only in the working set
            logger.info(
                f"Block {block.id} written to working set only (auto_commit=False). Changes need to be committed separately."
            )

        return True, commit_hash

    except Exception as e:
        logger.error(f"Failed to write block {block.id} to Dolt: {e}", exc_info=True)
        # Log queries only if needed for debugging sensitive info
        # logger.error(f"Failed memory_blocks SQL Query: {memory_blocks_query}")
        return False, None  # Return False for success, None for hash on error


def discard_working_changes(db_path: str, tables: List[str] = None) -> bool:
    """
    Discards uncommitted changes in the Dolt working set. Used for rollback when operations
    need to be atomic (e.g., when LlamaIndex operations fail but Dolt writes succeeded).

    Args:
        db_path: Path to the Dolt database directory.
        tables: Optional list of specific tables to reset. If None, all tables are reset.

    Returns:
        bool: True if changes were successfully discarded, False otherwise.
    """
    try:
        repo = Dolt(db_path)
        logger.info(f"Discarding uncommitted changes in Dolt working set at {db_path}")

        if tables:
            # Reset specific tables
            for table in tables:
                try:
                    # This uses the dolt checkout command to restore the table from HEAD
                    repo.checkout(["HEAD", "--", table])
                    logger.info(f"Successfully reset table '{table}' to HEAD")
                except Exception as table_e:
                    logger.error(f"Failed to reset table '{table}': {table_e}")
                    return False
        else:
            # Reset all changes in the working directory
            try:
                repo.checkout(["HEAD", "--", "."])
                logger.info("Successfully reset all tables to HEAD")
            except Exception as e:
                logger.error(f"Failed to reset all tables: {e}")
                return False

        return True
    except Exception as e:
        logger.error(f"Failed to discard working changes: {e}", exc_info=True)
        return False


def commit_working_changes(
    db_path: str, commit_msg: str, tables: List[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Commits uncommitted changes in the Dolt working set. Used for explicit commit
    after successful operations when auto_commit=False was used.

    Args:
        db_path: Path to the Dolt database directory.
        commit_msg: The commit message to use.
        tables: Optional list of specific tables to commit. If None, all staged changes are committed.

    Returns:
        Tuple[bool, Optional[str]]: A tuple containing:
            - bool: True if commit was successful, False otherwise.
            - Optional[str]: The Dolt commit hash if successful, else None.
    """
    commit_hash = None
    try:
        repo = Dolt(db_path)
        logger.info(f"Committing changes in Dolt working set at {db_path}")

        # Add tables to staging
        if tables:
            repo.add(tables)
        else:
            repo.add(["."])  # Add all changes

        # Check if there are changes to commit
        status = repo.status()
        if status.is_clean and not status.staged_tables:
            logger.info("No changes to commit.")
            # Get current commit hash
            try:
                result = repo.sql(
                    query="SELECT DOLT_HASHOF_DB('HEAD') AS commit_hash", result_format="json"
                )
                if (
                    result
                    and "rows" in result
                    and len(result["rows"]) > 0
                    and "commit_hash" in result["rows"][0]
                ):
                    commit_hash = result["rows"][0]["commit_hash"]
                    logger.info(f"Working set clean. Current HEAD hash: {commit_hash}")
                    return True, commit_hash
                else:
                    logger.warning(
                        "Could not parse commit hash from DOLT_HASHOF_DB('HEAD') query result."
                    )
                    return True, None
            except Exception as hash_e:
                logger.error(f"Error retrieving commit hash using DOLT_HASHOF_DB('HEAD'): {hash_e}")
                return True, None

        # Commit the changes
        repo.commit(commit_msg)

        # Get the commit hash
        try:
            result = repo.sql(
                query="SELECT DOLT_HASHOF_DB('HEAD') AS commit_hash", result_format="json"
            )
            if (
                result
                and "rows" in result
                and len(result["rows"]) > 0
                and "commit_hash" in result["rows"][0]
            ):
                commit_hash = result["rows"][0]["commit_hash"]
                logger.info(f"Successfully committed changes. Hash: {commit_hash}")
                return True, commit_hash
            else:
                logger.warning(
                    "Could not parse commit hash from DOLT_HASHOF_DB('HEAD') query result after commit."
                )
                return True, None
        except Exception as hash_e:
            logger.error(
                f"Error retrieving commit hash using DOLT_HASHOF_DB('HEAD') after commit: {hash_e}"
            )
            return True, None

    except Exception as e:
        logger.error(f"Failed to commit working changes: {e}", exc_info=True)
        return False, None


def delete_memory_block_from_dolt(
    block_id: str, db_path: str, auto_commit: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Deletes a single MemoryBlock object from the specified Dolt database by ID using Property-Schema Split approach.
    Deletes from both memory_blocks and block_properties tables.

    WARNING: This function uses manual SQL string formatting for the WHERE clause
    due to limitations in doltpy.cli.Dolt.sql() (lack of parameterized query support).
    This carries an inherent SQL injection risk if block_id is ever sourced
    from untrusted input without separate, robust validation.

    Args:
        block_id: The ID of the MemoryBlock to delete.
        db_path: Path to the Dolt database directory.
        auto_commit: If True, automatically runs `dolt add` and `dolt commit` after deleting.
                    If False, the changes are only in the working set and need to be committed later.

    Returns:
        Tuple[bool, Optional[str]]: A tuple containing:
            - bool: True if the delete was successful, False otherwise.
            - Optional[str]: The Dolt commit hash if auto_commit was True and successful, else None.
    """
    commit_hash: Optional[str] = None
    repo: Optional[Dolt] = None
    memory_blocks_query = ""
    properties_query = ""
    links_query = ""

    try:
        repo = Dolt(db_path)
        logger.info(
            f"Attempting to delete block {block_id} from Dolt DB at {db_path} using Property-Schema Split approach."
        )

        # Format the block_id safely for the SQL query
        safe_block_id = _escape_sql_string(block_id)

        # Step 1: Delete from block_properties table first (no FK constraints to worry about)
        properties_query = f"DELETE FROM block_properties WHERE block_id = {safe_block_id};"
        logger.debug(f"Executing SQL delete query for properties: {properties_query}")
        repo.sql(query=properties_query)
        logger.info(
            f"Successfully deleted properties for block {block_id} from block_properties table (if any existed)."
        )

        # Step 2: Delete from memory_blocks (will cascade to block_links due to FK constraint if present)
        memory_blocks_query = f"DELETE FROM memory_blocks WHERE id = {safe_block_id};"
        logger.debug(f"Executing SQL delete query for memory_blocks: {memory_blocks_query}")
        repo.sql(query=memory_blocks_query)
        logger.info(
            f"Successfully deleted block {block_id} from memory_blocks table (if it existed)."
        )

        # Step 3: Explicitly delete from block_links table even though FK should cascade
        # This is a safety measure in case the FK constraint is not properly set up
        links_query = (
            f"DELETE FROM block_links WHERE from_id = {safe_block_id} OR to_id = {safe_block_id};"
        )
        logger.debug(f"Executing SQL delete query for links: {links_query}")
        try:
            repo.sql(query=links_query)
            logger.info(
                f"Successfully deleted links for block {block_id} from block_links table (if any existed)."
            )
        except Exception as link_e:
            # Don't fail the entire operation if link deletion fails
            logger.warning(f"Failed to explicitly delete links for block {block_id}: {link_e}")

        if auto_commit:
            try:
                logger.info(f"Auto-committing delete for block {block_id}...")
                repo.add(
                    ["memory_blocks", "block_properties", "block_links"]
                )  # Add all relevant tables

                # Check if there are changes that need to be committed
                status = repo.status()
                is_clean = status.is_clean and not status.staged_tables

                if is_clean:
                    logger.info("No changes staged for commit (block may not have existed).")
                    # Get current commit hash if working set is clean
                    try:
                        result = repo.sql(
                            query="SELECT DOLT_HASHOF_DB('HEAD') AS commit_hash",
                            result_format="json",
                        )
                        if (
                            result
                            and "rows" in result
                            and len(result["rows"]) > 0
                            and "commit_hash" in result["rows"][0]
                        ):
                            commit_hash = result["rows"][0]["commit_hash"]
                            logger.info(f"Working set clean. Current HEAD hash: {commit_hash}")
                        else:
                            logger.warning("Could not parse commit hash")
                            commit_hash = None
                    except Exception as hash_e:
                        logger.error(f"Error retrieving commit hash: {hash_e}")
                        commit_hash = None
                else:
                    # Changes need to be committed
                    commit_msg = f"Delete memory block {block_id} and properties"
                    repo.commit(commit_msg)

                    # Get the commit hash after successful commit
                    try:
                        result = repo.sql(
                            query="SELECT DOLT_HASHOF_DB('HEAD') AS commit_hash",
                            result_format="json",
                        )
                        if (
                            result
                            and "rows" in result
                            and len(result["rows"]) > 0
                            and "commit_hash" in result["rows"][0]
                        ):
                            commit_hash = result["rows"][0]["commit_hash"]
                            logger.info(f"Committed changes. Hash: {commit_hash}")
                        else:
                            logger.warning("Could not parse commit hash after commit.")
                            commit_hash = None
                    except Exception as hash_e:
                        logger.error(f"Error retrieving commit hash after commit: {hash_e}")
                        commit_hash = None
            except Exception as commit_e:
                logger.error(
                    f"Failed to auto-commit delete for block {block_id}: {commit_e}", exc_info=True
                )
                # Return True for delete success, but None for commit hash
                return True, None
        else:
            # If auto_commit is False, log that changes are only in the working set
            logger.info(
                f"Block {block_id} deleted from working set only (auto_commit=False). Changes need to be committed separately."
            )

        return True, commit_hash

    except Exception as e:
        logger.error(f"Failed to delete block {block_id} from Dolt: {e}", exc_info=True)
        # Log queries only if needed for debugging sensitive info
        # logger.error(f"Failed memory_blocks query: {memory_blocks_query}")
        # logger.error(f"Failed properties query: {properties_query}")
        # logger.error(f"Failed links query: {links_query}")
        return False, None  # Return False for success, None for hash on error


# Example Usage (can be run as a script for testing)
if __name__ == "__main__":
    # Example usage remains the same, but now uses the reverted (less secure) writer
    logger.info("Running Dolt writer example (using manual SQL formatting)...")

    # Define the path to your experimental Dolt database
    dolt_db_dir = project_root_dir / "experiments" / "dolt_data" / "memory_db"

    if not dolt_db_dir.exists() or not (dolt_db_dir / ".dolt").exists():
        logger.error(f"Dolt database not found at {dolt_db_dir}. Please run Task 1.2 setup.")
    else:
        logger.info(f"Using Dolt DB at: {dolt_db_dir}")

        # Create a fun sample MemoryBlock
        test_block = MemoryBlock(
            id="hello-dolt-003",  # Yet another ID
            type="knowledge",
            text="Writing with manual escaping (necessary evil?). Watch out for quotes: ' and double quotes: \"",
            tags=["dolt", "manual-escape", "warning"],
            metadata={"test_run": datetime.now().isoformat(), "escaped": True},
            links=[],
            confidence=ConfidenceScore(ai=0.5),
        )

        # Write the block with auto-commit enabled
        success, final_hash = write_memory_block_to_dolt(
            block=test_block, db_path=str(dolt_db_dir), auto_commit=True
        )

        if success:
            logger.info(
                "MemoryBlock write successful (auto-commit attempted). Check data carefully."
            )
            if final_hash:
                logger.info(f"Dolt Commit Hash: {final_hash}")
            else:
                logger.warning("Commit hash not retrieved.")

            logger.info("Verify using:")
            logger.info(f"  cd {dolt_db_dir}")
            logger.info("  dolt log -n 1")  # Show latest log entry
            logger.info(f"  dolt sql -q \"SELECT * FROM memory_blocks WHERE id='{test_block.id}'\"")
        else:
            logger.error("Failed to write example block.")
