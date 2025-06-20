"""
Shared utility functions for the prefect-mcp-bridge package
"""

import os
from typing import Dict, Any, Optional
from .client import MCPClient


def get_default_mcp_client(
    base_url: Optional[str] = None, api_key: Optional[str] = None
) -> MCPClient:
    """
    Get a default MCPClient instance with standard configuration

    Args:
        base_url: Override default MCP URL
        api_key: Override default API key

    Returns:
        Configured MCPClient instance
    """
    return MCPClient(base_url=base_url, api_key=api_key)


def validate_mcp_connection(client: Optional[MCPClient] = None) -> Dict[str, Any]:
    """
    Validate that MCP server is reachable and responding

    Args:
        client: Optional MCPClient to test (creates new one if not provided)

    Returns:
        Dict with connection status and server info
    """
    test_client = client or MCPClient()

    try:
        with test_client:
            # Try a simple health check or status call
            # Note: This assumes the MCP server has a health endpoint
            # Adjust based on actual MCP server capabilities
            result = test_client.call("health", {})
            return {"connected": True, "server_response": result, "base_url": test_client.base_url}
    except Exception as e:
        return {"connected": False, "error": str(e), "base_url": test_client.base_url}


def format_dolt_commit_message(
    operation: str, details: Optional[str] = None, author: Optional[str] = None
) -> str:
    """
    Format a standardized commit message for Dolt operations

    Args:
        operation: Type of operation (e.g., "Prefect flow execution")
        details: Additional details about the operation
        author: Author of the operation

    Returns:
        Formatted commit message
    """
    message = f"feat: {operation}"

    if details:
        message += f" - {details}"

    if author:
        message += f"\n\nAuthor: {author}"

    return message


def setup_mcp_environment() -> Dict[str, str]:
    """
    Setup and validate required environment variables for MCP operations

    Returns:
        Dict containing environment configuration
    """
    config = {
        "MCP_URL": os.getenv("MCP_URL", "http://cogni-mcp:8080"),
        "PREFECT_MCP_API_KEY": os.getenv("PREFECT_MCP_API_KEY", ""),
    }

    # Log configuration (without sensitive data)
    print("MCP Configuration:")
    print(f"  MCP_URL: {config['MCP_URL']}")
    print(f"  API Key configured: {'Yes' if config['PREFECT_MCP_API_KEY'] else 'No'}")

    return config


def handle_mcp_error(error: Exception, operation: str) -> Dict[str, Any]:
    """
    Standardized error handling for MCP operations

    Args:
        error: The exception that occurred
        operation: Description of the operation that failed

    Returns:
        Standardized error response
    """
    return {
        "success": False,
        "operation": operation,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "timestamp": None,  # Could add timestamp if needed
    }
