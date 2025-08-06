from .sub_agent import _create_task_tool, SubAgent
from .model import get_default_model
from .tools import write_todos
from .state import DeepAgentState
from typing import Sequence, Union, Callable, Any, TypeVar, Type, Optional
from langchain_core.tools import BaseTool
from langchain_core.language_models import LanguageModelLike

from langgraph.prebuilt import create_react_agent

StateSchema = TypeVar("StateSchema", bound=DeepAgentState)
StateSchemaType = Type[StateSchema]

base_prompt = """You have access to a number of standard tools

## `write_todos`

You have access to the `write_todos` tools to help you manage and plan tasks. Use these tools VERY frequently to ensure that you are tracking your tasks and giving the user visibility into your progress.
These tools are also EXTREMELY helpful for planning tasks, and for breaking down larger complex tasks into smaller steps. If you do not use this tool when planning, you may forget to do important tasks - and that is unacceptable.

It is critical that you mark todos as completed as soon as you are done with a task. Do not batch up multiple tasks before marking them as completed.
## `task`

- When doing web search, prefer to use the `task` tool in order to reduce context usage."""


def create_deep_agent(
    tools: Sequence[Union[BaseTool, Callable, dict[str, Any]]],
    instructions: str,
    model: Optional[Union[str, LanguageModelLike]] = None,
    subagents: Sequence[SubAgent] = (),
    state_schema: Optional[StateSchemaType] = None,
):
    """Create a deep agent. Caller provides all tools including MCP memory tools.

    This agent will by default have access to:
    - write_todos: Task management tool

    The caller should provide MCP memory tools (GetMemoryBlock, CreateMemoryBlock, 
    UpdateMemoryBlock) in the tools parameter for persistent document storage.

    Args:
        tools: All tools the agent should have access to, including MCP memory tools.
        instructions: Additional instructions for the agent. Will be appended to
            the base system prompt.
        model: The model to use.
        subagents: The subagents to use. Each subagent should have:
                - `name`
                - `description` (used by the main agent to decide whether to call the sub agent)
                - `prompt` (used as the system prompt in the subagent)
                - (optional) `tools`
        state_schema: The schema of the deep agent. Should subclass from DeepAgentState
    """
    # Fix prompt ordering: base system rules first, then caller instructions
    prompt = base_prompt + instructions
    
    # Simple built-in tools: just todos (no async I/O)
    built_in_tools = [write_todos]
    
    if model is None:
        model = get_default_model()
    state_schema = state_schema or DeepAgentState
    
    task_tool = _create_task_tool(
        list(tools) + built_in_tools,
        instructions,
        subagents,
        model,
        state_schema
    )
    all_tools = built_in_tools + list(tools) + [task_tool]
    return create_react_agent(
        model,
        prompt=prompt,
        tools=all_tools,
        state_schema=state_schema,
    )
