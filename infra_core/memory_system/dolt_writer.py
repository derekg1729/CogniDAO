"""
Contains functions for writing MemoryBlock objects to a Dolt database.

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
except ImportError as e:
    # Add more context to the error message
    raise ImportError(
        f"Could not import MemoryBlock/ConfidenceScore schemas from infra_core/memory_system. "
        f"Project root added to path: {project_root_dir}. Check structure. Error: {e}"
    )

# Setup standard Python logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


# --- Manual Escaping (Reinstated due to doltpy.cli limitation) ---
# WARNING: These functions are a workaround for the lack of parameterized query support
# in doltpy.cli.Dolt.sql() and carry SQL injection risks.


def _escape_sql_string(value: Optional[str]) -> str:
    """Basic escaping for SQL strings. WARNING: Incomplete security measure."""
    if value is None:
        return "NULL"
    # Replace single quotes with two single quotes
    escaped_value = value.replace("'", "''")
    # Basic attempt to escape backslashes as well
    escaped_value = escaped_value.replace("\\", "\\\\")
    return f"'{escaped_value}'"


def _format_sql_value(value: Optional[Any]) -> str:
    """Formats different Python types into SQL-compatible strings using manual escaping.
    WARNING: Insecure due to reliance on manual escaping.
    """
    if value is None:
        return "NULL"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, datetime):
        # Ensure datetime is formatted correctly for SQL (YYYY-MM-DD HH:MM:SS.ffffff)
        # Remove timezone info if present, as Dolt DATETIME might not handle it directly
        value_naive = value.replace(tzinfo=None)
        return f"'{value_naive.isoformat(sep=' ', timespec='microseconds')}'"
    elif isinstance(value, str):
        return _escape_sql_string(value)
    elif isinstance(value, (list, dict)):
        # Handle nested JSON structures
        def json_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif hasattr(obj, "model_dump"):
                return obj.model_dump()
            return str(obj)

        try:
            json_str = json.dumps(value, default=json_serializer)
            return _escape_sql_string(json_str)
        except (TypeError, ValueError) as e:
            logger.warning(f"Could not serialize value to JSON, attempting string conversion: {e}")
            # Fallback to string conversion with escaping if JSON fails
            return _escape_sql_string(str(value))
    else:
        # Fallback for other types, treat as string with escaping
        return _escape_sql_string(str(value))


# --- End Manual Escaping ---


def write_memory_block_to_dolt(
    block: MemoryBlock, db_path: str, auto_commit: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Writes a single MemoryBlock object to the specified Dolt database.
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
    query = ""  # Initialize query string

    try:
        repo = Dolt(db_path)
        logger.info(
            f"Attempting to write block {block.id} to Dolt DB at {db_path} using manual SQL formatting."
        )

        # Manually format values for SQL insertion using the helper function
        # Ensure all relevant columns are included and match the table schema
        values = {
            "id": _format_sql_value(block.id),
            "type": _format_sql_value(block.type),
            "text": _format_sql_value(block.text),
            "tags": _format_sql_value(block.tags if block.tags is not None else []),
            "metadata": _format_sql_value(block.metadata if block.metadata is not None else {}),
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
            "schema_version": _format_sql_value(block.schema_version)
            if hasattr(block, "schema_version") and block.schema_version is not None
            else "NULL",
        }

        # Construct the raw SQL query string
        # Include schema_version in the column list and values
        query = f"""
        REPLACE INTO memory_blocks (id, type, text, tags, metadata, source_file,
                                   source_uri, confidence, created_by, created_at,
                                   updated_at, embedding, schema_version)
        VALUES ({values["id"]}, {values["type"]}, {values["text"]}, {values["tags"]}, {values["metadata"]}, {values["source_file"]},
                {values["source_uri"]}, {values["confidence"]}, {values["created_by"]}, {values["created_at"]},
                {values["updated_at"]}, {values["embedding"]}, {values["schema_version"]});
        """

        logger.debug(f"Executing manually formatted SQL (WARNING: Risk of SQLi):\n{query}")

        # Execute the raw SQL query (no args parameter)
        repo.sql(query=query)
        write_msg = f"Successfully wrote/updated block {block.id} in Dolt working set (using manual formatting)."
        logger.info(write_msg)

        # Note: Links are now managed through the LinkManager and block_links table
        # They are no longer written as part of the MemoryBlock write operation

        if auto_commit:
            try:
                logger.info(f"Auto-committing changes for block {block.id}...")
                repo.add(["memory_blocks"])  # Be specific about the table

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
                    commit_msg = f"Write memory block {block.id}"
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
        # Log query only if needed for debugging sensitive info
        # logger.error(f"Failed SQL Query: {query}")
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
    Deletes a single MemoryBlock object from the specified Dolt database by ID.

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
    query = ""  # Initialize query string

    try:
        repo = Dolt(db_path)
        logger.info(
            f"Attempting to delete block {block_id} from Dolt DB at {db_path} using manual SQL formatting."
        )

        # Format the block_id safely for the SQL query
        safe_block_id = _escape_sql_string(block_id)

        # Delete from memory_blocks (will cascade to block_links due to FK constraint)
        query = f"DELETE FROM memory_blocks WHERE id = {safe_block_id};"
        logger.debug(f"Executing SQL delete query: {query}")
        repo.sql(query=query)
        logger.info(
            f"Successfully deleted block {block_id} from memory_blocks table (if it existed)."
        )

        # Explicitly delete from block_links table even though FK should cascade
        # This is a safety measure in case the FK constraint is not properly set up
        link_query = (
            f"DELETE FROM block_links WHERE from_id = {safe_block_id} OR to_id = {safe_block_id};"
        )
        logger.debug(f"Executing SQL delete query for links: {link_query}")
        try:
            repo.sql(query=link_query)
            logger.info(
                f"Successfully deleted links for block {block_id} from block_links table (if any existed)."
            )
        except Exception as link_e:
            # Don't fail the entire operation if link deletion fails
            logger.warning(f"Failed to explicitly delete links for block {block_id}: {link_e}")

        if auto_commit:
            try:
                logger.info(f"Auto-committing delete for block {block_id}...")
                repo.add(["memory_blocks", "block_links"])

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
                    commit_msg = f"Delete memory block {block_id}"
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
