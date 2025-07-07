"""
Common State Types and Configurations for LangGraph Projects.

Provides shared TypedDict definitions and configuration schemas.
"""

from collections.abc import Sequence
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


class BaseAgentState(TypedDict):
    """Base state for all LangGraph agents."""

    messages: Annotated[Sequence[BaseMessage], add_messages]


class CogniAgentState(BaseAgentState):
    """State for Cogni presence agents."""

    # Inherits messages from BaseAgentState
    pass


class PlaywrightAgentState(BaseAgentState):
    """State for Playwright automation agents."""

    messages: Annotated[list[BaseMessage], add_messages]
    tools_available: bool
    current_task: str


class GraphConfig(TypedDict):
    """Configuration schema for LangGraph compilation."""

    model_name: Literal["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]


class ExtendedGraphConfig(GraphConfig):
    """Extended configuration schema with additional options."""

    model_name: Literal["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]
    temperature: float
    streaming: bool
    mcp_server_type: str
    timeout: float


# Common system prompts
COGNI_SYSTEM_PROMPT = """You are a helpful **CogniDAO assistant** 🤖 

**Primary Tools:** 
- 📋 `GetActiveWorkItems` - Show current tasks
- 🔍 `GlobalSemanticSearch` - Find relevant information  
- 📊 `GlobalMemoryInventory` - Browse memory blocks

**Response Style:**
✅ **Concise** answers with strategic emojis  
📝 Use `code blocks` for tool names  
🎯 Structure with **bold headers** when helpful

**Important:** Leave branch/namespace parameters empty in tool calls."""

PLAYWRIGHT_SYSTEM_PROMPT = """You are a helpful browser automation assistant using Playwright tools.

**Available Tools:**
- 🔗 Navigation and page interaction
- 📸 Screenshot capture  
- 🖱️ Click and form interactions
- 📝 Text extraction and analysis

**Response Style:**
✅ **Clear** step-by-step explanations
📝 Use `code blocks` for technical details
🎯 Structure responses with **bold headers**

**Important:** Always verify tool availability before executing complex workflows."""


def create_base_state(messages: Sequence[BaseMessage] | None = None) -> BaseAgentState:
    """
    Create a base agent state.

    Args:
        messages: Initial messages

    Returns:
        BaseAgentState instance
    """
    return BaseAgentState(messages=messages or [])


def create_cogni_state(messages: Sequence[BaseMessage] | None = None) -> CogniAgentState:
    """
    Create a Cogni agent state.

    Args:
        messages: Initial messages

    Returns:
        CogniAgentState instance
    """
    return CogniAgentState(messages=messages or [])


def create_playwright_state(
    messages: list[BaseMessage] | None = None, tools_available: bool = False, current_task: str = ""
) -> PlaywrightAgentState:
    """
    Create a Playwright agent state.

    Args:
        messages: Initial messages
        tools_available: Whether tools are available
        current_task: Current task description

    Returns:
        PlaywrightAgentState instance
    """
    return PlaywrightAgentState(
        messages=messages or [], tools_available=tools_available, current_task=current_task
    )


def create_graph_config(
    model_name: Literal["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"] = "gpt-4o-mini",
) -> GraphConfig:
    """
    Create a basic graph configuration.

    Args:
        model_name: Model to use

    Returns:
        GraphConfig instance
    """
    return GraphConfig(model_name=model_name)


def create_extended_graph_config(
    model_name: Literal["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"] = "gpt-4o-mini",
    temperature: float = 0.0,
    streaming: bool = True,
    mcp_server_type: str = "cogni",
    timeout: float = 30.0,
) -> ExtendedGraphConfig:
    """
    Create an extended graph configuration.

    Args:
        model_name: Model to use
        temperature: Model temperature
        streaming: Whether to enable streaming
        mcp_server_type: Type of MCP server
        timeout: Connection timeout

    Returns:
        ExtendedGraphConfig instance
    """
    return ExtendedGraphConfig(
        model_name=model_name,
        temperature=temperature,
        streaming=streaming,
        mcp_server_type=mcp_server_type,
        timeout=timeout,
    )
