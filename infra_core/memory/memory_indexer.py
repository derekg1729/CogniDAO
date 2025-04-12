import os
import glob
import uuid
from typing import List, Dict

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

# === CONFIG ===
LOGSEQ_DIR = "./logseq"  # path to your .md files
TARGET_TAGS = {"#thought", "#broadcast", "#approved"}
VECTOR_DB_DIR = "./cogni-memory/chroma"
EMBED_MODEL = "openai"  # or "local" if swapping in a local model later

# === INIT VECTOR DB ===
client = chromadb.Client(Settings(chroma_db_impl="duckdb+parquet", persist_directory=VECTOR_DB_DIR))
collection = client.get_or_create_collection(name="cogni-memory")

# === EMBEDDING SETUP ===
if EMBED_MODEL == "openai":
    embed_fn = embedding_functions.OpenAIEmbeddingFunction(
        api_key=os.getenv("OPENAI_API_KEY"),
        model_name="text-embedding-3-small"
    )
else:
    raise NotImplementedError("Local embedding model not implemented yet")

# === FILE PARSING + FILTERING ===

def load_md_files(folder: str) -> List[str]:
    return glob.glob(os.path.join(folder, "**/*.md"), recursive=True)

def extract_blocks(file_path: str) -> List[Dict]:
    """
    Returns a list of blocks from an .md file, where each block is:
    {
        "text": "...",
        "tags": [...],
        "source_file": "...",
        "block_ref": "..." (optional)
    }
    """
    with open(file_path, "r") as f:
        lines = f.readlines()

    blocks = []
    for line in lines:
        tags = {tag for tag in line.split() if tag.startswith("#")}
        if tags & TARGET_TAGS:
            blocks.append({
                "id": str(uuid.uuid4()),  # could be replaced with a hash or block-ref if available
                "text": line.strip(),
                "tags": list(tags),
                "source_file": os.path.basename(file_path)
            })
    return blocks

# === INDEXING ===

def index_blocks(blocks: List[Dict]):
    for block in blocks:
        embedding = embed_fn([block["text"]])[0]
        collection.add(
            ids=[block["id"]],
            embeddings=[embedding],
            documents=[block["text"]],
            metadatas=[{
                "tags": block["tags"],
                "source": block["source_file"]
            }]
        )

# === MAIN ===

def run_indexing():
    print("Scanning Logseq directory...")
    files = load_md_files(LOGSEQ_DIR)
    total_indexed = 0

    for file in files:
        blocks = extract_blocks(file)
        if blocks:
            index_blocks(blocks)
            total_indexed += len(blocks)

    print(f"✅ Indexed {total_indexed} high-signal blocks.")

if __name__ == "__main__":
    run_indexing()
