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
                ToolMessage(str(todos), tool_call_id=tool_call_id)  # Primary storage
            ],
        }
    )
```

### How It Works

1. **No Persistent Storage**: Todo lists aren't saved to databases or files
2. **Conversation History as Memory**: The `ToolMessage` injects the full todo list into chat history
3. **Full Replacement Strategy**: Each call writes a complete new todo list (no incremental updates)
4. **LLM Context Reading**: The LLM sees current state by reading its most recent `write_todos` message

### Why String Representation

Using `str(todos)` is critical because:
- **ToolMessage Requirements**: Complex objects cause `ValueError: Dict content block must have a type key`
- **LLM Readability**: String format is parseable by the LLM for task tracking
- **Minimal Overhead**: Simple conversion without complex formatting logic

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