"""
Shared utilities for CogniDAO LangGraph projects.

This package provides common functionality for MCP client setup, model binding,
state management, and other shared patterns across all LangGraph agents.
"""

from .error_handling import MCPConnectionError, handle_mcp_error
from .logging_utils import get_logger, log_model_binding, log_graph_compilation
from .mcp_client import MCPClientManager, get_mcp_tools
from .model_binding import ModelBindingManager, get_cached_bound_model
from .state_types import (
    BaseAgentState,
    CogniAgentState,
    PlaywrightAgentState,
    GraphConfig,
    COGNI_SYSTEM_PROMPT,
    PLAYWRIGHT_SYSTEM_PROMPT,
)

__version__ = "0.1.0"
__all__ = [
    "MCPClientManager",
    "get_mcp_tools",
    "ModelBindingManager",
    "get_cached_bound_model",
    "BaseAgentState",
    "CogniAgentState",
    "PlaywrightAgentState",
    "GraphConfig",
    "COGNI_SYSTEM_PROMPT",
    "PLAYWRIGHT_SYSTEM_PROMPT",
    "MCPConnectionError",
    "handle_mcp_error",
    "get_logger",
    "log_model_binding",
    "log_graph_compilation",
]
