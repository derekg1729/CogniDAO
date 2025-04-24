"""
Contains functions for reading MemoryBlock objects from a Dolt database.
"""

import json
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

def read_memory_blocks(db_path: str, branch: str = 'main') -> List[MemoryBlock]:
    """
    Reads MemoryBlocks from the specified Dolt database and branch.

    Queries the 'memory_blocks' table, parses rows, and validates them into
    MemoryBlock Pydantic objects.

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
        # Note: Ensure column names here match the Dolt table schema exactly
        query = f"""
        SELECT 
            id, type, schema_version, text, tags_json, metadata_json, links_json, 
            source_file, source_uri, confidence_json, created_by, created_at, updated_at
        FROM memory_blocks 
        AS OF '{branch}'
        """
        logger.debug(f"Executing SQL query on branch '{branch}':\n{query}")

        # 3. Execute the query
        result = repo.sql(query=query, result_format='json')

        # 4. Process Results
        if result and 'rows' in result and result['rows']:
            logger.info(f"Retrieved {len(result['rows'])} rows from Dolt.")
            for row in result['rows']:
                try:
                    # 5. Parse row data into a dictionary for Pydantic model
                    parsed_row: Dict[str, Any] = {}

                    # Direct mapping for simple fields
                    for field in ['id', 'type', 'schema_version', 'text', 'source_file', 'source_uri', 'created_by', 'created_at', 'updated_at']:
                        if field in row and row[field] is not None:
                            # Assume Pydantic handles datetime string parsing
                            parsed_row[field] = row[field]
                    
                    # Parse JSON fields
                    json_fields_map = {
                        'tags_json': 'tags',
                        'metadata_json': 'metadata',
                        'links_json': 'links', 
                        'confidence_json': 'confidence'
                    }
                    
                    for json_col, model_field in json_fields_map.items():
                        if json_col in row and row[json_col] is not None:
                            try:
                                parsed_row[model_field] = json.loads(row[json_col])
                            except json.JSONDecodeError as json_e:
                                logger.warning(f"Failed to parse JSON for field '{json_col}' in row for block ID {row.get('id', 'UNKNOWN')}: {json_e}")
                                # Decide how to handle: skip field, set default, raise error?
                                # Setting to default empty value for now
                                if model_field == 'tags' or model_field == 'links':
                                    parsed_row[model_field] = []
                                elif model_field == 'metadata':
                                     parsed_row[model_field] = {}
                                else: # confidence
                                    parsed_row[model_field] = None 

                    # Handle potential sub-model parsing within Pydantic (needed for links, confidence)
                    # Pydantic v2's model_validate should handle dict -> model conversion
                    # if 'links' in parsed_row:
                    #     parsed_row['links'] = [BlockLink(**link_dict) for link_dict in parsed_row['links']]
                    # if 'confidence' in parsed_row:
                    #     parsed_row['confidence'] = ConfidenceScore(**parsed_row['confidence'])
                        
                    # 6. Validate using Pydantic
                    memory_block = MemoryBlock.model_validate(parsed_row)
                    memory_blocks_list.append(memory_block)

                except ValidationError as e:
                    logger.error(f"Pydantic validation failed for row (Block ID: {row.get('id', 'UNKNOWN')}): {e}")
                except Exception as parse_e:
                    logger.error(f"Unexpected error parsing row (Block ID: {row.get('id', 'UNKNOWN')}): {parse_e}", exc_info=True)
        else:
            logger.info("No rows returned from the Dolt query.")

    except FileNotFoundError:
        logger.error(f"Dolt database path not found: {db_path}")
        # Re-raise or handle as appropriate for the application
        raise
    except Exception as e:
        logger.error(f"Failed to read from Dolt DB at {db_path} on branch '{branch}': {e}", exc_info=True)
        # Depending on use case, might want to return partial list or empty list
        # Returning empty list on major error for now.
        return [] # Return empty list on error

    logger.info(f"Finished reading. Successfully parsed {len(memory_blocks_list)} MemoryBlocks.")
    return memory_blocks_list


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