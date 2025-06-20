#!/usr/bin/env python3
"""
Existing MCP Connection - SSE Transport Example
===============================================

Demonstrates connecting to an existing MCP server via SSE transport:
1. Connect to existing ToolHive MCP server via SSE
2. List available tools
3. Call one tool
4. Exit cleanly

This example connects to your containerized MCP server instead of spawning a new process.

IMPORTANT: The default endpoint (127.0.0.1:24160) is only accessible from within
the ToolHive container network. To test from host, either:
1. Set MCP_SSE_URL to a proxy endpoint
2. Run this script from within a container on the same network
3. Use ToolHive's inspector: `docker exec toolhive thv inspector cogni-mcp`
"""

import asyncio
import logging
import os
from typing import Any, Dict

from prefect import flow, task
from prefect.logging import get_run_logger

# Official MCP Python SDK - SSE transport
from mcp import ClientSession
from mcp.client.sse import sse_client

# Configure logging
logging.basicConfig(level=logging.INFO)


@task(name="connect_and_list_tools_sse")
async def connect_and_list_tools_sse() -> Dict[str, Any]:
    """Connect to existing MCP server via SSE and list available tools"""
    logger = get_run_logger()

    # Environment-configurable SSE endpoint
    # Default to ToolHive internal address from `thv list` output
    mcp_sse_url = os.getenv("MCP_SSE_URL", "http://toolhive:24160/sse")

    logger.info(f"Connecting to existing MCP server via SSE: {mcp_sse_url}")

    try:
        # Create SSE client connection using official MCP SDK
        async with sse_client(mcp_sse_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                # Initialize the MCP session
                await session.initialize()

                # List available tools using official SDK
                tools_response = await session.list_tools()
                available_tools = tools_response.tools

                # Return only serializable data
                tools_list = [
                    {"name": tool.name, "description": tool.description or "No description"}
                    for tool in available_tools
                ]

                logger.info(f"Connected successfully! Found {len(available_tools)} tools")
                if logger.isEnabledFor(logging.DEBUG):
                    for tool in available_tools:
                        logger.debug(f"   🔧 {tool.name}: {tool.description}")

                return {
                    "success": True,
                    "tools_count": len(available_tools),
                    "tools": tools_list,
                    "connection_type": "official_mcp_sdk",
                    "transport": "sse",
                    "endpoint": mcp_sse_url,
                }

    except Exception as e:
        logger.error(f"SSE MCP connection failed: {e}")
        return {"success": False, "error": str(e), "tools_count": 0, "tools": []}


@task(name="call_single_tool_sse")
async def call_single_tool_sse(tool_name: str = "DoltStatus") -> Dict[str, Any]:
    """Call a single MCP tool via SSE and return the result"""
    logger = get_run_logger()

    # Environment-configurable SSE endpoint
    mcp_sse_url = os.getenv("MCP_SSE_URL", "http://toolhive:24160/sse")

    logger.info(f"Calling tool '{tool_name}' via SSE")

    try:
        # Create SSE connection and call tool
        async with sse_client(mcp_sse_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call the specified tool
                result = await session.call_tool(tool_name, {})

                logger.info(f"Tool '{tool_name}' called successfully via SSE")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"   📊 Result: {result.content}")

                return {"success": True, "tool_name": tool_name, "result": result.content}

    except Exception as e:
        logger.error(f"SSE tool call failed: {e}")
        return {"success": False, "tool_name": tool_name, "error": str(e)}


@flow(name="existing_mcp_connection_flow", log_prints=True)
async def existing_mcp_connection_flow() -> Dict[str, Any]:
    """
    Existing MCP Server Connection Demonstration

    This flow demonstrates connecting to an existing MCP server via SSE:
    1. Connect to existing ToolHive MCP server
    2. List available tools
    3. Call one tool (DoltStatus by default)
    4. Return results

    Environment Variables:
    - MCP_SSE_URL: SSE endpoint URL (default: "http://toolhive:24160/sse")
                   Use the internal ToolHive address from `thv list` output

    Network Requirements:
    - Must run from within ToolHive container network or use proxy
    - For testing: `docker exec toolhive thv inspector cogni-mcp`
    """
    logger = get_run_logger()
    logger.info("Starting existing MCP server connection demonstration via SSE")

    try:
        # Step 1: Connect and list tools via SSE
        connection_result = await connect_and_list_tools_sse()

        if not connection_result.get("success"):
            logger.error(f"SSE connection failed: {connection_result.get('error')}")
            return {"status": "failed", "error": connection_result.get("error")}

        logger.info(f"Connected successfully with {connection_result['tools_count']} tools")

        # Step 2: Call a simple tool
        if connection_result["tools_count"] > 0:
            # Use first available tool or default to DoltStatus
            # first_tool = (
            #     connection_result["tools"][0]["name"]
            #     if connection_result["tools"]
            #     else "DoltStatus"
            # )
            # hardcoding DoltStatus... first_tool kept calling CreateWorkItem
            first_tool = "DoltStatus"
            tool_result = await call_single_tool_sse(first_tool)

            if tool_result.get("success"):
                logger.info(f"Tool call successful: {first_tool}")
            else:
                logger.warning(f"Tool call failed: {tool_result.get('error')}")
        else:
            logger.warning("No tools available to call")
            tool_result = {"success": False, "error": "No tools available"}

        # Return simple, serializable results
        return {"status": "success", "connection": connection_result, "tool_call": tool_result}

    except Exception as e:
        logger.error(f"Flow failed: {e}")
        return {"status": "failed", "error": str(e)}


if __name__ == "__main__":
    # For direct testing
    print("Running existing_mcp_connection_flow directly...")
    print("Note: This requires network access to ToolHive internal endpoints")
    print("For testing, try: docker exec toolhive thv inspector cogni-mcp")
    asyncio.run(existing_mcp_connection_flow())
