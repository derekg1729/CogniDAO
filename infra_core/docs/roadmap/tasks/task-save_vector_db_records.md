# Task:[Save Vector DB Records]
:type: Task
:status: in-progress
:project: [project-cogni_memory_architecture]
:owner: 

## Current Status
Basic embedding and storage functionality is implemented in two places:
1. **memory_indexer.py**: Basic OpenAI integration for generating embeddings via `init_embedding_function()`
2. **storage.py**: ChromaDB storage implementation with the following features:
   - `ChromaStorage` class for vector database operations
   - Proper metadata handling for ChromaDB
   - Query functionality with tag filtering

To complete this task, we would need to:
1. Extract the embedding logic to a dedicated `embedder.py` module
2. Add batch processing and rate limiting for the OpenAI API
3. Implement retry mechanisms for API failures
4. Add versioning for embedded records
5. Create additional tests for these features

## Description
Implement functionality to embed extracted Logseq blocks using OpenAI embeddings and store them in a ChromaDB collection with appropriate metadata.

## Action Items
- [x] Set up OpenAI integration for text-embedding-3-small (implemented in memory_indexer.py)
  - Implemented in `memory_indexer.py` with `init_embedding_function()` using OpenAI API
- [ ] Create embeddings batch processing logic with rate limiting
- [x] Configure ChromaDB local persistence
  - Implemented in `storage.py` with `ChromaStorage` class and `init_chroma_client()` in memory_indexer.py
- [x] Define schema for block storage with metadata (text, tags, source_file, uuid)
  - Implemented in `schema.py` with `MemoryBlock` class and metadata handling in `ChromaStorage.add_blocks()`
- [ ] Implement saving logic with error handling and retry mechanisms
- [ ] Add versioning for embedded records

## Deliverables
1. An `embedder.py` module with:
   - OpenAI API integration for text-embedding-3-small
   - Batch processing with rate limiting
   - Retry mechanisms for API failures

2. A `storage.py` module with:
   - ChromaDB integration for persisting embeddings
   - Functions to save blocks with metadata
   - Retrieval capabilities for embedded blocks

3. Configuration for local ChromaDB persistence in `cogni-memory/chroma/`

## Test Criteria
- [x] Verify embedding generation with sample text:
  - Tested in `test_memory_indexer.py` using the mock embedding function
```python
def test_embedding_generation():
    embedder = OpenAIEmbedder()
    sample_text = "This is a test of the embedding system #broadcast"
    embedding = embedder.embed_text(sample_text)
    
    # Should produce a valid embedding vector
    assert len(embedding) > 0
    assert all(isinstance(x, float) for x in embedding)
```

- [x] Test ChromaDB storage and retrieval:
  - Implemented in `test_storage.py` with `TestChromaStorage.test_add_blocks()` and `test_query()`
```python
def test_chroma_storage():
    # Setup
    storage = ChromaStorage("./test_chroma")
    
    # Create test blocks
    blocks = [
        MemoryBlock(
            id="test-1",
            text="Test block with embedding",
            tags=["#thought"],
            source_file="test.md",
            embedding=[0.1]*1536  # Simplified test embedding
        )
    ]
    
    # Store blocks
    storage.add_blocks(blocks)
    
    # Query and verify
    results = storage.query("test block")
    assert len(results["ids"][0]) > 0
    assert results["documents"][0][0] == "Test block with embedding"
```

- [ ] Verify batch processing with multiple blocks
- [ ] Validate error handling with simulated API failures
- [x] Confirm all metadata is properly stored and retrievable
  - Tested in `test_storage.py` through various test methods

## Notes
- Use text-embedding-3-small model for efficiency and cost
- Ensure ChromaDB collection is properly persisted to cogni-memory/chroma/
- Consider batching for performance with large datasets
- Include proper error handling for API failures

## Dependencies
- OpenAI API access
- ChromaDB Python client
- Parsed Logseq blocks from task-parse_logseq_blocks 