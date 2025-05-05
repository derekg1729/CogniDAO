# Task:[Migrate BroadcastCogni to New Agent Architecture]
:type: Task
:status: todo
:project: [Agent Memory Integration]

## Current Status
BroadcastCogni currently uses context.py for loading context and spirit guides. We need to update it to use the new Agent base class with direct MemoryClient integration. This will align it with the new architecture and enable more powerful context retrieval.

## Description
Refactor BroadcastCogni to inherit from the new Agent base class and replace all context.py calls with base class methods. This migration will enhance BroadcastCogni's context capabilities and provide a more consistent architecture across all agents.

## Action Items
- [ ] Update BroadcastCogni to inherit from Agent base class
  - [ ] Modify initialization to use Agent base class
  - [ ] Replace context.py imports with Agent base class usage
  - [ ] Update context loading in core functions
- [ ] Replace specific context.py function calls:
  - [ ] Replace `get_core_documents` with `self.load_core_context`
  - [ ] Replace `get_guide_for_task` with `self.load_spirit_guide`
- [ ] Add memory querying where appropriate:
  - [ ] Use `self.query_relevant_context` for semantic search during broadcasts
  - [ ] Consider adding relevant context from memory for broadcasts
- [ ] Update any BroadcastCogni-specific formatting
- [ ] Update tests
  - [ ] Modify BroadcastCogni tests to work with the new architecture
  - [ ] Add tests for new memory querying functionality

## Deliverables
1. Updated BroadcastCogni implementation using Agent base class
2. Updated BroadcastCogni tests
3. Documentation updates reflecting the changes

## Test Criteria
- [ ] All existing BroadcastCogni tests pass
- [ ] Broadcasting functionality works with the new architecture
- [ ] Context loading produces the expected output
- [ ] Memory querying works correctly

## Implementation Examples

### Before - Current Implementation:
```python
# Current version (simplified)
from legacy_logseq.cogni_spirit.context import get_core_documents, get_guide_for_task

class BroadcastCogni:
    def __init__(self):
        self.context = get_core_documents(provider="openai")
        
    def broadcast(self, message):
        broadcast_context = get_guide_for_task(
            task="broadcasting message",
            guides=["cogni-broadcast-guide", "cogni-core-spirit"],
            provider="openai"
        )
        # Use context and broadcast_context for message
```

### After - Updated Implementation:
```python
# Updated version (simplified)
from legacy_logseq.cogni_agents.agent_base import Agent

class BroadcastCogni(Agent):
    def __init__(self, config=None):
        super().__init__(config)
        self.context = self.load_core_context(provider="openai")
        
    def broadcast(self, message):
        # Load task-specific guides
        broadcast_context = self.load_multiple_guides(
            guide_names=["cogni-broadcast-guide", "cogni-core-spirit"],
            provider="openai"
        )
        
        # Query for relevant context based on message
        message_context = self.query_relevant_context(
            query=message,
            n_results=3,
            provider="openai"
        )
        
        # Use context, broadcast_context, and message_context for broadcast
```

## Dependencies
- Completed [[task-implement-agent-base-memory]]
- Understanding of BroadcastCogni's current usage of context.py
- BroadcastCogni test suite 