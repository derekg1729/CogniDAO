"""
Core StructuredMemoryBank class for managing MemoryBlocks.

This class orchestrates interactions between the persistent Dolt storage
and the LlamaIndex (ChromaDB) indexing/retrieval system.
"""

import logging
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import datetime
from pydantic import ValidationError

# --- Path Setup --- START
script_dir = Path(__file__).parent
project_root_dir = script_dir.parent.parent.parent
if str(project_root_dir) not in sys.path:
    sys.path.insert(0, str(project_root_dir))
# --- Path Setup --- END

# Dolt Interactions
from doltpy.cli import Dolt  # noqa: E402
from experiments.src.memory_system.dolt_reader import read_memory_block, read_memory_blocks_by_tags  # noqa: E402
from experiments.src.memory_system.dolt_writer import write_memory_block_to_dolt, delete_memory_block_from_dolt, _escape_sql_string  # noqa: E402

# LlamaIndex Interactions
from experiments.src.memory_system.llama_memory import LlamaMemory  # noqa: E402

# Schemas
from experiments.src.memory_system.schemas.memory_block import MemoryBlock  # noqa: E402
from experiments.src.memory_system.schemas.common import BlockLink  # noqa: E402

# Schema manager
from experiments.src.memory_system.dolt_schema_manager import get_schema  # noqa: E402

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# TODO: Security Migration Plan for SQL Parameterization
# Currently, the code uses manual SQL string escaping via _escape_sql_string which
# is not ideal from a security perspective. A future enhancement should:
#
# 1. Wait for Doltpy to add proper parameterized query support (check latest updates)
# 2. If direct parameterization is still not available, consider:
#    - Creating a wrapper around the Dolt CLI that supports parameterized queries
#    - Using a more robust SQL escaping library instead of the current approach
#    - Implementing a query builder pattern with parameterization
# 3. Replace all instances of manual string interpolation with parameterized queries
#    in the following methods:
#    - _store_block_proof
#    - get_block_proofs
#    - get_forward_links
#    - get_backlinks
#
# Example of desired future API:
# ```
# self.repo.sql(
#     query="INSERT INTO block_proofs (block_id, commit_hash, operation, timestamp) VALUES (?, ?, ?, ?)",
#     params=[block_id, commit_hash, operation, timestamp]
# )
# ```

def diff_memory_blocks(old_block: MemoryBlock, new_block: MemoryBlock) -> Dict[str, Tuple[Any, Any]]:
    """
    Creates a diff between two MemoryBlock objects, showing what fields changed.

    Args:
        old_block: The original MemoryBlock object
        new_block: The updated MemoryBlock object

    Returns:
        Dictionary where keys are field names and values are tuples of (old_value, new_value)
        Only includes fields that actually changed.
    """
    changes = {}
    
    # Convert both blocks to dictionaries for comparison
    old_dict = old_block.model_dump()
    new_dict = new_block.model_dump()
    
    # Find differences
    for key in set(old_dict.keys()) | set(new_dict.keys()):
        old_value = old_dict.get(key)
        new_value = new_dict.get(key)
        
        # Special handling for complex fields to avoid comparing timestamps or
        # other fields that are expected to change
        if key == "updated_at":
            # Skip updated_at, as it's expected to change
            continue
            
        # Check if values are different
        if old_value != new_value:
            changes[key] = (old_value, new_value)
    
    return changes

