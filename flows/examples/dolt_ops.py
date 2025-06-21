#!/usr/bin/env python3
"""
Dolt Operations - DRY MCP Implementation with Persistent Session
===============================================================

Demonstrates Dolt workflow automation using direct MCP client session:
1. Check Dolt status
2. Stage changes
3. Commit with meaningful messages
4. Push to remote

This focuses purely on version control operations via MCP with persistent session.
Uses the proven working stdio transport pattern for reliable deployment.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
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


@task(name="call_mcp_tool_with_session", cache_policy=None)
async def call_mcp_tool_with_session(
    session: ClientSession, tool_name: str, tool_args: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Call a specific MCP tool using provided session"""
    logger = get_run_logger()

    logger.info(f"🛠️  Calling tool '{tool_name}'...")
    logger.info(f"   Session ID: {id(session)}")
    logger.info(f"   Arguments: {tool_args or {}}")

    try:
        # Use the provided session directly
        logger.info(f"📞 Executing session.call_tool('{tool_name}', {tool_args or {}})...")
        result = await session.call_tool(tool_name, tool_args or {})

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
        logger.error(f"   Arguments: {tool_args}")
        import traceback

        logger.error(f"   Full traceback: {traceback.format_exc()}")
        raise MCPConnectionError(f"Tool '{tool_name}' call failed: {type(e).__name__}: {e}")


@task(name="check_dolt_status", cache_policy=None)
async def check_dolt_status(session: ClientSession) -> Dict[str, Any]:
    """Check current Dolt repository status using MCP session"""
    logger = get_run_logger()
    logger.info("Checking Dolt repository status")

    result = await call_mcp_tool_with_session(session, "DoltStatus", {"input": "{}"})
    return result


@task(name="stage_dolt_changes", cache_policy=None)
async def stage_dolt_changes(session: ClientSession, tables: list | None = None) -> Dict[str, Any]:
    """Stage Dolt changes using MCP session"""
    logger = get_run_logger()

    add_args = {"input": "{}"}
    if tables:
        import json

        add_args = {"input": json.dumps({"tables": tables})}
        logger.info(f"Staging specific tables: {tables}")
    else:
        logger.info("Staging all changes")

    result = await call_mcp_tool_with_session(session, "DoltAdd", add_args)
    if result.get("success"):
        result["tables_staged"] = tables or "all"
    return result


@task(name="commit_dolt_changes", cache_policy=None)
async def commit_dolt_changes(
    session: ClientSession, commit_message: str, author: str | None = None
) -> Dict[str, Any]:
    """Commit Dolt changes using MCP session"""
    logger = get_run_logger()

    import json

    commit_args = {"commit_message": commit_message}
    if author:
        commit_args["author"] = author

    logger.info(f"Committing changes: '{commit_message}'")

    result = await call_mcp_tool_with_session(
        session, "DoltCommit", {"input": json.dumps(commit_args)}
    )
    if result.get("success"):
        result["commit_message"] = commit_message
        result["author"] = author
    return result


@task(name="push_dolt_changes", cache_policy=None)
async def push_dolt_changes(
    session: ClientSession, remote: str = "origin", branch: str = "main"
) -> Dict[str, Any]:
    """Push Dolt changes using MCP session"""
    logger = get_run_logger()

    import json

    push_args = {"remote_name": remote, "branch": branch}
    logger.info(f"Pushing to {remote}/{branch}")

    result = await call_mcp_tool_with_session(session, "DoltPush", {"input": json.dumps(push_args)})
    if result.get("success"):
        result["remote"] = remote
        result["branch"] = branch
    return result


@task(name="auto_commit_and_push", cache_policy=None)
async def auto_commit_and_push(
    session: ClientSession,
    commit_message: str,
    author: str | None = None,
    tables: list | None = None,
    remote: str = "origin",
    branch: str = "main",
) -> Dict[str, Any]:
    """Automated Dolt workflow: status -> add -> commit -> push"""
    logger = get_run_logger()

    import json

    auto_args = {"commit_message": commit_message}
    if author:
        auto_args["author"] = author
    if tables:
        auto_args["tables"] = tables
    if remote != "origin":
        auto_args["remote_name"] = remote
    if branch != "main":
        auto_args["branch"] = branch

    logger.info(f"Running automated Dolt workflow: '{commit_message}'")

    result = await call_mcp_tool_with_session(
        session, "DoltAutoCommitAndPush", {"input": json.dumps(auto_args)}
    )
    if result.get("success"):
        result.update(
            {
                "commit_message": commit_message,
                "author": author,
                "tables": tables,
                "remote": remote,
                "branch": branch,
            }
        )
    return result


