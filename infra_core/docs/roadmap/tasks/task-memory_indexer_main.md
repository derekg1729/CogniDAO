# Task:[Create Memory Indexer Entry Point]
:type: Task
:status: in-progress
:project: [project-cogni_memory_architecture]
:owner: 

## Current Status
A basic implementation of `memory_indexer.py` exists with the following functionality:
- Basic parsing of Logseq markdown files via `load_md_files()` and `extract_blocks()`
- Extraction of blocks with specific tags through filtering in `extract_blocks()`
- Integration with OpenAI for embeddings via `init_embedding_function()`
- Storage in ChromaDB through `init_chroma_client()` and `index_blocks()`
- A functional main entry point `run_indexing()`

To complete this task, we would need to:
1. Enhance the command-line interface with proper argument parsing
2. Add progress reporting and logging
3. Implement robust error handling and recovery
4. Add support for configuring the system via command-line arguments
5. Integrate with the new `storage.py` for both hot and cold storage

## Description
Create the main entry point script (memory_indexer.py) that ties together all components of the memory system, providing a complete pipeline from parsing Logseq blocks to embedding and storage.

## Action Items
- [x] Create the entry point script with command-line arguments (basic implementation)
  - Implemented in `memory_indexer.py` with `run_indexing()` function, though needs enhanced arguments
- [x] Integrate parser, embedder, and storage components (all in a single file)
  - Implemented in `memory_indexer.py` with `extract_blocks()`, `init_embedding_function()`, and `index_blocks()`
- [x] Add configuration handling for paths and settings
  - Implemented in `memory_indexer.py` with configurable paths and settings at the top of the file
- [x] Implement end-to-end indexing pipeline (basic functionality)
  - Implemented in `memory_indexer.py` with the `run_indexing()` function
- [ ] Create progress reporting and logging
- [ ] Add error handling and recovery

## Deliverables
1. A `memory_indexer.py` script that:
   - Can be run from the command line
   - Processes Logseq files from a specified directory
   - Embeds blocks using OpenAI
   - Stores in ChromaDB
   - Provides progress and summary reporting

2. Command-line interface with options:
   ```
   python memory_indexer.py --logseq-dir ./path/to/logseq --output-dir ./cogni-memory
   ```

3. Configuration handling for API keys, model selection, etc.

## Test Criteria
- [x] Test end-to-end indexing pipeline:
  - Implemented in `test_memory_indexer.py` with `test_indexer_creates_chroma_collection()`
```bash
# Create test data
mkdir -p test_data/logseq
echo "- Test block with #thought tag" > test_data/logseq/test.md
echo "- Another block with #broadcast tag" >> test_data/logseq/test.md

# Run indexer
python memory_indexer.py --logseq-dir ./test_data/logseq --output-dir ./test_output

# Verify output
ls -la ./test_output/chroma/
```

- [x] Test simple query after indexing:
  - Implemented in `test_memory_indexer.py` with `test_indexer_creates_chroma_collection()`
```python
import chromadb

# Should be able to query the collection
client = chromadb.PersistentClient(path="./test_output/chroma")
collection = client.get_collection("cogni-memory")
results = collection.query(query_texts=["test block"], n_results=3)

# Should find at least one result
assert len(results["ids"][0]) > 0
```

- [ ] Verify memory indexer with malformed inputs
- [ ] Test performance with larger datasets
- [/] Validate command-line argument handling (basic support)
  - Partially implemented with parameters in `run_indexing()` function
- [ ] Test recovery from interruptions

## Notes
- Design for easy extensibility and future integration
- Make the script robust to errors and interruptions
- Include clear progress reporting
- Support both one-time and continuous indexing modes

## Dependencies
- Parser module from task-parse_logseq_blocks
- Embedding functionality from task-save_vector_db_records
- Storage components from task-save_vector_db_records and task-create_memory_index_json 