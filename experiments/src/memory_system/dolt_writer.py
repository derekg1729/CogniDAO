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
from typing import Optional, Tuple, Any
import datetime # Import datetime for type checking

# Use the correct import path for doltpy v2+
from doltpy.cli import Dolt

# --- Path Setup --- START
# Must happen before importing local modules
script_dir = Path(__file__).parent
project_root_dir = script_dir.parent.parent.parent # Navigate up THREE levels
if str(project_root_dir) not in sys.path:
    sys.path.insert(0, str(project_root_dir))
# --- Path Setup --- END

# Import schema using path relative to project root
try:
    from experiments.src.memory_system.schemas.memory_block import MemoryBlock, ConfidenceScore
except ImportError as e:
    # Add more context to the error message
    raise ImportError(
        f"Could not import MemoryBlock/ConfidenceScore schemas from experiments/src. "
        f"Project root added to path: {project_root_dir}. Check structure. Error: {e}"
    )

# Setup standard Python logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


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
    elif isinstance(value, datetime.datetime):
        # Ensure datetime is formatted correctly for SQL (YYYY-MM-DD HH:MM:SS.ffffff)
        # Remove timezone info if present, as Dolt DATETIME might not handle it directly
        value_naive = value.replace(tzinfo=None)
        return f"'{value_naive.isoformat(sep=' ', timespec='microseconds')}'"
    elif isinstance(value, str):
        return _escape_sql_string(value)
    elif isinstance(value, (list, dict)):
        # Assume lists/dicts are intended for JSON columns
        try:
            json_str = json.dumps(value)
            return _escape_sql_string(json_str)
        except TypeError as e:
            logger.warning(f"Could not serialize value to JSON, attempting string conversion: {e}")
            # Fallback to string conversion with escaping if JSON fails
            return _escape_sql_string(str(value))
    else:
        # Fallback for other types, treat as string with escaping
        return _escape_sql_string(str(value))
# --- End Manual Escaping ---


