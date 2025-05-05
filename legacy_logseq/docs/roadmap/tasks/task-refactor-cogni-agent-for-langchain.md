# Task:[Refactor CogniAgent for LangChain Memory]
:type: Task
:status: completed
:project: [project-langchain-memory-integration]

## Current Status
- [x] Task design document created (this file)
- [x] Requirements analysis completed
- [x] Base class modifications designed
- [x] Memory initialization implemented (Using `FileMemoryBank` in `base.py`)
- [x] Spirit guide loading refactored (In `base.py`)
- [x] Record action refactored (In `base.py`)
- [x] Tests updated (See [[task-update-agent-tests]])

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
- [x] **Analyze Current Implementation:**
  - [x] Review `CogniAgent.__init__()` method
  - [x] Document current memory client usage
  - [x] Identify all memory operations in the base class
  - [x] Map current methods to LangChain memory interface (Adapter uses `FileMemoryBank`)

- [x] **Design Refactored Implementation:**
  - [x] Design new initialization process (Using `FileMemoryBank`)
  - [x] Create strategy for `load_spirit()` method
  - [x] Design refactored `record_action()` method
  - [x] Document required changes

- [x] **Implement Base Class Changes:**
  - [x] Update imports
  - [x] Modify `__init__()` to use `FileMemoryBank`
  - [x] Update initialization parameters
  - [ ] Create JSON schema directory and files (*Handled by `FileMemoryBank`*)
  - [x] Configure hierarchical memory directory structure (Via `FileMemoryBank` project/session)
  - [x] Add agent name as part of memory organization (Via `FileMemoryBank` session_id)

- [x] **Refactor Spirit Guide Loading:**
  - [x] Modify `load_spirit()` to use `FileMemoryBank` (`_read_file`, `write_context`)
  - [x] Update error handling
  - [x] Maintain fallback mechanisms (Checking `self.project_root`)

- [x] **Refactor Core Context Loading:**
  - [x] Update `load_core_context()` to use `FileMemoryBank`
  - [x] Adapt formatting for context structure
  - [x] Ensure metadata is preserved

- [x] **Refactor Action Recording:**
  - [x] Modify `record_action()` to use `FileMemoryBank` (`write_context`, `log_decision`)
  - [ ] Use markdown export utility if needed (*Formatting done in `format_output_markdown`*)
  - [x] Update file writing mechanism (Uses `Path.write_text` and `memory.write_context`)

- [x] **Update Tests:**
  - [x] Modify agent test cases (Done for `GitCogniAgent` in [[task-update-agent-tests]])
  - [x] Add tests for memory integration (Done in `test_memory_bank.py`)
  - [x] Verify correct error handling

## Deliverables
1. [x] Refactored `CogniAgent` base class (`legacy_logseq/cogni_agents/base.py`)
2. [x] Updated initialization method with `FileMemoryBank` configuration
3. [x] Refactored spirit guide and core context loading
4. [x] Refactored action recording using `FileMemoryBank`
5. [x] Updated test suite (Partially, via [[task-update-agent-tests]])

## Implementation Details
```python
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
import os
from typing import Dict, Any, List, Optional

from legacy_logseq.memory.adapters.mcp_file_memory import MCPFileMemory
from legacy_logseq.utils.markdown_renderer import format_agent_output, write_markdown


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
        memory_directory = os.path.join(project_root, "legacy_logseq/memory/json")
        schema_path = os.path.join(project_root, "legacy_logseq/memory/schemas/memory_block.schema.json")
        
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
- [x] All tests for derived agent classes pass with the refactored base class (Verified for `GitCogniAgent`)
- [x] Spirit guide loading functions correctly with the new memory adapter
- [x] Action recording produces the expected output files and memory entries
- [x] Memory operations use the `FileMemoryBank`
- [x] Error handling maintains robustness for all operations
- [x] Hierarchical memory organization works correctly by agent (via `session_id`)

## Integration Points
- **FileMemoryBank**: Primary memory implementation
- **Markdown Renderer**: For human-readable exports
- **Derived Agent Classes**: Must continue to function with the new base class
- **Testing Framework**: For validating the refactored implementation

## Notes
- Direct replacement of CogniMemoryClient with `FileMemoryBank`
- BaseMemory interface provided by `CogniLangchainMemoryAdapter`, which uses `FileMemoryBank`
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