class StructuredMemoryBank:
    """
    Manages MemoryBlocks using Dolt for persistence and LlamaIndex for indexing.
    """

    def __init__(self, dolt_db_path: str, chroma_path: str, chroma_collection: str):
        """
        Initializes the StructuredMemoryBank.

        Args:
            dolt_db_path: Path to the Dolt database directory.
            chroma_path: Path to the ChromaDB storage directory.
            chroma_collection: Name of the ChromaDB collection.
        """
        self.dolt_db_path = dolt_db_path
        self.repo = Dolt(dolt_db_path)  # Initialize a single Dolt repository connection
        self.llama_memory = LlamaMemory(
            chroma_path=chroma_path,
            collection_name=chroma_collection
        )

        if not self.llama_memory.is_ready():
            raise RuntimeError("Failed to initialize LlamaMemory backend.")

        logger.info(f"StructuredMemoryBank initialized. Dolt Path: {dolt_db_path}, LlamaIndex Ready: {self.llama_memory.is_ready()}")

    def get_latest_schema_version(self, node_type: str) -> Optional[int]:
        """
        Gets the latest schema version for a given node type by querying the node_schemas table.
        
        Args:
            node_type: The type of node/block (e.g., 'knowledge', 'task', 'project', 'doc')
            
        Returns:
            The latest schema version as an integer, or None if no schema is found
        """
        logger.debug(f"Fetching latest schema version for node type: {node_type}")
        
        try:
            # Use get_schema from dolt_schema_manager which already has logic to fetch latest version
            schema = get_schema(
                db_path=self.dolt_db_path,
                node_type=node_type
            )
            
            if schema and 'x_schema_version' in schema:
                version = schema['x_schema_version']
                logger.debug(f"Found schema version {version} for {node_type}")
                return version
            else:
                logger.warning(f"No schema found for node type: {node_type}")
                return None
                
        except Exception as e:
            logger.warning(f"Error fetching schema version for {node_type}: {e}")
            return None

    def create_memory_block(self, block: MemoryBlock) -> bool:
        """
        Creates a new MemoryBlock, persisting to Dolt and indexing in LlamaIndex.
        WARNING: Current implementation relies on auto-commit within dolt_writer,
                 making the Dolt write + LlamaIndex add operation NOT fully atomic.
                 Also depends on insecure manual SQL escaping in dolt_writer.

        Args:
            block: The MemoryBlock object to create.

        Returns:
            True if creation was successful (both Dolt write and LlamaIndex add), False otherwise.
        """
        logger.info(f"Attempting to create memory block: {block.id}")
        if not self.llama_memory.is_ready(): # Basic readiness check
             logger.error("LlamaMemory backend is not ready. Cannot create block.")
             return False

        # Query node_schemas for latest version and set block.schema_version if not already set
        if block.schema_version is None:
            try:
                latest_version = self.get_latest_schema_version(block.type)
                if latest_version is not None:
                    block.schema_version = latest_version
                    logger.info(f"Set schema_version to {latest_version} for block {block.id}")
                else:
                    logger.warning(f"No schema version found for block type '{block.type}'. Creating block without schema_version.")
            except Exception as e:
                logger.warning(f"Error looking up schema version for {block.type}: {e}")
                # Continue without schema version

        # --- VALIDATION PHASE ---
        # Ensure the block is valid before writing
        try:
            # Force re-validation of the entire block including nested fields
            block = MemoryBlock.model_validate(block)
        except ValidationError as ve:
            # Clear, specific logging for validation errors
            field_errors = [f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in ve.errors()]
            error_details = "\n- ".join(field_errors)
            logger.error(f"Validation failed for block {block.id}:\n- {error_details}")
            return False
        # --- END VALIDATION PHASE ---

        # --- PERSISTENCE PHASE ---
        try:
            # 1. Write block data to Dolt memory_blocks table
            dolt_write_success, commit_hash = write_memory_block_to_dolt(
                block=block,
                db_path=self.dolt_db_path,
                auto_commit=True
            )

            if not dolt_write_success:
                logger.error(f"Failed to write block {block.id} data to Dolt.")
                return False

            # 2. Add block to LlamaIndex (add_block handles conversion internally)
            self.llama_memory.add_block(block)
            logger.info(f"Successfully indexed block {block.id} in LlamaIndex.")
            
            # 3. Store proof of creation in block_proofs table (Phase 7)
            if commit_hash:
                self._store_block_proof(block.id, commit_hash, "create", "New memory block created")
                
            logger.info(f"Successfully created and indexed memory block: {block.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed during persistence of block {block.id}: {e}", exc_info=True)
            return False
        # --- END PERSISTENCE PHASE ---

    def get_memory_block(self, block_id: str) -> Optional[MemoryBlock]:
        """
        Retrieves a MemoryBlock from Dolt by its ID.

        Args:
            block_id: The ID of the block to retrieve.

        Returns:
            The MemoryBlock object if found, otherwise None.
        """
        logger.info(f"Attempting to get memory block: {block_id}")
        try:
            # Use the imported read_memory_block function
            block = read_memory_block(db_path=self.dolt_db_path, block_id=block_id)
            if block:
                logger.info(f"Successfully retrieved block {block_id}")
                # Note: The current read_memory_block implementation reads the 'links' JSON column.
                # If we manage links ONLY in the block_links table, we'd need to fetch them separately here.
                # For now, we assume the JSON column might suffice or will be addressed later.
            else:
                logger.info(f"Block {block_id} not found in Dolt.")
            return block
        except Exception as e:
            logger.error(f"Error retrieving block {block_id} from Dolt: {e}", exc_info=True)
            return None

    def update_memory_block(self, block_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Updates an existing MemoryBlock.

        Fetches the block, applies updates, validates, writes to Dolt,
        re-indexes in LlamaIndex. 
        WARNING: Currently relies on auto_commit in dolt_writer and separate LlamaIndex update,
                 making the operation NOT fully atomic. Depends on insecure dolt_writer.

        Args:
            block_id: The ID of the block to update.
            update_data: A dictionary containing the fields to update.

        Returns:
            True if the update was successful (both Dolt write and LlamaIndex update), False otherwise.
        """
        logger.info(f"Attempting to update memory block: {block_id}")
        if not self.llama_memory.is_ready():
            logger.error("LlamaMemory backend is not ready. Cannot update block.")
            return False

        # 1. Fetch existing block
        existing_block = self.get_memory_block(block_id)
        if not existing_block:
            logger.error(f"Cannot update block {block_id}: block not found.")
            return False

        # --- UPDATE PHASE ---
        # Create updated block data, ensuring updated_at is set
        update_payload = update_data.copy()
        update_payload['updated_at'] = datetime.datetime.now() # Use current time for update
        
        # Create the merged update
        updated_block = None
        try:
            # Merge updates
            updated_block = existing_block.model_copy(update=update_payload)
        except Exception as e:
            logger.error(f"Failed to apply updates to block {block_id}: {e}")
            return False
        # --- END UPDATE PHASE ---
            
        # --- VALIDATION PHASE ---
        try:
            # Validate fully (forces re-validation of nested fields too)
            updated_block = MemoryBlock.model_validate(updated_block)
        except ValidationError as ve:
            # Clear, specific logging for validation errors
            field_errors = [f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in ve.errors()]
            error_details = "\n- ".join(field_errors)
            logger.error(f"Validation failed after update for block {block_id}:\n- {error_details}")
            return False
        # --- END VALIDATION PHASE ---
        
        # --- DIFF PHASE ---
        # Generate and log diff before writing
        changes = diff_memory_blocks(existing_block, updated_block)
        change_summary = "No significant changes"
        if changes:
            change_log = []
            change_fields = []
            for field, (old_val, new_val) in changes.items():
                # Format the change in a readable way
                change_log.append(f"{field}: {old_val!r} -> {new_val!r}")
                change_fields.append(field)
            
            # Create a summary for the commit message
            change_summary = f"Updated {', '.join(change_fields)}"
            
            # Log at INFO level
            diff_message = f"Changes for block {block_id}:\n- " + "\n- ".join(change_log)
            logger.info(diff_message)
        else:
            logger.info(f"No significant changes detected for block {block_id}")
        # --- END DIFF PHASE ---

        # --- PERSISTENCE PHASE ---
        try:
            # 1. Write updated block to Dolt
            dolt_write_success, commit_hash = write_memory_block_to_dolt(
                block=updated_block,
                db_path=self.dolt_db_path,
                auto_commit=True
            )
            if not dolt_write_success:
                logger.error(f"Failed to write updated block {block_id} data to Dolt.")
                return False

            # 2. Re-index in LlamaIndex
            self.llama_memory.update_block(updated_block)
            logger.info(f"Successfully re-indexed updated block {block_id} in LlamaIndex.")
            
            # 3. Store proof of update in block_proofs table (Phase 7)
            if commit_hash:
                self._store_block_proof(block_id, commit_hash, "update", change_summary)
            
            logger.info(f"Successfully updated and re-indexed memory block: {block_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed during persistence of updated block {block_id}: {e}", exc_info=True)
            return False
        # --- END PERSISTENCE PHASE ---

    def delete_memory_block(self, block_id: str) -> bool:
        """
        Deletes a MemoryBlock from Dolt and LlamaIndex.
        WARNING: Relies on auto_commit in dolt_writer and separate LlamaIndex delete,
                 making the operation NOT fully atomic. Depends on insecure dolt_writer.

        Args:
            block_id: The ID of the block to delete.

        Returns:
            True if deletion was successful (both Dolt delete and LlamaIndex delete), False otherwise.
        """
        logger.info(f"Attempting to delete memory block: {block_id}")
        if not self.llama_memory.is_ready():
            logger.error("LlamaMemory backend is not ready. Cannot delete block.")
            return False

        # 1. Delete block from Dolt memory_blocks
        # Relies on insecure writer and auto_commit=True (not atomic)
        # Assumes block_links table uses ON DELETE CASCADE or links are irrelevant/handled elsewhere.
        # TODO: Explicitly delete from block_links if CASCADE is not set up.
        dolt_delete_success, commit_hash = delete_memory_block_from_dolt(
            block_id=block_id,
            db_path=self.dolt_db_path,
            auto_commit=True
        )

        if not dolt_delete_success:
            logger.error(f"Failed to delete block {block_id} data from Dolt.")
            # Even if Dolt delete failed, we might still want to try removing from index
            # but for now, we'll return False early.
            return False

        # 2. Delete node from LlamaIndex
        try:
            self.llama_memory.index.delete_nodes([block_id])
            # Persist changes in LlamaIndex storage (ChromaDB)
            self.llama_memory.storage_context.persist(persist_dir=self.llama_memory.chroma_path)
            # Also persist potential graph store changes (though delete_nodes might not affect SimpleGraphStore directly)
            self.llama_memory._persist_graph_store()
            logger.info(f"Successfully deleted node {block_id} from LlamaIndex.")
            
            # 3. Store proof of deletion in block_proofs table (Phase 7)
            if commit_hash:
                self._store_block_proof(block_id, commit_hash, "delete", "Block deleted")
                
        except ValueError as ve:
             # llama_index raises ValueError if the node doesn't exist
             logger.warning(f"Node {block_id} not found in LlamaIndex for deletion (or already deleted): {ve}")
             # Continue as success, since the desired state (not indexed) is achieved.
             
             # Still store proof of deletion even if node wasn't in LlamaIndex
             if commit_hash:
                self._store_block_proof(block_id, commit_hash, "delete", "Block deleted (not found in index)")
                
        except Exception as e:
            logger.error(f"Failed to delete node {block_id} from LlamaIndex: {e}", exc_info=True)
            # State is inconsistent: Deleted from Dolt, but not from LlamaIndex.
            # Proper atomicity (Task 3.4) would require rollback.
            
            # Still store proof of deletion since the Dolt operation succeeded
            if commit_hash:
                self._store_block_proof(block_id, commit_hash, "delete", "Block deleted (index deletion failed)")
                
            return False

        logger.info(f"Successfully deleted memory block {block_id} from Dolt and LlamaIndex.")
        return True

    def query_semantic(self, query_text: str, top_k: int = 5) -> List[MemoryBlock]:
        """
        Performs a semantic search using LlamaIndex and retrieves full blocks from Dolt.

        Args:
            query_text: The text query for semantic search.
            top_k: The maximum number of results to return.

        Returns:
            A list of relevant MemoryBlock objects, potentially fewer than top_k if retrieval fails for some IDs.
        """
        logger.info(f"Performing semantic query: '{query_text}' (top_k={top_k})")
        if not self.llama_memory.is_ready():
            logger.error("LlamaMemory backend is not ready. Cannot perform semantic query.")
            return []

        retrieved_blocks: List[MemoryBlock] = []
        try:
            # 1. Query LlamaIndex vector store
            nodes_with_scores = self.llama_memory.query_vector_store(query_text, top_k=top_k)

            if not nodes_with_scores:
                logger.info("Semantic query returned no results from LlamaIndex.")
                return []

            # 2. Extract block IDs and retrieve full blocks from Dolt
            block_ids = [node.node.id_ for node in nodes_with_scores if node.node and node.node.id_]
            logger.info(f"LlamaIndex query returned {len(block_ids)} potential block IDs: {block_ids}")

            # Consider adding a cache here later if performance becomes an issue
            for block_id in block_ids:
                try:
                    # 3. Retrieve full block from Dolt using existing method
                    block = self.get_memory_block(block_id)
                    if block:
                        # TODO: Consider adding relevance score from LlamaIndex to the returned block
                        # (Requires modifying MemoryBlock schema or returning a different structure)
                        retrieved_blocks.append(block)
                    else:
                        logger.warning(f"Could not retrieve block with ID {block_id} from Dolt, though it was found in LlamaIndex.")
                except Exception as e_get:
                     logger.error(f"Error retrieving block {block_id} from Dolt during semantic query: {e_get}", exc_info=True)
                     # Continue to try retrieving other blocks

            logger.info(f"Semantic query processing complete. Retrieved {len(retrieved_blocks)} full blocks from Dolt.")
            return retrieved_blocks

        except Exception as e:
            logger.error(f"Error during semantic query execution: {e}", exc_info=True)
            return [] # Return empty list on major query error

    def get_blocks_by_tags(self, tags: List[str], match_all: bool = True) -> List[MemoryBlock]:
        """
        Retrieves MemoryBlocks based on tags by querying Dolt directly.

        Args:
            tags: A list of tags to filter by.
            match_all: If True, blocks must have all tags. If False, blocks must have at least one tag.

        Returns:
            A list of matching MemoryBlock objects.
        """
        logger.info(f"Getting blocks by tags: {tags} (match_all={match_all})")
        try:
            # Call the new reader function
            # Assumes read_memory_blocks_by_tags is imported
            matching_blocks = read_memory_blocks_by_tags(
                db_path=self.dolt_db_path,
                tags=tags,
                match_all=match_all
                # branch='main' # Or allow specifying branch if needed
            )
            return matching_blocks
        except Exception as e:
            logger.error(f"Error retrieving blocks by tags ({tags}): {e}", exc_info=True)
            return [] # Return empty list on error

    def get_forward_links(self, block_id: str, relation: Optional[str] = None) -> List[BlockLink]:
        """
        Retrieves outgoing links from a specific block.

        Args:
            block_id: The ID of the source block.
            relation: Optional filter for the relationship type.

        Returns:
            A list of BlockLink objects representing the forward links.
        """
        logger.info(f"Getting forward links for block: {block_id} (relation={relation})")
        forward_links: List[BlockLink] = []
        
        try:
            # Escape input values for SQL query
            escaped_block_id = _escape_sql_string(block_id)
            
            # Build the query based on whether relation is specified
            if relation:
                escaped_relation = _escape_sql_string(relation)
                query = f"""
                SELECT from_id, to_id, relation 
                FROM block_links 
                WHERE from_id = {escaped_block_id} AND relation = {escaped_relation}
                """
            else:
                query = f"""
                SELECT from_id, to_id, relation 
                FROM block_links 
                WHERE from_id = {escaped_block_id}
                """
            
            logger.debug(f"Executing forward links query: {query}")
            result = self.repo.sql(query=query, result_format='json')
            
            # Process results
            if result and 'rows' in result and result['rows']:
                logger.info(f"Found {len(result['rows'])} forward links for block {block_id}")
                for row in result['rows']:
                    # Convert SQL results to BlockLink objects
                    link = BlockLink(
                        to_id=row['to_id'],
                        relation=row['relation']
                    )
                    forward_links.append(link)
            else:
                logger.info(f"No forward links found for block {block_id}")
                
            return forward_links
            
        except Exception as e:
            logger.error(f"Error retrieving forward links for block {block_id}: {e}", exc_info=True)
            return []

    def get_backlinks(self, block_id: str, relation: Optional[str] = None) -> List[BlockLink]:
        """
        Retrieves incoming links to a specific block.

        Args:
            block_id: The ID of the target block.
            relation: Optional filter for the relationship type.

        Returns:
            A list of BlockLink objects representing the backlinks.
        """
        logger.info(f"Getting backlinks for block: {block_id} (relation={relation})")
        backlinks: List[BlockLink] = []
        
        try:
            # Escape input values for SQL query
            escaped_block_id = _escape_sql_string(block_id)
            
            # Build the query based on whether relation is specified
            if relation:
                escaped_relation = _escape_sql_string(relation)
                query = f"""
                SELECT from_id, to_id, relation 
                FROM block_links 
                WHERE to_id = {escaped_block_id} AND relation = {escaped_relation}
                """
            else:
                query = f"""
                SELECT from_id, to_id, relation 
                FROM block_links 
                WHERE to_id = {escaped_block_id}
                """
            
            logger.debug(f"Executing backlinks query: {query}")
            result = self.repo.sql(query=query, result_format='json')
            
            # Process results
            if result and 'rows' in result and result['rows']:
                logger.info(f"Found {len(result['rows'])} backlinks for block {block_id}")
                for row in result['rows']:
                    # BlockLink constructor expects to_id, so we need to adjust 
                    # when creating from backlinks table data
                    link = BlockLink(
                        to_id=row['from_id'],  # The "from" block is our target for backlinks
                        relation=row['relation']
                    )
                    backlinks.append(link)
            else:
                logger.info(f"No backlinks found for block {block_id}")
                
            return backlinks
            
        except Exception as e:
            logger.error(f"Error retrieving backlinks for block {block_id}: {e}", exc_info=True)
            return []

    # Optional: Add chat history methods if needed
    # def read_history_dicts(self, ...) -> List[Dict[str, Any]]: ...
    # def write_history_dicts(self, messages: List[Dict[str, Any]]) -> None: ...

    # TODO: (Optional) Store commit hash in block_proofs (Phase 7)
    def _ensure_block_proofs_table_exists(self) -> bool:
        """
        Ensures that the block_proofs table exists in the Dolt database.
        Creates it if it does not exist.
        
        The block_proofs table tracks the commit hash for each operation
        on a memory block, enabling historical proof tracking.
        
        Returns:
            bool: True if the table exists or was created successfully, False otherwise.
        """
        logger.info("Ensuring block_proofs table exists in Dolt database")
        try:
            # Check if the table already exists
            table_check_query = "SHOW TABLES LIKE 'block_proofs'"
            table_check_result = self.repo.sql(query=table_check_query, result_format='json')
            
            if table_check_result and 'rows' in table_check_result and table_check_result['rows']:
                logger.info("block_proofs table already exists")
                return True
                
            # Create the table if it doesn't exist
            # Use VARCHAR instead of TEXT to match the memory_blocks table column types
            create_table_query = """
            CREATE TABLE block_proofs (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                block_id VARCHAR(255) NOT NULL,
                commit_hash VARCHAR(255) NOT NULL,
                operation VARCHAR(10) NOT NULL CHECK (operation IN ('create', 'update', 'delete')),
                timestamp DATETIME NOT NULL,
                INDEX block_id_idx (block_id)
            );
            """
            
            self.repo.sql(query=create_table_query)
            logger.info("Successfully created block_proofs table")
            
            # Commit the table creation
            self.repo.add(['block_proofs'])
            self.repo.commit('Create block_proofs table for tracking block history')
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to ensure block_proofs table exists: {e}", exc_info=True)
            return False
            
    def format_commit_message(self, operation: str, block_id: str, change_summary: Optional[str] = None, extra_info: Optional[str] = None) -> str:
        """
        Format a standardized commit message for block operations.
        
        Args:
            operation: The operation type ('create', 'update', or 'delete')
            block_id: The ID of the block being operated on
            change_summary: Optional summary of changes. Defaults to 'No significant changes'
            extra_info: Optional additional metadata (e.g., actor_identity_id, tool_name, session_id)
            
        Returns:
            Formatted commit message following the standard: 
            "{OPERATION}: {block_id} - {summary_of_change} [{extra_info}]" if extra_info is provided,
            or "{OPERATION}: {block_id} - {summary_of_change}" otherwise
        """
        # Standardize operation to uppercase
        operation_upper = operation.upper()
        
        # Use default summary if none provided
        if not change_summary:
            change_summary = "No significant changes"
            
        # Format according to the standard
        message = f"{operation_upper}: {block_id} - {change_summary}"
        
        # Append extra info if provided
        if extra_info:
            message += f" [{extra_info}]"
            
        return message

    def _store_block_proof(self, block_id: str, commit_hash: str, operation: str, change_summary: Optional[str] = None) -> bool:
        """
        Stores a proof record in the block_proofs table.
        
        Args:
            block_id: The ID of the block that was modified
            commit_hash: The Dolt commit hash after the operation
            operation: The type of operation ('create', 'update', or 'delete')
            change_summary: Optional summary of changes. Defaults to 'No significant changes'
            
        Returns:
            bool: True if the proof was stored successfully, False otherwise
        """
        if not commit_hash:
            logger.warning(f"Cannot store block proof for {block_id}: No commit hash provided")
            return False
            
        try:
            # Ensure the table exists
            if not self._ensure_block_proofs_table_exists():
                return False
                
            # Format values for the query
            escaped_block_id = _escape_sql_string(block_id)
            escaped_commit_hash = _escape_sql_string(commit_hash)
            escaped_operation = _escape_sql_string(operation)
            now = datetime.datetime.now().isoformat(sep=' ', timespec='seconds')
            escaped_timestamp = _escape_sql_string(now)
            
            # Insert the proof record
            query = f"""
            INSERT INTO block_proofs (block_id, commit_hash, operation, timestamp)
            VALUES ({escaped_block_id}, {escaped_commit_hash}, {escaped_operation}, {escaped_timestamp});
            """
            
            self.repo.sql(query=query)
            
            # Generate standardized commit message
            commit_message = self.format_commit_message(operation, block_id, change_summary)
            
            # Log the commit message before submitting
            logger.info(f"Commit message: {commit_message}")
            
            # Commit the changes to the block_proofs table
            self.repo.add(['block_proofs'])
            self.repo.commit(commit_message)
            
            logger.info(f"Stored {operation} proof for block {block_id} with commit hash {commit_hash}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store block proof for {block_id}: {e}", exc_info=True)
            return False

    def get_block_proofs(self, block_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all proof records for a specific block_id.
        
        Args:
            block_id: The ID of the block to retrieve proofs for
            
        Returns:
            A list of dictionaries containing proof records, each with
            fields: id, block_id, commit_hash, operation, and timestamp
        """
        logger.info(f"Retrieving proof records for block: {block_id}")
        proofs = []
        
        try:
            # Ensure the table exists
            if not self._ensure_block_proofs_table_exists():
                return []
                
            # Escape the block_id for SQL
            escaped_block_id = _escape_sql_string(block_id)
            
            # Query for proofs
            query = f"""
            SELECT id, block_id, commit_hash, operation, timestamp
            FROM block_proofs
            WHERE block_id = {escaped_block_id}
            ORDER BY timestamp DESC;
            """
            
            result = self.repo.sql(query=query, result_format='json')
            
            if result and 'rows' in result:
                proofs = result['rows']
                logger.info(f"Found {len(proofs)} proof records for block {block_id}")
            else:
                logger.info(f"No proof records found for block {block_id}")
                
            return proofs
            
        except Exception as e:
            logger.error(f"Failed to retrieve proof records for block {block_id}: {e}", exc_info=True)
            return [] 