def write_memory_block_to_dolt(block: MemoryBlock, db_path: str, auto_commit: bool = False) -> Tuple[bool, Optional[str]]:
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

    Returns:
        Tuple[bool, Optional[str]]: A tuple containing:
            - bool: True if the write was successful, False otherwise.
            - Optional[str]: The Dolt commit hash if auto_commit was True and successful, else None.
    """
    commit_hash: Optional[str] = None
    repo: Optional[Dolt] = None
    query = "" # Initialize query string

    try:
        repo = Dolt(db_path)
        logger.info(f"Attempting to write block {block.id} to Dolt DB at {db_path} using manual SQL formatting.")

        # Manually format values for SQL insertion using the helper function
        # Ensure all relevant columns are included and match the table schema
        sql_values = {
            "id": _format_sql_value(block.id),
            "type": _format_sql_value(block.type),
            "text": _format_sql_value(block.text),
            "tags": _format_sql_value(block.tags) if block.tags else "NULL",
            "metadata": _format_sql_value(block.metadata) if block.metadata else "NULL",
            "links": _format_sql_value([link.model_dump() for link in block.links]) if block.links else "NULL",
            "source_file": _format_sql_value(block.source_file),
            "source_uri": _format_sql_value(block.source_uri),
            "confidence": _format_sql_value(block.confidence.model_dump()) if block.confidence else "NULL",
            "created_by": _format_sql_value(block.created_by),
            "created_at": _format_sql_value(block.created_at),
            "updated_at": _format_sql_value(block.updated_at),
            "embedding": _format_sql_value(block.embedding) if block.embedding is not None else "NULL",
            # Add schema_version if needed and present in the table/block object
            # "schema_version": _format_sql_value(block.schema_version) if hasattr(block, 'schema_version') else "NULL"
        }

        # Construct the raw SQL query string
        # Adjust columns based on the actual table schema
        query = f"""
        REPLACE INTO memory_blocks (id, type, text, tags, metadata, links, source_file,
                                   source_uri, confidence, created_by, created_at,
                                   updated_at, embedding)
        VALUES ({sql_values['id']}, {sql_values['type']}, {sql_values['text']}, {sql_values['tags']}, {sql_values['metadata']}, {sql_values['links']}, {sql_values['source_file']},
                {sql_values['source_uri']}, {sql_values['confidence']}, {sql_values['created_by']}, {sql_values['created_at']},
                {sql_values['updated_at']}, {sql_values['embedding']});
        """
        # Example if schema_version is included:
        # query = f"""
        # REPLACE INTO memory_blocks (id, type, text, tags, metadata, links, source_file,
        #                            source_uri, confidence, created_by, created_at,
        #                            updated_at, embedding, schema_version)
        # VALUES ({sql_values['id']}, {sql_values['type']}, {sql_values['text']}, {sql_values['tags']}, {sql_values['metadata']}, {sql_values['links']}, {sql_values['source_file']},
        #         {sql_values['source_uri']}, {sql_values['confidence']}, {sql_values['created_by']}, {sql_values['created_at']},
        #         {sql_values['updated_at']}, {sql_values['embedding']}, {sql_values['schema_version']});
        # """

        logger.debug(f"Executing manually formatted SQL (WARNING: Risk of SQLi):\n{query}")

        # Execute the raw SQL query (no args parameter)
        repo.sql(query=query)
        write_msg = f"Successfully wrote/updated block {block.id} in Dolt working set (using manual formatting)."
        logger.info(write_msg)
        
        # Write links to block_links table - ensure table exists first
        try:
            repo.sql(query="CREATE TABLE IF NOT EXISTS block_links (from_id VARCHAR(255) NOT NULL, to_id VARCHAR(255) NOT NULL, relation VARCHAR(255) NOT NULL, PRIMARY KEY (from_id, to_id, relation), FOREIGN KEY (from_id) REFERENCES memory_blocks(id) ON DELETE CASCADE, FOREIGN KEY (to_id) REFERENCES memory_blocks(id) ON DELETE CASCADE);")
            # Now write the links
            for link in block.links:
                # Only insert links where target exists (to avoid foreign key constraint errors)
                check_query = f"SELECT 1 FROM memory_blocks WHERE id = {_format_sql_value(link.to_id)};"
                check_result = repo.sql(query=check_query, result_format='json')
                if check_result and 'rows' in check_result and check_result['rows']:
                    link_query = f"REPLACE INTO block_links (from_id, to_id, relation) VALUES ({_format_sql_value(block.id)}, {_format_sql_value(link.to_id)}, {_format_sql_value(link.relation)});"
                    repo.sql(query=link_query)
        except Exception as e:
            logger.warning(f"Failed to write links for block {block.id}: {e}")
        
        if auto_commit:
            # Commit logic remains the same as before
            try:
                logger.info(f"Auto-committing changes for block {block.id}...")
                repo.add(['memory_blocks', 'block_links']) # Be specific about both tables
                status = repo.status()
                # Correct check for clean status based on original working code
                if status.is_clean and not status.staged_tables:
                    logger.info("No changes staged for commit.")
                    try:
                        # Use correct function DOLT_HASHOF_DB('HEAD') to get current commit hash
                        result = repo.sql(query="SELECT DOLT_HASHOF_DB('HEAD') AS commit_hash", result_format='json')
                        if result and 'rows' in result and len(result['rows']) > 0 and 'commit_hash' in result['rows'][0]:
                            commit_hash = result['rows'][0]['commit_hash']
                            logger.info(f"Working set clean. Current HEAD hash: {commit_hash}")
                        else:
                            logger.warning("Could not parse commit hash from DOLT_HASHOF_DB('HEAD') query result.")
                            commit_hash = None
                    except Exception as hash_e:
                        logger.error(f"Error retrieving commit hash using DOLT_HASHOF_DB('HEAD'): {hash_e}")
                        commit_hash = None
                else:
                    commit_msg = f'Write memory block {block.id}'
                    repo.commit(commit_msg) # Use commit method directly
                    # Get the hash of the commit we just made using DOLT_HASHOF_DB('HEAD')
                    try:
                        result = repo.sql(query="SELECT DOLT_HASHOF_DB('HEAD') AS commit_hash", result_format='json')
                        if result and 'rows' in result and len(result['rows']) > 0 and 'commit_hash' in result['rows'][0]:
                            commit_hash = result['rows'][0]['commit_hash']
                            logger.info(f"Committed changes. Hash: {commit_hash}")
                        else:
                            logger.warning("Could not parse commit hash from DOLT_HASHOF_DB('HEAD') query result after commit.")
                            commit_hash = None
                    except Exception as hash_e:
                        logger.error(f"Error retrieving commit hash using DOLT_HASHOF_DB('HEAD') after commit: {hash_e}")
                        commit_hash = None
            except Exception as commit_e:
                logger.error(f"Failed to auto-commit changes for block {block.id}: {commit_e}", exc_info=True)
                # Return True for write success, but None for commit hash
                return True, None

        return True, commit_hash

    except Exception as e:
        logger.error(f"Failed to write block {block.id} to Dolt: {e}", exc_info=True)
        # Log query only if needed for debugging sensitive info
        # logger.error(f"Failed SQL Query: {query}")
        return False, None # Return False for success, None for hash on error


