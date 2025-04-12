import sys
sys.path.append('.')

from infra_core.memory import memory_indexer
from infra_core.memory.parser import LogseqParser
import os

# Print which model we're using
print(f"Using embedding model: {memory_indexer.EMBED_MODEL}")

# Create test directories
os.makedirs("./test_memory", exist_ok=True)

# Parse the cogni_graph.md file
parser = LogseqParser(".", {"#thought", "#broadcast", "#approved"})
print("Parsing cogni_graph.md...")
blocks = parser.extract_blocks_from_file("cogni_graph.md")
print(f"Found {len(blocks)} blocks in cogni_graph.md")

# If we found blocks, test embedding them
if blocks:
    # Initialize the real BGE embedding function
    print("Initializing BGE embedding function...")
    embed_fn = memory_indexer.init_embedding_function("bge")
    
    # Test it on one block
    print("Testing embeddings on first block...")
    text = blocks[0]["text"]
    print(f"Text: {text}")
    embedding = embed_fn([text])[0]
    print(f"Embedding dimensions: {len(embedding)}")
    print(f"First few values: {embedding[:5]}")
else:
    # If no blocks found, try embedding the whole file content
    print("No blocks found, testing embedding on the file content...")
    with open("cogni_graph.md", "r") as f:
        content = f.read()
    
    embed_fn = memory_indexer.init_embedding_function("bge")
    embedding = embed_fn([content])[0]
    print(f"Embedding dimensions: {len(embedding)}")
    print(f"First few values: {embedding[:5]}")

print("Test completed successfully!")