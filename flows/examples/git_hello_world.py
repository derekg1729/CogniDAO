#!/usr/bin/env python3
"""
Git Hello World - Git MCP Integration Example
=============================================

Demonstrates Git operations via MCP (Model Context Protocol):
1. Connect to Git MCP server via SSE transport
2. List available Git tools
3. Call basic Git operations (status, log)
4. Return structured results

This follows the established pattern from existing MCP flows but targets Git operations.
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

from prefect import flow, task  # noqa: E402
from prefect.logging import get_run_logger  # noqa: E402

# Import the shared MCP helper (following established pattern)
from utils.mcp_setup import configure_existing_mcp, MCPConnectionError  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO)


@task(name="git_list_tools")
async def git_list_tools(sse_url: str) -> Dict[str, Any]:
    """Connect to Git MCP server and list available tools"""
    logger = get_run_logger()
    logger.info("🔧 Listing Git MCP tools...")

    try:
        async with configure_existing_mcp(sse_url) as (session, tools):
            tools_list = [
                {"name": tool.name, "description": tool.description or "No description"}
                for tool in tools
            ]

            logger.info(f"📋 Found {len(tools)} Git tools")
            for tool in tools:
                logger.info(f"   🔧 {tool.name}: {tool.description or 'No description'}")

            return {
                "success": True,
                "tools_count": len(tools),
                "tools": tools_list,
                "connection_type": "sse_transport",
                "server_url": sse_url,
            }

    except Exception as e:
        logger.error(f"❌ Git MCP connection failed: {e}")
        return {"success": False, "error": str(e), "tools_count": 0, "tools": []}


@task(name="git_status_check")
async def git_status_check(sse_url: str) -> Dict[str, Any]:
    """Call git status via MCP to check repository state"""
    logger = get_run_logger()
    logger.info("📊 Checking Git repository status...")

    try:
        async with configure_existing_mcp(sse_url) as (session, tools):
            # Look for git status tool (name may vary by MCP implementation)
            git_tools = [
                tool
                for tool in tools
                if "status" in tool.name.lower() or "git" in tool.name.lower()
            ]

            if git_tools:
                tool_name = git_tools[0].name
                logger.info(f"🔍 Using tool: {tool_name}")

                # Call git status tool
                result = await session.call_tool(tool_name, {})

                logger.info("✅ Git status check completed")
                return {
                    "success": True,
                    "tool_name": tool_name,
                    "result": result.content,
                    "operation": "git_status",
                }
            else:
                logger.warning("⚠️ No git status tool found")
                # Fallback: try first available tool
                if tools:
                    tool_name = tools[0].name
                    result = await session.call_tool(tool_name, {})
                    return {
                        "success": True,
                        "tool_name": tool_name,
                        "result": result.content,
                        "operation": "fallback_tool",
                        "note": "Used first available tool since no git-specific tool found",
                    }
                else:
                    return {"success": False, "error": "No tools available"}

    except Exception as e:
        logger.error(f"❌ Git status check failed: {e}")
        return {"success": False, "error": str(e), "operation": "git_status"}


@task(name="git_hello_world_demo")
async def git_hello_world_demo(sse_url: str) -> Dict[str, Any]:
    """Demonstrate basic Git operations via MCP"""
    logger = get_run_logger()
    logger.info("🌍 Running Git Hello World demo...")

    try:
        async with configure_existing_mcp(sse_url) as (session, tools):
            demo_results = []

            # Try a few basic Git operations if tools are available
            git_operations = ["status", "log", "branch"]

            for operation in git_operations:
                # Find tools that might handle this operation
                matching_tools = [
                    tool
                    for tool in tools
                    if operation in tool.name.lower() or "git" in tool.name.lower()
                ]

                if matching_tools:
                    tool_name = matching_tools[0].name
                    logger.info(f"🔧 Trying {operation} with tool: {tool_name}")

                    try:
                        result = await session.call_tool(tool_name, {})
                        demo_results.append(
                            {
                                "operation": operation,
                                "tool_name": tool_name,
                                "success": True,
                                "result": result.content[:200] + "..."
                                if len(str(result.content)) > 200
                                else result.content,
                            }
                        )
                        logger.info(f"✅ {operation} completed successfully")
                    except Exception as e:
                        demo_results.append(
                            {
                                "operation": operation,
                                "tool_name": tool_name,
                                "success": False,
                                "error": str(e),
                            }
                        )
                        logger.warning(f"⚠️ {operation} failed: {e}")
                else:
                    logger.info(f"⏭️ No tool found for {operation}")

            # If no git-specific tools, just use first available tool as demo
            if not demo_results and tools:
                tool_name = tools[0].name
                logger.info(f"🔧 Demo using first available tool: {tool_name}")
                result = await session.call_tool(tool_name, {})
                demo_results.append(
                    {
                        "operation": "demo",
                        "tool_name": tool_name,
                        "success": True,
                        "result": result.content[:200] + "..."
                        if len(str(result.content)) > 200
                        else result.content,
                    }
                )

            return {
                "success": True,
                "demo_results": demo_results,
                "tools_available": len(tools),
                "operations_attempted": len(demo_results),
            }

    except Exception as e:
        logger.error(f"❌ Git demo failed: {e}")
        return {"success": False, "error": str(e)}


@flow(name="git_hello_world_flow", log_prints=True)
async def git_hello_world_flow() -> Dict[str, Any]:
    """
    Git Hello World MCP Flow

    Demonstrates Git operations via MCP using the established SSE transport pattern.
    This shows how to integrate with a new MCP server type (Git) following the
    same patterns as existing cogni-mcp flows.

    Environment Variables:
    - GIT_MCP_SSE_URL: SSE URL for Git MCP server (default: "http://toolhive:24161/sse")
    """
    logger = get_run_logger()
    logger.info("🚀 Starting Git Hello World MCP Flow")

    # Get Git MCP SSE URL from environment (new port 24161)
    sse_url = os.getenv("GIT_MCP_SSE_URL", "http://toolhive:24161/sse")
    logger.info(f"🔗 Using Git MCP SSE URL: {sse_url}")

    try:
        # Step 1: List available Git tools
        tools_result = await git_list_tools(sse_url)

        if not tools_result.get("success"):
            logger.error(f"❌ Failed to connect to Git MCP: {tools_result.get('error')}")
            return {"status": "failed", "error": tools_result.get("error"), "stage": "connection"}

        logger.info(f"✅ Connected to Git MCP with {tools_result['tools_count']} tools")

        # Step 2: Check Git repository status
        status_result = await git_status_check(sse_url)

        # Step 3: Run Hello World demo
        demo_result = await git_hello_world_demo(sse_url)

        # Return comprehensive results
        return {
            "status": "success",
            "git_mcp_connection": tools_result,
            "git_status": status_result,
            "hello_world_demo": demo_result,
            "summary": {
                "tools_found": tools_result.get("tools_count", 0),
                "status_success": status_result.get("success", False),
                "demo_operations": demo_result.get("operations_attempted", 0)
                if demo_result.get("success")
                else 0,
            },
        }

    except MCPConnectionError as e:
        logger.error(f"❌ Git MCP connection error: {e}")
        return {"status": "failed", "error": str(e), "stage": "mcp_connection"}
    except Exception as e:
        logger.error(f"❌ Git Hello World flow failed: {e}")
        return {"status": "failed", "error": str(e), "stage": "flow_execution"}


if __name__ == "__main__":
    # For direct testing
    print("Running git_hello_world_flow...")
    print("This demonstrates Git operations via MCP server on port 24161")
    asyncio.run(git_hello_world_flow())
