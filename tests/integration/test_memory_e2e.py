"""
End-to-end tests for the Memory Architecture using BGE embeddings.

This test module demonstrates the complete flow:
1. Initialize memory components
2. Read actual content files
3. Create embeddings with BGE
4. Save to ChromaDB
5. Perform semantic queries
6. Verify results

Run with verbose logging:
pytest -xvs tests/integration/test_memory_e2e.py
"""

import os
import sys
import uuid
import pytest
import shutil
import tempfile
import logging
import warnings
import numpy as np
from numpy.linalg import norm
from datetime import datetime

# Silence warnings from dependencies
warnings.filterwarnings("ignore", message=".*No ONNX providers provided.*")
warnings.filterwarnings("ignore", category=UserWarning, module="chromadb")
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")
warnings.filterwarnings("ignore", category=UserWarning, module="torch")
warnings.filterwarnings("ignore", category=UserWarning, module="sentence_transformers")

# Configure logging - set default level to WARNING for most modules
logging.basicConfig(
    level=logging.WARNING,  # Default to WARNING to reduce noise
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Only show INFO logs for our test code by default
logger = logging.getLogger("memory_e2e_test")
logger.setLevel(logging.INFO)

# Silence third-party loggers by default
for module in ["chromadb", "urllib3", "sentence_transformers", "huggingface_hub", 
              "transformers", "tqdm"]:
    logging.getLogger(module).setLevel(logging.WARNING)

# Import memory components
try:
    from infra_core.memory.memory_indexer import init_embedding_function
    from infra_core.memory.memory_client import CogniMemoryClient
    from infra_core.memory.schema import MemoryBlock
    import chromadb
except ImportError:
    # Add project root to path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    from infra_core.memory.memory_indexer import init_embedding_function
    from infra_core.memory.memory_client import CogniMemoryClient
    from infra_core.memory.schema import MemoryBlock
    import chromadb


class TestMemoryE2E:
    """End-to-end tests for the Memory Architecture."""
    
    @pytest.fixture
    def test_memory_dirs(self):
        """Create temporary directories for test memory storage."""
        # Create temp dirs
        temp_dir = tempfile.mkdtemp()
        chroma_dir = os.path.join(temp_dir, "chroma")
        archive_dir = os.path.join(temp_dir, "archive")
        
        # Create dirs
        os.makedirs(chroma_dir, exist_ok=True)
        os.makedirs(archive_dir, exist_ok=True)
        
        yield {"root": temp_dir, "chroma": chroma_dir, "archive": archive_dir}
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def real_content_files(self):
        """Find real content files from the workspace."""
        # Get project root directory
        if os.path.exists('cogni_graph.md'):
            project_root = '.'
        elif os.path.exists('../cogni_graph.md'):
            project_root = '..'
        else:
            # If cogni_graph.md not found, return mock data
            logger.warning("cogni_graph.md not found, using mock data instead")
            return self.mock_content()
        
        # Find all markdown files in project root
        content_files = []
        if os.path.exists(os.path.join(project_root, 'cogni_graph.md')):
            content_files.append(os.path.join(project_root, 'cogni_graph.md'))
        
        # Add other interesting files if they exist
        for filename in ['CHARTER.md', 'MANIFESTO.md']:
            if os.path.exists(os.path.join(project_root, filename)):
                content_files.append(os.path.join(project_root, filename))
        
        logger.info(f"Found {len(content_files)} real content files")
        for file in content_files:
            logger.info(f"  - {file}")
        
        return content_files
    
    def mock_content(self):
        """Create mock content for testing if real files not available."""
        return [
            {
                "title": "Cogni Central Graph Node",
                "text": """
# 🔮 Cogni Central Graph Node

This is the meta-map of Cogni's mind: where vision, thought, and action converge.

[[rituals-and-flows]] – organic logs and reflections from Cogni
[[infra_core]] – The core functionality for Cogni and CogniDAO
[[cogni_spirits]] – embedded values and spirit guides for Cogni
[[CHARTER]] – foundational principles
[[MANIFESTO]] – core intent and vision

This is the one node where the full system touches.
                """,
                "tags": ["#thought", "#approved"],
                "source": "cogni_graph.md"
            },
            {
                "title": "Memory Architecture",
                "text": """
# Memory Architecture

The Cogni Memory Architecture provides semantic search over Logseq blocks:
- Tiered storage with hot and cold archives
- Vector embeddings for semantic search
- Tag-based filtering
- Open-source BGE embedding model

This enables Cogni to recall relevant information when needed.
                """,
                "tags": ["#thought", "#broadcast"],
                "source": "memory_architecture.md"
            },
            {
                "title": "Python Integration",
                "text": """
# Python Integration

Python is a powerful programming language used throughout the Cogni system.
Key features include:
- Easy integration with ML models
- Robust package ecosystem
- Clean syntax and readability

This makes it ideal for implementing Cogni's cognitive capabilities.
                """,
                "tags": ["#thought"],
                "source": "python_integration.md"
            }
        ]
    
    def test_memory_e2e_flow(self, test_memory_dirs, real_content_files, caplog):
        """Test the end-to-end memory flow with BGE embeddings."""
        try:
            # Check if sentence-transformers is installed without importing it
            import importlib.util
            if importlib.util.find_spec("sentence_transformers") is None:
                pytest.skip("sentence-transformers package not installed")
        except ImportError:
            pytest.skip("sentence-transformers package not installed")
        
        # Set logging based on pytest verbosity
        verbose = False
        for arg in sys.argv:
            if arg in ['-v', '-vv', '-vvv', '--verbose', '-x', '-xvs']:
                verbose = True
                break
                
        if verbose:
            # Enable all logs in verbose mode
            caplog.set_level(logging.DEBUG)
            logger.setLevel(logging.DEBUG)
            # Also enable infra_core logs
            logging.getLogger("infra_core").setLevel(logging.DEBUG)
        else:
            # Keep it quiet in normal mode
            caplog.set_level(logging.INFO)
            logger.setLevel(logging.INFO)
            # Explicitly silence external logs
            for module in ["chromadb", "urllib3", "sentence_transformers", "huggingface_hub", 
                          "transformers", "tqdm"]:
                logging.getLogger(module).setLevel(logging.WARNING)
        
        # Step 1: Log test start
        logger.info("=== Starting Memory E2E Test ===")
        logger.debug(f"Using test directories: {test_memory_dirs}")
        
        # Step 2: Initialize the embedding function
        logger.info("Initializing BGE embedding function...")
        embed_fn = init_embedding_function("bge")
        
        # Step 3: Create the ChromaDB collection directly
        logger.info("Initializing ChromaDB storage...")
        collection_name = "cogni-memory"
        
        # Initialize ChromaDB client directly
        logger.debug("Creating ChromaDB client...")
        chroma_client = chromadb.PersistentClient(
            path=test_memory_dirs["chroma"],
            settings=chromadb.Settings(
                anonymized_telemetry=False,
                allow_reset=True,
                chroma_server_ssl_enabled=False
            )
        )
        
        # Create the collection first
        try:
            # Try to get the collection
            logger.debug(f"Checking if collection '{collection_name}' exists...")
            try:
                collection = chroma_client.get_collection(name=collection_name)
                logger.debug(f"Collection '{collection_name}' already exists")
            except Exception:
                # Collection doesn't exist, create it
                logger.debug(f"Creating new collection '{collection_name}'...")
                collection = chroma_client.create_collection(name=collection_name)
                logger.debug(f"Collection '{collection_name}' created successfully")
        except Exception as e:
            logger.error(f"Error with ChromaDB collection: {e}")
            raise
        
        # Step 4: Create memory client
        logger.info("Creating memory client...")
        
        # First, create storage components manually to reuse existing client
        from infra_core.memory.storage import ChromaStorage, ArchiveStorage
        
        # Initialize storage with the existing client
        chroma_storage = ChromaStorage(test_memory_dirs["chroma"], collection_name)
        # Important: replace the client with our existing one to avoid conflicts
        chroma_storage.client = chroma_client
        chroma_storage.collection = collection
        
        # Initialize archive storage
        archive_storage = ArchiveStorage(test_memory_dirs["archive"])
        
        # Create client with manual storage initialization
        client = CogniMemoryClient(
            chroma_path=test_memory_dirs["chroma"],
            archive_path=test_memory_dirs["archive"],
            collection_name=collection_name
        )
        
        # Replace the storage components with our manually initialized ones
        client.chroma_storage = chroma_storage
        client.archive_storage = archive_storage
        client.storage.chroma = chroma_storage
        client.storage.archive = archive_storage
        
        # Ensure client is correctly initialized
        logger.debug("Verifying memory client initialization...")
        block_count = client.count_blocks()
        logger.debug(f"Initial block count: {block_count}")
        
        # Step 5: Create memory blocks from real files
        logger.info("Creating memory blocks from real files...")
        memory_blocks = []
        
        # Check if we have real content or need to use mock data
        if isinstance(real_content_files, list) and all(isinstance(item, str) for item in real_content_files):
            # Real content files
            logger.info("Using real content files...")
            
            for file_path in real_content_files:
                # Read the file content
                with open(file_path, 'r') as f:
                    content = f.read()
                
                # Get file name only
                file_name = os.path.basename(file_path)
                logger.info(f"Processing {file_name}...")
                
                # Generate embeddings
                logger.debug(f"Generating embedding for: {file_name}")
                # Note: we avoid show_progress_bar parameter if it's unsupported in the installed version
                embedding = embed_fn([content])[0]
                
                # Create block with tags based on filename
                tags = ["#thought"]  # Default tag
                
                # Create block
                block = MemoryBlock(
                    id=str(uuid.uuid4()),
                    text=content,
                    tags=tags,
                    source_file=file_name,
                    embedding=embedding,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                
                # Add to blocks list
                memory_blocks.append(block)
                
                # Log embedding info
                logger.debug(f"Created block with ID: {block.id}")
                logger.debug(f"Embedding dimensions: {len(embedding)}")
                logger.debug(f"Embedding range: {min(embedding):.4f} to {max(embedding):.4f}")
        else:
            # Using mock content (our fixture returned the mock data)
            logger.info("Using mock content...")
            mock_data = real_content_files  # Actually contains mock data
            
            for item in mock_data:
                # Generate embeddings
                logger.debug(f"Generating embedding for: {item['title']}")
                embedding = embed_fn([item['text']])[0]
                
                # Create block
                block = MemoryBlock(
                    id=str(uuid.uuid4()),
                    text=item['text'],
                    tags=item['tags'],
                    source_file=item['source'],
                    embedding=embedding,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                
                # Add to blocks list
                memory_blocks.append(block)
                
                # Log embedding info
                logger.debug(f"Created block with ID: {block.id}")
                logger.debug(f"Embedding dimensions: {len(embedding)}")
                logger.debug(f"Embedding range: {min(embedding):.4f} to {max(embedding):.4f}")
        
        # Step 6: Save blocks to memory
        logger.info("Saving blocks to memory system...")
        client.save_blocks(memory_blocks)
        logger.info(f"Saved {len(memory_blocks)} blocks to memory")
        
        # Step 7: Verify blocks were saved
        block_count = client.count_blocks()
        logger.debug(f"Memory system block count: {block_count}")
        assert block_count["hot_storage"] >= len(memory_blocks)
        
        # Step 8: Perform semantic queries
        # Define test queries based on what content we have
        if any(os.path.basename(f) == 'cogni_graph.md' for f in real_content_files if isinstance(f, str)):
            # If we have real cogni_graph.md
            test_queries = [
                {
                    "query": "What is Cogni's central graph node?",
                    "expected_source": "cogni_graph.md",
                    "description": "query about Cogni's central graph"
                }
            ]
        else:
            # Use mock-appropriate queries
            test_queries = [
                {
                    "query": "What is Cogni's purpose?",
                    "description": "general query about Cogni"
                }
            ]
        
        # Add generic queries that should work with any content
        test_queries.append({
            "query": "Tell me about the most important concepts in this document",
            "description": "generic importance query"
        })
        
        # Run each query and validate
        for test_case in test_queries:
            logger.info(f"Testing {test_case['description']}")
            logger.info(f"Query: '{test_case['query']}'")
            
            # Perform query
            results = client.query(
                query_text=test_case['query'],
                n_results=1
            )
            
            # Validate results
            assert len(results.blocks) > 0, f"No results for query: {test_case['query']}"
            top_result = results.blocks[0]
            
            logger.info(f"Top result source: {top_result.source_file}")
            logger.debug(f"Top result text: {top_result.text[:100]}...")
            
            # If we have expected source, check it
            if 'expected_source' in test_case:
                assert top_result.source_file == test_case['expected_source'], \
                    f"Expected {test_case['expected_source']} but got {top_result.source_file}"
        
        # Step 9: Test archiving
        # Archive the first block
        block_to_archive = memory_blocks[0].id
        logger.info(f"Archiving block: {block_to_archive}")
        client.archive_blocks([block_to_archive])
        
        # Verify archiving
        after_archive_count = client.count_blocks()
        logger.debug(f"Block count after archiving: {after_archive_count}")
        assert after_archive_count["cold_storage"] >= 1, "Block was not archived properly"
        assert after_archive_count["hot_storage"] == block_count["hot_storage"] - 1, "Hot storage count did not decrease"
        
        # Step 10: Query with inclusion of archived blocks
        logger.info("Querying with inclusion of archived blocks...")
        archive_results = client.query(
            query_text="important concepts",
            n_results=2,
            include_archived=True
        )
        
        logger.info(f"Found {len(archive_results.blocks)} results including archived")
        assert len(archive_results.blocks) >= 1, "No results found including archived blocks"
        
        # Step 11: Calculate and log embedding similarities
        logger.info("Calculating embedding similarities between blocks...")
        
        def cosine_similarity(a, b):
            return np.dot(a, b) / (norm(a) * norm(b))
        
        # Calculate similarities between all blocks
        if len(memory_blocks) > 1:
            for i in range(len(memory_blocks)):
                for j in range(i+1, len(memory_blocks)):
                    if memory_blocks[i].embedding and memory_blocks[j].embedding:
                        sim = cosine_similarity(memory_blocks[i].embedding, memory_blocks[j].embedding)
                        logger.info(f"Similarity between '{memory_blocks[i].source_file}' and '{memory_blocks[j].source_file}': {sim:.4f}")
        
        logger.info("=== Memory E2E Test Completed Successfully ===")


if __name__ == "__main__":
    # Enable direct running of the test for debugging
    import sys
    if "--verbose" in sys.argv or "-v" in sys.argv:
        # Set verbose logging if flagged
        logging.getLogger("memory_e2e_test").setLevel(logging.DEBUG)
        logging.getLogger("infra_core").setLevel(logging.DEBUG)
    
    pytest.main(["-xvs", __file__]) 