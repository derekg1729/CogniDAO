#!/usr/bin/env python3
"""
Shared MCP Setup - Reusable Helper for Prefect Flows
====================================================

Provides `configure_existing_mcp()` context manager that any Prefect flow can import.
Returns a tuple of (session, tools_list) for immediate use.

This extracts the proven working SSE pattern from flows/examples/existing_mcp_connection.py
into a reusable helper, eliminating code duplication across flows.

Usage:
    from utils.mcp_setup import configure_existing_mcp

    async with configure_existing_mcp("http://toolhive:24160/sse") as (session, tools):
        # Use session and tools directly
        result = await session.call_tool("DoltStatus", {})
        print(f"Found {len(tools)} tools")
"""

import logging
from contextlib import asynccontextmanager
from typing import List, Tuple

from mcp import ClientSession
from mcp.client.sse import sse_client


class MCPConnectionError(Exception):
    """Custom exception for MCP connection issues"""

    pass


@asynccontextmanager
async def configure_existing_mcp(sse_url: str, timeout: int = 30) -> Tuple[ClientSession, List]:
    """
    Yield `(session, tools_list)` for the MCP server exposed by ToolHive.

    Args:
        sse_url: SSE URL for the MCP server (required, e.g., "http://toolhive:24160/sse")
        timeout: Connection timeout in seconds (default: 30)

    Yields:
        Tuple containing:
        - session: Live `ClientSession` (keep it in the async context)
        - tools_list: List of tool proxies from `session.list_tools()`

    Raises:
        MCPConnectionError: If connection fails
        ValueError: If sse_url is not provided

    Example:
        async with configure_existing_mcp("http://toolhive:24160/sse") as (session, tools):
            # orchestration work
            first_tool = next((t.name for t in tools if t.name == "DoltStatus"), tools[0].name)
            result = await session.call_tool(first_tool, {})
    """

    # Validate required URL parameter
    if not sse_url:
        raise ValueError("sse_url parameter is required and cannot be empty")

    # Set up logging (compatible with both Prefect and standalone usage)
    logger = logging.getLogger(__name__)

    logger.info("🔗 Configuring MCP connection...")
    logger.info("   Transport: SSE")
    logger.info(f"   URL: {sse_url}")
    logger.info(f"   Timeout: {timeout}s")

    session = None
    try:
        logger.info("📡 Creating SSE client connection...")

        async with sse_client(sse_url, timeout=timeout) as (read_stream, write_stream):
            logger.info("✅ SSE client connected, creating session...")

            async with ClientSession(read_stream, write_stream) as session:
                logger.info("📋 Initializing MCP session...")

                # Initialize the session once
                await session.initialize()
                logger.info("✅ MCP session initialized successfully!")
                logger.info(f"   Session ID: {id(session)}")

                # Get tools list immediately
                logger.info("🔧 Fetching tools list...")
                tools_response = await session.list_tools()
                tools = tools_response.tools
                logger.info(f"📊 Found {len(tools)} tools")

                # Log first few tools for debugging
                for i, tool in enumerate(tools[:3]):
                    logger.info(
                        f"   🔧 Tool {i + 1}: {tool.name} - {tool.description or 'No description'}"
                    )

                if len(tools) > 3:
                    logger.info(f"   ... and {len(tools) - 3} more tools")

                # Yield both session and tools for caller use
                yield session, tools

                logger.info("🔚 MCP session context exiting cleanly")

    except ConnectionError as e:
        logger.error(f"❌ Connection failed to MCP server: {e}")
        raise MCPConnectionError(f"Connection failed to MCP server: {e}")
    except TimeoutError as e:
        logger.error(f"❌ Connection timeout to MCP server: {e}")
        raise MCPConnectionError(f"Connection timeout to MCP server: {e}")
    except Exception as e:
        logger.error(f"❌ MCP session failed: {type(e).__name__}: {e}")
        logger.error(f"   MCP SSE URL: {sse_url}")
        logger.error(f"   Session state: {session}")
        import traceback

        logger.error(f"   Full traceback: {traceback.format_exc()}")
        raise MCPConnectionError(f"Failed to establish MCP session: {type(e).__name__}: {e}")
