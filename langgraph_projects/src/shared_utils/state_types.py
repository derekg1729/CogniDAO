"""
Common State Types and Configurations for LangGraph Projects.

Provides shared TypedDict definitions and configuration schemas.
"""

from collections.abc import Sequence
from typing import Annotated, Literal, TypedDict, Dict, Any

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


class BaseAgentState(TypedDict):
    """Base state for all LangGraph agents, compatible with create_react_agent."""

    messages: Annotated[Sequence[BaseMessage], add_messages]
    remaining_steps: int  # Required for create_react_agent
    structured_response: Dict[str, Any]  # Required when using response_format


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
