# Project:[LangChain Memory Integration]
:type: Project
:status: planning
:epic: [[Epic_Presence_and_Control_Loops]]
- ## Project Overview
  This project aims to replace the custom `CogniMemoryClient` with LangChain-compatible memory components, aligning Cogni with the LangChain/LangGraph ecosystem while preserving key functionalities such as agent context loading, spirit guides, and markdown exports. This streamlined approach will significantly reduce complexity and enable seamless integration with LangChain's powerful features.
- ## Architecture
  ```
  ┌────────────────────────┐
  │      CogniAgent        │
  └─────────┬──────────────┘
          │
          │ uses
          ▼
  ┌────────────────────────┐         ┌────────────────────────┐
  │    MCPFileMemory       │────────►│    JSON Storage        │
  │   (LangChain-Based)    │         │  (MCP Schema Format)   │
  │ CogniLangchainMemoryAdapter│───────►│ JSON Session Storage   │
  │ (LangChain BaseMemory) │         │ (MCP-inspired schema)  │
  └─────────┬──────────────┘         └─────────┬──────────────┘
          │ uses                             │ uses
          │                                  ▼
          │                          ┌────────────────────────┐
          │                          │    CogniMemoryBank     │
          │                          │   (Core File Logic)    │
          │                          └────────────────────────┘
          │
  ┌────────────────────────┐
  │   Markdown Renderer    │
  │   (Human-Readable)     │
  └────────────────────────┘
  ```
- ## Implementation Flow
- [ ] Design the LangChain Memory Architecture
	- [ ] Define MCP schema for memory blocks
	- [ ] Map LangChain BaseMemory interface to our requirements
	- [ ] Design directory structure
- [x] Create the MCPFileMemory adapter (*Refactored to CogniMemoryBank + CogniLangchainMemoryAdapter*)
	- [x] Implement BaseMemory interface (load_memory_variables, save_context) in Adapter
	- [ ] Add schema validation (*Deferred*)
	- [x] Implement directory-based JSON storage in Core Bank
	- [ ] Add basic in-memory indexing for performance (*Deferred*)
- [ ] Create simple utility for Markdown export
	- [ ] Implement basic formatting for human readability
	- [ ] Add minimal export utilities
- [ ] Refactor CogniAgent base class
	- [ ] Replace CogniMemoryClient with CogniLangchainMemoryAdapter
	- [ ] Update load_spirit to use memory adapter
	- [ ] Refactor record_action for memory adapter
- [ ] Migrate existing agents
	- [ ] Update GitCogni
	- [ ] Update CoreCogni
	- [ ] Update BroadcastCogni
- [ ] Update tests
	- [ ] Create tests for CogniMemoryBank and Adapter
	- [ ] Update agent tests
- ## Success Criteria
  1. Agents use LangChain BaseMemory implementation for all memory operations
  2. No functionality regression in existing agents
  3. Improved context relevance through structured memory
  4. Seamless integration with LangChain and LangGraph
  5. Optional human-readable exports via Markdown
  6. Simplified codebase with reduced custom logic
  7. Validated schema for all memory operations (*Deferred for MVP*)
- ## Design Principles
  1. **Ecosystem Alignment**: Leverage LangChain patterns and interfaces
  2. **Schema Validation**: Use MCP schema for all memory operations
  3. **Separation of Concerns**: Memory storage vs. export formats
  4. **JSON First**: Use JSON as the single source of truth
  5. **Simplicity**: Focus on core functionality, defer complex features
- ## Tasks
- [ ] [[task-design-langchain-memory-architecture]] - Design the overall architecture (*Consider marking as complete or refining based on MVP*)
- [x] [[task-implement-mcp-file-memory]] - Implement the `CogniMemoryBank` and `CogniLangchainMemoryAdapter` (*Task name might need update to reflect split*)
- [ ] [[task-create-markdown-export-utility]] - Create minimal utility for human-readable exports
- [ ] [[task-refactor-cogni-agent-for-langchain]] - Refactor base agent to use LangChain memory
- [ ] [[task-update-agent-tests]] - Update tests for new memory system
- ## Notes
## Deferred for v1
- Vector store integration (planned for LangChain hybrid memory)
- Context deduplication or summarization
- Session linking or memory inheritance
- File locking/concurrent writes
- Schema validation beyond basic JSON structure
- Basic in-memory indexing for performance

## Notes (Original)
The LangChain adapter (`CogniLangchainMemoryAdapter`) implements BaseMemory.
The core logic (`CogniMemoryBank`) handles file I/O.
Markdown export remains an optional view layer.
Vector storage integration is deferred.
This approach prioritizes simplicity and direct alignment with LangChain patterns
Skip compatibility shims, custom formatters, and advanced queries for v1
File structure should follow `memory/json/<agent_name>/<timestamp>.json` or use UUIDs with origin metadata (*Current MVP uses `_memory_banks_experiment/<project_name>/<session_id>`*)
Schema should maintain flexibility in metadata to accommodate future embedding IDs
While complex indexing is deferred, a simple in-memory index should be added for performance
MCP in the name maintains conceptual clarity and alignment with the protocol system (*Name changed to reflect Cogni implementation*)