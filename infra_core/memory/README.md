# Cogni Memory Architecture

The Cogni Memory system is designed with a dual-layer architecture that provides both high-performance semantic search and direct file manipulation capabilities.

## Dual-Layer Architecture

### 🔥 Hot Memory Layer (Vector-Based)
- Optimized for fast semantic search using ChromaDB
- Stores embedded blocks for similarity matching
- Used for context retrieval and knowledge search
- Not directly visible to humans without query

### 🐢 Structured Memory Layer (File-Based)
- Direct operations on Logseq .md files
- Enables human visibility through standard Logseq interface
- Provides reading, writing, and scanning operations
- No vector embedding, focuses on file I/O

## Operation Types

### Vector-Only Operations
These operations exclusively interact with the vector database (ChromaDB) and do not perform any file I/O:

- `save_blocks()` - Save memory blocks to the vector database for semantic search
- `query()` - Search for semantically similar blocks in the vector database
- `archive_blocks()` - Move blocks from hot storage to archive storage

### File Operations
These operations interact directly with Logseq markdown files and do not affect the vector database:

- `scan_logseq()` - Extract blocks from Logseq markdown files without embedding
- `get_page()` - Load the full content of a markdown file
- `write_page()` - Write or append content to a markdown file

### Bridging Operations
This operation connects both layers:

- `index_from_logseq()` - Scans Logseq files and indexes the blocks in the vector database

## Important Usage Notes

1. **Vector-File Separation**: Changes made to files do not automatically update the vector database. You must explicitly re-index or save blocks to keep the vector database in sync with file changes.

2. **Query Limitations**: The `query()` method only searches through blocks that have been previously saved to the vector database using `save_blocks()` or `index_from_logseq()`. It does not scan or read any files during the search.

3. **File Write Limitations**: The `save_blocks()` method only affects the vector database and does not write to any markdown files. To create or update files, use the `write_page()` method.

## Example: Dual-Layer Workflow

```python
# 1. Read directly from files (file operation)
blocks = memory_client.scan_logseq("./logseq", tag_filter=["#thought"])

# 2. Store in vector database for search (vector operation)
memory_client.save_blocks(blocks)

# 3. Perform semantic search (vector operation)
results = memory_client.query("What are my recent thoughts about AI?", n_results=5)

# 4. Write new content to a file (file operation)
memory_client.write_page(
    "./logseq/insights.md",
    "# New Insights\n\nBased on your recent thoughts about AI, I think...",
    append=True
)
```

## Performance Considerations

- Vector operations (`save_blocks()`, `query()`) involve embedding, which may be computationally intensive for large datasets.
- File operations (`scan_logseq()`, `get_page()`, `write_page()`) are generally faster as they don't require embedding.
- For large-scale operations, use batch processing and consider memory constraints. 