# Task:[Add scan_logseq() to CogniMemoryClient]
:type: Task
:status: todo
:project: [project-cogni_memory_architecture]
:owner: 

## Description
Add a `scan_logseq()` method to CogniMemoryClient that extracts high-signal blocks from Logseq .md files without embedding them. This enables applications to quickly scan and filter Logseq content without the overhead of vector embedding.

## Action Items
- [ ] Add a `scan_logseq(logseq_dir, tag_filter=None)` method to CogniMemoryClient
- [ ] Reuse the existing LogseqParser functionality to extract blocks
- [ ] Implement tag filtering with both string and list inputs
- [ ] Add error handling for invalid directories
- [ ] Return structured MemoryBlock instances without embedding them
- [ ] Add type hints and comprehensive docstrings
- [ ] Write unit tests in test_memory_client.py

## Deliverables
1. Implementation of `scan_logseq()` in memory_client.py:
   ```python
   def scan_logseq(
       self, 
       logseq_dir: str, 
       tag_filter: Optional[Union[List[str], Set[str], str]] = None
   ) -> List[MemoryBlock]:
       """
       Scan Logseq directory for blocks with specified tags without embedding.
       
       Args:
           logseq_dir: Path to directory containing Logseq .md files
           tag_filter: Optional tag or list of tags to filter for
                      (default: {"#thought", "#broadcast", "#approved"})
                      
       Returns:
           List of MemoryBlock instances (without embeddings)
       """
   ```

2. Unit tests in test_memory_client.py

## Test Criteria
- [ ] Test scanning a directory with multiple .md files:
```python
def test_scan_logseq():
    # Setup test directory with sample files
    test_dir = "./test_logseq"
    os.makedirs(test_dir, exist_ok=True)
    
    # Create sample files
    with open(f"{test_dir}/test1.md", "w") as f:
        f.write("- This is a test block with #thought tag\n")
        f.write("- This is another block without tags\n")
    
    with open(f"{test_dir}/test2.md", "w") as f:
        f.write("- This block has #broadcast tag\n")
    
    # Initialize client
    client = CogniMemoryClient(
        chroma_path="./test_chroma",
        archive_path="./test_archive"
    )
    
    # Test scanning with default tags
    blocks = client.scan_logseq(test_dir)
    assert len(blocks) == 2
    assert any("#thought" in block.tags for block in blocks)
    assert any("#broadcast" in block.tags for block in blocks)
    
    # Test scanning with specific tag filter
    blocks = client.scan_logseq(test_dir, tag_filter="#thought")
    assert len(blocks) == 1
    assert blocks[0].tags == ["#thought"]
    
    # Test scanning with list of tags
    blocks = client.scan_logseq(test_dir, tag_filter=["#broadcast"])
    assert len(blocks) == 1
    assert blocks[0].tags == ["#broadcast"]
    
    # Clean up
    shutil.rmtree(test_dir)
```

- [ ] Test error handling for invalid directories:
```python
def test_scan_logseq_invalid_dir():
    client = CogniMemoryClient(
        chroma_path="./test_chroma",
        archive_path="./test_archive"
    )
    
    # Test with non-existent directory
    with pytest.raises(FileNotFoundError):
        client.scan_logseq("./nonexistent_dir")
```

- [ ] Test tag filtering with different input formats:
```python
def test_scan_logseq_tag_filtering():
    # Setup test directory with sample file
    test_dir = "./test_logseq"
    os.makedirs(test_dir, exist_ok=True)
    
    with open(f"{test_dir}/test.md", "w") as f:
        f.write("- Block with multiple #thought #broadcast #approved tags\n")
    
    client = CogniMemoryClient(
        chroma_path="./test_chroma",
        archive_path="./test_archive"
    )
    
    # Test with string input
    blocks = client.scan_logseq(test_dir, tag_filter="#thought")
    assert len(blocks) == 1
    
    # Test with list input
    blocks = client.scan_logseq(test_dir, tag_filter=["#broadcast"])
    assert len(blocks) == 1
    
    # Test with set input
    blocks = client.scan_logseq(test_dir, tag_filter={"#approved"})
    assert len(blocks) == 1
    
    # Test with non-existent tag
    blocks = client.scan_logseq(test_dir, tag_filter="#nonexistent")
    assert len(blocks) == 0
    
    # Clean up
    shutil.rmtree(test_dir)
```

## Notes
- Reuse the existing LogseqParser from parser.py for block extraction
- Make tag filtering flexible with both string and list/set inputs
- Return MemoryBlock instances directly, ready for use or further processing
- No need for embedding at this stage - focus on fast file scanning

## Dependencies
- LogseqParser from infra_core/memory/parser.py
- MemoryBlock schema from infra_core/memory/schema.py 