#!/usr/bin/env python3
"""
Existing MCP Connection - DRY Implementation with Persistent Session
===================================================================

Demonstrates connecting to an existing MCP server with a persistent session:
1. Establish single MCP session for entire flow lifecycle
2. List available tools using shared session
3. Call tools using same shared session
4. Support transport switching via MCP_TRANSPORT environment variable

This example maintains one session throughout the flow, following MCP best practices.

Uses stdio transport to spawn MCP server process directly.
This follows the proven working pattern from other flows for reliable deployment.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict

from prefect import flow, task
from prefect.logging import get_run_logger

# Official MCP Python SDK
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Configure logging
logging.basicConfig(level=logging.INFO)


class MCPConnectionError(Exception):
    """Custom exception for MCP connection issues"""

    pass


@asynccontextmanager
async def mcp_session():
    """
    Shared MCP session context manager that maintains a single session throughout flow lifecycle.
    Uses stdio transport to spawn MCP server process directly (proven working pattern).
    """
    # Use stdio transport (proven working pattern from other flows)
    transport = "stdio"

    logger = get_run_logger()
    logger.info("🔗 Attempting MCP connection...")
    logger.info(f"   Transport: {transport}")

    # Path resolution following proven working pattern from shared_tasks.py
    from pathlib import Path

    workspace_root = Path("/workspace")  # Container path
    cogni_mcp_path = workspace_root / "services" / "mcp_server" / "app" / "mcp_server.py"

    if not cogni_mcp_path.exists():
        # Fallback to local development path
        workspace_root = Path(__file__).resolve().parent.parent.parent
        cogni_mcp_path = workspace_root / "services" / "mcp_server" / "app" / "mcp_server.py"

    if not cogni_mcp_path.exists():
        logger.error(f"❌ Cogni MCP server not found at: {cogni_mcp_path}")
        raise MCPConnectionError(f"MCP server file not found at {cogni_mcp_path}")

    logger.info(f"🔧 Using MCP server at: {cogni_mcp_path}")

    # Environment configuration following proven working pattern from shared_tasks.py
    workspace_root = Path("/workspace")  # Container workspace root
    server_env = {
        **os.environ,
        "DOLT_HOST": os.getenv("DOLT_HOST", "dolt-db"),  # Use container hostname in deployment
        "DOLT_PORT": os.getenv("DOLT_PORT", "3306"),
        "DOLT_USER": os.getenv("DOLT_USER", "root"),
        "DOLT_ROOT_PASSWORD": os.getenv(
            "DOLT_ROOT_PASSWORD", "kXMnM6firYohXzK+2r0E0DmSjOl6g3A2SmXc6ALDOlA="
        ),
        "DOLT_DATABASE": "cogni-dao-memory",
        "MYSQL_DATABASE": "cogni-dao-memory",
        "CHROMA_PATH": os.getenv("CHROMA_PATH", "/tmp/chroma"),
        "CHROMA_COLLECTION_NAME": "cogni_mcp_collection",
    }

    # Add workspace root to Python path for both container and local (CRITICAL for imports)
    if str(workspace_root) not in server_env.get("PYTHONPATH", ""):
        existing_pythonpath = server_env.get("PYTHONPATH", "")
        server_env["PYTHONPATH"] = (
            f"{workspace_root}:{existing_pythonpath}"
            if existing_pythonpath
            else str(workspace_root)
        )

    session = None
    try:
        logger.info("📡 Creating stdio client connection...")

        # StdioServerParameters following proven working pattern
        server_params = StdioServerParameters(
            command="python", args=[str(cogni_mcp_path)], env=server_env
        )

        async with stdio_client(server_params) as (read_stream, write_stream):
            logger.info("✅ Stdio client connected, creating session...")

            async with ClientSession(read_stream, write_stream) as session:
                logger.info("📋 Initializing MCP session...")

                # Initialize the session once
                await session.initialize()
                logger.info("✅ MCP session initialized successfully!")
                logger.info(f"   Session ID: {id(session)}")
                logger.info(f"   Session type: {type(session)}")

                # Yield the session for use throughout the flow
                yield session
                logger.info("🔚 MCP session context exiting cleanly")

    except ConnectionError as e:
        logger.error(f"❌ Connection failed to MCP server: {e}")
        raise MCPConnectionError(f"Connection failed to MCP server: {e}")
    except TimeoutError as e:
        logger.error(f"❌ Connection timeout to MCP server: {e}")
        raise MCPConnectionError(f"Connection timeout to MCP server: {e}")
    except Exception as e:
        logger.error(f"❌ MCP session failed: {type(e).__name__}: {e}")
        logger.error(f"   MCP server path: {cogni_mcp_path}")
        logger.error(f"   Session state: {session}")
        import traceback

        logger.error(f"   Full traceback: {traceback.format_exc()}")
        raise MCPConnectionError(f"Failed to establish MCP session: {type(e).__name__}: {e}")


@task(name="list_tools_with_session", cache_policy=None)
async def list_tools_with_session(session: ClientSession) -> Dict[str, Any]:
    """List available tools using provided session"""
    logger = get_run_logger()

    logger.info("🔧 Listing tools from MCP session...")
    logger.info(f"   Session ID: {id(session)}")
    logger.info(f"   Session type: {type(session)}")

    try:
        # Use the provided session directly
        logger.info("📋 Calling session.list_tools()...")
        tools_response = await session.list_tools()
        logger.info(f"✅ Got tools response: {type(tools_response)}")

        available_tools = tools_response.tools
        logger.info(f"📊 Found {len(available_tools)} tools")

        # Log first few tools for debugging
        for i, tool in enumerate(available_tools[:3]):
            logger.info(f"   🔧 Tool {i + 1}: {tool.name} - {tool.description or 'No description'}")

        if len(available_tools) > 3:
            logger.info(f"   ... and {len(available_tools) - 3} more tools")

        return {
            "success": True,
            "tools": available_tools,  # Keep as SDK objects
            "tools_count": len(available_tools),
        }

    except Exception as e:
        logger.error(f"❌ Failed to list tools: {type(e).__name__}: {e}")
        import traceback

        logger.error(f"   Full traceback: {traceback.format_exc()}")
        raise MCPConnectionError(f"Tool listing failed: {type(e).__name__}: {e}")


@task(name="call_tool_with_session", cache_policy=None)
async def call_tool_with_session(
    session: ClientSession, tool_name: str, arguments: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Call a tool using provided session"""
    logger = get_run_logger()

    logger.info(f"🛠️  Calling tool '{tool_name}'...")
    logger.info(f"   Session ID: {id(session)}")
    logger.info(f"   Arguments: {arguments or {}}")

    try:
        # Use the provided session directly
        logger.info(f"📞 Executing session.call_tool('{tool_name}', {arguments or {}})...")
        result = await session.call_tool(tool_name, arguments or {})

        logger.info(f"✅ Tool '{tool_name}' executed successfully")
        logger.info(f"   Result type: {type(result)}")
        logger.info(f"   Result content preview: {str(result.content)[:200]}...")

        return {
            "success": True,
            "tool_name": tool_name,
            "result": result,  # Keep as SDK object
        }

    except Exception as e:
        logger.error(f"❌ Tool call failed: {type(e).__name__}: {e}")
        logger.error(f"   Tool: {tool_name}")
        logger.error(f"   Arguments: {arguments}")
        import traceback

        logger.error(f"   Full traceback: {traceback.format_exc()}")
        raise MCPConnectionError(f"Tool '{tool_name}' call failed: {type(e).__name__}: {e}")