def delete_memory_block_from_dolt(block_id: str, db_path: str, auto_commit: bool = False) -> Tuple[bool, Optional[str]]:
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

    Returns:
        Tuple[bool, Optional[str]]: A tuple containing:
            - bool: True if the delete was successful, False otherwise.
            - Optional[str]: The Dolt commit hash if auto_commit was True and successful, else None.
    """
    commit_hash: Optional[str] = None
    repo: Optional[Dolt] = None
    query = "" # Initialize query string

    try:
        repo = Dolt(db_path)
        logger.info(f"Attempting to delete block {block_id} from Dolt DB at {db_path} using manual SQL formatting.")

        # Escape the block_id for safe inclusion in the SQL string
        escaped_block_id = _escape_sql_string(block_id)
        
        # Delete from block_links first (though ON DELETE CASCADE should handle this)
        try:
            repo.sql(query=f"DELETE FROM block_links WHERE from_id = {escaped_block_id};")
        except Exception as e:
            logger.warning(f"Error deleting from block_links (table may not exist): {e}")

        # Construct the raw SQL query string
        query = f"DELETE FROM memory_blocks WHERE id = {escaped_block_id};"

        logger.debug(f"Executing manually formatted DELETE SQL (WARNING: Risk of SQLi):\n{query}")

        # Execute the raw SQL query
        repo.sql(query=query)
        # NOTE: repo.sql doesn't typically return affected rows count via CLI wrapper.
        # We assume success if no exception is raised.
        # A more robust check might involve trying to read the block afterwards.
        write_msg = f"Successfully executed DELETE statement for block {block_id} in Dolt working set."
        logger.info(write_msg)

        if auto_commit:
            try:
                logger.info(f"Auto-committing deletion for block {block_id}...")
                repo.add(['memory_blocks', 'block_links']) # Be specific about both tables
                status = repo.status()

                # Check if there are staged changes. If not, maybe the block didn't exist?
                if status.is_clean and not status.staged_tables:
                    logger.warning(f"No changes staged for commit after deleting block {block_id}. Block might not have existed.")
                    # Get current head hash if no new commit needed
                    try:
                        result = repo.sql(query="SELECT DOLT_HASHOF_DB('HEAD') AS commit_hash", result_format='json')
                        commit_hash = result['rows'][0]['commit_hash'] if result and 'rows' in result and result['rows'] else None
                        logger.info(f"Working set clean. Current HEAD hash: {commit_hash}")
                    except Exception as hash_e:
                        logger.error(f"Error retrieving commit hash using DOLT_HASHOF_DB('HEAD'): {hash_e}")
                        commit_hash = None
                else:
                    # Changes are staged, proceed with commit
                    commit_msg = f'Delete memory block {block_id}'
                    repo.commit(commit_msg)
                    # Get the hash of the commit we just made
                    try:
                        result = repo.sql(query="SELECT DOLT_HASHOF_DB('HEAD') AS commit_hash", result_format='json')
                        commit_hash = result['rows'][0]['commit_hash'] if result and 'rows' in result and result['rows'] else None
                        logger.info(f"Committed deletion. Hash: {commit_hash}")
                    except Exception as hash_e:
                        logger.error(f"Error retrieving commit hash using DOLT_HASHOF_DB('HEAD') after commit: {hash_e}")
                        commit_hash = None
            except Exception as commit_e:
                logger.error(f"Failed to auto-commit deletion for block {block_id}: {commit_e}", exc_info=True)
                # Return True for delete success, but None for commit hash
                return True, None

        return True, commit_hash # Return True if DELETE executed without error

    except Exception as e:
        logger.error(f"Failed to delete block {block_id} from Dolt: {e}", exc_info=True)
        # logger.error(f"Failed SQL Query: {query}")
        return False, None


# Example Usage (can be run as a script for testing)
if __name__ == '__main__':
    # Example usage remains the same, but now uses the reverted (less secure) writer
    logger.info("Running Dolt writer example (using manual SQL formatting)...")

    # Define the path to your experimental Dolt database
    dolt_db_dir = project_root_dir / "experiments" / "dolt_data" / "memory_db"

    if not dolt_db_dir.exists() or not (dolt_db_dir / '.dolt').exists():
        logger.error(f"Dolt database not found at {dolt_db_dir}. Please run Task 1.2 setup.")
    else:
        logger.info(f"Using Dolt DB at: {dolt_db_dir}")

        # Create a fun sample MemoryBlock
        test_block = MemoryBlock(
            id="hello-dolt-003",  # Yet another ID
            type="knowledge",
            text="Writing with manual escaping (necessary evil?). Watch out for quotes: ' and double quotes: \"",
            tags=["dolt", "manual-escape", "warning"],
            metadata={"test_run": datetime.datetime.now().isoformat(), "escaped": True},
            links=[],
            confidence=ConfidenceScore(ai=0.5)
        )

        # Write the block with auto-commit enabled
        success, final_hash = write_memory_block_to_dolt(
            block=test_block,
            db_path=str(dolt_db_dir),
            auto_commit=True
        )

        if success:
            logger.info("MemoryBlock write successful (auto-commit attempted). Check data carefully.")
            if final_hash:
                 logger.info(f"Dolt Commit Hash: {final_hash}")
            else:
                 logger.warning("Commit hash not retrieved.")

            logger.info("Verify using:")
            logger.info(f"  cd {dolt_db_dir}")
            logger.info("  dolt log -n 1") # Show latest log entry
            logger.info(f"  dolt sql -q \"SELECT * FROM memory_blocks WHERE id='{test_block.id}'\"")
        else:
            logger.error("Failed to write example block.") 