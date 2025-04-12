# Task:[Parse Logseq Blocks]
:type: Task
:status: in-progress
:project: [project-cogni_memory_architecture]
:owner: 

## Description
Implement the parsing logic to scan and extract high-signal blocks from Logseq `.md` files. Focus on blocks tagged with #thought, #broadcast, #approved or other designated tags.

## Action Items
- [x] Create parser module to scan through .md files in a given Logseq directory (basic implementation in memory_indexer.py)
- [x] Implement regex or markdown parser to extract individual blocks (basic line-based parsing)
- [x] Add filtering logic to identify blocks with specific tags (#thought, #broadcast, #approved)
- [x] Create data structure to store block text, tags, source file, and unique identifier
- [ ] Add metadata extraction for blocks (timestamp, references, etc.)
- [/] Include unit tests for parser functionality (basic tests implemented)

## Deliverables
1. A `parser.py` module with functions to:
   - Scan directories for .md files
   - Extract blocks from markdown with regex
   - Filter blocks based on tags
   - Create structured data with metadata

2. Unit tests demonstrating parser functionality with sample data

## Test Criteria
- [x] Test with sample Logseq markdown files containing various blocks
- [x] Verify all blocks with #thought, #broadcast, #approved tags are detected
- [x] Confirm parser extracts correct metadata (file source, tags, etc.)
- [ ] Validate parser handling of malformed markdown without crashing
- [ ] Verify extraction of block text preserves formatting

Example test:
```python
def test_parser():
    parser = LogseqParser("./test_data")
    blocks = parser.extract_all_blocks()
    
    # Should find at least 3 blocks with target tags
    assert len(blocks) >= 3
    
    # Verify tags are extracted correctly
    assert any("#thought" in block.tags for block in blocks)
    
    # Verify metadata contains source file
    assert all(block.source_file for block in blocks)
```

## Notes
- Parser should be file-based only, no integration with Logseq internals
- Consider supporting both full-text blocks and references
- Prioritize reliability and clear error handling
- Design for extensibility to support additional tags in the future

## Dependencies
- Python frontmatter library for `.md` parsing
- File I/O utilities 