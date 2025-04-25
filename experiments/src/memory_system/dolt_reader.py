"""
Contains functions for reading MemoryBlock objects from a Dolt database.
"""

import logging
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any

from pydantic import ValidationError

# Use the correct import path for doltpy v2+
try:
    from doltpy.cli import Dolt
except ImportError:
    raise ImportError("doltpy not found. Please install it: pip install doltpy")

# --- Path Setup --- START
# Ensure the project root is in the Python path for schema imports
script_dir = Path(__file__).parent
project_root_dir = script_dir.parent.parent.parent # Adjust if structure changes
if str(project_root_dir) not in sys.path:
    sys.path.insert(0, str(project_root_dir))
# --- Path Setup --- END

# Import schema using path relative to project root
try:
    from experiments.src.memory_system.schemas.memory_block import MemoryBlock
except ImportError as e:
    raise ImportError(
        f"Could not import MemoryBlock/related schemas from experiments/src. "
        f"Project root added to path: {project_root_dir}. Check structure. Error: {e}"
    )

# Setup standard Python logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Helper function from dolt_writer for safe SQL formatting
def _escape_sql_string(value: Optional[str]) -> str:
    """Basic escaping for SQL strings to prevent simple injection issues."""
    if value is None:
        return "NULL"
    # Replace single quotes with two single quotes
    escaped_value = value.replace("'", "''")
    return f"'{escaped_value}'"

def read_memory_blocks(db_path: str, branch: str = 'main') -> List[MemoryBlock]:
    """
    Reads MemoryBlocks from the specified Dolt database and branch.

    Queries the 'memory_blocks' table, parses rows, and validates them into
    MemoryBlock Pydantic objects. Assumes columns like 'tags', 'metadata', 'links',
    'confidence' are returned as appropriate Python types (list, dict) by doltpy
    when using result_format='json'.

    Args:
        db_path: Path to the Dolt database directory.
        branch: The Dolt branch to read from (defaults to 'main').

    Returns:
        A list of validated MemoryBlock objects.
    """
    logger.info(f"Attempting to read MemoryBlocks from Dolt DB at {db_path} on branch '{branch}'")
    memory_blocks_list: List[MemoryBlock] = []
    repo: Optional[Dolt] = None

    try:
        # 1. Connect to Dolt repository
        repo = Dolt(db_path)

        # 2. Define the SQL Query (excluding embedding)
        # Use AS OF syntax to query a specific branch/commit
        # Select columns without the '_json' suffix
        query = f"""
        SELECT 
            id, type, schema_version, text, tags, metadata, links, 
            source_file, source_uri, confidence, created_by, created_at, updated_at
        FROM memory_blocks 
        AS OF '{branch}'
        """
        logger.debug(f"Executing SQL query on branch '{branch}':\\n{query}")

        # 3. Execute the query
        result = repo.sql(query=query, result_format='json')

        # 4. Process Results
        if result and 'rows' in result and result['rows']:
            logger.info(f"Retrieved {len(result['rows'])} rows from Dolt.")
            for row in result['rows']:
                try:
                    # 5. Prepare row data for Pydantic model validation
                    # Directly use the dictionary returned by doltpy.
                    # Pydantic's model_validate should handle type checking,
                    # conversion (e.g., dict to ConfidenceScore/BlockLink models),
                    # and validation.
                    
                    # Filter out None values explicitly if needed, though Pydantic usually handles optional fields.
                    # Create a copy to avoid modifying the original result row if necessary.
                    parsed_row: Dict[str, Any] = {k: v for k, v in row.items() if v is not None}

                    # Pydantic v2's model_validate handles the dict -> model conversion,
                    # including nested models like BlockLink and ConfidenceScore.
                    # No manual parsing or json.loads needed here if doltpy + result_format='json'
                    # returns Python objects for JSON columns.

                    # 6. Validate using Pydantic
                    memory_block = MemoryBlock.model_validate(parsed_row)
                    memory_blocks_list.append(memory_block)

                except ValidationError as e:
                    # Log Pydantic validation errors specifically
                    logger.error(f"Pydantic validation failed for row (Block ID: {row.get('id', 'UNKNOWN')}): {e}")
                except Exception as parse_e:
                    # Log any other unexpected errors during processing of a row
                    logger.error(f"Unexpected error processing row (Block ID: {row.get('id', 'UNKNOWN')}): {parse_e}", exc_info=True)
        else:
            logger.info("No rows returned from the Dolt query.")

    except FileNotFoundError:
        logger.error(f"Dolt database path not found: {db_path}")
        # Re-raise or handle as appropriate for the application
        raise
    except Exception as e:
        # Log errors related to DB connection or SQL execution
        logger.error(f"Failed to read from Dolt DB at {db_path} on branch '{branch}': {e}", exc_info=True)
        # Depending on use case, might want to return partial list or empty list
        # Returning empty list on major error for now.
        return [] # Return empty list on error

    logger.info(f"Finished reading. Successfully parsed {len(memory_blocks_list)} MemoryBlocks.")
    return memory_blocks_list


