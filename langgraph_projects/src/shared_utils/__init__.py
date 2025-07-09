"""
Shared utilities for CogniDAO LangGraph projects.

This package provides common functionality for MCP client setup, model binding,
state management, and other shared patterns across all LangGraph agents.
"""

from .error_handling import MCPConnectionError, handle_mcp_error
from .logging_utils import (
    get_logger,
    log_model_binding,
    log_graph_compilation,
    log_mcp_connection,
    log_mcp_reconnection,
    log_mcp_fallback,
    log_mcp_health_check,
)
from .mcp_client import (
    MCPClientManager,
    get_mcp_tools,
    get_mcp_tools_with_refresh,
    get_mcp_connection_info,
    ConnectionState,
)
from .mcp_monitor import (
    check_mcp_health,
    check_all_mcp_health,
    force_mcp_reconnection,
    print_mcp_status,
)
from .model_binding import ModelBindingManager, get_cached_bound_model
from .state_types import (
    BaseAgentState,
    CogniAgentState,
    PlaywrightAgentState,
    GraphConfig,
    COGNI_SYSTEM_PROMPT,
    PLAYWRIGHT_SYSTEM_PROMPT,
)
from .prompt_templates import (
    generate_tool_specs_from_mcp_tools,
    render_playwright_navigator_prompt,
    render_playwright_observer_prompt,
    PLAYWRIGHT_NAVIGATOR_PROMPT,
    COGNI_PRESENCE_PROMPT,
)

__version__ = "0.1.0"
__all__ = [
    # MCP Client
    "MCPClientManager",
    "get_mcp_tools",
    "get_mcp_tools_with_refresh",
    "get_mcp_connection_info",
    "ConnectionState",
    # MCP Monitoring
    "check_mcp_health",
    "check_all_mcp_health",
    "force_mcp_reconnection",
    "print_mcp_status",
    # Model Binding
    "ModelBindingManager",
    "get_cached_bound_model",
    # State Management
    "BaseAgentState",
    "CogniAgentState",
    "PlaywrightAgentState",
    "GraphConfig",
    "COGNI_SYSTEM_PROMPT",
    "PLAYWRIGHT_SYSTEM_PROMPT",
    # Prompt Templates
    "generate_tool_specs_from_mcp_tools",
    "render_playwright_navigator_prompt",
    "render_playwright_observer_prompt",
    "PLAYWRIGHT_NAVIGATOR_PROMPT",
    "COGNI_PRESENCE_PROMPT",
    # Error Handling
    "MCPConnectionError",
    "handle_mcp_error",
    # Logging
    "get_logger",
    "log_model_binding",
    "log_graph_compilation",
    "log_mcp_connection",
    "log_mcp_reconnection",
    "log_mcp_fallback",
    "log_mcp_health_check",
]
