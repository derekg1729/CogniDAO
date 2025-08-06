"""
Common State Types and Configurations for LangGraph Projects.

Provides shared TypedDict definitions and configuration schemas.
"""

from collections.abc import Sequence
from typing import Annotated, Literal, TypedDict, Dict, Any

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


# Constants for guaranteed memory block reference entries
PREV_EDO = "previous_agent_edo_log"
CURR_EDO = "current_agent_edo_log"


def memory_refs_reducer(left, right):
    """Reducer for relevant_memory_block_refs dictionary."""
    if left is None:
        return right
    elif right is None:
        return left
    else:
        return {**left, **right}


class BaseAgentState(TypedDict):
    """Base state for all LangGraph agents, compatible with create_react_agent."""

    messages: Annotated[Sequence[BaseMessage], add_messages]
    remaining_steps: int  # Required for create_react_agent
    structured_response: Dict[str, Any]  # Required when using response_format
    relevant_memory_block_refs: Annotated[Dict[str, str], memory_refs_reducer] = {}


class EDOAgentState(BaseAgentState):
    """State for agents using the Event-Decision-Outcome pattern."""
    
    # Universal memory block reference system
    relevant_memory_block_refs: Annotated[Dict[str, str], memory_refs_reducer] = {}
    # Key = block_name, Value = block_id (e.g., "previous_agent_edo_log": "f4b04e1f-8985-440d-8b16-3a3c6365f82f")
    
    # Legacy EDO field (to be removed after transition)
    edo_handoff_summary: str | None = None  # Generated summary for next agent


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
