import os
import glob
import uuid
from typing import List, Dict, Set

import chromadb
from chromadb.utils import embedding_functions

# === CONFIG ===
LOGSEQ_DIR = "./logseq"  # path to your .md files
TARGET_TAGS = {"#thought", "#broadcast", "#approved"}
VECTOR_DB_DIR = "./cogni-memory/chroma"
EMBED_MODEL = "openai"  # or "local" if swapping in a local model later

def init_chroma_client(vector_db_dir: str = VECTOR_DB_DIR):
    """Initialize the ChromaDB client with the given directory."""
    return chromadb.PersistentClient(path=vector_db_dir)

def init_embedding_function(embed_model: str = EMBED_MODEL):
    """Initialize the embedding function based on the model type."""
    if embed_model == "openai":
        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name="text-embedding-3-small"
        )
    elif embed_model == "mock":
        # Mock embedding function for testing
        class MockEmbeddingFunction:
            def __call__(self, texts):
                return [[0.1] * 1536 for _ in texts]
        return MockEmbeddingFunction()
    else:
        raise NotImplementedError(f"Embedding model {embed_model} not implemented yet")

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
    for block in blocks:
        embedding = embed_fn([block["text"]])[0]
        
        # Convert tags list to a string for ChromaDB metadata (which requires scalar values)
        tags_str = ", ".join(block["tags"])
        
        collection.add(
            ids=[block["id"]],
            embeddings=[embedding],
            documents=[block["text"]],
            metadatas=[{
                "tags": tags_str,  # Use string instead of list
                "source": block["source_file"]
            }]
        )

# === MAIN ===

def run_indexing(logseq_dir: str = LOGSEQ_DIR, 
                 vector_db_dir: str = VECTOR_DB_DIR,
                 embed_model: str = EMBED_MODEL,
                 client = None,
                 embed_fn = None,
                 target_tags: Set[str] = None):
    """
    Run the indexing process to extract, embed, and store blocks from Logseq files.
    
    Args:
        logseq_dir: Directory containing Logseq .md files
        vector_db_dir: Directory to store ChromaDB files
        embed_model: Type of embedding model to use
        client: Optional pre-initialized ChromaDB client
        embed_fn: Optional pre-initialized embedding function
        target_tags: Optional set of tags to filter for (default: TARGET_TAGS)
    """
    print("Scanning Logseq directory...")
    
    # Use default target tags if not provided
    if target_tags is None:
        target_tags = TARGET_TAGS
    
    # Initialize client and collection if not provided
    if client is None:
        client = init_chroma_client(vector_db_dir)
    collection = client.get_or_create_collection(name="cogni-memory")
    
    # Initialize embedding function if not provided
    if embed_fn is None:
        embed_fn = init_embedding_function(embed_model)
    
    files = load_md_files(logseq_dir)
    total_indexed = 0

    for file in files:
        blocks = extract_blocks(file, target_tags=target_tags)
        if blocks:
            index_blocks(blocks, collection, embed_fn)
            total_indexed += len(blocks)

    print(f"✅ Indexed {total_indexed} high-signal blocks.")
    return total_indexed

if __name__ == "__main__":
    run_indexing()
