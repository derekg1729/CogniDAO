# Task:[Refactor memory_indexer.py Into CogniMemoryClient]
:type: Task
:status: completed
:project: [project-cogni_memory_architecture]
:owner: 

## Current Status
- [x] Task design document completed
- [x] Comprehensive stubbed tests created in test_memory_client.py
- [x] Implementation completed

## Description
Refactor the standalone `memory_indexer.py` script to extract reusable indexing logic into CogniMemoryClient as an `index_from_logseq()` method. This will enable programmatic use of the indexing capabilities rather than relying solely on the CLI, while maintaining backward compatibility with the existing script.

## Action Items
- [x] Add an `index_from_logseq()` method to CogniMemoryClient
- [x] Extract core indexing logic from `memory_indexer.py`
- [x] Maintain embedding initialization functionality
- [x] Reorganize error handling and progress reporting
- [x] Add comprehensive logging
- [x] Write unit tests in test_memory_client.py

## Deliverables
1. Implementation of `index_from_logseq()` in memory_client.py:
   ```python
   def index_from_logseq(
       self,
       logseq_dir: str,
       tag_filter: Optional[Union[List[str], Set[str], str]] = None,
       embed_model: str = "bge",
       verbose: bool = False
   ) -> int:
       """
       Scan Logseq directory for blocks with specified tags and index them in ChromaDB.
       
       Args:
           logseq_dir: Path to directory containing Logseq .md files
           tag_filter: Optional tag or list of tags to filter for
                     (default: {"#thought", "#broadcast", "#approved"})
           embed_model: Model to use for embeddings (default: "bge")
           verbose: Whether to display verbose logging
           
       Returns:
           Number of blocks indexed
           
       Raises:
           FileNotFoundError: If logseq_dir doesn't exist
           ValueError: If embedding initialization fails
       """
   ```

2. Refactored memory_indexer.py that uses the new CogniMemoryClient method

3. Unit tests in test_memory_client.py

## Test Criteria
- [x] Test indexing blocks from a Logseq directory:
```python
def test_index_from_logseq():
    # Setup test directories
    test_logseq_dir = "./test_logseq"
    test_chroma_dir = "./test_chroma"
    test_archive_dir = "./test_archive"
    
    os.makedirs(test_logseq_dir, exist_ok=True)
    
    # Create sample files
    with open(f"{test_logseq_dir}/test1.md", "w") as f:
        f.write("- This is a test block with #thought tag\n")
        f.write("- This is another block without tags\n")
    
    with open(f"{test_logseq_dir}/test2.md", "w") as f:
        f.write("- This block has #broadcast tag\n")
    
    # Remove existing test chroma directory if it exists
    if os.path.exists(test_chroma_dir):
        shutil.rmtree(test_chroma_dir)
    
    # Initialize client
    client = CogniMemoryClient(
        chroma_path=test_chroma_dir,
        archive_path=test_archive_dir
    )
    
    # Test indexing with mock embeddings
    total_indexed = client.index_from_logseq(
        logseq_dir=test_logseq_dir,
        embed_model="mock"  # Use mock for testing
    )
    
    # Verify blocks were indexed
    assert total_indexed == 2
    
    # Verify blocks can be queried
    results = client.query("test block")
    assert len(results.blocks) > 0
    assert any("#thought" in block.tags for block in results.blocks)
    
    # Clean up
    shutil.rmtree(test_logseq_dir)
    shutil.rmtree(test_chroma_dir)
    shutil.rmtree(test_archive_dir)
```

- [x] Test indexing with specific tag filters:
```python
def test_index_from_logseq_with_tag_filter():
    # Setup test directories
    test_logseq_dir = "./test_logseq"
    test_chroma_dir = "./test_chroma"
    test_archive_dir = "./test_archive"
    
    os.makedirs(test_logseq_dir, exist_ok=True)
    
    # Create sample files with multiple tags
    with open(f"{test_logseq_dir}/multi_tags.md", "w") as f:
        f.write("- This has #thought tag only\n")
        f.write("- This has #broadcast tag only\n")
        f.write("- This has both #thought and #broadcast tags\n")
    
    # Remove existing test chroma directory if it exists
    if os.path.exists(test_chroma_dir):
        shutil.rmtree(test_chroma_dir)
    
    # Initialize client
    client = CogniMemoryClient(
        chroma_path=test_chroma_dir,
        archive_path=test_archive_dir
    )
    
    # Test indexing with specific tag filter
    total_indexed = client.index_from_logseq(
        logseq_dir=test_logseq_dir,
        tag_filter="#thought",
        embed_model="mock"
    )
    
    # Verify only blocks with #thought tag were indexed
    assert total_indexed == 2  # Two blocks with #thought tag
    
    # Verify tag filtering worked
    results = client.query("tag")
    assert len(results.blocks) == 2
    assert all("#thought" in block.tags for block in results.blocks)
    
    # Clean up
    shutil.rmtree(test_logseq_dir)
    shutil.rmtree(test_chroma_dir)
    shutil.rmtree(test_archive_dir)
```

- [x] Test error handling for invalid directories:
```python
def test_index_from_logseq_invalid_dir():
    client = CogniMemoryClient(
        chroma_path="./test_chroma",
        archive_path="./test_archive"
    )
    
    # Test with non-existent directory
    with pytest.raises(FileNotFoundError):
        client.index_from_logseq("./nonexistent_dir")
```

## Notes
- Extract core logic from `memory_indexer.py` while keeping the CLI functionality
- Ensure the CogniMemoryClient method handles embedding initialization properly
- Add clear progress reporting for long-running operations
- Keep a clean separation between CLI concerns and core functionality
- Use the existing LogseqParser for block extraction
- Maintain compatibility with CLI tool

## Dependencies
- LogseqParser from infra_core/memory/parser.py
- Embedding initialization from memory_indexer.py
- ChromaDB for vector storage
- MemoryBlock schema from infra_core/memory/schema.py 