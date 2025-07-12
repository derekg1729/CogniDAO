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

    # Inherits messages from BaseAgentState - identical to CogniAgentState
    pass


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




