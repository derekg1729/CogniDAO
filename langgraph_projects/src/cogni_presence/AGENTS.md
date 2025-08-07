# CogniDAO Presence Agents Architecture

## Current System Overview
The cogni_presence system implements a CEO + VP organizational structure using two different agent patterns:

- **CEO**: Uses langgraph_supervisor pattern with tool injection
- **VP Agents**: Use deepagent pattern with persistent memory and subagents
- **VP Product**: Enhanced deepagent with workitem research subagent

## Architecture Patterns

### CEO Supervisor (graph.py)
- Uses `create_supervisor()` with `tools=ceo_tools` injection
- Has write_todos + 5 MCP memory tools for strategic planning
- Delegates operational work to VP agents via handoff tools
- Prompt enforces: create todos → delegate → complete ALL → report

### VP Agents (deepagents)
- VP Product: Full deepagent with subagents and 8+ tools
- Other VPs: Standard react agents (not yet converted)
- All VPs report to CEO supervisor via delegation pattern

### VP Product DeepAgent Specifics
- Tools: 6 MCP tools + 2 EDO tools + deepagent built-ins
- MCP: GetMemoryBlock, CreateMemoryBlock, UpdateMemoryBlock, GlobalSemanticSearch, GlobalMemoryInventory, GetActiveWorkItems
- EDO: get_relevant_memory_block_refs, add_memory_block_ref
- Subagent: workitem-research specialist
- State: BaseAgentState for supervisor compatibility

## Critical Gotchas

### DeepAgent Requirements
- **String prompts only** - ChatPromptTemplate breaks deepagents
- **Name assignment required** - Must set `deepagent.name = "vp_product"` for supervisor
- **State schema** - Use BaseAgentState, not custom schemas
- **Subagent tools** - Use `"tools": []` to inherit all parent tools (don't filter by name)

### CEO Tool Injection
- **No tool spec generation** - LangChain auto-extracts descriptions
- **No .partial()** - String prompts don't need template substitution
- **Import write_todos** - Don't copy, import from deepagents framework

### Memory Integration
- **EDO tools required** - All deepagents need get_relevant_memory_block_refs + add_memory_block_ref
- **Subagents must register** - Use add_memory_block_ref for relevant findings or context is lost
- **MCP tool filtering** - Filter by exact `tool.name` strings

### Supervisor Pattern
- **Mixed agent types OK** - CEO supervisor can manage react agents + deepagents
- **Tool injection available** - langgraph_supervisor v0.0.27+ supports tools parameter
- **Handoff tools automatic** - Supervisor auto-generates VP delegation tools

## Testing Notes
- Run `uv run tox -e graphs` after any changes
- MCP connection failures normal in test environment (0 tools is OK)
- All tests must pass before deployment
- VP Product has subagent - can delegate complex research tasks

## File Structure
- `graph.py` - CEO supervisor + compilation
- `ceo_supervisor.py` - CEO tool definitions
- `vp_product_agent.py` - Full deepagent with subagents
- `vp_*_agent.py` - Standard react agents (legacy)
- `prompts.py` - All agent prompts (mix of templates + strings)