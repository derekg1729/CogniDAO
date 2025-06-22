#!/usr/bin/env python3
"""
Echo Tool - Minimal MCP SDK Example
===================================

Demonstrates the simplest possible MCP client usage:
1. Connect to MCP server via stdio
2. List available tools
3. Call one tool
4. Exit cleanly

This is the foundational example for understanding MCP integration.
"""

import asyncio
import logging
import os
from typing import Any, Dict

from prefect import flow, task
from prefect.logging import get_run_logger

# Official MCP Python SDK
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Configure logging
logging.basicConfig(level=logging.INFO)


@task(name="connect_and_list_tools")
async def connect_and_list_tools() -> Dict[str, Any]:
    """Connect to MCP server and list available tools using official SDK"""
    logger = get_run_logger()

    # Environment-configurable server parameters (addressing ENV-01)
    mcp_command = os.getenv("MCP_SERVER_COMMAND", "python")
    mcp_args = os.getenv("MCP_SERVER_ARGS", "-m,services.mcp_server.app.mcp_server").split(",")

    logger.info(f"Connecting to MCP server: {mcp_command} {' '.join(mcp_args)}")

    try:
        server_params = StdioServerParameters(command=mcp_command, args=mcp_args, env=None)

        # Create stdio client connection using official MCP SDK
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                # Initialize the MCP session
                await session.initialize()

                # List available tools using official SDK
                tools_response = await session.list_tools()
                available_tools = tools_response.tools

                # Return only serializable data (addressing SER-01)
                tools_list = [
                    {"name": tool.name, "description": tool.description or "No description"}
                    for tool in available_tools
                ]

                logger.info(f"Connected successfully! Found {len(available_tools)} tools")
                if logger.isEnabledFor(logging.DEBUG):  # Conditional emoji (addressing OBS-01)
                    for tool in available_tools:
                        logger.debug(f"   🔧 {tool.name}: {tool.description}")

                return {
                    "success": True,
                    "tools_count": len(available_tools),
                    "tools": tools_list,
                    "connection_type": "official_mcp_sdk",
                    "transport": "stdio",
                }

    except Exception as e:
        logger.error(f"MCP connection failed: {e}")
        return {"success": False, "error": str(e), "tools_count": 0, "tools": []}


@task(name="call_single_tool")
async def call_single_tool(tool_name: str = "DoltStatus") -> Dict[str, Any]:
    """Call a single MCP tool and return the result"""
    logger = get_run_logger()

    # Environment-configurable server parameters
    mcp_command = os.getenv("MCP_SERVER_COMMAND", "python")
    mcp_args = os.getenv("MCP_SERVER_ARGS", "-m,services.mcp_server.app.mcp_server").split(",")

    logger.info(f"Calling tool '{tool_name}'")

    try:
        server_params = StdioServerParameters(command=mcp_command, args=mcp_args, env=None)

        # Create connection and call tool
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call the specified tool
                result = await session.call_tool(tool_name, {})

                logger.info(f"Tool '{tool_name}' called successfully")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"   📊 Result: {result.content}")

                return {"success": True, "tool_name": tool_name, "result": result.content}

    except Exception as e:
        logger.error(f"Tool call failed: {e}")
        return {"success": False, "tool_name": tool_name, "error": str(e)}


@flow(name="echo_tool_flow", log_prints=True)
async def echo_tool_flow() -> Dict[str, Any]:
    """
    Minimal MCP Tool Demonstration

    This flow demonstrates the simplest possible MCP integration:
    1. Connect to MCP server
    2. List available tools
    3. Call one tool (DoltStatus by default)
    4. Return results

    Environment Variables:
    - MCP_SERVER_COMMAND: Command to run MCP server (default: "python")
    - MCP_SERVER_ARGS: Comma-separated args (default: "-m,services.mcp_server.app.mcp_server")
    """
    logger = get_run_logger()
    logger.info("Starting minimal MCP tool demonstration")

    try:
        # Step 1: Connect and list tools
        connection_result = await connect_and_list_tools()

        if not connection_result.get("success"):
            logger.error(f"Connection failed: {connection_result.get('error')}")
            return {"status": "failed", "error": connection_result.get("error")}

        logger.info(f"Connected successfully with {connection_result['tools_count']} tools")

        # Step 2: Call a simple tool
        if connection_result["tools_count"] > 0:
            # Use first available tool or default to DoltStatus
            first_tool = (
                connection_result["tools"][0]["name"]
                if connection_result["tools"]
                else "DoltStatus"
            )
            tool_result = await call_single_tool(first_tool)

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
    print("Running echo_tool_flow directly...")
    asyncio.run(echo_tool_flow())