def read_memory_block(db_path: str, block_id: str, branch: str = 'main') -> Optional[MemoryBlock]:
    """
    Reads a single MemoryBlock from the specified Dolt database and branch by its ID.

    Queries the 'memory_blocks' table for a specific ID, parses the row, and
    validates it into a MemoryBlock Pydantic object.

    Args:
        db_path: Path to the Dolt database directory.
        block_id: The ID of the MemoryBlock to retrieve.
        branch: The Dolt branch to read from (defaults to 'main').

    Returns:
        A validated MemoryBlock object if found, otherwise None.
    """
    logger.info(f"Attempting to read MemoryBlock {block_id} from Dolt DB at {db_path} on branch '{branch}'")
    repo: Optional[Dolt] = None

    try:
        repo = Dolt(db_path)

        # Escape block_id for safe insertion into the query string
        # NOTE: Using manual escaping because doltpy.cli.Dolt.sql() does not
        # appear to support the 'args' parameter for parameterized SELECT queries,
        # based on previous TypeErrors. This is less ideal than parameterized queries
        # but necessary with the current library constraints for reads.
        escaped_block_id = _escape_sql_string(block_id)

        # Query for a specific block ID (using formatted string)
        query = f"""
        SELECT
            id, type, schema_version, text, tags, metadata, links,
            source_file, source_uri, confidence, created_by, created_at, updated_at
        FROM memory_blocks
        AS OF '{branch}'
        WHERE id = {escaped_block_id}
        LIMIT 1
        """
        logger.debug(f"Executing SQL query for block {escaped_block_id} on branch '{branch}':\n{query}")

        # Execute query without the 'args' parameter
        result = repo.sql(query=query, result_format='json')

        if result and 'rows' in result and result['rows']:
            row = result['rows'][0]
            logger.info(f"Retrieved row for block ID: {block_id}")
            try:
                # Prepare row data for Pydantic model validation
                parsed_row: Dict[str, Any] = {k: v for k, v in row.items() if v is not None}
                memory_block = MemoryBlock.model_validate(parsed_row)
                logger.info(f"Successfully parsed MemoryBlock {block_id}.")
                return memory_block

            except ValidationError as e:
                logger.error(f"Pydantic validation failed for row (Block ID: {block_id}): {e}")
                return None
            except Exception as parse_e:
                logger.error(f"Unexpected error processing row (Block ID: {block_id}): {parse_e}", exc_info=True)
                return None
        else:
            logger.info(f"No row found for MemoryBlock ID: {block_id}")
            return None

    except FileNotFoundError:
        logger.error(f"Dolt database path not found: {db_path}")
        raise # Re-raise critical error
    except Exception as e:
        logger.error(f"Failed to read block {block_id} from Dolt DB at {db_path} on branch '{branch}': {e}", exc_info=True)
        return None


# Example Usage (can be run as a script for testing)
if __name__ == '__main__':
    logger.info("Running Dolt reader example...")

    # Define the path to your experimental Dolt database
    # Assumes script is run from project root or PYTHONPATH is set
    dolt_db_dir = project_root_dir / "experiments" / "dolt_data" / "memory_db"

    if not dolt_db_dir.exists() or not (dolt_db_dir / '.dolt').exists():
        logger.error(f"Dolt database not found at {dolt_db_dir}. Please run Task 1.2 setup.")
    else:
        logger.info(f"Using Dolt DB at: {dolt_db_dir}")
        
        # Read blocks from the 'main' branch
        try:
            blocks = read_memory_blocks(str(dolt_db_dir), branch='main')
            if blocks:
                logger.info(f"Successfully read {len(blocks)} MemoryBlocks from main branch:")
                # Print summary of first few blocks for verification
                for i, block in enumerate(blocks[:3]):
                    logger.info(f"  Block {i+1}: ID={block.id}, Type={block.type}, Text='{block.text[:50]}...' Tags={block.tags}, Links={len(block.links)}")
                if len(blocks) > 3:
                    logger.info(f"  ... and {len(blocks) - 3} more.")
            else:
                logger.info("No MemoryBlocks found in the main branch.")
        except Exception as e:
            logger.error(f"Failed to read blocks during example run: {e}", exc_info=True) 