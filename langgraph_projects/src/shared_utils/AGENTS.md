# Shared Utils for LangGraph Agents

This directory contains utilities and tools to be shared among all LangGraph agents in this project.

## Key Files

- `edo_hooks.py` - Event-Decision-Outcome pattern utilities
- `tool_registry.py` - MCP tool loading and caching
- `mcp_client.py` - MCP connection management
- `logging_utils.py` - Consistent logging configuration
- `state_types.py` - Common TypedDict definitions

## Important: MCP Response Format

**MCP tools, when invoked manually, return JSON as a string** that requires parsing:

```python
result = await mcp_tool.ainvoke({...})
if isinstance(result, str):
    result = json.loads(result)
# Now result is a dict you can use with .get()
```

This is critical for all MCP tool integrations. Do not assume tools return dict objects directly.
