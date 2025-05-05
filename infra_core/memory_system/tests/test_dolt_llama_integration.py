#!/usr/bin/env python3
"""
Integration tests for the Dolt to LlamaIndex sync process.
"""

import unittest
import shutil
import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone
import importlib
import tempfile
import subprocess

# Configure logging for tests
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add project root to path for imports
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent.parent  # Navigate up to project root
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Skip tests if doltpy or dolt cli not available
DOLTPY_AVAILABLE = importlib.util.find_spec('doltpy') is not None
DOLT_CLI_AVAILABLE = shutil.which('dolt') is not None
SKIP_REASON = ""
if not DOLTPY_AVAILABLE:
    SKIP_REASON = "doltpy library not installed"
elif not DOLT_CLI_AVAILABLE:
    SKIP_REASON = "Dolt CLI not found in PATH"

# Local imports
# These might need adjustment based on exact location and structure
IMPORTS_AVAILABLE = False # Default to False
try:
    from infra_core.memory_system.schemas.memory_block import MemoryBlock, BlockLink, ConfidenceScore  # noqa: E402
    from infra_core.memory_system.dolt_writer import write_memory_block_to_dolt  # noqa: E402
    from experiments.scripts.sync_dolt_to_llamaindex import sync_dolt_to_llamaindex  # noqa: E402
    from infra_core.memory_system.llama_memory import LlamaMemory  # noqa: E402
    from infra_core.memory_system.initialize_dolt import initialize_dolt_db # noqa: E402
    IMPORTS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import necessary modules, skipping integration tests: {e}")
    if not SKIP_REASON: # Prioritize Dolt availability reasons
        SKIP_REASON = f"Failed to import necessary modules: {e}"


def create_test_blocks():
    """Create sample memory blocks for testing. (Copied from unit tests)"""
    blocks = []
    # Block 1: Basic block with tags
    blocks.append(MemoryBlock(
        id="int-test-block-1", # Using different ID prefix for integration tests
        type="doc",
        schema_version=1,
        text="This is an integration test document. It relates to system setup.",
        tags=["integration", "setup", "sync"],
        metadata={"title": "Integration Test Doc 1", "priority": 1},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        created_by="integration_test"
    ))
    # Block 2: Block with links to Block 1
    blocks.append(MemoryBlock(
        id="int-test-block-2",
        type="knowledge",
        schema_version=1,
        text="This knowledge block depends on the setup document.",
        tags=["knowledge", "dependency"],
        metadata={"title": "Knowledge Block 2", "source": "derived"},
        links=[BlockLink(to_id="int-test-block-1", relation="related_to")],
        confidence=ConfidenceScore(ai=0.75, human=0.9),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        created_by="integration_test"
    ))
    # Block 3: Task block
    blocks.append(MemoryBlock(
        id="int-test-block-3",
        type="task",
        schema_version=1,
        text="Verify the sync process correctly handles document, knowledge, and task types.",
        tags=["task", "verification"],
        metadata={"title": "Task: Verify Sync Types", "status": "pending"},
        links=[BlockLink(to_id="int-test-block-1", relation="related_to")],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        created_by="integration_test"
    ))
    return blocks

