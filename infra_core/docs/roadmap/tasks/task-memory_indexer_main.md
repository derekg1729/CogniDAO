# Task:[Create Memory Indexer Entry Point]
:type: Task
:status: todo
:project: [project-cogni_memory_architecture]
:owner: 

## Description
Create the main entry point script (memory_indexer.py) that ties together all components of the memory system, providing a complete pipeline from parsing Logseq blocks to embedding and storage.

## Action Items
- [ ] Create the entry point script with command-line arguments
- [ ] Integrate parser, embedder, and storage components
- [ ] Add configuration handling for paths and settings
- [ ] Implement end-to-end indexing pipeline
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
- [ ] Test end-to-end indexing pipeline:
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

- [ ] Test simple query after indexing:
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
- [ ] Validate command-line argument handling
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