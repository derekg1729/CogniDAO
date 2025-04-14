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
  └────────────────────────┘         └────────────────────────┘
          │
          │ exports (when needed)
          ▼
  ┌────────────────────────┐
  │   Markdown Renderer    │
  │   (Human-Readable)     │
  └────────────────────────┘
  ```
- ## MVP Scope Clarification
  This project will begin in a new Git branch (`feat/langchain_memory_agents`) and isolate its first MVP in a standalone directory (`experiments/langchain_agents/`). The MVP goal is to demonstrate two agents using a LangChain-compatible memory adapter to persist and recall structured memory.

  The adapter will initially use the existing MCP-style JSON format as the storage layer. Integration with Cogni's full MemoryClient will come after the MVP.

  Markdown export is a secondary priority, to be added after successful agent memory round-trips are validated.
- ## Implementation Flow
- [ ] Design the LangChain Memory Architecture
	- [ ] Define MCP schema for memory blocks
	- [ ] Map LangChain BaseMemory interface to our requirements
	- [ ] Design directory structure
- [ ] Create the MCPFileMemory adapter
	- [ ] Implement BaseMemory interface (load_memory_variables, save_context)
	- [ ] Add schema validation
	- [ ] Implement directory-based JSON storage
	- [ ] Add basic in-memory indexing for performance
- [ ] Create simple utility for Markdown export
	- [ ] Implement basic formatting for human readability
	- [ ] Add minimal export utilities
- [ ] Refactor CogniAgent base class
	- [ ] Replace CogniMemoryClient with MCPFileMemory
	- [ ] Update load_spirit to use memory adapter
	- [ ] Refactor record_action for memory adapter
- [ ] Migrate existing agents
	- [ ] Update GitCogni
	- [ ] Update CoreCogni
	- [ ] Update BroadcastCogni
- [ ] Update tests
	- [ ] Create tests for MCPFileMemory
	- [ ] Update agent tests
- ## Success Criteria
  1. Agents use LangChain BaseMemory implementation for all memory operations
  2. No functionality regression in existing agents
  3. Improved context relevance through structured memory
  4. Seamless integration with LangChain and LangGraph
  5. Optional human-readable exports via Markdown
  6. Simplified codebase with reduced custom logic
  7. Validated schema for all memory operations
- ## Design Principles
  1. **Ecosystem Alignment**: Leverage LangChain patterns and interfaces
  2. **Schema Validation**: Use MCP schema for all memory operations
  3. **Separation of Concerns**: Memory storage vs. export formats
  4. **JSON First**: Use JSON as the single source of truth
  5. **Simplicity**: Focus on core functionality, defer complex features
- ## Tasks
- [ ] [[task-design-langchain-memory-architecture]] - Design the overall architecture
- [ ] [[task-implement-mcp-file-memory]] - Implement the MCPFileMemory adapter
- [ ] [[task-create-markdown-export-utility]] - Create minimal utility for human-readable exports
- [ ] [[task-create-mvp-prefect-flow]] - Create a basic Prefect flow for the 2-agent MVP
- [ ] [[task-refactor-cogni-agent-for-langchain]] - Refactor base agent to use LangChain memory
- [ ] [[task-update-agent-tests]] - Update tests for new memory system
- ## Notes
- MCPFileMemory will be a direct implementation of LangChain's BaseMemory
- Markdown export is an optional view layer, not the primary storage format
- Vector storage can be added as an optional search layer using LangChain-native components
- This approach prioritizes simplicity and direct alignment with LangChain patterns
- Skip compatibility shims, custom formatters, and advanced queries for v1
- File structure should follow `memory/json/<agent_name>/<timestamp>.json` or use UUIDs with origin metadata
- Schema should maintain flexibility in metadata to accommodate future embedding IDs
- While complex indexing is deferred, a simple in-memory index should be added for performance
- MCP in the name maintains conceptual clarity and alignment with the protocol system