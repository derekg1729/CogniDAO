"""
Logging Utilities for LangGraph Projects.

Provides consistent logging configuration and utilities across all graph projects.
"""

import logging
import os
from typing import Any


def configure_logging(
    level: str = "INFO",
    format_string: str | None = None,
    include_timestamp: bool = True,
    include_module: bool = True,
) -> None:
    """
    Configure logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string
        include_timestamp: Whether to include timestamp in logs
        include_module: Whether to include module name in logs
    """
    if format_string is None:
        parts = []
        if include_timestamp:
            parts.append("%(asctime)s")
        if include_module:
            parts.append("%(name)s")
        parts.extend(["%(levelname)s", "%(message)s"])
        format_string = " - ".join(parts)

    logging.basicConfig(
        level=getattr(logging, level.upper()), format=format_string, datefmt="%Y-%m-%d %H:%M:%S"
    )


def get_logger(name: str, level: str | None = None) -> logging.Logger:
    """
    Get a logger with consistent configuration.

    Args:
        name: Logger name (typically __name__)
        level: Optional logging level override

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    if level:
        logger.setLevel(getattr(logging, level.upper()))

    return logger


def setup_langgraph_logging(debug: bool = False) -> None:
    """
    Set up logging specifically for LangGraph projects.

    Args:
        debug: Whether to enable debug logging
    """
    level = "DEBUG" if debug else "INFO"

    # Configure root logger
    configure_logging(
        level=level,
        format_string="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        include_timestamp=True,
        include_module=True,
    )

    # Set specific logger levels
    logging.getLogger("langchain").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Enable debug for our packages
    if debug:
        logging.getLogger("shared_utils").setLevel(logging.DEBUG)
        logging.getLogger("cogni_presence").setLevel(logging.DEBUG)
        logging.getLogger("playwright_poc").setLevel(logging.DEBUG)


def log_function_call(func_name: str, args: tuple = (), kwargs: dict[str, Any] = None) -> None:
    """
    Log a function call with arguments.

    Args:
        func_name: Name of the function
        args: Function arguments
        kwargs: Function keyword arguments
    """
    logger = get_logger(__name__)
    kwargs = kwargs or {}

    if args or kwargs:
        logger.debug(f"Calling {func_name} with args={args}, kwargs={kwargs}")
    else:
        logger.debug(f"Calling {func_name}")


def log_function_result(func_name: str, result: Any, duration: float | None = None) -> None:
    """
    Log a function result.

    Args:
        func_name: Name of the function
        result: Function result
        duration: Optional execution duration in seconds
    """
    logger = get_logger(__name__)

    if duration:
        logger.debug(f"{func_name} completed in {duration:.3f}s with result type: {type(result)}")
    else:
        logger.debug(f"{func_name} completed with result type: {type(result)}")


def log_mcp_connection(server_type: str, url: str, tool_count: int) -> None:
    """
    Log MCP connection success.

    Args:
        server_type: Type of MCP server
        url: Server URL
        tool_count: Number of tools retrieved
    """
    logger = get_logger(__name__)
    logger.info(f"✅ Connected to {server_type} MCP server at {url}. Got {tool_count} tools")


def log_mcp_reconnection(server_type: str, url: str, attempt: int, success: bool) -> None:
    """
    Log MCP reconnection attempt.

    Args:
        server_type: Type of MCP server
        url: Server URL
        attempt: Attempt number
        success: Whether the reconnection was successful
    """
    logger = get_logger(__name__)
    if success:
        logger.info(
            f"🎉 MCP reconnection successful for {server_type} at {url} (attempt {attempt})"
        )
    else:
        logger.warning(f"⚠️ MCP reconnection failed for {server_type} at {url} (attempt {attempt})")


def log_mcp_fallback(server_type: str, url: str, reason: str) -> None:
    """
    Log MCP connection fallback.

    Args:
        server_type: Type of MCP server
        url: Server URL
        reason: Reason for fallback
    """
    logger = get_logger(__name__)
    logger.warning(
        f"⚠️ Failed to connect to {server_type} MCP server at {url}: {reason}. Using fallback tools."
    )


def log_mcp_health_check(server_type: str, connection_info: dict) -> None:
    """
    Log MCP health check status.

    Args:
        server_type: Type of MCP server
        connection_info: Connection information dictionary
    """
    logger = get_logger(__name__)
    state = connection_info.get("state", "unknown")
    tools_count = connection_info.get("tools_count", 0)

    if state == "failed":
        logger.debug(f"🔍 MCP health check for {server_type}: state={state}, connection failed")
    else:
        logger.debug(
            f"🔍 MCP health check for {server_type}: state={state}, {tools_count} tools available"
        )


def log_model_binding(model_name: str, tool_count: int) -> None:
    """
    Log model binding success.

    Args:
        model_name: Name of the model
        tool_count: Number of tools bound
    """
    logger = get_logger(__name__)
    logger.info(f"✅ Bound model {model_name} with {tool_count} tools")


def log_graph_compilation(graph_type: str, node_count: int) -> None:
    """
    Log graph compilation success.

    Args:
        graph_type: Type of graph
        node_count: Number of nodes in the graph
    """
    logger = get_logger(__name__)
    logger.info(f"✅ Compiled {graph_type} graph with {node_count} nodes")


# Initialize logging when module is imported
_debug_mode = os.getenv("DEBUG", "").lower() in ("true", "1", "yes", "on")
setup_langgraph_logging(debug=_debug_mode)
