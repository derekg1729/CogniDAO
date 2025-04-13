# Task:[Deprecate Context Module]
:type: Task
:status: todo
:project: [Agent Memory Integration]

## Current Status
After migrating GitCogni and BroadcastCogni to use the new Agent base class with direct MemoryClient integration, we need to deprecate the legacy context.py module and provide a clear migration path for any remaining usages.

## Description
Add deprecation notices to the context.py module, create documentation for migrating away from it, and ensure any remaining usages have a clear migration path. This is the final step in the transition to the new agent memory architecture.

## Action Items
- [ ] Add deprecation notices to context.py
  - [ ] Add module-level deprecation warning
  - [ ] Add function-level deprecation warnings
  - [ ] Point users to Agent base class methods
- [ ] Create migration guide
  - [ ] Document replacements for each context.py function
  - [ ] Provide specific examples for common usage patterns
- [ ] Check for and update any remaining usages
  - [ ] Identify any code still using context.py
  - [ ] Create migration plan for remaining uses
- [ ] Prepare for eventual removal
  - [ ] Create timeline for removal
  - [ ] Document in future tasks

## Deliverables
1. Updated context.py with comprehensive deprecation notices
2. Migration guide documentation
3. Plan for future removal of context.py

## Test Criteria
- [ ] Deprecation warnings are clear and helpful
- [ ] Migration guide is comprehensive and accurate
- [ ] All existing functionality continues to work during deprecation period

## Implementation Examples

### Adding Deprecation Notices:
```python
# context.py
import warnings
import functools

# Module-level deprecation warning
warnings.warn(
    "The context.py module is deprecated and will be removed in a future version. "
    "Please use the Agent base class with MemoryClient integration instead. "
    "See docs/migration/context_migration.md for details.",
    DeprecationWarning,
    stacklevel=2
)

def deprecated(func):
    """Decorator to mark functions as deprecated."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        warnings.warn(
            f"Function {func.__name__} is deprecated and will be removed in a future version. "
            "Please use the Agent base class with MemoryClient integration instead. "
            "See docs/migration/context_migration.md for details.",
            DeprecationWarning,
            stacklevel=2
        )
        return func(*args, **kwargs)
    return wrapper

@deprecated
def get_guide(guide_name, guides_dir=None):
    """
    Get a specific spirit guide by name.
    
    DEPRECATED: Use Agent.load_spirit_guide() instead.
    
    Args:
        guide_name: Name of the guide (without .md extension)
        guides_dir: Optional custom directory to load guides from
        
    Returns:
        The guide content as a string, or None if not found
    """
    # Original implementation
    # ...
```

### Migration Guide:
```markdown
# Migrating from context.py to Agent Memory Architecture

This guide provides instructions for migrating from the legacy `context.py` module to the new Agent base class with MemoryClient integration.

## Function Replacements

| context.py function | Agent base class replacement |
|---------------------|------------------------------|
| `get_guide()` | `agent.load_spirit_guide()` |
| `get_specific_guides()` | `agent.load_multiple_guides()` |
| `get_core_documents()` | `agent.load_core_context()` |
| `get_guide_for_task()` | `agent.load_multiple_guides()` |

## Example Migration

### Before:
```python
from infra_core.cogni_spirit.context import get_core_documents, get_guide_for_task

# Load core documents
context = get_core_documents(provider="openai")

# Load specific guides for a task
task_context = get_guide_for_task(
    task="my task",
    guides=["cogni-core-spirit", "cogni-core-valuing"],
    provider="openai"
)
```

### After:
```python
from infra_core.cogni_agents.agent_base import Agent

# Create agent instance
agent = Agent()

# Load core context
context = agent.load_core_context(provider="openai")

# Load specific guides for a task
task_context = agent.load_multiple_guides(
    guide_names=["cogni-core-spirit", "cogni-core-valuing"],
    provider="openai"
)
```
```

## Dependencies
- Completed [[task-implement-agent-base-memory]]
- Completed [[task-migrate-git-cogni]]
- Completed [[task-migrate-broadcast-cogni]]
- Completed [[task-update-agent-tests]] 