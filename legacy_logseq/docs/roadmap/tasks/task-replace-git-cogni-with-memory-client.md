# task-replace-git-cogni-with-memory-client
:type: Task
:status: completed
:project: [[project-git-cogni-agent]]

## Core Mapping

```
│ Current Implementation  │  →  │     CogniMemoryClient    │
├───────────────────────┤     ├───────────────────────┤
│ get_core_documents()  │  →  │ get_page() for docs   │
│ get_guide_for_task()  │  →  │ get_page() for guides │
│ record_action()       │  →  │ write_page()          │
```

## Implementation Details

- Implemented memory client integration in base `CogniAgent` class
  - Added memory client initialization in `__init__`
  - Implemented `load_core_context()` using `get_page()`
  - Added `get_guide_for_task()` using `get_page()`
  - Updated `record_action()` to use `write_page()`

- Updated `GitCogniAgent` to use base class functionality
  - Removed direct dependency on context.py
  - Updated `act()` to use `get_guide_for_task()`
  - Simplified `record_action()` to only track files

- Updated tests to mock memory client
  - Added proper mocking of memory client methods
  - Verified all test cases pass

## Original Files Modified
- `legacy_logseq/cogni_agents/base.py` - Added memory client integration
- `legacy_logseq/cogni_agents/git_cogni/git_cogni.py` - Removed context.py dependency
- `tests/agents/test_git_cogni_agent.py` - Updated tests

## Testing Notes
- All unit tests pass with the new implementation
- Functionality is preserved with the same return types and formats
- Core document loading has been validated
- Spirit guide loading has been validated
- File writing operations have been validated 