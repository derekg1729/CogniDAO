# Memory Block Links

This document describes how to create and work with links between memory blocks.

## Overview

Links between memory blocks form a knowledge graph that represents relationships between different pieces of information. They allow you to express dependencies, hierarchical structures, task sequences, and semantic relationships.

## Link Creation Tools

Cogni provides dedicated tools for creating links between memory blocks:

1. **Core Tool** (`infra_core/memory_system/tools/memory_core/create_block_link_tool.py`): Low-level link creation with full validation and error handling.
2. **Agent-Facing Tool** (`infra_core/memory_system/tools/agent_facing/create_block_link_tool.py`): User-friendly interface for agents with simplified parameters and helpful error messages.

## Agent Usage Guide

As an agent, you can create links between memory blocks using the `create_block_link_agent` function.

### Basic Link Creation

Here's an example of creating a simple one-way dependency link:

```python
from infra_core.memory_system.tools.agent_facing.create_block_link_tool import create_block_link_agent

# Create a "depends_on" link from task A to task B
result = await create_block_link_agent(
    source_block_id="550e8400-e29b-41d4-a716-446655440000",  # Task A
    target_block_id="6ba7b810-9dad-11d1-80b4-00c04fd430c8",  # Task B
    relation="depends_on"  # Task A depends on Task B
)

# Check if link creation was successful
if result.success:
    print(f"Link created: {result.message}")
    for link in result.created_links:
        print(f"  {link['from_id']} -> {link['to_id']} ({link['relation']})")
else:
    print(f"Error: {result.message}")
    print(f"Details: {result.error_details}")
```

### Bidirectional Links

For relationships that should be represented in both directions, use the `bidirectional` parameter:

```python
# Create bidirectional "related_to" links between two knowledge blocks
result = await create_block_link_agent(
    source_block_id="550e8400-e29b-41d4-a716-446655440000",  # Knowledge block A
    target_block_id="6ba7b810-9dad-11d1-80b4-00c04fd430c8",  # Knowledge block B
    relation="related_to",
    bidirectional=True  # Creates both "related_to" links automatically
)
```

### Using Human-Readable Relation Types

The agent-facing tool accepts various formats for relation types:

1. **Canonical form** (as defined in `RelationType`): `depends_on`, `is_blocked_by`, etc.
2. **Human-readable form** (spaces instead of underscores): `depends on`, `is blocked by`, etc.
3. **Aliases** (as defined in `RELATION_ALIASES`): `blocked_by` for `is_blocked_by`, etc.

```python
# These all create the same type of relationship
await create_block_link_agent(source_id, target_id, relation="is_blocked_by")
await create_block_link_agent(source_id, target_id, relation="is blocked by")
await create_block_link_agent(source_id, target_id, relation="blocked_by")
```

### Adding Metadata

You can include additional information about the link using the metadata parameter:

```python
# Create a link with metadata
result = await create_block_link_agent(
    source_block_id="550e8400-e29b-41d4-a716-446655440000",
    target_block_id="6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    relation="depends_on",
    metadata={
        "reason": "Task A needs output from Task B",
        "estimated_delay": "2 days"
    }
)
```

## Available Relation Types

The following relation types are available for creating links:

- `depends_on` / `blocks`: Task dependency relationships
- `is_blocked_by` / `blocks`: Blocker relationships
- `related_to`: Generic bidirectional relationship
- `child_of` / `parent_of`: Hierarchical relationships
- `subtask_of` / `parent_task_of`: Task breakdown relationships
- `belongs_to_epic`: Association with an epic

## Error Handling

The agent tool provides friendly error messages for common issues:

- Invalid block IDs (not in UUID format)
- Non-existent blocks
- Invalid relation types
- Dependency cycles
- Duplicate links

Always check the `success` flag in the result to handle errors appropriately.

## Implementation Details

### LinkManager Integration

The link creation tools are built on top of the `LinkManager` component, which handles:

- Link storage and retrieval
- Validation of blocks and relations
- Cycle detection in dependency graphs
- Duplicate link prevention

### Bidirectional Link Creation

When `bidirectional=True` is specified, the tool:

1. Looks up the inverse relation in `INVERSE_RELATIONS`
2. Creates both links in a single atomic operation
3. Returns details about both created links

Not all relations support bidirectional operation. The tool validates that an inverse relation exists before proceeding. 