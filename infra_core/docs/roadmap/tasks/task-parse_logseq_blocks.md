# Task:[Parse Logseq Blocks]
:type: Task
:status: completed
:project: [project-cogni_memory_architecture]
:owner: 

## Current Status
Parser functionality has been fully implemented in a dedicated `parser.py` module with the following features:
- Scan directories for .md files with configurable glob patterns
- Extract blocks with regex and proper tag filtering
- Robust metadata extraction including frontmatter, file dates, block references
- Conversion to structured MemoryBlock objects
- Comprehensive unit tests verifying all functionality
- Backwards compatibility with existing code

## Description
Implement the parsing logic to scan and extract high-signal blocks from Logseq `.md` files. Focus on blocks tagged with #thought, #broadcast, #approved or other designated tags.

## Action Items
- [x] Create parser module to scan through .md files in a given Logseq directory
  - Implemented in `parser.py` with `LogseqParser.get_markdown_files()` function
- [x] Implement regex or markdown parser to extract individual blocks
  - Implemented in `parser.py` with `LogseqParser.extract_blocks_from_file()` function
- [x] Add filtering logic to identify blocks with specific tags (#thought, #broadcast, #approved)
  - Implemented in `parser.py` with configurable target_tags
- [x] Create data structure to store block text, tags, source file, and unique identifier
  - Implemented in `schema.py` as `MemoryBlock` model and supported in parser
- [x] Add metadata extraction for blocks (timestamp, references, etc.)
  - Implemented frontmatter extraction, date parsing, and reference extraction
- [x] Include unit tests for parser functionality
  - Implemented in `tests/test_parser.py` with comprehensive test cases

## Deliverables
1. A `parser.py` module with functions to:
   - Scan directories for .md files ✅
   - Extract blocks from markdown with regex ✅
   - Filter blocks based on tags ✅
   - Create structured data with metadata ✅

2. Unit tests demonstrating parser functionality with sample data ✅

## Test Criteria
- [x] Test with sample Logseq markdown files containing various blocks
  - Tested in `test_parser.py` with sample files created in test fixtures
- [x] Verify all blocks with #thought, #broadcast, #approved tags are detected
  - Tested in `test_extract_blocks_with_tags` function in `test_parser.py`
- [x] Confirm parser extracts correct metadata (file source, tags, etc.)
  - Tested in `test_block_metadata` function in `test_parser.py`
- [x] Validate parser handling of malformed markdown without crashing
  - Tested in `test_malformed_markdown` function in `test_parser.py`
- [x] Verify extraction of block text preserves formatting
  - Validated in multiple test functions in `test_parser.py`

## Implementation Details
The parser implementation includes:

1. `LogseqParser` class with methods:
   - `get_markdown_files()` - Find all markdown files in Logseq directory
   - `extract_blocks_from_file()` - Extract tagged blocks from a file
   - `extract_all_blocks()` - Process all files and extract all blocks
   - `create_memory_blocks()` - Convert to Pydantic models

2. Private helper methods for metadata extraction:
   - `_extract_frontmatter()` - Parse YAML frontmatter
   - `_extract_file_date()` - Extract dates from filenames
   - `_extract_block_tags()` - Extract tags from block text
   - `_parse_block_references()` - Extract Logseq block references
   - `_generate_block_id()` - Create deterministic IDs

3. Standalone functions for backward compatibility:
   - `load_md_files()` - Legacy function for finding markdown files
   - `extract_blocks()` - Legacy function for extracting blocks

## Notes
- Parser is file-based only, no integration with Logseq internals
- Support for both full-text blocks and references
- Implemented error handling at multiple levels
- Design supports extensibility for additional tags

## Dependencies
- Python frontmatter library for `.md` parsing
  - Tested in various parts of `test_memory_indexer.py` and `test_storage.py`
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