# Task:[Migrate GitCogni to New Agent Architecture]
:type: Task
:status: todo
:project: [Agent Memory Integration]

## Current Status
GitCogni currently uses context.py for loading context and spirit guides. We need to update it to use the new Agent base class with direct MemoryClient integration.

## Description
Refactor GitCogni to inherit from the new Agent base class and replace all context.py calls with base class methods. This will ensure GitCogni benefits from the improved memory access and standardized context loading.

## Action Items
- [ ] Update GitCogni to inherit from Agent base class
  - [ ] Modify initialization to use Agent base class
  - [ ] Replace context.py imports with Agent base class usage
  - [ ] Update context loading in core functions
- [ ] Replace specific context.py function calls:
  - [ ] Replace `get_core_documents` with `self.load_core_context`
  - [ ] Replace `get_guide_for_task` with `self.load_spirit_guide`
- [ ] Add memory querying where appropriate:
  - [ ] Use `self.query_relevant_context` for semantic search during reviews
- [ ] Update any GitCogni-specific formatting
- [ ] Update tests
  - [ ] Modify GitCogni tests to work with the new architecture
  - [ ] Add tests for new memory querying functionality

## Deliverables
1. Updated GitCogni implementation using Agent base class
2. Updated GitCogni tests
3. Documentation updates reflecting the changes

## Test Criteria
- [ ] All existing GitCogni tests pass
- [ ] Review functionality works with the new architecture
- [ ] Context loading produces the expected output
- [ ] Memory querying works correctly

## Implementation Examples

### Current GitCogni Implementation:
```python
# Current version
from infra_core.cogni_spirit.context import get_core_documents, get_guide_for_task

class GitCogni:
    def __init__(self):
        self.context = get_core_documents(provider="openai")
        
    def review_commit(self, commit_info):
        task_context = get_guide_for_task(
            task="review git commit",
            guides=["cogni-code-review", "cogni-core-spirit"],
            provider="openai"
        )
        # Use context and task_context for review
```

### Updated GitCogni Implementation:
```python
# Updated version
from infra_core.cogni_agents.agent_base import Agent

class GitCogni(Agent):
    def __init__(self, config=None):
        super().__init__(config)
        self.context = self.load_core_context(provider="openai")
        
    def review_commit(self, commit_info):
        # Load task-specific guides
        task_context = self.load_multiple_guides(
            guide_names=["cogni-code-review", "cogni-core-spirit"],
            provider="openai"
        )
        
        # Optional: Query for relevant context
        commit_context = self.query_relevant_context(
            query=commit_info.message,
            n_results=3,
            provider="openai"
        )
        
        # Use context, task_context, and commit_context for review
```

## Dependencies
- Completed [[task-implement-agent-base-memory]]
- Understanding of GitCogni's current usage of context.py
- GitCogni test suite 