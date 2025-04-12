# Task:[Create Memory Index JSON]
:type: Task
:status: todo
:project: [project-cogni_memory_architecture]
:owner: 

## Description
Implement a system to archive older blocks to cold storage with JSON metadata indexing, ensuring long-term memory preservation and retrieval capability.

## Action Items
- [ ] Design JSON schema for memory block metadata
- [ ] Implement archiving logic for moving older blocks to cold storage
- [ ] Create JSON index files with metadata mirroring the vector database
- [ ] Add source URI format for traceability (e.g., logseq://date#block-id)
- [ ] Implement versioning for archived records
- [ ] Create retrieval mechanism for cold storage blocks

## Deliverables
1. An archive system in `storage.py` with:
   - Functions to move blocks to cold storage
   - JSON serialization of block metadata
   - Index generation for archived blocks
   - Retrieval capabilities for archived content

2. Directory structure for cold storage:
   ```
   cogni-memory/
   ├── chroma/      # Hot storage (vector DB)
   └── archive/     # Cold storage
       ├── blocks/  # Individual block JSON files
       └── index/   # Searchable index files
   ```

3. Source URI format implementation for block traceability

## Test Criteria
- [ ] Test archiving and retrieval workflow:
```python
def test_archive_workflow():
    # Setup storage
    chroma = ChromaStorage("./test_chroma")
    archive = ArchiveStorage("./test_archive")
    
    # Create test blocks with embeddings
    blocks = [create_test_memory_block() for _ in range(3)]
    
    # First store in ChromaDB
    chroma.add_blocks(blocks)
    
    # Then archive them
    archive.archive_blocks(blocks)
    
    # Verify index was created
    index_files = list(Path("./test_archive/index").glob("*.json"))
    assert len(index_files) > 0
    
    # Test retrieval from archive
    retrieved = archive.retrieve_block(blocks[0].id)
    assert retrieved is not None
    assert retrieved["text"] == blocks[0].text
    assert "source_uri" in retrieved
```

- [ ] Verify index file structure and contents:
```python
def test_index_structure():
    archive = ArchiveStorage("./test_archive")
    # Trigger index creation
    archive._update_index()
    
    # Load latest index
    with open("./test_archive/index/latest.json", "r") as f:
        index = json.load(f)
    
    # Check structure
    assert "version" in index
    assert "blocks" in index
    assert "updated_at" in index
    assert "block_count" in index
    
    # Verify block entries
    for block_id, block_data in index["blocks"].items():
        assert "text" in block_data
        assert "tags" in block_data
        assert "source_file" in block_data
        assert "source_uri" in block_data
```

- [ ] Test source URI format and parsing
- [ ] Verify retrieval performance with larger datasets
- [ ] Test index update functionality

## Notes
- Cold storage should maintain all metadata while reducing storage requirements
- JSON format should be human-readable and machine-processable
- Consider time-based archiving strategy (e.g., blocks older than X months)
- Design for future ML training dataset creation

## Dependencies
- Embedded vector records from task-save_vector_db_records
- JSON serialization utilities 