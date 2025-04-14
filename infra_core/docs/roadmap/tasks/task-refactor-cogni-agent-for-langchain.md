# Task:[Refactor CogniAgent for LangChain Memory]
:type: Task
:status: todo
:project: [project-langchain-memory-integration]

## Current Status
- [x] Task design document created (this file)
- [ ] Requirements analysis completed
- [ ] Base class modifications designed
- [ ] Memory initialization implemented
- [ ] Spirit guide loading refactored
- [ ] Record action refactored
- [ ] Tests updated

## Description
Refactor the `CogniAgent` base class to use LangChain-compatible memory components instead of the custom `CogniMemoryClient`. This task involves updating the initialization, spirit guide loading, and action recording methods to work with the new `MCPFileMemory` adapter for a clean, direct implementation.

## Input
- Current `CogniAgent` implementation
- `MCPFileMemory` implementation
- Usage patterns from derived agent classes

## Output
- Refactored `CogniAgent` base class
- Updated initialization with LangChain memory
- Refactored spirit guide loading
- Refactored action recording
- Updated tests

## Action Items
- [ ] **Analyze Current Implementation:**
  - [ ] Review `CogniAgent.__init__()` method
  - [ ] Document current memory client usage
  - [ ] Identify all memory operations in the base class
  - [ ] Map current methods to LangChain memory interface

- [ ] **Design Refactored Implementation:**
  - [ ] Design new initialization process
  - [ ] Create strategy for `load_spirit()` method
  - [ ] Design refactored `record_action()` method
  - [ ] Document required changes

- [ ] **Implement Base Class Changes:**
  - [ ] Update imports to include LangChain components
  - [ ] Modify `__init__()` to use `MCPFileMemory`
  - [ ] Update initialization parameters
  - [ ] Create JSON schema directory and files
  - [ ] Configure hierarchical memory directory structure
  - [ ] Add agent name as part of memory organization

- [ ] **Refactor Spirit Guide Loading:**
  - [ ] Modify `load_spirit()` to use LangChain memory
  - [ ] Update error handling
  - [ ] Maintain fallback mechanisms

- [ ] **Refactor Core Context Loading:**
  - [ ] Update `load_core_context()` to use LangChain memory
  - [ ] Adapt formatting for context structure
  - [ ] Ensure metadata is preserved

- [ ] **Refactor Action Recording:**
  - [ ] Modify `record_action()` to use LangChain memory
  - [ ] Use markdown export utility if needed
  - [ ] Update file writing mechanism

- [ ] **Update Tests:**
  - [ ] Modify agent test cases
  - [ ] Add tests for memory integration
  - [ ] Verify correct error handling

## Deliverables
1. Refactored `CogniAgent` base class with LangChain memory integration
2. Updated initialization method with memory configuration
3. Refactored spirit guide and core context loading
4. Refactored action recording with markdown export capabilities
5. Updated test suite

## Implementation Details
```python
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
import os
from typing import Dict, Any, List, Optional

from infra_core.memory.adapters.mcp_file_memory import MCPFileMemory
from infra_core.utils.markdown_renderer import format_agent_output, write_markdown


class CogniAgent(ABC):
    """
    Abstract base class for all Cogni agents.
    
    Each agent represents an autonomous entity with a specific role and spirit guide.
    Agents load their spirit guide, prepare inputs, act based on their guide,
    and record their actions.
    """
    
    def __init__(self, name: str, spirit_path: Path, agent_root: Path):
        """
        Initialize a new CogniAgent.
        
        Args:
            name: The name of the agent
            spirit_path: Path to the spirit guide markdown file
            agent_root: Root directory for agent outputs
        """
        self.name = name
        self.spirit_path = spirit_path
        self.agent_root = agent_root
        self.spirit = None
        self.core_context = None
        
        # Get the project root directory (3 levels up from this file)
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
        
        # Use absolute paths for memory locations
        memory_directory = os.path.join(project_root, "infra_core/memory/json")
        schema_path = os.path.join(project_root, "infra_core/memory/schemas/memory_block.schema.json")
        
        # Initialize memory with LangChain adapter
        # Use agent name for hierarchical organization
        self.memory = MCPFileMemory(
            memory_directory=memory_directory,
            schema_path=schema_path,
            memory_key="history",
            agent_id=name
        )

        # Load the spirit guide
        self.load_spirit()
```

## Test Criteria
- All tests for derived agent classes pass with the refactored base class
- Spirit guide loading functions correctly with the new memory adapter
- Action recording produces the expected output files
- Memory operations use the LangChain BaseMemory interface
- Error handling maintains robustness for all operations
- Hierarchical memory organization works correctly by agent

## Integration Points
- **MCPFileMemory**: Primary memory implementation
- **Markdown Renderer**: For human-readable exports
- **Derived Agent Classes**: Must continue to function with the new base class
- **Testing Framework**: For validating the refactored implementation

## Notes
- Direct replacement of CogniMemoryClient with MCPFileMemory
- Use LangChain's BaseMemory interface for all memory operations
- JSON is the primary storage format, markdown is just for display
- Keep implementation simple and focused
- Document the new approach clearly
- No compatibility shims or backward compatibility layers
- Use agent name for hierarchical organization of memory files
- Memory files will be stored in agent-specific directories for clean separation

## Dependencies
- MCPFileMemory implementation
- Markdown rendering utility
- JSON schema definition
- Existing agent implementations
- Updated test framework 