# Task:[Implement MCP File Memory]
:type: Task
:status: todo
:project: [project-langchain-memory-integration]

## Current Status
- [x] Task design document created (this file)
- [ ] Directory structure created
- [ ] MemoryBlock schema implementation
- [ ] BaseMemory interface implementation
- [ ] JSON storage backend implementation
- [ ] Schema validation integration
- [ ] Unit tests implemented

## Description
Implement the `MCPFileMemory` adapter that conforms to LangChain's `BaseMemory` interface while storing data in a schema-validated JSON format. This adapter will serve as the primary memory component for Cogni agents, replacing the current `CogniMemoryClient` with a LangChain-compatible solution that maintains all essential functionality.

## Input
- Memory architecture design document
- MCP schema definition
- LangChain BaseMemory interface requirements
- Current memory usage patterns

## Output
- Fully implemented `MCPFileMemory` class
- Schema validation system
- File-based JSON storage backend
- Comprehensive unit tests

## Action Items
- [ ] **Set Up Development Environment:**
  - [ ] Create directory structure
  - [ ] Install required dependencies (langchain, jsonschema, etc.)
  - [ ] Set up test framework

- [ ] **Implement MemoryBlock Data Model:**
  - [ ] Define Pydantic model for memory blocks
  - [ ] Implement serialization and deserialization methods
  - [ ] Integrate JSON schema validation
  - [ ] Create helper methods for common operations
  - [ ] Ensure metadata flexibility for future embedding IDs

- [ ] **Create JSON Storage Backend:**
  - [ ] Implement file-based JSON storage
  - [ ] Design hierarchical path structure (`<agent_name>/<timestamp>.json`)
  - [ ] Add CRUD operations for memory blocks
  - [ ] Implement basic retrieval capabilities
  - [ ] Handle error conditions
  - [ ] Add simple in-memory index for performance

- [ ] **Implement MCPFileMemory Class:**
  - [ ] Create class inheriting from `BaseMemory`
  - [ ] Implement `load_memory_variables()` method
  - [ ] Implement `save_context()` method
  - [ ] Add simple memory retrieval
  - [ ] Implement basic filtering
  - [ ] Create minimal configuration options

- [ ] **Implement Tests:**
  - [ ] Create unit tests for core functionality
  - [ ] Test schema validation
  - [ ] Test error handling
  - [ ] Add basic performance tests
  - [ ] Test overwriting memory blocks
  - [ ] Test merging outputs across workflows
  - [ ] Test invalid writes (schema errors)
  - [ ] Test concurrent access

## Deliverables
1. `MCPFileMemory` class implementing BaseMemory interface
2. MemoryBlock model with schema validation
3. JSON storage backend for persistent memory
4. Basic query and retrieval system
5. Core test suite

## Implementation Details
```python
from langchain.memory.base import BaseMemory
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
import json
import os
from datetime import datetime
import jsonschema

class MemoryBlock(BaseModel):
    """Simple memory block model with basic fields."""
    id: str
    content: str
    metadata: Dict[str, Any]
    created_at: datetime
    tags: List[str] = []
    agent_id: Optional[str] = None
    embedding_id: Optional[str] = None  # For future vector integration
    
    # Schema validation and serialization methods

class MCPFileMemory(BaseMemory):
    """Memory implementation that stores data in schema-validated JSON files."""
    
    memory_directory: str
    schema_path: str
    memory_key: str = "history"
    agent_id: Optional[str] = None
    
    def __init__(self, memory_directory: str, schema_path: str, memory_key: str = "history", agent_id: Optional[str] = None):
        """Initialize with directory to store memory files."""
        self.memory_directory = memory_directory
        self.schema_path = schema_path
        self.memory_key = memory_key
        self.agent_id = agent_id
        self._memory_blocks = {}  # Simple in-memory index for performance
        
        # Create base directory
        os.makedirs(memory_directory, exist_ok=True)
        
        # Create agent directory if specified
        if agent_id:
            agent_dir = os.path.join(memory_directory, agent_id)
            os.makedirs(agent_dir, exist_ok=True)
            
        # Load schema
        with open(schema_path, 'r') as f:
            self.schema = json.load(f)
            
        # Initialize memory cache
        self._load_memory_index()
    
    def _load_memory_index(self):
        """Load memory blocks into in-memory index for faster access."""
        # Implementation of index loading logic
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Load memory variables relevant to the inputs."""
        # Implementation of memory loading logic
        
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """Save context from this conversation to memory."""
        # Implementation of memory saving logic with schema validation
        
    def _get_file_path(self, memory_id: str) -> str:
        """Get the file path for a memory block based on agent_id."""
        if self.agent_id:
            return os.path.join(self.memory_directory, self.agent_id, f"{memory_id}.json")
        return os.path.join(self.memory_directory, f"{memory_id}.json")
```

## Test Criteria
- All BaseMemory interface methods correctly implemented
- Schema validation enforced on all memory operations
- Memory retrieval returns relevant context based on inputs
- Memory persistence works correctly
- Error handling gracefully manages edge cases
- Hierarchical file structure works as expected
- In-memory index improves performance
- Concurrent access handled properly

## Integration Points
- **LangChain**: BaseMemory interface implementation
- **JSON Schema**: For memory validation
- **CogniAgent**: For agent integration
- **Markdown Export**: For integration with human-readable exports

## Notes
- Focus on simplicity and reliability for the first implementation
- Use JSON as the single source of truth
- Skip advanced features like complex filtering in v1
- Consider performance for basic operations with simple indexing
- Document the interface thoroughly
- Design with extensibility in mind but implement only core features
- Ensure metadata flexibility for future embedding IDs
- Implement hierarchical file structure for better organization and future scaling

## Dependencies
- LangChain/LangChain-Core libraries
- JSON Schema validation library
- Memory architecture design document
- MCP schema definition
- Pydantic for data modeling 