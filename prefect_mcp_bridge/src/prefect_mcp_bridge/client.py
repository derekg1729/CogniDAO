"""
MCPClient - Lightweight HTTP client for MCP server endpoints
"""

import os
import requests
from typing import Any, Dict, Optional
import json


class MCPClient:
    """
    Lightweight MCPClient with base_url + auth header handling

    Usage:
        client = MCPClient()
        result = client.call('dolt.commit', {'message': 'test commit', 'branch': 'main'})
    """

    def __init__(self, base_url: str = None, api_key: Optional[str] = None, timeout: int = 30):
        """
        Initialize MCPClient

        Args:
            base_url: MCP server base URL (defaults to MCP_URL env var or http://cogni-mcp:8080)
            api_key: Optional API key for authentication (defaults to PREFECT_MCP_API_KEY env var)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or os.getenv("MCP_URL", "http://cogni-mcp:8080")
        self.api_key = api_key or os.getenv("PREFECT_MCP_API_KEY")
        self.timeout = timeout

        # Ensure base_url doesn't end with slash
        self.base_url = self.base_url.rstrip("/")

        # Setup session with auth headers
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update(
                {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            )
        else:
            self.session.headers.update({"Content-Type": "application/json"})

    def call(self, tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        POST {base_url}/{tool_name} with JSON payload; raise on non-200; return r.json()

        Args:
            tool_name: MCP tool name (e.g., 'dolt.commit', 'dolt.add')
            payload: JSON payload to send

        Returns:
            JSON response from MCP server

        Raises:
            requests.HTTPError: If response status is not 2xx
            requests.RequestException: For network/connection errors
            json.JSONDecodeError: If response is not valid JSON
        """
        url = f"{self.base_url}/{tool_name}"

        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)

            # Raise HTTPError for bad status codes
            response.raise_for_status()

            # Parse and return JSON response
            return response.json()

        except requests.HTTPError as e:
            # Add more context to HTTP errors
            error_msg = f"MCP call failed: {e.response.status_code} {e.response.reason}"
            try:
                error_detail = e.response.json()
                error_msg += f" - {error_detail}"
            except (json.JSONDecodeError, AttributeError):
                error_msg += f" - {e.response.text[:200]}"
            raise requests.HTTPError(error_msg) from e

        except requests.RequestException as e:
            # Add context to network errors
            raise requests.RequestException(f"MCP network error calling {url}: {e}") from e

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup session"""
        self.session.close()