@flow(name="dolt_ops_flow", log_prints=True)
async def dolt_ops_flow(
    operation: str = "status",
    commit_message: str | None = None,
    author: str | None = None,
    tables: list | None = None,
    remote: str = "origin",
    branch: str = "main",
) -> Dict[str, Any]:
    """
    Dolt Operations Flow with Persistent Session

    Demonstrates version control operations using MCP with persistent session:

    Operations:
    - "status": Check repository status
    - "add": Stage changes
    - "commit": Commit changes (requires commit_message)
    - "push": Push to remote
    - "auto": Full workflow - add, commit, push (requires commit_message)
    - "outro": Call shared outro helper

    Parameters:
    - operation: Which Dolt operation to perform
    - commit_message: Required for "commit" and "auto" operations
    - author: Optional author for commits
    - tables: Optional list of specific tables to operate on
    - remote: Remote name for push operations (default: "origin")
    - branch: Branch name for push operations (default: "main")

    Uses stdio transport to spawn MCP server process directly.
    This follows the proven working pattern for reliable deployment.
    """
    logger = get_run_logger()
    logger.info(f"🚀 Starting Dolt operation: {operation}")

    try:
        # Single session for entire flow - this is the key DRY improvement
        logger.info("🔄 Entering MCP session context...")
        async with mcp_session() as session:
            logger.info("📡 MCP session established - using throughout flow")
            logger.info(f"   Session object: {session}")
            logger.info(f"   Session ID: {id(session)}")

            # Execute the requested operation using shared session
            if operation == "status":
                result = await check_dolt_status(session)

            elif operation == "add":
                result = await stage_dolt_changes(session, tables=tables)

            elif operation == "commit":
                if not commit_message:
                    return {
                        "status": "failed",
                        "error": "commit_message required for commit operation",
                    }
                result = await commit_dolt_changes(
                    session, commit_message=commit_message, author=author
                )

            elif operation == "push":
                result = await push_dolt_changes(session, remote=remote, branch=branch)

            elif operation == "auto":
                if not commit_message:
                    return {
                        "status": "failed",
                        "error": "commit_message required for auto operation",
                    }
                result = await auto_commit_and_push(
                    session,
                    commit_message=commit_message,
                    author=author,
                    tables=tables,
                    remote=remote,
                    branch=branch,
                )

            elif operation == "outro":
                from utils.mcp_outro import automated_dolt_outro

                outro_result = await automated_dolt_outro(session, flow_context="manual outro call")
                result = {
                    "success": True,
                    "tool_name": "automated_dolt_outro",
                    "result": type("MockResult", (), {"content": outro_result})(),
                    "commit_message": outro_result.get("commit_message"),
                    "push_result": outro_result.get("push_result"),
                }

            else:
                return {"status": "failed", "error": f"Unknown operation: {operation}"}

            if result.get("success"):
                logger.info(f"✅ Dolt operation '{operation}' completed successfully")

                # Only convert to JSON at API boundary (here in flow return)
                return {
                    "status": "success",
                    "operation": operation,
                    "result": {
                        "success": result.get("success"),
                        "tool_name": result.get("tool_name"),
                        "content": result["result"].content if result.get("result") else None,
                        **{
                            k: v
                            for k, v in result.items()
                            if k not in ["result", "success", "tool_name"]
                        },
                    },
                }
            else:
                logger.error(f"❌ Dolt operation '{operation}' failed: {result.get('error')}")
                return {"status": "failed", "operation": operation, "error": result.get("error")}

    except MCPConnectionError as e:
        logger.error(f"❌ MCP connection error: {e}")
        return {"status": "failed", "error": str(e)}
    except Exception as e:
        logger.error(f"❌ Dolt operations flow failed: {e}")
        return {"status": "failed", "error": str(e)}


if __name__ == "__main__":
    # For direct testing - demonstrates different operations
    print("Testing Dolt operations with persistent MCP session...")
    print("Using stdio transport to spawn MCP server process directly")
    print("This follows the proven working pattern for reliable deployment")

    # Test status check
    result = asyncio.run(dolt_ops_flow(operation="status"))
    print(f"Status check result: {result}")

    # Test auto workflow (will require commit message)
    # result = asyncio.run(dolt_ops_flow(
    #     operation="auto",
    #     commit_message="Test commit from dolt_ops.py",
    #     author="dolt_ops_demo"
    # ))
    # print(f"Auto workflow result: {result}")
