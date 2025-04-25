"""
Core StructuredMemoryBank class for managing MemoryBlocks.

This class orchestrates interactions between the persistent Dolt storage
and the LlamaIndex (ChromaDB) indexing/retrieval system.
"""

import logging
from typing import List, Dict, Any, Optional
import datetime

# Dolt Interactions
from doltpy.cli import Dolt
from experiments.src.memory_system.dolt_reader import read_memory_block, read_memory_blocks_by_tags # Assuming read_memory_blocks will be needed
from experiments.src.memory_system.dolt_writer import write_memory_block_to_dolt, delete_memory_block_from_dolt, _escape_sql_string # Assuming write_memory_block_to_dolt and delete_memory_block_from_dolt will be needed

# LlamaIndex Interactions
from experiments.src.memory_system.llama_memory import LlamaMemory

# Schemas
from experiments.src.memory_system.schemas.memory_block import MemoryBlock
from experiments.src.memory_system.schemas.common import BlockLink

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

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
        self.llama_memory = LlamaMemory(chroma_path=chroma_path, collection_name=chroma_collection)

        if not self.llama_memory.is_ready():
            raise RuntimeError("Failed to initialize LlamaMemory backend.")

        logger.info(f"StructuredMemoryBank initialized. Dolt Path: {dolt_db_path}, LlamaIndex Ready: {self.llama_memory.is_ready()}")

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

        # TODO: Query node_schemas for latest version and set block.schema_version

        # 1. Write block data to Dolt memory_blocks table
        # Using auto_commit=True for now, which isn't ideal for atomicity with indexing.
        # The secure migration project should address transactional writes.
        # This also relies on the insecure manual escaping in dolt_writer.
        dolt_write_success, _ = write_memory_block_to_dolt(
            block=block,
            db_path=self.dolt_db_path,
            auto_commit=True
        )

        if not dolt_write_success:
            logger.error(f"Failed to write block {block.id} data to Dolt.")
            return False

        # TODO: Implement writing links to the separate block_links table.
        # The current write_memory_block_to_dolt writes links to a JSON column in memory_blocks,
        # which might be redundant or incorrect depending on the final design.

        # 2. Convert block to LlamaIndex Node(s) <- This step is redundant
        # try:
        #     node = memory_block_to_node(block)
        # except Exception as e:
        #     logger.error(f"Failed to convert block {block.id} to LlamaIndex node: {e}", exc_info=True)
        #     # Consider cleanup: Should we try to delete the Dolt record if indexing fails?
        #     # For now, we report failure but leave the Dolt record.
        #     return False

        # 3. Add block to LlamaIndex (add_block handles conversion internally)
        try:
            self.llama_memory.add_block(block) # add_block handles the node conversion internally now
            logger.info(f"Successfully indexed block {block.id} in LlamaIndex.")
        except Exception as e:
            logger.error(f"Failed to index block {block.id} in LlamaIndex: {e}", exc_info=True)
            # Consider cleanup: Delete Dolt record?
            return False

        # TODO: Implement transactional commit (Phase 2/3 of Secure Dolt Write Migration)
        # Currently relies on auto_commit=True in write_memory_block_to_dolt

        # TODO: (Optional) Store commit hash in block_proofs (Phase 7)

        logger.info(f"Successfully created and indexed memory block: {block.id}")
        return True

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

        # 2. Apply updates and validate
        try:
            # Create updated block data, ensuring updated_at is set
            update_payload = update_data.copy()
            update_payload['updated_at'] = datetime.datetime.now() # Use current time for update
            
            updated_block = existing_block.model_copy(update=update_payload)
            logger.debug(f"Block {block_id} updated in memory. New text: '{updated_block.text[:50]}...'")
        except Exception as e: # Catch potential Pydantic validation errors or others
            logger.error(f"Failed to apply updates or validate block {block_id}: {e}", exc_info=True)
            return False

        # 3. Write updated block to Dolt
        # Relies on insecure writer and auto_commit=True (not atomic)
        dolt_write_success, _ = write_memory_block_to_dolt(
            block=updated_block,
            db_path=self.dolt_db_path,
            auto_commit=True
        )
        if not dolt_write_success:
            logger.error(f"Failed to write updated block {block_id} data to Dolt.")
            # State is now inconsistent: update attempted but not saved in Dolt.
            return False

        # TODO: Update links in Dolt block_links table if links changed.

        # 4. Re-index in LlamaIndex
        try:
            self.llama_memory.update_block(updated_block)
            logger.info(f"Successfully re-indexed updated block {block_id} in LlamaIndex.")
        except Exception as e:
            logger.error(f"Failed to re-index updated block {block_id} in LlamaIndex: {e}", exc_info=True)
            # State is now inconsistent: Dolt updated, but LlamaIndex update failed.
            # Proper atomicity (Task 3.4) would require rollback here.
            return False

        logger.info(f"Successfully updated and re-indexed memory block: {block_id}")
        return True

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
        dolt_delete_success, _ = delete_memory_block_from_dolt(
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
        except ValueError as ve:
             # llama_index raises ValueError if the node doesn't exist
             logger.warning(f"Node {block_id} not found in LlamaIndex for deletion (or already deleted): {ve}")
             # Continue as success, since the desired state (not indexed) is achieved.
        except Exception as e:
            logger.error(f"Failed to delete node {block_id} from LlamaIndex: {e}", exc_info=True)
            # State is inconsistent: Deleted from Dolt, but not from LlamaIndex.
            # Proper atomicity (Task 3.4) would require rollback.
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
        repo = None
        forward_links: List[BlockLink] = []
        
        try:
            # Connect to Dolt repository
            repo = Dolt(self.dolt_db_path)
            
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
            result = repo.sql(query=query, result_format='json')
            
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
        repo = None
        backlinks: List[BlockLink] = []
        
        try:
            # Connect to Dolt repository
            repo = Dolt(self.dolt_db_path)
            
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
            result = repo.sql(query=query, result_format='json')
            
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
    pass # Placeholder 