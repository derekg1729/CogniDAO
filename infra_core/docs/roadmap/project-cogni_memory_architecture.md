# project-cogni_memory_architecture
:type: Project
:status: in-progress
:epic: [[Epic_Presence_and_Control_Loops]]

## Description
Establish a multi-tiered memory system for Cogni that supports human-readable working context, fast AI lookup, and long-term memory preservation. This project powers selective oversight, state awareness, and structured evolution of Cogni agents.

### MVP
- Logseq `.md` files are indexed as the working set
- Approved blocks are ingested into a local Vector DB (e.g. Chroma or Qdrant)
- Cold archive system for older `.md` blocks with metadata indexing
- Unified memory client interface to:
  - query relevant context
  - write new memories
  - archive old blocks

### Future Vision
- Fully unified CogniMemory abstraction layer used across all agents
- Memory snapshots for state-time debugging and inflection tracking
- Memory-weighted prompt construction (recency, approval, strategic tags)
- Cross-agent memory syncing with MCP hooks
- Training of tone/style classifiers from historical human approvals

## Implementation Flow
1. [[task-parse_logseq_blocks]] - Parse Logseq blocks from markdown files
2. [[task-save_vector_db_records]] - Embed and store blocks in ChromaDB
3. [[task-create_memory_index_json]] - Create archive system with JSON indexing
4. [[task-build_cogni_memory_client]] - Build unified memory client interface
5. [[task-memory_indexer_main]] - Create main entry point script
6. [[task-integrate_into_broadcastcogni]] - Integrate with BroadcastCogni agent

## Testing Strategy
Each component includes specific test criteria as outlined in the individual task files.
The testing strategy progresses from:
1. Unit tests for each component (parser, embedder, storage)
2. Integration tests across components
3. End-to-end tests of the complete pipeline
4. Agent integration tests with BroadcastCogni

## Key Components
- Logseq `.md` file parser and tag indexer (`parser.py`)
- OpenAI embedding integration (`embedder.py`)
- ChromaDB storage system (`storage.py`)
- Cold archive system with JSON metadata
- Unified memory access interface (`CogniMemoryClient`)
- Memory tool for agent integration (`memory_tool.py`)
- Main entry point script (`memory_indexer.py`)

## Key Libraries
- [ChromaDB](https://github.com/chroma-core/chroma) - Vector database
- [OpenAI API](https://platform.openai.com/) - Text embeddings
- [Pydantic](https://docs.pydantic.dev/) - Schema validation
- [Pytest](https://docs.pytest.org/) - Testing framework
- [Frontmatter](https://github.com/eyeseast/python-frontmatter) - Markdown parsing
- [tqdm](https://github.com/tqdm/tqdm) - Progress reporting

## Dependencies
- Existing Logseq graph format and tagging conventions
- OpenAI API access for embeddings
- Python 3.8+ environment

## Success Criteria
- Memory indexer successfully processes Logseq files
- ChromaDB collection is created with embedded blocks
- Semantic search returns relevant results
- Archive system preserves older blocks
- BroadcastCogni uses memory for context enrichment
- Performance meets expectations (indexing speed, query latency)
