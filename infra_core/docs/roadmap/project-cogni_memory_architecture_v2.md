# Project:[CogniMemoryClient V2 (Dual Layer)]
:type: Project
:status: planning
:epic: [[Cogni_Memory_System]]

```
┌───────────────────────────────────────────────────────────────┐
│                     CogniMemoryClient V2                      │
└───────────────────────────────────────────────────────────────┘
               ┌─────────────┐         ┌─────────────┐
               │  Interface  │         │    Tests    │
               └─────────────┘         └─────────────┘
               ┌─────────────────────────────────────┐
               │                                     │
    ┌──────────▼───────────┐           ┌─────────────▼────────┐
    │ 🔥 Hot Memory Layer  │           │ 🐢 Structured Layer  │
    │   (Vector-Based)     │           │    (File-Based)      │
    └──────────┬───────────┘           └─────────────┬────────┘
               │                                     │
┌──────────────▼─────────────┐      ┌───────────────▼────────────┐
│ • save_blocks()            │      │ • scan_logseq()            │
│ • query()                  │      │ • get_page()               │
│ • archive_blocks()         │      │ • write_page()             │
│ • index_from_logseq()      │      │                            │
└──────────────┬─────────────┘      └───────────────┬────────────┘
               │                                    │
   ┌───────────▼────────────┐      ┌───────────────▼────────────┐
   │     ChromaDB           │      │     Logseq .md Files       │
   │  (Vector Database)     │      │  (Human-Readable Files)    │
   └────────────────────────┘      └────────────────────────────┘
```

## Project Overview
Expand the current CogniMemoryClient to support both hot vector-based memory (ChromaDB) and structured file-based memory (direct Logseq .md file operations). This dual-layer approach enables both high-performance semantic search and direct file manipulation for human visibility.

## Architecture
CogniMemoryClient V2 will provide a unified interface with two distinct layers:

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

## Implementation Flow
- [x] Add scan_logseq() - Extract blocks without embedding
  - [x] Design task document with requirements
  - [x] Create stubbed tests
  - [x] Implementation
- [x] Add get_page() - Load full content of markdown files
  - [x] Design task document with requirements
  - [x] Create stubbed tests
  - [x] Implementation
- [x] Add write_page() - Write or append to markdown files
  - [x] Design task document with requirements
  - [x] Create stubbed tests
  - [x] Implementation
- [/] Refactor memory_indexer.py - Extract logic to CogniMemoryClient
  - [x] Design task document with requirements
  - [x] Create stubbed tests
  - [ ] Implementation
- [/] Document save_blocks() and query() - Clarify vector-only behavior
  - [x] Design task document with requirements
  - [ ] Implementation

## Success Criteria
1. Agent systems can directly scan and extract blocks from Logseq files without embedding overhead
2. Agents can read full page content from markdown files without parsing into blocks
3. Agents can write content to markdown files for direct human visibility
4. Vector indexing is available programmatically through a clean interface
5. Documentation clearly separates vector operations from file operations
6. All functionality is well-tested with comprehensive test coverage

## Design Principles
1. **Clear Separation**: Each method should clearly indicate whether it operates on vectors or files
2. **Reuse Existing Code**: Leverage the existing LogseqParser and embedding functions
3. **Minimal Dependencies**: Keep external dependencies to a minimum
4. **Comprehensive Documentation**: Ensure clear docstrings and examples for all methods
5. **Thorough Testing**: Implement tests for all new functionality with good coverage

## Use Cases

### Case 1: Agent Reading Logseq Files
```python
# Scan specific tags without embedding overhead
blocks = memory_client.scan_logseq("./logseq", tag_filter=["#task", "#todo"])

# Read full page content
page_content = memory_client.get_page("./logseq/projects/project-x.md")
```

### Case 2: Agent Writing to Logseq Files
```python
# Write new content to a file (creating if needed)
memory_client.write_page(
    "./logseq/projects/new-insights.md",
    "# Agent Insights\n\nHere are my thoughts on the data..."
)

# Append to an existing page
memory_client.write_page(
    "./logseq/journal/2023_07_01.md",
    "\n- New journal entry added by agent #agent-note",
    append=True
)
```

### Case 3: Vector Indexing for Semantic Search
```python
# Index blocks from Logseq for vector search
total_indexed = memory_client.index_from_logseq(
    logseq_dir="./logseq",
    tag_filter="#important"
)

# Query the vector database
results = memory_client.query(
    "What were the key insights from last week?",
    filter_tags=["#insight"]
)
```

## Benefits
1. **Human-Agent Alignment**: Enables agents to read from and write to the same files humans use
2. **Dual-Speed Access**: Fast vector search when needed, direct file access when appropriate
3. **Visibility**: Agent actions become visible in Logseq interface
4. **Flexibility**: Different access patterns for different use cases
5. **Clean Architecture**: Clear separation between vector and file operations 