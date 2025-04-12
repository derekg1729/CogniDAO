import os
import glob
import uuid
import argparse
import sys
from typing import List, Dict, Set
import logging
from tqdm import tqdm  # For progress reporting

import chromadb
from chromadb.utils import embedding_functions

from infra_core.memory.parser import LogseqParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === CONFIG ===
LOGSEQ_DIR = "./logseq"  # path to your .md files
TARGET_TAGS = {"#thought", "#broadcast", "#approved"}
VECTOR_DB_DIR = "./cogni-memory/chroma"
EMBED_MODEL = "openai"  # or "local" if swapping in a local model later

def init_chroma_client(vector_db_dir: str = VECTOR_DB_DIR):
    """Initialize the ChromaDB client with the given directory."""
    try:
        # Create directory if it doesn't exist
        os.makedirs(vector_db_dir, exist_ok=True)
        logger.info(f"Initializing ChromaDB client with directory: {vector_db_dir}")
        return chromadb.PersistentClient(path=vector_db_dir)
    except Exception as e:
        logger.error(f"Failed to initialize ChromaDB client: {e}")
        raise

def init_embedding_function(embed_model: str = EMBED_MODEL):
    """Initialize the embedding function based on the model type."""
    try:
        logger.info(f"Initializing embedding function with model: {embed_model}")
        
        if embed_model == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.error("OPENAI_API_KEY environment variable not set")
                raise ValueError("OpenAI API key not found. Set the OPENAI_API_KEY environment variable.")
                
            return embedding_functions.OpenAIEmbeddingFunction(
                api_key=api_key,
                model_name="text-embedding-3-small"
            )
        elif embed_model == "mock":
            # Mock embedding function for testing
            logger.info("Using mock embedding function for testing")
            class MockEmbeddingFunction:
                def __call__(self, texts):
                    return [[0.1] * 1536 for _ in texts]
            return MockEmbeddingFunction()
        else:
            logger.error(f"Embedding model {embed_model} not implemented yet")
            raise NotImplementedError(f"Embedding model {embed_model} not implemented yet")
            
    except Exception as e:
        logger.error(f"Failed to initialize embedding function: {e}")
        raise

# === FILE PARSING + FILTERING ===

def load_md_files(folder: str) -> List[str]:
    return glob.glob(os.path.join(folder, "**/*.md"), recursive=True)

def extract_blocks(file_path: str, target_tags: Set[str] = TARGET_TAGS) -> List[Dict]:
    """
    Returns a list of blocks from an .md file, where each block is:
    {
        "text": "...",
        "tags": [...],
        "source_file": "...",
        "block_ref": "..." (optional)
    }
    
    Args:
        file_path: Path to the .md file
        target_tags: Set of tags to filter for (default: TARGET_TAGS)
    """
    with open(file_path, "r") as f:
        lines = f.readlines()

    blocks = []
    for line in lines:
        tags = {tag for tag in line.split() if tag.startswith("#")}
        if tags & target_tags:
            blocks.append({
                "id": str(uuid.uuid4()),  # could be replaced with a hash or block-ref if available
                "text": line.strip(),
                "tags": list(tags),
                "source_file": os.path.basename(file_path)
            })
    return blocks

# === INDEXING ===

def index_blocks(blocks: List[Dict], collection, embed_fn):
    """Index blocks using the provided collection and embedding function."""
    try:
        for block in tqdm(blocks, desc="Embedding blocks"):
            embedding = embed_fn([block["text"]])[0]
            
            # Convert tags list to a string for ChromaDB metadata (which requires scalar values)
            tags_str = ", ".join(block["tags"])
            
            collection.add(
                ids=[block["id"]],
                embeddings=[embedding],
                documents=[block["text"]],
                metadatas=[{
                    "tags": tags_str,  # Use string instead of list
                    "source": block["source_file"],
                    "source_uri": block.get("source_uri", "")
                }]
            )
        logger.info(f"Successfully indexed {len(blocks)} blocks")
    except Exception as e:
        logger.error(f"Error during block indexing: {e}")
        raise

# === MAIN ===

