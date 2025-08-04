# DeepAgents Framework - Tool Message Patterns

## Todo List as Conversational Memory

The `write_todos` tool uses a simple but effective pattern: treating conversation history as ephemeral task storage, similar to approaches in Claude Code and LangGraph demos.

### The Core Pattern

```python
@tool(description=WRITE_TODOS_DESCRIPTION)
def write_todos(
    todos: list[Todo], tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    return Command(
        update={
            "todos": todos,                                    # State backup
            "messages": [
                ToolMessage(json.dumps(todos), tool_call_id=tool_call_id)  # Primary storage
            ],
        }
    )
```

### How It Works

1. **No Persistent Storage**: Todo lists aren't saved to databases or files
2. **Conversation History as Memory**: The `ToolMessage` injects the full todo list into chat history
3. **Full Replacement Strategy**: Each call writes a complete new todo list (no incremental updates)
4. **LLM Context Reading**: The LLM sees current state by reading its most recent `write_todos` message

### Why JSON Serialization

Using `json.dumps(todos)` is critical because:
- **ToolMessage Requirements**: Complex objects cause `ValueError: Dict content block must have a type key`
- **Frontend Compatibility**: JavaScript `JSON.parse()` requires valid JSON with double quotes
- **LLM Readability**: JSON format is parseable by the LLM for task tracking

### Benefits of This Approach

- **Simplicity**: No complex persistence or state management needed
- **Visibility**: Current todo state is always visible in conversation context
- **Self-Contained**: Everything needed exists within the conversation window
- **Stateless Operations**: Each todo write is independent and complete

### Pattern Origins

This mirrors ephemeral state patterns from:
- **Claude Code**: Task lists exist only in conversation context
- **LangGraph Demos**: Use tool messages for structured data visibility
- **Conversational Agents**: Leverage chat history as short-term working memory

The todo list exists only as long as it's visible in the conversation window - perfect for single-session task tracking without infrastructure overhead.

## Why `_create_task_tool()` Lives in `graph.py`

The `task` tool is **configuration-dependent**, not a static utility. It must be created fresh for each agent because it captures five agent-specific values:

| Captured Value | Source | Purpose |
|---|---|---|
| `tools` | `create_deep_agent()` args | Sub-agents inherit parent's exact tool bundle |
| `instructions` | User-supplied prompt | Woven into sub-agent system prompts |
| `subagents` | Optional SubAgent configs | Enables runtime routing to specialists |
| `model` | LLM configuration | Sub-agents use same model/temperature |
| `state_schema` | DeepAgentState subclass | Ensures compatible state shapes |

### The Factory Pattern

```python
def _create_task_tool(tools, instructions, subagents, model, state_schema):
    # Creates agent registry
    agents = {
        "general-purpose": create_react_agent(model, prompt=instructions, tools=tools)
    }
    
    # Register each subagent with its specific config
    for _agent in subagents:
        agents[_agent["name"]] = create_react_agent(
            model, prompt=_agent["prompt"], tools=_tools, state_schema=state_schema
        )
    
    # Return closure that can route to any registered agent
    @tool(description=dynamic_description)
    def task(description: str, subagent_type: str, ...):
        sub_agent = agents[subagent_type]  # Runtime selection
        return sub_agent.invoke(state)
    
    return task
```

### Why Not `tools.py`?

**Static tools** like `write_todos`:
- Depend only on their arguments 
- Work identically across any agent
- Can be imported once

**Dynamic tools** like `task`:
- Close over agent configuration
- Would break with multiple agents in same process
- Must be manufactured during agent assembly

**Litmus test**: If a tool needs the agent's prompt, model, or tool list → it's configuration-dependent and belongs in graph assembly.