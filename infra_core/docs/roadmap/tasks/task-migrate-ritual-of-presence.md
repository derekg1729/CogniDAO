# Task:[Migrate Ritual of Presence to Agent Architecture]
:type: Task
:status: todo
:project: [project-agent-memory-integration]

## Current Status
The Ritual of Presence currently uses the `context.py` module directly to fetch core documents for thought generation. As part of our migration to the new Agent Memory Architecture, we need to refactor it to use the CogniAgent base class for consistent context handling across the system.

## Specific Function Calls to Replace
- `from cogni_spirit.context import get_core_documents` → Should use CogniAgent
- `core_context = get_core_documents()` → Should use agent's `load_core_context()` method
- Direct OpenAI calls with `create_completion()` → Should use agent's standardized methods

## Agent Model Analysis
Creating a CoreCogni agent would be appropriate for the Ritual of Presence, since:

1. **Conceptual fit**: The Ritual of Presence represents Cogni's core identity and introspection, matching the purpose of a CoreCogni agent
2. **Functionality**: The operation is simple (generating thoughts) but would benefit from the structured context and memory capabilities of the agent architecture
3. **Future expansion**: Using an agent allows for future enhancements like memory retrieval and more coherent thoughts over time
4. **Consistency**: This would align with our overall architecture of specialized agents (GitCogni, BroadcastCogni, CoreCogni)

## Action Items
- [ ] Create a CoreCogni agent class inheriting from CogniAgent
  - [ ] Implement proper initialization with spirit guide for thought generation
  - [ ] Add thought generation functionality in `act()` method
  - [ ] Include memory writing capabilities for thoughts
- [ ] Update Ritual of Presence flow
  - [ ] Replace direct context.py calls with CoreCogni agent usage
  - [ ] Modify `create_thought()` task to initialize and use CoreCogni
  - [ ] Use agent's memory client for writing thought files
- [ ] Update tests
  - [ ] Add CoreCogni agent tests
  - [ ] Update Ritual of Presence tests to mock agent instead of context.py
- [ ] Update documentation for the new approach

## Deliverables
1. New CoreCogni agent class
2. Updated Ritual of Presence flow using the agent
3. Tests for CoreCogni agent and updated Ritual of Presence
4. Documentation for the new approach

## Implementation Examples

### Current Implementation:
```python
from cogni_spirit.context import get_core_documents
from openai_handler import initialize_openai_client, create_completion, extract_content

@task
def create_thought():
    client = initialize_openai_client()
    core_context = get_core_documents()
    user_prompt = "Generate a thoughtful reflection..."
    response = create_completion(
        client=client,
        system_message=core_context['context'],
        user_prompt=user_prompt,
        temperature=0.8
    )
    ai_content = extract_content(response)
    # Write to file...
```

### Proposed Implementation:
```python
from infra_core.cogni_agents.core_cogni import CoreCogniAgent
from pathlib import Path

@task
def create_thought():
    # Initialize the CoreCogni agent
    agent = CoreCogniAgent(
        agent_root=Path("presence/thoughts")
    )
    
    # Define input for the agent
    agent_input = {
        "prompt": "Generate a thoughtful reflection from Cogni. Please keep thoughts as short form morsels under 280 characters."
    }
    
    # Let the agent act (generate thought)
    result = agent.act(agent_input)
    
    # Result already contains filepath where thought was saved
    return result["timestamp"], result["filepath"], result["thought_content"]
```

## Dependencies
- Completed base CogniAgent implementation
- Understanding of Ritual of Presence requirements
- Testing infrastructure for agents 