"""
Core StructuredMemoryBank class for managing MemoryBlocks.

This class orchestrates interactions between the persistent Dolt storage
and the LlamaIndex (ChromaDB) indexing/retrieval system.
"""

import logging
from typing import List, Dict, Any, Optional
import datetime

# Dolt Interactions
from experiments.src.memory_system.dolt_reader import read_memory_block # Assuming read_memory_blocks will be needed
from experiments.src.memory_system.dolt_writer import write_memory_block_to_dolt # Assuming write_memory_block_to_dolt will be needed

# LlamaIndex Interactions
from experiments.src.memory_system.llama_memory import LlamaMemory

# Schemas
from experiments.src.memory_system.schemas.memory_block import MemoryBlock, BlockLink

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

        Args:
            block_id: The ID of the block to delete.

        Returns:
            True if deletion was successful, False otherwise.
        """
        logger.info(f"Attempting to delete memory block: {block_id}")
        # TODO: Delete block from Dolt memory_blocks (Needs SQL DELETE)
        # TODO: Delete links from Dolt block_links (Handled by CASCADE or needs explicit delete)
        # TODO: Delete node from LlamaIndex (using self.llama_memory.index.delete_nodes)
        # TODO: Commit changes in Dolt
        pass # Placeholder

    def query_semantic(self, query_text: str, top_k: int = 5) -> List[MemoryBlock]:
        """
        Performs a semantic search using LlamaIndex and retrieves full blocks from Dolt.

        Args:
            query_text: The text query for semantic search.
            top_k: The maximum number of results to return.

        Returns:
            A list of relevant MemoryBlock objects.
        """
        logger.info(f"Performing semantic query: '{query_text}' (top_k={top_k})")
        # TODO: Query LlamaIndex vector store (using self.llama_memory.query_vector_store)
        # TODO: Extract block IDs from the results
        # TODO: Retrieve full blocks from Dolt using the extracted IDs (batch read?)
        pass # Placeholder

    def get_blocks_by_tags(self, tags: List[str], match_all: bool = True) -> List[MemoryBlock]:
        """
        Retrieves MemoryBlocks based on tags.

        Args:
            tags: A list of tags to filter by.
            match_all: If True, blocks must have all tags. If False, blocks must have at least one tag.

        Returns:
            A list of matching MemoryBlock objects.
        """
        logger.info(f"Getting blocks by tags: {tags} (match_all={match_all})")
        # TODO: Implement querying Dolt's JSON tags column (using SQL JSON functions)
        # OR
        # TODO: Filter results from LlamaIndex metadata if tags are indexed there
        pass # Placeholder

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
        # TODO: Query Dolt block_links table for matching from_id
        # OR
        # TODO: Query LlamaIndex graph store (using self.llama_memory.graph_store)
        pass # Placeholder

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
        # TODO: Query Dolt block_links table for matching to_id
        # OR
        # TODO: Query LlamaIndex graph store (using self.llama_memory.get_backlinks and potentially filtering)
        pass # Placeholder

    # Optional: Add chat history methods if needed
    # def read_history_dicts(self, ...) -> List[Dict[str, Any]]: ...
    # def write_history_dicts(self, messages: List[Dict[str, Any]]) -> None: ...

    # TODO: (Optional) Store commit hash in block_proofs (Phase 7)
    pass # Placeholder 