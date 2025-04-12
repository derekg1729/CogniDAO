# Task:[Build Cogni Memory Client]
:type: Task
:status: todo
:project: [project-cogni_memory_architecture]
:owner: 

## Description
Create a unified CogniMemoryClient interface that provides consistent access to memory operations (query, save, archive) across the memory system, enabling integration with agent workflows.

## Action Items
- [ ] Define Pydantic schema models for memory records
- [ ] Implement unified query interface with semantic search
- [ ] Create memory writing/saving interfaces
- [ ] Add archive operations to move content to cold storage
- [ ] Implement version handling for memory schema
- [ ] Create simple utility for testing memory operations

## Deliverables
1. A `schema.py` module with:
   - Pydantic models for memory blocks
   - Query and response models
   - Schema versioning

2. A `query.py` module with:
   - Unified memory query interface
   - Functions to search across both hot and cold storage
   - Support for filtering by tags and relevance

3. A unified `CogniMemoryClient` class that provides:
   - Simplified memory operations (query, save, archive)
   - Consistent interface for all memory interactions
   - Integration hooks for agent workflows

4. A simple `memory_tool.py` utility for integrating with agent frameworks

## Test Criteria
- [ ] Test end-to-end memory operations:
```python
def test_memory_client():
    # Initialize client with test storage
    client = CogniMemoryClient(
        chroma_path="./test_chroma",
        archive_path="./test_archive"
    )
    
    # Save new memory blocks
    blocks = [create_test_memory_block() for _ in range(3)]
    client.save_blocks(blocks)
    
    # Query memories
    results = client.query("test memory", n_results=2)
    assert len(results.blocks) > 0
    
    # Archive memories
    client.archive_blocks(blocks)
    
    # Query across both hot and cold storage
    results = client.query("test memory", include_archived=True)
    assert len(results.blocks) > 0
```

- [ ] Test memory schema validation:
```python
def test_schema_validation():
    # Test valid block
    valid_block = MemoryBlock(
        text="Valid block",
        tags=["#thought"],
        source_file="test.md"
    )
    
    # This should work fine
    valid_json = valid_block.json()
    
    # Test with missing required field
    try:
        # Missing required 'text' field
        invalid_block = MemoryBlock(
            tags=["#thought"],
            source_file="test.md"
        )
        assert False, "Should have raised validation error"
    except:
        # Expected to fail validation
        pass
```

- [ ] Test memory tool integration:
```python
def test_memory_tool():
    result = memory_tool(
        input_text="test memory",
        n_results=3
    )
    
    assert isinstance(result, dict)
    assert "query" in result
    assert "results" in result
    assert "result_count" in result
```

- [ ] Verify version compatibility handling
- [ ] Test integration with both hot and cold storage
- [ ] Validate error handling in client operations

## Notes
- Design for agent interoperability from the start
- Support future integration with MCP or Agent2Agent SDK
- Implement a clean, typed interface with proper error handling
- Consider implementing a memory_tool.py for quick integration with agent frameworks

## Dependencies
- ChromaDB integration from task-save_vector_db_records
- JSON archive format from task-create_memory_index_json
- Pydantic for schema enforcement 