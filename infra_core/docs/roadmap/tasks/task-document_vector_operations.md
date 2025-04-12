# Task:[Document save_blocks() and query() In CogniMemoryClient]
:type: Task
:status: todo
:project: [project-cogni_memory_architecture]
:owner: 

## Current Status
- [x] Task design document completed
- [ ] Implementation not yet started
- Note: This task only requires documentation updates, not code changes or tests

## Description
Clarify the behavior of existing `save_blocks()` and `query()` methods in CogniMemoryClient, emphasizing that they operate on the vector database only, with no direct file I/O. This will help developers understand the clear separation between vectorized "hot" memory and file-based "structured" memory operations.

## Action Items
- [ ] Review and update docstrings for `save_blocks()` method
- [ ] Review and update docstrings for `query()` method
- [ ] Add explanatory comments about the vector-only nature of these operations
- [ ] Create a clear example in the documentation showing the separation
- [ ] Update type hints for clarity where needed
- [ ] Add warnings where appropriate about memory limitations
- [ ] Write developer documentation in README.md or a dedicated documentation file

## Deliverables
1. Updated docstrings for `save_blocks()` in memory_client.py:
   ```python
   def save_blocks(self, blocks: List[Union[MemoryBlock, Dict]]):
       """
       Save memory blocks to hot storage (ChromaDB vector database).
       
       IMPORTANT: This method only affects the vector database, NOT markdown files.
       Blocks are embedded and saved for semantic search, but no files are written.
       Use write_page() if you need to write to disk.
       
       Args:
           blocks: List of MemoryBlock objects or dictionaries
                  If dictionaries are provided, they must have at minimum
                  the following fields: text, tags, source_file
       
       Raises:
           ValueError: If blocks are missing required fields
           Exception: For embedding or storage errors
       """
   ```

2. Updated docstrings for `query()` in memory_client.py:
   ```python
   def query(
       self, 
       query_text: str, 
       n_results: int = 5, 
       include_archived: bool = False, 
       filter_tags: Optional[List[str]] = None
   ) -> QueryResult:
       """
       Query memory blocks with semantic search using the vector database.
       
       This method performs a similarity search against the vector embeddings
       stored in ChromaDB. It does NOT search markdown files directly.
       Use scan_logseq() if you need to extract blocks from markdown files.
       
       Args:
           query_text: Text to search for
           n_results: Number of results to return
           include_archived: Whether to include archived blocks
           filter_tags: Optional filter for specific tags
           
       Returns:
           QueryResult object with blocks sorted by relevance to the query
           
       Notes:
           - Results are ranked by semantic similarity to the query
           - Performance is optimized for speed over exhaustive search
           - Very large result sets may impact performance
       """
   ```

3. Developer documentation in README.md or dedicated documentation file

## Test Criteria
The main goal is to clarify existing functionality rather than adding new features, so the test criteria focus on ensuring the behavior is clear and documented properly:

- [ ] Review docstrings for clarity and accuracy
- [ ] Verify all parameters are properly described
- [ ] Confirm return values are clearly specified
- [ ] Ensure limitations and edge cases are documented
- [ ] Validate that examples accurately reflect behavior

## Notes
- Focus on clear separation between vector operations and file operations
- Emphasize when embedding occurs and when it does not
- Highlight that save_blocks() does not write to disk in Logseq format
- Document performance considerations for large result sets
- Provide guidance on when to use which method for different use cases

## Dependencies
- None for documentation updates, as these clarify existing behavior 