# Task:[Replace context.py with memory_client]
:type: Task
:status: todo
:project: [project-cogni_memory_architecture]

## Current Status
The `context.py` module provides functionality to load spirit guides and core documents as context for AI model API calls. Now that we have implemented a robust `CogniMemoryClient` that can handle standard markdown files without requiring conversion, we need to replace `context.py` with the memory client to standardize context access across all agents.

## Description
Migrate all functionality and usage of `infra_core/cogni_spirit/context.py` to use the new `CogniMemoryClient`. This will provide a unified interface for all memory operations and take advantage of the improved parsing capabilities.

## Action Items
- [ ] Scan codebase and identify all locations where context.py is used
  - Known locations:
    - infra_core/flows/rituals/ritual_of_presence.py
    - infra_core/cogni_agents/git_cogni/git_cogni.py
    - tests/test_context.py

- [ ] Create test fixtures and baselines to verify consistent behavior

- [ ] One at a time, replace context.py calls with MemoryClient calls that have the same behavior
  - [ ] Replace get_core_documents() with memory_client.get_page() calls
  - [ ] Replace get_guide() with memory_client.get_page() for spirit guides
  - [ ] Replace get_guide_for_task() with appropriate memory_client methods
  - [ ] Replace get_core_context() with memory_client implementation

- [ ] Ensure sufficient test coverage for new implementations
  - [ ] Add tests for any functionality not covered by existing tests
  - [ ] Verify memory_client produces equivalent results to context.py

- [ ] Run tests, iterate, and repeat until all uses are migrated

- [ ] Update documentation referencing context.py to point to memory_client
  - [ ] Update any relevant README files or documentation
  - [ ] Add examples of new usage patterns with memory_client

- [ ] Clean up after migration is complete
  - [ ] Add deprecation warning to context.py
  - [ ] Remove context.py when no longer referenced (separate task)

## Deliverables
1. Updated code in affected files now using memory_client
2. Tests verifying correct behavior of the replacements
3. Updated documentation showing new usage patterns

## Test Criteria
- [ ] All existing tests pass with memory_client implementations
- [ ] New tests verify compatibility with old behavior
- [ ] Integration tests confirm the system works end-to-end
- [ ] No regression in functionality

## Implementation Notes
The memory_client provides several methods that should be used to replace context.py functionality:

```python
# Instead of:
from infra_core.cogni_spirit.context import get_core_documents

# Use:
from infra_core.memory.memory_client import CogniMemoryClient

memory_client = CogniMemoryClient(chroma_path="./memory/chroma", archive_path="./memory/archive")
charter = memory_client.get_page("CHARTER.md")
```

The main advantage of using memory_client is the improved parser that can extract content from all markdown elements, not just bullet points, providing more complete context.

## Dependencies
- CogniMemoryClient fully implemented
- LogseqParser with improved content extraction
- Existing tests for context.py functionality 