import os
import logging
import chromadb
from llama_index.core import StorageContext, VectorStoreIndex, load_index_from_storage
from llama_index.core.schema import NodeWithScore  # Added import for return type
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.graph_stores.simple import SimpleGraphStore
from typing import List, Optional

# Local schema import (assuming it will exist)
from .schemas.memory_block import MemoryBlock
from .llamaindex_adapters import memory_block_to_node  # Added import for node conversion

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
        self.graph_store = None

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

            # 5. Initialize SimpleGraphStore for graph relationships
            self.graph_store = SimpleGraphStore()
            logging.info("Initialized SimpleGraphStore for graph relationships.")

            # 6. Create StorageContext with both stores
            self.storage_context = StorageContext.from_defaults(
                vector_store=self.vector_store,
                graph_store=self.graph_store
            )
            logging.info("Created StorageContext with vector and graph stores.")

            # 7. Load or Create Index
            try:
                # Attempt to load the index from storage
                self.index = load_index_from_storage(self.storage_context)
                logging.info("Loaded existing LlamaIndex index from storage.")
            except ValueError:
                # If index doesn't exist (e.g., first run), create it empty
                logging.info("No existing index found. Creating a new VectorStoreIndex.")
                self.index = VectorStoreIndex.from_vector_store(
                    vector_store=self.vector_store,
                    storage_context=self.storage_context
                )
                logging.info("Initialized new empty VectorStoreIndex.")


            # 8. Create Query Engine
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
            self.graph_store = None


    def is_ready(self) -> bool:
        """Check if the memory system is fully initialized and ready."""
        return bool(self.index and self.query_engine and self.vector_store and self.client)

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
            # Ensure changes are persisted to disk
            self.index.storage_context.persist()
            logging.info(f"Successfully inserted node for block ID: {block.id}")
        except Exception as e:
            logging.error(f"Failed to insert node for block ID {block.id}: {e}", exc_info=True)

        # Add graph relationships to graph store
        if hasattr(node, 'relationships') and node.relationships:
            for relationship_type, related_nodes in node.relationships.items():
                for related_node in related_nodes:
                    try:
                        self.graph_store.upsert_triplet(
                            subj=node.id_,
                            rel=relationship_type.name,
                            obj=related_node.node_id
                        )
                        logging.info(f"Added graph triplet: {node.id_} -[{relationship_type.name}]-> {related_node.node_id}")
                    except Exception as e:
                        logging.warning(f"Failed to add graph triplet for block {block.id}: {e}")

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
            # Ensure changes are persisted to disk
            self.index.storage_context.persist()
            logging.info(f"Successfully updated node for block ID: {block.id}")
            
            # 4. Update relationships in graph store
            if hasattr(node, 'relationships') and node.relationships:
                for relationship_type, related_nodes in node.relationships.items():
                    for related_node in related_nodes:
                        try:
                            self.graph_store.upsert_triplet(
                                subj=node.id_,
                                rel=relationship_type.name,
                                obj=related_node.node_id
                            )
                            logging.info(f"Updated graph triplet: {node.id_} -[{relationship_type.name}]-> {related_node.node_id}")
                        except Exception as e:
                            logging.warning(f"Failed to update graph triplet for block {block.id}: {e}")
                            
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
                logging.info(f"  Result {i+1}: Node ID {node_id}, Score: {score}")
                
            return nodes_with_scores
            
        except Exception as e:
            logging.error(f"Vector store query failed: {e}", exc_info=True)
            return []

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
            # Note: Implementation depends on the exact SimpleGraphStore API
            # Here we use get_rel_map which returns relationships in the graph
            backlinks = []
            
            # The SimpleGraphStore doesn't directly support querying by object,
            # so we need to extract this information from the full relationship map
            rel_map = self.graph_store.get_rel_map()
            
            # Iterate through all subjects and their relationships
            for subject_id, relations in rel_map.items():
                for rel_type, objects in relations.items():
                    # Check if any of the objects match the target block ID
                    if target_block_id in objects:
                        backlinks.append(subject_id)
                        logging.info(f"Found backlink: {subject_id} -[{rel_type}]-> {target_block_id}")
            
            logging.info(f"Found {len(backlinks)} backlinks to block {target_block_id}")
            return backlinks
            
        except Exception as e:
            logging.error(f"Failed to get backlinks for block ID {target_block_id}: {e}", exc_info=True)
            return []


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