@flow(name="existing_mcp_connection_flow", log_prints=True)
async def existing_mcp_connection_flow() -> Dict[str, Any]:
    """
    MCP Connection Flow with Persistent Session

    Uses a single MCP session throughout the entire flow lifecycle.
    Connects via stdio transport (spawns MCP server process directly).

    This uses the proven working pattern from other flows for reliable deployment.
    """
    logger = get_run_logger()
    logger.info("🚀 Starting MCP connection flow with persistent session")

    try:
        # Single session for entire flow - this is the key improvement
        logger.info("🔄 Entering MCP session context...")
        async with mcp_session() as session:
            logger.info("📡 MCP session established - using throughout flow")
            logger.info(f"   Session object: {session}")
            logger.info(f"   Session ID: {id(session)}")

            # Step 1: List tools using shared session
            logger.info("📋 Step 1: Listing tools...")
            tools_result = await list_tools_with_session(session)
            logger.info(
                f"✅ Tools result: {tools_result.get('success')} ({tools_result.get('tools_count', 0)} tools)"
            )

            if not tools_result.get("success"):
                logger.error("❌ Tool listing failed")
                return {"status": "failed", "error": "Failed to list tools"}

            # Step 2: Call tool using same session
            logger.info("🛠️  Step 2: Calling tool...")
            if tools_result["tools_count"] > 0:
                # Call DoltStatus with proper input parameter
                tool_result = await call_tool_with_session(session, "DoltStatus", {"input": "{}"})

                # Only convert to JSON at API boundary (here in flow return)
                return {
                    "status": "success",
                    "connection": {
                        "tools_count": tools_result["tools_count"],
                        "tools": [
                            {"name": tool.name, "description": tool.description or "No description"}
                            for tool in tools_result["tools"]
                        ],
                        "transport": "stdio",
                        "server_path": "cogni-mcp-server",
                    },
                    "tool_call": {
                        "success": tool_result.get("success"),
                        "tool_name": tool_result.get("tool_name"),
                        "result": tool_result["result"].content
                        if tool_result.get("success")
                        else None,
                    },
                }
            else:
                return {"status": "success", "message": "No tools available"}

    except MCPConnectionError as e:
        logger.error(f"❌ MCP connection error: {e}")
        return {"status": "failed", "error": str(e)}
    except Exception as e:
        logger.error(f"❌ Flow failed: {e}")
        return {"status": "failed", "error": str(e)}


if __name__ == "__main__":
    # For direct testing
    print("Running existing_mcp_connection_flow with persistent session...")
    print("Using stdio transport to spawn MCP server process directly")
    print("This follows the proven working pattern for reliable deployment")
    asyncio.run(existing_mcp_connection_flow())
