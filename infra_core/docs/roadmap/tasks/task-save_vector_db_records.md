# Task:[Save Vector DB Records]
:type: Task
:status: todo
:project: [project-cogni_memory_architecture]
:owner: 

## Description
Implement functionality to embed extracted Logseq blocks using OpenAI embeddings and store them in a ChromaDB collection with appropriate metadata.

## Action Items
- [ ] Set up OpenAI integration for text-embedding-3-small
- [ ] Create embeddings batch processing logic with rate limiting
- [ ] Configure ChromaDB local persistence
- [ ] Define schema for block storage with metadata (text, tags, source_file, uuid)
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
- [ ] Verify embedding generation with sample text:
```python
def test_embedding_generation():
    embedder = OpenAIEmbedder()
    sample_text = "This is a test of the embedding system #broadcast"
    embedding = embedder.embed_text(sample_text)
    
    # Should produce a valid embedding vector
    assert len(embedding) > 0
    assert all(isinstance(x, float) for x in embedding)
```

- [ ] Test ChromaDB storage and retrieval:
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
- [ ] Confirm all metadata is properly stored and retrievable

## Notes
- Use text-embedding-3-small model for efficiency and cost
- Ensure ChromaDB collection is properly persisted to cogni-memory/chroma/
- Consider batching for performance with large datasets
- Include proper error handling for API failures

## Dependencies
- OpenAI API access
- ChromaDB Python client
- Parsed Logseq blocks from task-parse_logseq_blocks 