def run_indexing(
    logseq_dir: str = LOGSEQ_DIR, 
    vector_db_dir: str = VECTOR_DB_DIR,
    embed_model: str = EMBED_MODEL,
    client = None,
    embed_fn = None,
    target_tags: Set[str] = None,
    collection_name: str = "cogni-memory",
    verbose: bool = False
):
    """
    Run the indexing process to extract, embed, and store blocks from Logseq files.
    
    Args:
        logseq_dir: Directory containing Logseq .md files
        vector_db_dir: Directory to store ChromaDB files
        embed_model: Type of embedding model to use
        client: Optional pre-initialized ChromaDB client
        embed_fn: Optional pre-initialized embedding function
        target_tags: Optional set of tags to filter for (default: TARGET_TAGS)
        collection_name: Name of the ChromaDB collection
        verbose: Whether to display verbose logging
    
    Returns:
        total_indexed: Number of blocks indexed
    """
    # Set logging level based on verbosity
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Ensure directories exist
    os.makedirs(logseq_dir, exist_ok=True)
    os.makedirs(vector_db_dir, exist_ok=True)
    
    logger.info(f"Starting indexing process for Logseq directory: {logseq_dir}")
    
    try:
        # Use default target tags if not provided
        if target_tags is None:
            target_tags = TARGET_TAGS
        
        # Initialize client and collection if not provided
        if client is None:
            client = init_chroma_client(vector_db_dir)
        
        # Get or create collection
        try:
            collection = client.get_collection(name=collection_name)
            logger.info(f"Using existing collection: {collection_name}")
        except ValueError:
            collection = client.create_collection(name=collection_name)
            logger.info(f"Created new collection: {collection_name}")
        
        # Initialize embedding function if not provided
        if embed_fn is None:
            embed_fn = init_embedding_function(embed_model)
        
        # Create parser and extract blocks
        parser = LogseqParser(logseq_dir, target_tags)
        blocks = parser.extract_all_blocks()
        
        if not blocks:
            logger.warning(f"No blocks found in {logseq_dir} with tags {target_tags}")
            return 0
        
        logger.info(f"Found {len(blocks)} blocks to index")
        
        # Index blocks
        index_blocks(blocks, collection, embed_fn)
        
        total_indexed = len(blocks)
        logger.info(f"✅ Successfully indexed {total_indexed} blocks")
        return total_indexed
        
    except Exception as e:
        logger.error(f"Error during indexing: {e}")
        if verbose:
            logger.exception("Detailed error information:")
        return 0

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Index Logseq blocks to ChromaDB")
    
    parser.add_argument(
        "--logseq-dir", 
        type=str, 
        default=LOGSEQ_DIR,
        help=f"Directory containing Logseq .md files (default: {LOGSEQ_DIR})"
    )
    parser.add_argument(
        "--vector-db-dir", 
        type=str, 
        default=VECTOR_DB_DIR,
        help=f"Directory to store ChromaDB files (default: {VECTOR_DB_DIR})"
    )
    parser.add_argument(
        "--embed-model", 
        type=str, 
        default=EMBED_MODEL,
        choices=["openai", "mock"],
        help=f"Type of embedding model to use (default: {EMBED_MODEL})"
    )
    parser.add_argument(
        "--collection", 
        type=str, 
        default="cogni-memory",
        help="Name of the ChromaDB collection (default: cogni-memory)"
    )
    parser.add_argument(
        "--tags", 
        type=str, 
        nargs="+", 
        default=None,
        help="Tags to filter for (default: #thought #broadcast #approved)"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Display verbose logging"
    )
    
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    # Convert tags to set with hashtags
    target_tags = None
    if args.tags:
        target_tags = {f"#{tag.lstrip('#')}" for tag in args.tags}
    
    try:
        total_indexed = run_indexing(
            logseq_dir=args.logseq_dir,
            vector_db_dir=args.vector_db_dir,
            embed_model=args.embed_model,
            target_tags=target_tags,
            collection_name=args.collection,
            verbose=args.verbose
        )
        
        if total_indexed > 0:
            sys.exit(0)  # Success
        else:
            logger.warning("No blocks were indexed")
            sys.exit(1)  # No blocks indexed
    
    except Exception as e:
        logger.error(f"Indexing failed: {e}")
        if args.verbose:
            logger.exception("Detailed error information:")
        sys.exit(2)  # Error
