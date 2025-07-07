"""
Error Handling Utilities for LangGraph Projects.

Provides custom exceptions and error handling patterns for MCP connections,
model binding, and other common error scenarios.
"""

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import TypeVar

from .logging_utils import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class MCPConnectionError(Exception):
    """Raised when MCP connection fails."""

    def __init__(
        self, message: str, server_type: str, url: str, original_error: Exception | None = None
    ):
        super().__init__(message)
        self.server_type = server_type
        self.url = url
        self.original_error = original_error


class ModelBindingError(Exception):
    """Raised when model binding fails."""

    def __init__(self, message: str, model_name: str, original_error: Exception | None = None):
        super().__init__(message)
        self.model_name = model_name
        self.original_error = original_error


class GraphBuildError(Exception):
    """Raised when graph building fails."""

    def __init__(self, message: str, graph_type: str, original_error: Exception | None = None):
        super().__init__(message)
        self.graph_type = graph_type
        self.original_error = original_error


def handle_mcp_error(error: Exception, server_type: str, url: str) -> MCPConnectionError:
    """
    Handle MCP connection errors with proper logging and error wrapping.

    Args:
        error: Original exception
        server_type: Type of MCP server
        url: Server URL

    Returns:
        MCPConnectionError instance
    """
    message = (
        f"Failed to connect to {server_type} MCP server at {url}: {type(error).__name__}: {error}"
    )
    logger.error(message)
    logger.error(f"Exception details: {repr(error)}")

    # Log stack trace for debugging
    import traceback

    logger.error(f"Full traceback: {traceback.format_exc()}")

    return MCPConnectionError(message, server_type, url, error)


def handle_model_binding_error(error: Exception, model_name: str) -> ModelBindingError:
    """
    Handle model binding errors with proper logging and error wrapping.

    Args:
        error: Original exception
        model_name: Name of the model

    Returns:
        ModelBindingError instance
    """
    message = f"Failed to bind model {model_name}: {type(error).__name__}: {error}"
    logger.error(message)
    logger.error(f"Exception details: {repr(error)}")

    return ModelBindingError(message, model_name, error)


def handle_graph_build_error(error: Exception, graph_type: str) -> GraphBuildError:
    """
    Handle graph building errors with proper logging and error wrapping.

    Args:
        error: Original exception
        graph_type: Type of graph being built

    Returns:
        GraphBuildError instance
    """
    message = f"Failed to build {graph_type} graph: {type(error).__name__}: {error}"
    logger.error(message)
    logger.error(f"Exception details: {repr(error)}")

    return GraphBuildError(message, graph_type, error)


def with_error_handling(error_handler: Callable[[Exception], Exception]):
    """
    Decorator to wrap functions with error handling.

    Args:
        error_handler: Function to handle exceptions

    Returns:
        Decorator function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                raise error_handler(e)

        return wrapper

    return decorator


def with_async_error_handling(error_handler: Callable[[Exception], Exception]):
    """
    Decorator to wrap async functions with error handling.

    Args:
        error_handler: Function to handle exceptions

    Returns:
        Decorator function
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                raise error_handler(e)

        return wrapper

    return decorator


def safe_execute(func: Callable[..., T], *args, default: T = None, **kwargs) -> T:
    """
    Safely execute a function with error handling.

    Args:
        func: Function to execute
        *args: Function arguments
        default: Default value to return on error
        **kwargs: Function keyword arguments

    Returns:
        Function result or default value
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Error executing {func.__name__}: {e}")
        return default


async def safe_execute_async(
    func: Callable[..., Awaitable[T]], *args, default: T = None, **kwargs
) -> T:
    """
    Safely execute an async function with error handling.

    Args:
        func: Async function to execute
        *args: Function arguments
        default: Default value to return on error
        **kwargs: Function keyword arguments

    Returns:
        Function result or default value
    """
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Error executing {func.__name__}: {e}")
        return default


def log_and_reraise(error: Exception, context: str = ""):
    """
    Log an error and re-raise it.

    Args:
        error: Exception to log
        context: Additional context information
    """
    if context:
        logger.error(f"Error in {context}: {type(error).__name__}: {error}")
    else:
        logger.error(f"Error: {type(error).__name__}: {error}")

    logger.error(f"Exception details: {repr(error)}")
    raise error
