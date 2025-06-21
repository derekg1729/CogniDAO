#!/usr/bin/env python3
"""
Existing MCP Connection - DRY Implementation with Shared Helper
===============================================================

Demonstrates using the shared `configure_existing_mcp` helper:
1. Single import for any flow needing a live MCP session
2. One-liner to get session and tools
3. Direct tool usage without helper functions

This example shows how any Prefect flow can now easily connect to MCP.
Uses the shared helper that extracts the proven working SSE pattern.
"""

import sys
from pathlib import Path

# Ensure proper Python path for container environment
current_dir = Path(__file__).parent
workspace_root = current_dir.parent.parent  # Go up two levels: flows/examples -> flows -> workspace
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

import asyncio  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
from typing import Any, Dict  # noqa: E402

from prefect import flow  # noqa: E402
from prefect.logging import get_run_logger  # noqa: E402

# Import the shared MCP helper
from utils.mcp_setup import configure_existing_mcp, MCPConnectionError  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO)


@flow(name="existing_mcp_connection_flow", log_prints=True)
async def existing_mcp_connection_flow() -> Dict[str, Any]:
    """
    MCP Connection Flow with Shared Helper

    Uses the shared `configure_existing_mcp` helper for clean, reusable MCP connections.
    Connects via SSE transport to existing MCP server (ToolHive deployment).

    This demonstrates the simplified pattern that any flow can now use.
    """
    logger = get_run_logger()
    logger.info("🚀 Starting MCP connection flow with shared helper")

    # Get SSE URL from environment with fallback
    sse_url = os.getenv("COGNI_MCP_SSE_URL", "http://toolhive:24160/sse")
    logger.info(f"🔧 Using MCP SSE URL: {sse_url}")

    try:
        # Single line to get session and tools - this is the key improvement
        logger.info("🔄 Using shared MCP helper...")
        async with configure_existing_mcp(sse_url) as (session, tools):
            logger.info("📡 MCP session and tools ready")
            logger.info(f"   Session ID: {id(session)}")
            logger.info(f"   Tools count: {len(tools)}")

            # Direct tool usage - much simpler than before
            if len(tools) > 0:
                # Find DoltStatus tool or use first available
                first_tool = next((t.name for t in tools if t.name == "DoltStatus"), tools[0].name)
                logger.info(f"🛠️  Calling tool: {first_tool}")

                # Direct session call - no helper function needed
                result = await session.call_tool(first_tool, {"input": "{}"})

                return {
                    "status": "success",
                    "connection": {
                        "tools_count": len(tools),
                        "tools": [
                            {"name": tool.name, "description": tool.description or "No description"}
                            for tool in tools
                        ],
                        "transport": "sse",
                        "server_url": sse_url,
                    },
                    "tool_call": {
                        "success": True,
                        "tool_name": first_tool,
                        "result": result.content,
                    },
                }
            else:
                return {"status": "success", "message": "No tools available"}

    except MCPConnectionError as e:
        logger.error(f"❌ MCP connection error: {e}")
        return {"status": "failed", "error": str(e)}
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        return {"status": "failed", "error": str(e)}
    except Exception as e:
        logger.error(f"❌ Flow failed: {e}")
        return {"status": "failed", "error": str(e)}


if __name__ == "__main__":
    # For direct testing
    print("Running existing_mcp_connection_flow with shared helper...")
    print("Using shared configure_existing_mcp() helper")
    print("This demonstrates the simplified pattern for any Prefect flow")
    asyncio.run(existing_mcp_connection_flow())
