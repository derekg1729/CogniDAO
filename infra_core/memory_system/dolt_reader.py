"""
Contains functions for reading MemoryBlock objects from a Dolt database.
"""

import logging
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
import json
from datetime import datetime

from doltpy.cli import Dolt
from pydantic import ValidationError

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


# Helper function from dolt_writer for safe SQL formatting
def _escape_sql_string(value: Optional[str]) -> str:
    """Basic escaping for SQL strings to prevent simple injection issues."""
    if value is None:
        return "NULL"
    # Replace single quotes with two single quotes
    escaped_value = value.replace("'", "''")
    return f"'{escaped_value}'"


def read_memory_blocks(db_path: str, branch: str = "main") -> List[MemoryBlock]:
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
            id, type, schema_version, text, tags, metadata, 
            source_file, source_uri, confidence, created_by, created_at, updated_at
        FROM memory_blocks 
        AS OF '{branch}'
        """
        logger.debug(f"Executing SQL query on branch '{branch}':\\n{query}")

        # 3. Execute the query
        result = repo.sql(query=query, result_format="json")

        # 4. Process Results
        if result and "rows" in result and result["rows"]:
            logger.info(f"Retrieved {len(result['rows'])} rows from Dolt.")
            for row in result["rows"]:
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

    logger.info(f"Finished reading. Successfully parsed {len(memory_blocks_list)} MemoryBlocks.")
    return memory_blocks_list


def read_block_properties(db_path: str, block_id: str, branch: str = "main") -> List[BlockProperty]:
    """
    Read BlockProperty instances for a specific block from the block_properties table.

    Args:
        db_path: Path to the Dolt database directory
        block_id: ID of the block to read properties for
        branch: The Dolt branch to read from (defaults to 'main')

    Returns:
        List of BlockProperty instances
    """
    logger.debug(f"Reading properties for block {block_id} from branch '{branch}'")
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


def read_memory_block(db_path: str, block_id: str, branch: str = "main") -> Optional[MemoryBlock]:
    """
    Reads a single MemoryBlock from the specified Dolt database using the Property-Schema Split approach.

    Uses PropertyMapper to compose metadata from the block_properties table instead of reading
    from a metadata JSON column.

    WARNING: This function constructs SQL queries with block_id manually escaped
    due to limitations in doltpy.cli.Dolt.sql() (lack of parameterized query support).
    This carries SQL injection risks if block_id is not sanitized elsewhere.

    Args:
        db_path: Path to the Dolt database directory.
        block_id: The ID of the block to read.
        branch: The Dolt branch to read from (defaults to 'main').

    Returns:
        A validated MemoryBlock object if found, or None if not found/error.
    """
    logger.info(
        f"Attempting to read block {block_id} from Dolt DB at {db_path} on branch '{branch}' using Property-Schema Split"
    )
    repo: Optional[Dolt] = None

    try:
        repo = Dolt(db_path)
        escaped_block_id = _escape_sql_string(block_id)

        # Step 1: Read from memory_blocks table (NO metadata column - Property-Schema Split)
        query = f"""
        SELECT
            id, type, schema_version, text, tags, 
            source_file, source_uri, confidence, created_by, created_at, updated_at
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
    Reads MemoryBlocks from Dolt filtered by tags contained in the 'tags' JSON column.

    WARNING: This function constructs SQL queries with tag values manually formatted
    due to limitations in doltpy.cli.Dolt.sql() (lack of parameterized query support
    for complex JSON operations). This carries SQL injection risks if tags
    originate from untrusted input without robust validation elsewhere.

    Args:
        db_path: Path to the Dolt database directory.
        tags: A list of tags to filter by.
        match_all: If True, blocks must contain ALL tags. If False, blocks must contain AT LEAST ONE tag.
        branch: The Dolt branch to read from (defaults to 'main').

    Returns:
        A list of validated MemoryBlock objects matching the tag criteria.
    """
    if not tags:
        logger.warning("read_memory_blocks_by_tags called with empty tags list.")
        return []

    logger.info(
        f"Attempting to read MemoryBlocks by tags {tags} (match_all={match_all}) from Dolt DB at {db_path} on branch '{branch}'"
    )
    memory_blocks_list: List[MemoryBlock] = []
    repo: Optional[Dolt] = None

    try:
        repo = Dolt(db_path)

        # --- Construct WHERE clause based on tags ---
        where_clauses = []
        for tag in tags:
            # Escape each tag individually for safe inclusion in the JSON_CONTAINS check
            escaped_tag_for_json = json.dumps(tag)  # JSON encode the tag string
            # Escape the resulting JSON string for the SQL query
            escaped_tag_for_sql = _escape_sql_string(escaped_tag_for_json)
            # Use JSON_CONTAINS to check if the tag exists in the 'tags' JSON array
            # Assumes the 'tags' column is named 'tags' and stores a JSON array.
            where_clauses.append(f"JSON_CONTAINS(tags, {escaped_tag_for_sql})")

        if not where_clauses:
            logger.error("Could not generate WHERE clauses for tags.")
            return []  # Should not happen if tags list is not empty

        # Combine clauses with AND or OR
        clause_separator = " AND " if match_all else " OR "
        full_where_clause = clause_separator.join(where_clauses)
        # --- End WHERE clause construction ---

        query = f"""
        SELECT
            id, type, schema_version, text, tags, metadata, 
            source_file, source_uri, confidence, created_by, created_at, updated_at
        FROM memory_blocks
        AS OF '{branch}'
        WHERE {full_where_clause}
        """
        logger.debug(f"Executing SQL query for tags on branch '{branch}':\n{query}")

        result = repo.sql(query=query, result_format="json")

        if result and "rows" in result and result["rows"]:
            logger.info(f"Retrieved {len(result['rows'])} rows matching tags from Dolt.")
            for row in result["rows"]:
                try:
                    parsed_row: Dict[str, Any] = {k: v for k, v in row.items() if v is not None}
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
        f"Finished reading by tags. Successfully parsed {len(memory_blocks_list)} MemoryBlocks."
    )
    return memory_blocks_list


def read_memory_blocks_from_working_set(db_path: str) -> List[MemoryBlock]:
    """
    Reads MemoryBlocks from the working set of the specified Dolt database.

    Queries the 'memory_blocks' table, parses rows, and validates them into
    MemoryBlock Pydantic objects.
    """
    logger.info(f"Attempting to read MemoryBlocks from Dolt DB working set at {db_path}")
    memory_blocks_list: List[MemoryBlock] = []
    repo: Optional[Dolt] = None

    try:
        repo = Dolt(db_path)

        # Query to select all relevant columns from memory_blocks in the working set.
        # No 'AS OF' clause is used, so it queries the working tables.
        query = """
        SELECT
            id, type, schema_version, text, tags, metadata, 
            source_file, source_uri, confidence, created_by, created_at, updated_at,
            state, visibility
        FROM memory_blocks
        """
        # Removed block_version and embedding for now to match ingest script's --no-commit path more closely
        # and typical Dolt select, can be added if needed and present.

        logger.debug(f"Executing SQL query on working set:\\n{query}")

        result = repo.sql(query=query, result_format="json")

        if result and "rows" in result and result["rows"]:
            logger.info(f"Retrieved {len(result['rows'])} rows from Dolt working set.")
            for row_data in result["rows"]:
                try:
                    # Prepare row data for Pydantic model validation.
                    # Pydantic should handle type conversions (e.g., str to datetime, JSON str to dict/list).
                    # Create a copy to avoid modifying the original result row if necessary.
                    # Fields like 'tags', 'metadata', 'confidence' might be JSON strings
                    # if not automatically parsed by doltpy with result_format="json".
                    # The MemoryBlock model expects Python dicts/lists for these.

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

                    # Ensure all required fields for MemoryBlock are present or handle defaults
                    # This simplified example assumes most fields are coming from Dolt.
                    # Add default values here if any are missing from the SELECT but required by MemoryBlock
                    # and not Optional with a default in the model. For example:
                    # parsed_row.setdefault('state', 'draft') # If state can be null from DB but required

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
        f"Finished reading. Successfully parsed {len(memory_blocks_list)} MemoryBlocks from working set."
    )
    return memory_blocks_list


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
