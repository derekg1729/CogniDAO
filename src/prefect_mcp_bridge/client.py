"""
HTTP client for MCP (Model Context Protocol) endpoints
"""

import os
import logging
import time
from typing import Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Set up logger
logger = logging.getLogger(__name__)


class MCPClient:
    """
    HTTP client for MCP endpoints with authentication and error handling
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        api_key_block: Optional[str] = None,
        timeout: int = 30,
    ):
        """
        Initialize MCP client

        Args:
            base_url: Base URL for MCP server (defaults to MCP_URL env var)
            api_key: API key for authentication (defaults to PREFECT_MCP_API_KEY env var)
            api_key_block: Optional Prefect Secret block name to load API key from
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or os.getenv("MCP_URL", "http://cogni-mcp:8080")
        self.timeout = timeout

        # Handle API key from multiple sources
        if api_key_block:
            try:
                from prefect.blocks.system import Secret

                secret_block = Secret.load(api_key_block)
                self.api_key = secret_block.get()
                logger.debug(f"Loaded API key from Prefect Secret block: {api_key_block}")
            except ImportError:
                logger.warning("Prefect Secret blocks not available, falling back to env var")
                self.api_key = api_key or os.getenv("PREFECT_MCP_API_KEY")
            except Exception as e:
                logger.warning(
                    f"Failed to load Secret block {api_key_block}: {e}, falling back to env var"
                )
                self.api_key = api_key or os.getenv("PREFECT_MCP_API_KEY")
        else:
            self.api_key = api_key or os.getenv("PREFECT_MCP_API_KEY")

        # Set up session with retry strategy
        self.session = requests.Session()

        # Configure retries for transient failures
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=1,
            allowed_methods=["POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

        logger.debug(f"Initialized MCPClient with base_url={self.base_url}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, "session"):
            self.session.close()

    def call(
        self, tool_name: str, payload: Dict[str, Any], timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Call an MCP tool endpoint

        Args:
            tool_name: Name of the MCP tool to call
            payload: Request payload
            timeout: Override default timeout

        Returns:
            Response data from MCP endpoint

        Raises:
            requests.RequestException: For network or HTTP errors
        """
        url = f"{self.base_url}/{tool_name}"
        request_timeout = timeout or self.timeout

        # Log request details
        payload_size = len(str(payload))
        logger.debug(
            f"Calling MCP tool: {tool_name}, payload_size={payload_size}b, timeout={request_timeout}s"
        )

        start_time = time.time()

        try:
            response = self.session.post(url, json=payload, timeout=request_timeout)
            response_time = time.time() - start_time

            logger.debug(
                f"MCP call completed: {tool_name}, status={response.status_code}, response_time={response_time:.3f}s"
            )

            # Handle HTTP errors
            if not response.ok:
                error_detail = ""
                try:
                    error_data = response.json()
                    error_detail = error_data.get("error", "Unknown error")
                    logger.error(
                        f"MCP tool {tool_name} returned HTTP {response.status_code}: {error_detail}"
                    )
                except Exception:
                    error_detail = response.text[:200] if response.text else "No error details"
                    logger.error(
                        f"MCP tool {tool_name} returned HTTP {response.status_code}: {error_detail}"
                    )

                raise requests.HTTPError(
                    f"MCP call failed with status {response.status_code}: {error_detail}",
                    response=response,
                )

            # Parse and return response
            try:
                result = response.json()
                logger.debug(
                    f"MCP tool {tool_name} succeeded with response size: {len(str(result))}b"
                )
                return result
            except Exception as e:
                logger.error(f"Failed to parse JSON response from {tool_name}: {e}")
                raise requests.RequestException(
                    f"Invalid JSON response from {tool_name}: {e}"
                ) from e

        except requests.exceptions.Timeout as e:
            logger.error(f"MCP tool {tool_name} timed out after {request_timeout}s")
            raise requests.RequestException(f"MCP call timeout for {tool_name}: {e}") from e
        except requests.exceptions.ConnectionError as e:
            logger.error(f"MCP tool {tool_name} connection failed: {e}")
            raise requests.RequestException(f"MCP network error calling {url}: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error calling MCP tool {tool_name}: {e}")
            raise requests.RequestException(f"MCP call error for {tool_name}: {e}") from e
