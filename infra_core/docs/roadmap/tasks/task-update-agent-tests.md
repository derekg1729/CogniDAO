# Task:[Update Agent Tests]
:type: Task
:status: todo
:project: [project-langchain-memory-integration]

## Current Status
- [x] Task design document created (this file)
- [ ] Test requirements analyzed
- [ ] Test utilities designed 
- [ ] CogniAgent base tests updated
- [ ] Agent-specific tests updated
- [ ] Integration tests implemented

## Description
Update the test suite to work with the new `MCPFileMemory` implementation, ensuring all agent functionality continues to work correctly with the LangChain-based memory system. This task involves refactoring existing tests, creating test utilities, and verifying that all agents operate correctly with the new memory implementation.

## Input
- Current test suite
- Refactored `CogniAgent` base class
- `MCPFileMemory` implementation
- Agent-specific requirements

## Output
- Updated test suite for all agents
- Test utilities for MCPFileMemory
- Integration tests for the memory system
- Documentation for testing patterns

## Action Items
- [ ] **Analyze Current Tests:**
  - [ ] Review existing test suite
  - [ ] Identify tests using `CogniMemoryClient`
  - [ ] Document test patterns and utilities
  - [ ] Determine required changes

- [ ] **Design Test Utilities:**
  - [ ] Create test fixtures for MCPFileMemory
  - [ ] Implement setup and teardown utilities
  - [ ] Design test data generators
  - [ ] Create mock implementations if needed

- [ ] **Update CogniAgent Base Tests:**
  - [ ] Refactor base agent tests
  - [ ] Update initialization tests
  - [ ] Modify memory operation tests
  - [ ] Test spirit guide loading
  - [ ] Test record_action functionality

- [ ] **Update Agent-Specific Tests:**
  - [ ] Update GitCogni tests
  - [ ] Update CoreCogni tests
  - [ ] Update BroadcastCogni tests
  - [ ] Verify specialized memory operations

- [ ] **Implement Integration Tests:**
  - [ ] Test MCPFileMemory with agents
  - [ ] Verify correct memory storage and retrieval
  - [ ] Test error handling
  - [ ] Validate schema enforcement
  - [ ] Test memory overwriting scenarios
  - [ ] Test merging outputs across workflows
  - [ ] Test invalid writes (schema errors)
  - [ ] Test concurrent access

- [ ] **Document Testing Patterns:**
  - [ ] Create examples for testing with MCPFileMemory
  - [ ] Document common testing patterns
  - [ ] Capture best practices

## Deliverables
1. Updated test suite for all agents
2. Test utilities for MCPFileMemory
3. Integration tests for the memory system
4. Test documentation and examples

## Implementation Details
```python
import pytest
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import threading
import time
import uuid

from infra_core.memory.adapters.mcp_file_memory import MCPFileMemory
from infra_core.cogni_agents.base import CogniAgent


@pytest.fixture
def temp_memory_dir():
    """Create a temporary directory for memory files."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname


@pytest.fixture
def test_schema_path(temp_memory_dir):
    """Create a test schema file."""
    schema_path = Path(temp_memory_dir) / "memory_block.schema.json"
    schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "content": {"type": "string"},
            "created_at": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "metadata": {"type": "object"},
            "agent_id": {"type": "string"},
            "embedding_id": {"type": ["string", "null"]}
        },
        "required": ["id", "content"]
    }
    
    with open(schema_path, "w") as f:
        json.dump(schema, f)
    
    return schema_path


@pytest.fixture
def memory(temp_memory_dir, test_schema_path):
    """Create a test memory instance."""
    return MCPFileMemory(
        memory_directory=temp_memory_dir,
        schema_path=test_schema_path,
        memory_key="history",
        agent_id="test_agent"
    )


class TestAgentBase:
    """Tests for the CogniAgent base class with MCPFileMemory."""
    
    def test_initialization(self, temp_memory_dir, test_schema_path):
        """Test agent initialization with memory."""
        # Implementation will depend on the final CogniAgent design
        pass
    
    def test_load_spirit(self, memory):
        """Test loading spirit guide using memory."""
        # Implementation will depend on the final CogniAgent design
        pass
    
    def test_record_action(self, memory):
        """Test recording actions using memory."""
        # Implementation will depend on the final CogniAgent design
        pass
        
    def test_overwrite_memory(self, memory):
        """Test overwriting existing memory blocks."""
        # Test overwriting scenario
        pass
        
    def test_memory_merging(self, memory):
        """Test merging outputs across workflows."""
        # Test merging scenario
        pass
        
    def test_invalid_writes(self, memory, test_schema_path):
        """Test handling of invalid writes that violate schema."""
        # Test schema validation errors
        pass
        
    def test_concurrent_access(self, temp_memory_dir, test_schema_path):
        """Test concurrent access to memory."""
        # Test concurrent read/writes
        memory = MCPFileMemory(
            memory_directory=temp_memory_dir,
            schema_path=test_schema_path,
            memory_key="history"
        )
        
        def writer_thread(thread_id):
            """Thread function that writes to memory."""
            for i in range(5):
                memory.save_context(
                    {"thread": thread_id},
                    {"content": f"Thread {thread_id} write {i}", "id": str(uuid.uuid4())}
                )
                time.sleep(0.01)
        
        # Create and start threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=writer_thread, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # Verify results
        variables = memory.load_memory_variables({})
        # Assert on variables content
```

## Test Criteria
- All tests pass with the new memory implementation
- Test coverage meets or exceeds previous levels
- Tests validate both basic and edge cases
- Error handling is properly tested
- Schema validation is verified
- Memory overwriting is correctly handled
- Output merging across workflows is validated
- Invalid writes are properly rejected
- Concurrent access is handled safely

## Integration Points
- **MCPFileMemory**: Primary object under test
- **CogniAgent**: Base class being tested
- **Derived Agent Classes**: For specific agent tests
- **pytest**: Testing framework

## Notes
- Focus on testing core functionality first
- Create reusable test fixtures
- Use temporary directories for test data
- Mock external dependencies when appropriate
- Test schema validation explicitly
- Keep tests fast and independent
- Add thread safety tests for concurrent operations
- Test both agent-specific and shared memory scenarios

## Dependencies
- MCPFileMemory implementation
- Refactored CogniAgent base class
- pytest testing framework
- Agent-specific implementations