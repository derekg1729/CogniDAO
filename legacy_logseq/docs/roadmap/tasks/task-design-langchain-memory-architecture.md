# Task:[Design LangChain Memory Architecture]
:type: Task
:status: todo
:project: [project-langchain-memory-integration]

## Current Status
- [x] Task design document created (this file)
- [ ] MCP schema definition drafted
- [ ] BaseMemory interface mapping completed
- [ ] Directory structure designed
- [ ] Data flow diagrams created
- [ ] Implementation plan documented

## Description
Design the architecture for replacing the custom `CogniMemoryClient` with a streamlined LangChain-compatible memory component. This task will establish the foundation for implementing the LangChain memory integration, ensuring a clear schema definition, interface mapping, and implementation plan for direct transition from the current approach.

## Input
- Current `CogniMemoryClient` implementation and usage patterns
- LangChain `BaseMemory` interface requirements
- Agent memory requirements (context loading, spirit guides, etc.)
- Project constraints and requirements

## Output
- MCP schema definition for memory blocks
- Interface mapping from LangChain BaseMemory to our requirements
- Directory structure for memory storage
- Simple data flow diagrams
- Streamlined implementation plan

## Action Items
- [ ] **Analyze Current Usage Patterns:**
  - [ ] Review agent code using `CogniMemoryClient`
  - [ ] Document essential methods used in current implementation
  - [ ] Identify core functionality to preserve
  
- [ ] **Define MCP Schema:**
  - [ ] Design JSON schema for memory blocks
  - [ ] Include essential fields (content, metadata, source, etc.)
  - [ ] Define validation rules
  - [ ] Create schema documentation
  - [ ] Provide example memory blocks
  - [ ] Ensure metadata flexibility for embedding IDs
  - [ ] Add agent_id field for hierarchical organization
  
- [ ] **Map LangChain BaseMemory Interface:**
  - [ ] Review `BaseMemory` interface requirements
  - [ ] Map `load_memory_variables()` to our requirements
  - [ ] Map `save_context()` to our requirements
  - [ ] Document the mapping
  
- [ ] **Design Directory Structure:**
  - [ ] Define hierarchical folder organization (`memory/json/<agent_id>/`)
  - [ ] Establish naming conventions
  - [ ] Determine file organization strategy
  - [ ] Document directory structure
  - [ ] Plan for UUID-based file naming
  
- [ ] **Create Data Flow Diagrams:**
  - [ ] Diagram memory load operations
  - [ ] Diagram memory save operations
  - [ ] Diagram in-memory indexing for performance
  - [ ] Document component interactions
  
- [ ] **Document Implementation Approach:**
  - [ ] Outline implementation steps and sequence
  - [ ] List required changes to agent base class
  - [ ] Document migration strategy for existing agents
  - [ ] Create implementation timeline
  - [ ] Detail simple in-memory indexing strategy

## Deliverables
1. MCP schema definition for memory blocks (JSON Schema format)
2. Interface mapping document (LangChain BaseMemory to Cogni requirements)
3. Directory structure specification with hierarchical organization
4. Data flow diagrams (load, save operations)
5. Implementation plan document

## Sample Schema
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "description": "Unique identifier for the memory block"
    },
    "content": {
      "type": "string",
      "description": "The main content of the memory block"
    },
    "metadata": {
      "type": "object",
      "description": "Flexible metadata for the memory block",
      "additionalProperties": true
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "description": "Timestamp when this memory was created"
    },
    "tags": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "Tags associated with this memory"
    },
    "agent_id": {
      "type": "string",
      "description": "ID of the agent that created this memory"
    },
    "embedding_id": {
      "type": ["string", "null"],
      "description": "Optional ID for associated embedding in vector store"
    }
  },
  "required": ["id", "content", "created_at"],
  "additionalProperties": false
}
```

## Test Criteria
- Schema covers essential memory block requirements
- Interface mapping addresses core functionality
- Directory structure optimized for JSON storage
- Data flow diagrams clearly illustrate the new architecture
- Implementation plan is direct and straightforward

## Integration Points
- **LangChain BaseMemory**: Primary interface implementation
- **CogniAgent base class**: For integration of new memory approach
- **Existing agents**: GitCogni, CoreCogni, BroadcastCogni
- **Markdown export utility**: For human-readable exports (optional)

## Notes
- Focus on simplicity and LangChain alignment
- JSON is the single source of truth for memory storage
- Schema validation is essential for data integrity
- Separate storage from rendering/export for clean architecture
- Skip backward compatibility, compatibility shims, and complex features for v1
- Use agent_id for hierarchical organization of memory files
- Include embedding_id in schema for future vector integration
- Simple in-memory index should supplement file system for performance
- Design for future extensibility while keeping v1 implementation focused

## Dependencies
- LangChain documentation review
- Understanding of current agent memory usage
- JSON Schema expertise 