@unittest.skipIf(not DOLTPY_AVAILABLE or not DOLT_CLI_AVAILABLE or not IMPORTS_AVAILABLE, SKIP_REASON)
class TestSyncDoltToLlamaIndexIntegration(unittest.TestCase):
    """
    Integration tests for the Dolt to LlamaIndex sync process.
    These tests use actual Dolt databases and LlamaIndex storage.
    """

    def setUp(self):
        """Set up test environment with temporary Dolt DB and LlamaIndex storage."""
        logger.info("Setting up integration test...")
        self.dolt_temp_dir = None # Initialize to None
        self.llama_temp_dir = None # Initialize to None
        try:
            # Create temporary directories
            dolt_dir = tempfile.mkdtemp(prefix="test_dolt_sync_")
            self.dolt_temp_dir = dolt_dir
            logger.info(f"Created temporary Dolt directory: {self.dolt_temp_dir}")

            llama_dir = tempfile.mkdtemp(prefix="test_llama_sync_")
            self.llama_temp_dir = llama_dir
            logger.info(f"Created temporary LlamaIndex directory: {self.llama_temp_dir}")

            # Use initialize_dolt_db script
            logger.info(f"Initializing Dolt DB using script for path: {self.dolt_temp_dir}")
            init_success = initialize_dolt_db(self.dolt_temp_dir)
            if not init_success:
                self.fail("Failed to initialize Dolt database using initialize_dolt_db script.")

            # Populate data using dolt_writer
            logger.info("Populating memory_blocks table with test data using dolt_writer...")
            test_blocks = create_test_blocks()
            for block in test_blocks:
                logger.debug(f"Writing block {block.id} to Dolt working set...")
                success, _ = write_memory_block_to_dolt(
                    block=block,
                    db_path=self.dolt_temp_dir,
                    auto_commit=False # Commit manually after all writes
                )
                if not success:
                    self.fail(f"Failed to write block {block.id} using write_memory_block_to_dolt.")
            logger.info(f"Successfully wrote {len(test_blocks)} blocks to Dolt working set.")

            # Commit the test data
            logger.info("Adding and committing test data to Dolt...")
            try:
                # Dolt Add
                add_result = subprocess.run(
                    ['dolt', 'add', 'memory_blocks'], # Add the specific table
                    cwd=self.dolt_temp_dir,
                    check=True, capture_output=True, text=True
                )
                logger.debug(f"Dolt add output:\n{add_result.stdout}")

                # Dolt Commit
                commit_result = subprocess.run(
                    ['dolt', 'commit', '-m', 'Add integration test data'],
                    cwd=self.dolt_temp_dir,
                    check=True, capture_output=True, text=True
                )
                logger.debug(f"Dolt commit output:\n{commit_result.stdout}")
                logger.info("Test data committed successfully.")

            except subprocess.CalledProcessError as e:
                logger.error(f"Dolt add/commit failed with exit code {e.returncode}")
                logger.error(f"Command: {' '.join(e.cmd)}")
                logger.error(f"Stderr:\n{e.stderr}")
                raise # Re-raise to fail test

        except Exception as e:
            logger.error(f"Error during setUp: {e}")
            # Ensure cleanup happens even if setup fails partially
            self.tearDown()
            raise # Re-raise exception to fail the test

    def tearDown(self):
        """Clean up temporary directories."""
        logger.info("Tearing down integration test...")
        # Use self attributes which are None if setup failed before assignment
        if self.dolt_temp_dir and os.path.exists(self.dolt_temp_dir):
            logger.debug(f"Removing temporary Dolt directory: {self.dolt_temp_dir}")
            shutil.rmtree(self.dolt_temp_dir)
        if self.llama_temp_dir and os.path.exists(self.llama_temp_dir):
            logger.debug(f"Removing temporary LlamaIndex directory: {self.llama_temp_dir}")
            shutil.rmtree(self.llama_temp_dir)

    def test_end_to_end_sync(self):
        """
        Test the full sync process from a temporary Dolt DB to LlamaIndex.
        """
        logger.info("Running end-to-end sync test...")

        # 1. Run the sync script
        logger.info(f"Running sync_dolt_to_llamaindex: Dolt={self.dolt_temp_dir}, Llama={self.llama_temp_dir}")
        sync_successful = sync_dolt_to_llamaindex(
            dolt_db_path=self.dolt_temp_dir,
            llama_storage_path=self.llama_temp_dir
        )
        self.assertTrue(sync_successful, "sync_dolt_to_llamaindex script failed to run.")
        logger.info("sync_dolt_to_llamaindex completed.")

        # 2. Initialize LlamaMemory with the synced data
        logger.info(f"Initializing LlamaMemory from: {self.llama_temp_dir}")
        try:
            llama_memory = LlamaMemory(chroma_path=self.llama_temp_dir)
            # Ensure the index is loaded - might require specific method call if lazy loading
            if not llama_memory.vector_store or not llama_memory.graph_store:
                 # Attempt to load if needed (adjust based on LlamaMemory implementation)
                 # llama_memory._load_index() # Assuming LlamaMemory loads eagerly now
                 # Check again
                 self.assertIsNotNone(llama_memory.vector_store, "Vector store not loaded after sync.")
                 self.assertIsNotNone(llama_memory.graph_store, "Graph store not loaded after sync.")

            # --- BEGIN Index Verification (Feedback) ---
            self.assertIsNotNone(llama_memory.vector_store, "Vector store should be initialized.")
            self.assertIsNotNone(llama_memory.graph_store, "Graph store should be initialized.")

            # Check node count in ChromaDB collection
            try:
                # Access the ChromaDB client and collection name from LlamaMemory
                chroma_client = llama_memory.client
                self.assertIsNotNone(chroma_client, "ChromaDB client should be initialized in LlamaMemory")
                chroma_collection = chroma_client.get_collection(llama_memory.collection_name)
                node_count = chroma_collection.count()
                expected_blocks = 3 # Based on create_test_blocks()
                self.assertEqual(node_count, expected_blocks, f"Expected {expected_blocks} nodes in ChromaDB, found {node_count}")
                logger.info(f"ChromaDB node count verified: {node_count}")
            except Exception as e:
                self.fail(f"Failed to verify node count in ChromaDB: {e}")
            # --- END Index Verification ---

            logger.info("LlamaMemory initialized successfully.")
        except Exception as e:
            self.fail(f"Failed to initialize LlamaMemory from synced directory: {e}")

        # 3. Perform verification queries
        logger.info("Performing verification queries...")

        # Vector Search Test (Existing)
        search_query = "integration test document system setup"
        logger.info(f"Performing vector search for: '{search_query}'")
        try:
            search_results = llama_memory.query_vector_store(search_query, top_k=3)
            # Log the actual node IDs retrieved
            retrieved_ids = [r.node.id_ for r in search_results]
            logger.info(f"Vector search retrieved node IDs: {retrieved_ids}")

            # Assert that the relevant block ID is found among the node IDs
            found_block_1 = any(
                result.node.id_ == "int-test-block-1"
                for result in search_results
            )
            self.assertTrue(found_block_1, f"Expected 'int-test-block-1' not found in retrieved node IDs: {retrieved_ids} for query '{search_query}'")
            logger.info("Vector search test passed.")

        except Exception as e:
            self.fail(f"Vector search failed: {e}")

        # --- BEGIN Graph Verification (Feedback) ---
        logger.info("Performing graph verification tests...")

        # Test Backlinks
        try:
            backlinks_to_1 = llama_memory.get_backlinks("int-test-block-1")
            logger.info(f"Backlinks found for int-test-block-1: {backlinks_to_1}")
            # Both block 2 and block 3 link to block 1 with 'related_to'
            self.assertIn("int-test-block-2", backlinks_to_1, "Block 2 should link to Block 1")
            self.assertIn("int-test-block-3", backlinks_to_1, "Block 3 should link to Block 1")
            logger.info("Backlink test passed.")
        except Exception as e:
            self.fail(f"Backlink test failed: {e}")

        # Test Forward Links / Graph Consistency
        try:
            # Get the full relationship map from the graph store
            # Expected structure based on SimpleGraphStore: Dict[str, List[List[str]]]
            # { subj_id: [ [subj_id, relation_name, obj_id], ... ], ... }
            rel_map = llama_memory.graph_store.get_rel_map()
            logger.info(f"Graph store rel_map: {rel_map}")

            # Check outgoing link from block 2
            block_2_triplets = rel_map.get("int-test-block-2", [])
            expected_b2_triplet = ["int-test-block-2", "NEXT", "int-test-block-1"] # 'related_to' maps to 'NEXT'
            self.assertIn(expected_b2_triplet, block_2_triplets, f"Expected forward link {expected_b2_triplet} not found for block 2")

            # Check outgoing link from block 3
            block_3_triplets = rel_map.get("int-test-block-3", [])
            expected_b3_triplet = ["int-test-block-3", "NEXT", "int-test-block-1"] # 'related_to' maps to 'NEXT'
            self.assertIn(expected_b3_triplet, block_3_triplets, f"Expected forward link {expected_b3_triplet} not found for block 3")

            # Optional: More rigorous check - ensure no unexpected links exist for these blocks
            self.assertEqual(len(block_2_triplets), 1, "Block 2 should only have one outgoing link defined in this test")
            self.assertEqual(len(block_3_triplets), 1, "Block 3 should only have one outgoing link defined in this test")

            logger.info("Forward link / graph consistency test passed.")

        except Exception as e:
             self.fail(f"Graph consistency test failed: {e}")
        # --- END Graph Verification ---

        logger.info("End-to-end sync test completed successfully.")

if __name__ == '__main__':
    unittest.main() 