import os
import logging
import chromadb
from llama_index.core import StorageContext, VectorStoreIndex, load_index_from_storage
from llama_index.vector_stores.chroma import ChromaVectorStore
from typing import List, Optional

# Local schema import (assuming it will exist)
# from .schemas.memory_block import MemoryBlock

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
DEFAULT_CHROMA_PATH = "./storage/chroma"
DEFAULT_COLLECTION_NAME = "cogni_memory_poc"


class LlamaMemory:
    """
    Manages interactions with the LlamaIndex memory system, using ChromaDB as the backend.

    Handles initialization, indexing of MemoryBlocks, and querying.
    """

    def __init__(
        self,
        chroma_path: str = DEFAULT_CHROMA_PATH,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        # Add embedding model config later if needed
    ):
        """
        Initializes the LlamaMemory system.

        Args:
            chroma_path: Path to the directory for ChromaDB persistent storage.
            collection_name: Name of the collection within ChromaDB.
        """
        self.chroma_path = chroma_path
        self.collection_name = collection_name
        self.index = None
        self.query_engine = None
        self.client = None
        self.vector_store = None

        logging.info(f"Initializing LlamaMemory with ChromaDB path: {self.chroma_path} and collection: {self.collection_name}")

        try:
            # 1. Ensure ChromaDB directory exists
            if not os.path.exists(self.chroma_path):
                os.makedirs(self.chroma_path)
                logging.info(f"Created ChromaDB storage directory: {self.chroma_path}")
            else:
                logging.info(f"ChromaDB storage directory already exists: {self.chroma_path}")

            # 2. Initialize ChromaDB client
            self.client = chromadb.PersistentClient(path=self.chroma_path)
            logging.info(f"Initialized ChromaDB PersistentClient at: {self.chroma_path}")

            # 3. Get or create the ChromaDB collection
            chroma_collection = self.client.get_or_create_collection(self.collection_name)
            logging.info(f"Ensured ChromaDB collection '{self.collection_name}' exists.")

            # 4. Initialize LlamaIndex ChromaVectorStore with the collection
            self.vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
            logging.info(f"Initialized ChromaVectorStore with collection: {self.collection_name}")

            # 5. Create StorageContext
            self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
            logging.info("Created StorageContext.")

            # 6. Load or Create Index
            try:
                # Attempt to load the index from storage
                self.index = load_index_from_storage(self.storage_context)
                logging.info("Loaded existing LlamaIndex index from storage.")
            except ValueError:
                # If index doesn't exist (e.g., first run), create it empty
                logging.info("No existing index found. Creating a new VectorStoreIndex.")
                # We need nodes to create an index, but we can create it empty and add later
                # For now, let's just log this. The index will be properly formed on first insertion.
                # Alternatively, create an empty index if supported, or just prepare context
                # For simplicity, we will rely on index being created/updated on first add_block
                # Or, initialize with an empty index if the API supports it cleanly.
                # Let's assume VectorStoreIndex can be initialized directly with storage_context
                # If this causes issues, we'll adjust.
                self.index = VectorStoreIndex.from_vector_store(
                    vector_store=self.vector_store,
                    storage_context=self.storage_context
                )
                logging.info("Initialized new empty VectorStoreIndex.")


            # 7. Create Query Engine
            if self.index:
                self.query_engine = self.index.as_query_engine()
                logging.info("Created query engine from index.")
            else:
                # This case might happen if index creation failed silently or needs nodes
                logging.warning("Index could not be loaded or created. Query engine not available.")


            logging.info(f"LlamaMemory initialization complete. Ready: {self.is_ready()}")

        except Exception as e:
            logging.error(f"Failed to initialize LlamaMemory: {e}", exc_info=True)
            # Ensure partial states are None if init fails
            self.index = None
            self.query_engine = None
            self.vector_store = None
            self.client = None


    def is_ready(self) -> bool:
        """Check if the memory system is fully initialized and ready."""
        return bool(self.index and self.query_engine and self.vector_store and self.client)

    def add_block(self, block): # block should be MemoryBlock type hint later
        """
        Converts a MemoryBlock to a LlamaIndex Node and adds it to the index.
        (Placeholder - requires MemoryBlock schema and Node conversion logic)
        """
        if not self.is_ready():
            logging.error("LlamaMemory is not ready. Cannot add block.")
            return

        logging.info(f"Received block to add (ID: {getattr(block, 'id', 'N/A')}).")
        # 1. Convert MemoryBlock to LlamaIndex Node(s)
        #    - This will involve mapping fields (text, metadata, etc.)
        #    - Need the MemoryBlock schema definition first.
        # node = self._convert_block_to_node(block)
        nodes = [] # Placeholder
        if not nodes:
             logging.warning("Node conversion not implemented yet.")
             return

        # 2. Insert Node(s) into the index
        try:
            self.index.insert_nodes(nodes)
            logging.info(f"Successfully inserted nodes for block ID: {getattr(block, 'id', 'N/A')}")
            # Optionally, trigger index refresh or check persistence
        except Exception as e:
            logging.error(f"Failed to insert nodes for block ID {getattr(block, 'id', 'N/A')}: {e}", exc_info=True)


    def query(self, query_text: str) -> Optional[List]: # Return type TBD (LlamaIndex Response or List[MemoryBlock])
        """
        Performs a semantic query against the indexed MemoryBlocks.
        (Placeholder - requires response handling)
        """
        if not self.is_ready():
            logging.error("LlamaMemory is not ready. Cannot query.")
            return None

        logging.info(f'Performing query: "{query_text}"')
        try:
            response = self.query_engine.query(query_text)
            logging.info(f"Query successful. Response: {response}") # Log basic response for now
            # TODO: Process response (e.g., extract nodes, convert back to MemoryBlocks?)
            return response # Return raw response for now
        except Exception as e:
            logging.error(f"Query failed: {e}", exc_info=True)
            return None

    # --- Helper methods (Potentially) ---
    # def _convert_block_to_node(self, block: MemoryBlock) -> Node:
    #     pass


if __name__ == "__main__":
    print("Attempting to initialize LlamaMemory...")
    memory = LlamaMemory()

    if memory.is_ready():
        print("-" * 20)
        print("LlamaMemory initialized successfully.")
        print(f"  Chroma Path: {memory.chroma_path}")
        print(f"  Collection Name: {memory.collection_name}")
        print(f"  Index object: {memory.index}")
        print(f"  Query Engine: {memory.query_engine}")
        print("-" * 20)
        # Example placeholder usage (will fail until add_block/query are implemented)
        # print("Attempting placeholder query...")
        # response = memory.query("test query")
        # print(f"Placeholder query response: {response}")
    else:
        print("LlamaMemory initialization failed.") 