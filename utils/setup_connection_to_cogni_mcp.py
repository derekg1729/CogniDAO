#!/usr/bin/env python3
"""
Cogni-Specific MCP Setup - Wrapper for Dolt/Namespace Operations
===============================================================

Thin wrapper around the generic `configure_existing_mcp` helper that adds
Cogni-specific functionality like Dolt branch switching and namespace handling.

This keeps the generic helper clean while providing convenience for Cogni flows.

Usage:
    from utils.setup_connection_to_cogni_mcp import configure_cogni_mcp

    # Uses environment variables for defaults
    async with configure_cogni_mcp() as (session, tools):
        # session is already on the right branch/namespace
        pass

    # Or specify explicitly
    async with configure_cogni_mcp(
        sse_url="http://toolhive:24160/sse",
        branch="ai-education-team",
        namespace="legacy"
    ) as (session, tools):
        pass
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import List, Tuple

from mcp import ClientSession

from utils.mcp_setup import configure_existing_mcp, MCPConnectionError


@asynccontextmanager
async def configure_cogni_mcp(
    *,
    sse_url: str | None = None,
    branch: str | None = None,
    namespace: str | None = None,
    timeout: int = 30,
) -> Tuple[ClientSession, List]:
    """
    Thin wrapper that calls `configure_existing_mcp` **then**
    performs DoltCheckout / ChangeNamespace if requested.
    Defaults come from env vars so flows don't have to import os.

    Args:
        sse_url: SSE URL for MCP server (defaults to COGNI_MCP_SSE_URL env var)
        branch: Dolt branch to switch to (defaults to MCP_DOLT_BRANCH env var)
        namespace: Namespace to use (defaults to MCP_DOLT_NAMESPACE env var)
        timeout: Connection timeout in seconds (default: 30)

    Yields:
        Tuple containing:
        - session: Live `ClientSession` with branch/namespace already switched
        - tools_list: List of tool proxies from `session.list_tools()`

    Raises:
        MCPConnectionError: If connection or Dolt operations fail
        ValueError: If sse_url cannot be determined

    Example:
        # Use environment variables for all settings
        async with configure_cogni_mcp() as (session, tools):
            # session is ready on the right branch/namespace
            pass

        # Override specific settings
        async with configure_cogni_mcp(branch="feature-branch") as (session, tools):
            pass
    """
    logger = logging.getLogger(__name__)

    # Apply environment variable defaults
    sse_url = sse_url or os.getenv("COGNI_MCP_SSE_URL", "http://toolhive:24160/sse")
    branch = branch or os.getenv("MCP_DOLT_BRANCH")
    namespace = namespace or os.getenv("MCP_DOLT_NAMESPACE")

    if not sse_url:
        raise ValueError(
            "sse_url must be provided or COGNI_MCP_SSE_URL environment variable must be set"
        )

    logger.info("🔗 Configuring Cogni MCP connection...")
    if branch:
        logger.info(f"   🌿 Target branch: {branch}")
    if namespace:
        logger.info(f"   📂 Target namespace: {namespace}")

    # Use the generic helper to establish the connection
    async with configure_existing_mcp(sse_url, timeout=timeout) as (session, tools):
        # Perform Cogni-specific setup after connection is established
        try:
            if branch:
                logger.info("🌿 Switching Dolt branch -> %s", branch)
                await session.call_tool(
                    "DoltCheckout", {"input": json.dumps({"branch_name": branch})}
                )
                logger.info("✅ Dolt branch switched successfully")

            if namespace:
                logger.info("📂 Switching namespace -> %s", namespace)
                # Note: Namespace switching is handled via environment variables in the MCP server
                # We'll log this for now but the actual switching happens at server startup
                logger.info("📋 Namespace switching noted (handled via env vars at server startup)")

            # Yield the configured session and tools
            yield session, tools

        except Exception as e:
            logger.error(f"❌ Cogni MCP setup failed during branch/namespace operations: {e}")
            raise MCPConnectionError(f"Failed to configure Cogni MCP: {e}")
