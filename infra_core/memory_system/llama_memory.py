import os
import logging
import chromadb
from llama_index.core import StorageContext, VectorStoreIndex, load_index_from_storage
from llama_index.core.schema import NodeWithScore  # Added import for return type
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.graph_stores.simple import SimpleGraphStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.settings import Settings
from typing import List, Optional

# Local schema import (assuming it will exist)
from .schemas.memory_block import MemoryBlock
from .llamaindex_adapters import memory_block_to_node  # Added import for node conversion

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Constants
DEFAULT_CHROMA_PATH = "./storage/chroma"
DEFAULT_COLLECTION_NAME = "cogni_memory_poc"
DEFAULT_GRAPH_STORE_FILENAME = "graph_store.json"
IN_MEMORY_PATH = ":memory:"  # Define a constant for clarity


class LlamaMemory:
    """
    Manages interactions with the LlamaIndex memory system, using ChromaDB as the backend.

    Handles initialization, indexing of MemoryBlocks, and querying.
    """

    def __init__(
        self,
        chroma_path: str = DEFAULT_CHROMA_PATH,
        collection_name: str = DEFAULT_COLLECTION_NAME,
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
        self.graph_store = None
        self._is_in_memory = self.chroma_path == IN_MEMORY_PATH

        # Set up local embedding model instead of OpenAI
        logging.info("Setting up local HuggingFace embedding model")
        embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
        Settings.embed_model = embed_model
        logging.info("Local embedding model configured")

        if not self._is_in_memory:
            self.graph_store_path = os.path.join(self.chroma_path, DEFAULT_GRAPH_STORE_FILENAME)
        else:
            self.graph_store_path = None  # No persistence path for in-memory graph store

        logging.info(
            f"Initializing LlamaMemory. Path: '{self.chroma_path}', Collection: '{self.collection_name}', In-memory: {self._is_in_memory}"
        )

        try:
            if self._is_in_memory:
                # Use ephemeral client for true in-memory operation
                self.client = chromadb.Client()
                logging.info("Initialized ChromaDB EphemeralClient for in-memory operation.")
            else:
                # Persistent client logic
                if not os.path.exists(self.chroma_path):
                    os.makedirs(self.chroma_path)
                    logging.info(f"Created ChromaDB storage directory: {self.chroma_path}")
                else:
                    logging.info(f"ChromaDB storage directory already exists: {self.chroma_path}")
                self.client = chromadb.PersistentClient(path=self.chroma_path)
                logging.info(f"Initialized ChromaDB PersistentClient at: {self.chroma_path}")

            chroma_collection = self.client.get_or_create_collection(self.collection_name)
            logging.info(f"Ensured ChromaDB collection '{self.collection_name}' exists.")

            self.vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
            logging.info(f"Initialized ChromaVectorStore with collection: {self.collection_name}")

            # Initialize SimpleGraphStore (always in-memory for now if master is in-memory)
            # Or load if persistent and path exists
            if (
                not self._is_in_memory
                and self.graph_store_path
                and os.path.exists(self.graph_store_path)
            ):
                try:
                    self.graph_store = SimpleGraphStore.from_persist_path(self.graph_store_path)
                    logging.info(f"Loaded SimpleGraphStore from {self.graph_store_path}")
                except Exception as e:
                    logging.warning(
                        f"Failed to load graph store from {self.graph_store_path}, creating new: {e}"
                    )
                    self.graph_store = SimpleGraphStore()
            else:
                self.graph_store = SimpleGraphStore()
                logging.info(
                    "Initialized new SimpleGraphStore (will not persist if main DB is in-memory)."
                )

            self.storage_context = StorageContext.from_defaults(
                vector_store=self.vector_store, graph_store=self.graph_store
            )
            logging.info("Created StorageContext with vector and graph stores.")

            # Load or Create Index
            # For true in-memory, we always create a new index as there's no persistence to load from.
            if self._is_in_memory:
                logging.info("Creating new VectorStoreIndex for in-memory operation.")
                self.index = VectorStoreIndex.from_vector_store(
                    vector_store=self.vector_store, storage_context=self.storage_context
                )
                logging.info("Initialized new empty VectorStoreIndex for in-memory.")
            else:
                try:
                    self.index = load_index_from_storage(self.storage_context)
                    logging.info("Loaded existing LlamaIndex index from storage.")
                except ValueError:
                    logging.info("No existing index found. Creating a new VectorStoreIndex.")
                    self.index = VectorStoreIndex.from_vector_store(
                        vector_store=self.vector_store, storage_context=self.storage_context
                    )
                    logging.info("Initialized new empty VectorStoreIndex.")

            if self.index:
                self.query_engine = self.index.as_query_engine()
                logging.info("Created query engine from index.")
            else:
                logging.warning("Index could not be loaded or created. Query engine not available.")

            logging.info(f"LlamaMemory initialization complete. Ready: {self.is_ready()}")

        except Exception as e:
            logging.error(f"Failed to initialize LlamaMemory: {e}", exc_info=True)
            self.index = None
            self.query_engine = None
            self.vector_store = None
            self.client = None
            self.graph_store = None

    def is_ready(self) -> bool:
        """Check if the memory system is fully initialized and ready."""
        return bool(self.index and self.query_engine and self.vector_store and self.client)

    def _persist_graph_store(self):
        """Persists the graph store to disk."""
        if self.graph_store and not self._is_in_memory and self.graph_store_path:
            try:
                self.graph_store.persist(persist_path=self.graph_store_path)
                logging.debug(f"Persisted graph store to {self.graph_store_path}")
            except Exception as e:
                logging.error(f"Failed to persist graph store: {e}", exc_info=True)

    def add_block(self, block: MemoryBlock):
        """
        Converts a MemoryBlock to a LlamaIndex TextNode and adds it to the index.
        """
        if not self.is_ready():
            logging.error("LlamaMemory is not ready. Cannot add block.")
            return

        logging.info(f"Processing block to add (ID: {block.id}).")

        # Convert MemoryBlock to TextNode using adapter function
        node = memory_block_to_node(block)

        # Insert Node into the index
        try:
            self.index.insert_nodes([node])
            if not self._is_in_memory:
                # For persistent storage, explicitly persist changes.
                # This might be redundant if ChromaDB auto-persists with PersistentClient,
                # but explicit is often better.
                self.index.storage_context.persist(persist_dir=self.chroma_path)
            logging.info(f"Successfully inserted node for block ID: {block.id}")
        except Exception as e:
            logging.error(f"Failed to insert node for block ID {block.id}: {e}", exc_info=True)
            return  # Stop if vector insert fails

        # Add graph relationships to graph store
        graph_changed = False
        if hasattr(node, "relationships") and node.relationships:
            for relationship_type, related_nodes in node.relationships.items():
                for related_node in related_nodes:
                    try:
                        self.graph_store.upsert_triplet(
                            subj=node.id_, rel=relationship_type.name, obj=related_node.node_id
                        )
                        graph_changed = True  # Mark graph as changed
                        logging.info(
                            f"Added graph triplet: {node.id_} -[{relationship_type.name}]-> {related_node.node_id}"
                        )
                    except Exception as e:
                        logging.warning(f"Failed to add graph triplet for block {block.id}: {e}")

        # Persist graph store if it changed
        if graph_changed:
            self._persist_graph_store()

    def update_block(self, block: MemoryBlock):
        """
        Updates an existing memory block in the index.
        This is implemented as a delete + insert operation.

        Args:
            block: The updated MemoryBlock to store in the index.
        """
        if not self.is_ready():
            logging.error("LlamaMemory is not ready. Cannot update block.")
            return

        logging.info(f"Updating block (ID: {block.id}).")

        try:
            # 1. Delete the existing node with the same ID
            self.index.delete_nodes([block.id])

            # 2. Create a new node from the updated block
            node = memory_block_to_node(block)

            # 3. Insert the new node
            self.index.insert_nodes([node])
            if not self._is_in_memory:
                self.index.storage_context.persist(persist_dir=self.chroma_path)
            logging.info(f"Successfully updated node for block ID: {block.id}")

            # 4. Update relationships in graph store
            graph_changed = False
            if hasattr(node, "relationships") and node.relationships:
                # Note: SimpleGraphStore's upsert handles updates implicitly.
                # We might need more complex logic here if we need to REMOVE old relationships
                # before adding new ones for a true update.
                for relationship_type, related_nodes in node.relationships.items():
                    for related_node in related_nodes:
                        try:
                            self.graph_store.upsert_triplet(
                                subj=node.id_, rel=relationship_type.name, obj=related_node.node_id
                            )
                            graph_changed = True
                            logging.info(
                                f"Updated graph triplet: {node.id_} -[{relationship_type.name}]-> {related_node.node_id}"
                            )
                        except Exception as e:
                            logging.warning(
                                f"Failed to update graph triplet for block {block.id}: {e}"
                            )

            # Persist graph store if it changed
            if graph_changed:
                self._persist_graph_store()

        except Exception as e:
            logging.error(f"Failed to update node for block ID {block.id}: {e}", exc_info=True)

    def query_vector_store(self, query_text: str, top_k: int = 5) -> List[NodeWithScore]:
        """
        Performs semantic search against the indexed MemoryBlocks.

        Args:
            query_text: The text query to search for similar content.
            top_k: Maximum number of results to return.

        Returns:
            List of NodeWithScore objects containing the retrieved nodes and their similarity scores.
        """
        if not self.is_ready():
            logging.error("LlamaMemory is not ready. Cannot query vector store.")
            return []

        logging.info(f'Performing vector store query: "{query_text}" (top_k={top_k})')

        try:
            # Create retriever from the index
            retriever = self.index.as_retriever(similarity_top_k=top_k)

            # Retrieve nodes based on query
            nodes_with_scores = retriever.retrieve(query_text)

            num_results = len(nodes_with_scores)
            logging.info(f"Query successful. Retrieved {num_results} nodes.")

            # Log some basic info about results
            for i, node_with_score in enumerate(nodes_with_scores):
                node_id = node_with_score.node.id_
                score = node_with_score.score
                logging.info(f"  Result {i + 1}: Node ID {node_id}, Score: {score}")

            return nodes_with_scores

        except Exception as e:
            logging.error(f"Vector store query failed: {e}", exc_info=True)
            return []

    def query(
        self, query_text: str
    ) -> Optional[List]:  # Return type TBD (LlamaIndex Response or List[MemoryBlock])
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
            logging.info(f"Query successful. Response: {response}")  # Log basic response for now
            # TODO: Process response (e.g., extract nodes, convert back to MemoryBlocks?)
            return response
        except Exception as e:
            logging.error(f"Query failed: {e}", exc_info=True)
            return None

    def get_backlinks(self, target_block_id: str) -> List[str]:
        """
        Find all MemoryBlocks that link *to* a given block ID using the graph store.

        Args:
            target_block_id: The ID of the block to find references to

        Returns:
            List of block IDs that link to the target block
        """
        if not self.is_ready() or not self.graph_store:
            logging.error("LlamaMemory or graph store is not ready. Cannot get backlinks.")
            return []

        logging.info(f"Finding backlinks to block: {target_block_id}")

        try:
            # Get the relationship map from the graph store
            # SimpleGraphStore.get_rel_map() returns Dict[str, List[List[str]]]
            # Key: subject_id, Value: List of triplets involving that subject [subj, rel, obj]
            rel_map_dict = self.graph_store.get_rel_map()

            backlinks = []

            # Iterate through all triplets stored in the map
            for subject_id, triplets_list in rel_map_dict.items():
                for triplet in triplets_list:
                    # triplet is [subj, rel, obj]
                    if len(triplet) == 3:
                        subj, rel, obj = triplet
                        # Check if the object of the triplet matches the target block ID
                        if obj == target_block_id:
                            # Ensure we don't add duplicates if structure is redundant
                            if subj not in backlinks:
                                backlinks.append(subj)
                                logging.info(f"Found backlink: {subj} -[{rel}]-> {target_block_id}")
                    else:
                        logging.warning(f"Skipping malformed triplet in graph map: {triplet}")

            logging.info(f"Found {len(backlinks)} backlinks to block {target_block_id}")
            return backlinks

        except Exception as e:
            logging.error(
                f"Failed to get backlinks for block ID {target_block_id}: {e}", exc_info=True
            )
            return []

    def delete_block(self, block_id: str) -> None:
        """
        Deletes a memory block from the LlamaIndex index.

        Args:
            block_id: The ID of the block to delete.

        Raises:
            KeyError: If the block with the given ID is not found in the index.
            Exception: If there is an error during deletion.
        """
        if not self.is_ready():
            logging.error("LlamaMemory is not ready. Cannot delete block.")
            raise RuntimeError("LlamaMemory is not ready")

        logging.info(f"Deleting block from LlamaIndex (ID: {block_id}).")

        try:
            # Delete the node from the index
            self.index.delete_nodes([block_id])

            # Persist changes to disk to ensure they are saved
            if not self._is_in_memory:
                self.index.storage_context.persist(persist_dir=self.chroma_path)

            # Also handle graph relationships if needed
            graph_changed = False
            try:
                # Remove all relationships where this node is the subject
                triplets = self.graph_store.get_triplets_by_subj(block_id)
                for triplet in triplets:
                    self.graph_store.delete_triplet(subj=block_id, rel=triplet.rel, obj=triplet.obj)
                    graph_changed = True

                # Remove all relationships where this node is the object
                triplets = self.graph_store.get_triplets_by_obj(block_id)
                for triplet in triplets:
                    self.graph_store.delete_triplet(
                        subj=triplet.subj, rel=triplet.rel, obj=block_id
                    )
                    graph_changed = True

                # Persist graph changes if any were made
                if graph_changed:
                    self._persist_graph_store()

            except Exception as graph_e:
                logging.warning(
                    f"Error cleaning up graph relationships for block {block_id}: {graph_e}"
                )
                # Continue with deletion even if graph cleanup fails

            logging.info(f"Successfully deleted block {block_id} from LlamaIndex.")

        except KeyError:
            # Re-raise to allow caller to handle this specific case
            logging.warning(f"Block {block_id} not found in LlamaIndex.")
            raise
        except Exception as e:
            logging.error(f"Failed to delete block {block_id} from LlamaIndex: {e}", exc_info=True)
            raise


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
