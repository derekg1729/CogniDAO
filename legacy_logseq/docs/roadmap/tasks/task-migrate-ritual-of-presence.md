# Task:[Migrate Ritual of Presence to Agent Architecture]
:type: Task
:status: completed
:project: [project-agent-memory-integration]

## Current Status
The Ritual of Presence has been successfully migrated to use the new CoreCogniAgent class instead of directly calling the `context.py` module. This aligns with our Agent Memory Architecture and provides consistent context handling across the system.

## Specific Function Calls to Replace
- ✅ `from cogni_spirit.context import get_core_documents` → Now uses CogniAgent
- ✅ `core_context = get_core_documents()` → Now uses agent's `load_core_context()` method
- ✅ Direct OpenAI calls with `create_completion()` → Now uses agent's standardized methods

## Agent Model Analysis
Creating a CoreCogni agent was appropriate for the Ritual of Presence, since:

1. **Conceptual fit**: The Ritual of Presence represents Cogni's core identity and introspection, matching the purpose of a CoreCogni agent
2. **Functionality**: The operation is simple (generating thoughts) but benefits from the structured context and memory capabilities of the agent architecture
3. **Future expansion**: Using an agent allows for future enhancements like memory retrieval and more coherent thoughts over time
4. **Consistency**: This aligns with our overall architecture of specialized agents (GitCogni, BroadcastCogni, CoreCogni)

## Action Items
- [x] Create a CoreCogni agent class inheriting from CogniAgent
  - [x] Implement proper initialization with spirit guide for thought generation
  - [x] Add thought generation functionality in `act()` method
  - [x] Include memory writing capabilities for thoughts
- [x] Update Ritual of Presence flow
  - [x] Replace direct context.py calls with CoreCogni agent usage
  - [x] Modify `create_thought()` task to initialize and use CoreCogni
  - [x] Use agent's memory client for writing thought files
- [x] Update tests
  - [x] Add CoreCogni agent tests
  - [x] Update Ritual of Presence tests to mock agent instead of context.py
- [x] Update documentation for the new approach

## Deliverables
1. ✅ New CoreCogni agent class in `legacy_logseq/cogni_agents/core_cogni.py`
2. ✅ Updated Ritual of Presence flow using the agent
3. ✅ Tests for CoreCogni agent and updated Ritual of Presence
4. ✅ Documentation for the new approach

## Implementation Examples

### Previous Implementation:
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

### New Implementation:
```python
from legacy_logseq.cogni_agents.core_cogni import CoreCogniAgent
from pathlib import Path

@task
def create_thought():
    # Import CoreCogniAgent here to avoid import errors when running as flow
    from legacy_logseq.cogni_agents.core_cogni import CoreCogniAgent
    
    # Create CoreCogniAgent
    agent_root = Path(THOUGHTS_DIR)
    core_cogni = CoreCogniAgent(agent_root=agent_root)
    
    # Prepare input and act
    prepared_input = core_cogni.prepare_input()
    result = core_cogni.act(prepared_input)
    
    # Return essential information
    return result['timestamp'], result['filepath'], result['thought_content']
```

## Dependencies
- Completed base CogniAgent implementation
- Understanding of Ritual of Presence requirements
- Testing infrastructure for agents

## Implementation Notes
- CoreCogniAgent uses absolute paths for memory storage to avoid creating directory structures in unexpected locations
- Import paths were adjusted to work with Prefect deployment environment
- Memory client is now properly configured to use the right locations for memory storage 