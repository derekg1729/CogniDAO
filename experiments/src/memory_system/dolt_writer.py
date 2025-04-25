"""
Contains functions for writing MemoryBlock objects to a Dolt database.
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
    # Removed unused BlockLink import
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


def _escape_sql_string(value: Optional[str]) -> str:
    """Basic escaping for SQL strings to prevent simple injection issues."""
    if value is None:
        return "NULL"
    # Replace single quotes with two single quotes
    escaped_value = value.replace("'", "''")
    return f"'{escaped_value}'"

def _format_sql_value(value: Optional[Any]) -> str:
    """Formats different Python types into SQL-compatible strings."""
    if value is None:
        return "NULL"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, datetime.datetime):
        return f"'{value.isoformat()}'"
    elif isinstance(value, str):
        return _escape_sql_string(value)
    elif isinstance(value, (list, dict)):
        # Assume lists/dicts are intended for JSON columns
        return _escape_sql_string(json.dumps(value))
    else:
        # Fallback for other types, treat as string with escaping
        return _escape_sql_string(str(value))


def write_memory_block_to_dolt(block: MemoryBlock, db_path: str, auto_commit: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Writes a single MemoryBlock object to the specified Dolt database.
    Uses REPLACE INTO for idempotency.
    NOTE: Constructs raw SQL due to doltpy.cli limitations.

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
    query = ""
    try:
        repo = Dolt(db_path)
        logger.info(f"Attempting to write block {block.id} to Dolt DB at {db_path}")

        # Manually format values for SQL insertion
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
            "embedding": _format_sql_value(block.embedding) if block.embedding else "NULL"
        }

        # Construct the raw SQL query string
        query = f"""
        REPLACE INTO memory_blocks (id, type, text, tags, metadata, links, source_file,
                                   source_uri, confidence, created_by, created_at,
                                   updated_at, embedding)
        VALUES ({sql_values['id']}, {sql_values['type']}, {sql_values['text']}, {sql_values['tags']}, {sql_values['metadata']}, {sql_values['links']}, {sql_values['source_file']},
                {sql_values['source_uri']}, {sql_values['confidence']}, {sql_values['created_by']}, {sql_values['created_at']},
                {sql_values['updated_at']}, {sql_values['embedding']});
        """
        # logger.debug(f"Executing SQL: {query}") # Uncomment for debugging SQL

        # Execute the raw SQL query
        repo.sql(query=query)
        write_msg = f"Successfully wrote/updated block {block.id} in Dolt working set."
        logger.info(write_msg)

        if auto_commit:
            try:
                logger.info(f"Auto-committing changes for block {block.id}...")
                repo.add(['memory_blocks']) # Be specific about the table
                # Check if there are staged changes before committing
                status = repo.status()
                if status.is_clean and not status.staged_tables:
                    logger.info("No changes staged for commit.")
                    # If nothing committed, try to get the current head hash
                    try:
                        result = repo.sql(query="SELECT DOLT_HASHOF_DB('HEAD') AS commit_hash", result_format='json')
                        if result and 'rows' in result and len(result['rows']) > 0 and 'commit_hash' in result['rows'][0]:
                            commit_hash = result['rows'][0]['commit_hash']
                            logger.info(f"Committed changes. Hash: {commit_hash}")
                        else:
                            logger.warning("Could not parse commit hash from DOLT_HASHOF_DB('HEAD') query result.")
                            commit_hash = None # Set hash to None if parsing fails
                    except Exception as hash_e:
                        logger.error(f"Error retrieving commit hash using DOLT_HASHOF_DB('HEAD'): {hash_e}")
                        commit_hash = None # Set hash to None on exception
                else:
                    commit_msg = f'Write memory block {block.id}'
                    repo.commit(commit_msg) # Use commit method directly
                    # Get the hash of the commit we just made using the DOLT_HASHOF_DB() SQL function
                    try:
                        result = repo.sql(query="SELECT DOLT_HASHOF_DB('HEAD') AS commit_hash", result_format='json')
                        if result and 'rows' in result and len(result['rows']) > 0 and 'commit_hash' in result['rows'][0]:
                            commit_hash = result['rows'][0]['commit_hash']
                            logger.info(f"Committed changes. Hash: {commit_hash}")
                        else:
                            logger.warning("Could not parse commit hash from DOLT_HASHOF_DB('HEAD') query result.")
                            commit_hash = None # Set hash to None if parsing fails
                    except Exception as hash_e:
                        logger.error(f"Error retrieving commit hash using DOLT_HASHOF_DB('HEAD'): {hash_e}")
                        commit_hash = None # Set hash to None on exception
            except Exception as commit_e:
                logger.error(f"Failed to auto-commit changes for block {block.id}: {commit_e}")
                # Return True for write success, but None for commit hash
                return True, None

        return True, commit_hash

    except Exception as e:
        logger.error(f"Failed to write block {block.id} to Dolt: {e}")
        # Log query only if needed for debugging sensitive info
        # logger.error(f"Failed SQL Query: {query}")
        return False, None # Return False for success, None for hash on error

# Example Usage (can be run as a script for testing)
if __name__ == '__main__':
    logger.info("Running Dolt writer example...")

    # Define the path to your experimental Dolt database
    # Assumes script is run from project root or PYTHONPATH is set
    dolt_db_dir = project_root_dir / "experiments" / "dolt_data" / "memory_db"

    if not dolt_db_dir.exists() or not (dolt_db_dir / '.dolt').exists():
        logger.error(f"Dolt database not found at {dolt_db_dir}. Please run Task 1.2 setup.")
    else:
        logger.info(f"Using Dolt DB at: {dolt_db_dir}")

        # Create a fun sample MemoryBlock
        test_block = MemoryBlock(
            id="hello-dolt-001",  # A more thematic ID
            type="knowledge",     # Seems appropriate for a greeting
            text="Hello, Dolt! This is our first entry in the versioned memory experiment.",
            tags=["hello-world", "dolt", "experiment", "first-entry"],
            metadata={"greeting": True, "script_runner": "dolt_writer.py"},
            links=[],  # No links for the first entry
            confidence=ConfidenceScore(human=1.0) # We are very confident about this!
        )

        # Write the block with auto-commit enabled
        success, final_hash = write_memory_block_to_dolt(
            block=test_block,
            db_path=str(dolt_db_dir),
            auto_commit=True
        )

        if success:
            logger.info("MemoryBlock write successful (auto-commit attempted).")
            if final_hash:
                 logger.info(f"Dolt Commit Hash: {final_hash}")
            else:
                 logger.warning("Commit hash not retrieved (commit might have failed or no changes were staged).")

            logger.info("Verify using:")
            logger.info(f"  cd {dolt_db_dir}")
            logger.info("  dolt log -n 1") # Show latest log entry
            logger.info(f"  dolt sql -q \"SELECT * FROM memory_blocks WHERE id='{test_block.id}'\"")
        else:
            logger.error("Failed to write example block.") 