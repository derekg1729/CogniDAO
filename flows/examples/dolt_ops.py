#!/usr/bin/env python3
"""
Dolt Operations - MCP-Based Version Control Demo
================================================

Demonstrates Dolt workflow automation using MCP tools:
1. Check Dolt status
2. Stage changes
3. Commit with meaningful messages
4. Push to remote

This focuses purely on version control operations via MCP.
Updated to use the proven working MCP pattern from shared_tasks.py
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict

from prefect import flow, task
from prefect.logging import get_run_logger

# Ensure proper Python path for container environment
current_dir = Path(__file__).parent
workspace_root = current_dir.parent.parent  # Go up two levels: flows/examples -> flows -> workspace
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

# Import proven working MCP setup from shared_tasks
from flows.presence.shared_tasks import setup_cogni_mcp_connection  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO)


@task(name="call_mcp_tool")
async def call_mcp_tool(
    tool_name: str, tool_args: Dict[str, Any], mcp_tools: list
) -> Dict[str, Any]:
    """Call a specific MCP tool with given arguments using AutoGen tool interface"""
    logger = get_run_logger()

    try:
        # Find the tool by name
        target_tool = None
        for tool in mcp_tools:
            if tool.name == tool_name:
                target_tool = tool
                break

        if not target_tool:
            return {"success": False, "error": f"Tool '{tool_name}' not found"}

        logger.info(f"📞 Calling MCP tool: {tool_name}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"   Arguments: {tool_args}")

        # Import CancellationToken for AutoGen tool calling
        from autogen_core import CancellationToken

        # Call the tool using AutoGen's run_json method
        cancellation_token = CancellationToken()

        # MCP tools expect input as a JSON string wrapped in an 'input' key
        import json

        tool_input = {"input": json.dumps(tool_args)}

        result = await target_tool.run_json(tool_input, cancellation_token)

        # Extract result content using the tool's method
        result_content = target_tool.return_value_as_string(result)

        logger.info(f"✅ Tool '{tool_name}' executed successfully")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"   Result: {result_content}")

        return {
            "success": True,
            "result": result_content,
            "tool_used": tool_name,
        }

    except Exception as e:
        logger.error(f"❌ Tool '{tool_name}' failed: {e}")
        return {"success": False, "error": str(e), "tool_used": tool_name}


@task(name="check_dolt_status")
async def check_dolt_status(mcp_tools: list) -> Dict[str, Any]:
    """Check current Dolt repository status using MCP tools"""
    logger = get_run_logger()
    logger.info("Checking Dolt repository status")

    result = await call_mcp_tool("DoltStatus", {}, mcp_tools)
    return result


@task(name="stage_dolt_changes")
async def stage_dolt_changes(mcp_tools: list, tables: list | None = None) -> Dict[str, Any]:
    """Stage Dolt changes using MCP tools"""
    logger = get_run_logger()

    add_args = {}
    if tables:
        add_args["tables"] = tables
        logger.info(f"Staging specific tables: {tables}")
    else:
        logger.info("Staging all changes")

    result = await call_mcp_tool("DoltAdd", add_args, mcp_tools)
    if result.get("success"):
        result["tables_staged"] = tables or "all"
    return result


@task(name="commit_dolt_changes")
async def commit_dolt_changes(
    mcp_tools: list, commit_message: str, author: str | None = None
) -> Dict[str, Any]:
    """Commit Dolt changes using MCP tools"""
    logger = get_run_logger()

    commit_args = {"commit_message": commit_message}
    if author:
        commit_args["author"] = author

    logger.info(f"Committing changes: '{commit_message}'")

    result = await call_mcp_tool("DoltCommit", commit_args, mcp_tools)
    if result.get("success"):
        result["commit_message"] = commit_message
        result["author"] = author
    return result


@task(name="push_dolt_changes")
async def push_dolt_changes(
    mcp_tools: list, remote: str = "origin", branch: str = "main"
) -> Dict[str, Any]:
    """Push Dolt changes using MCP tools"""
    logger = get_run_logger()

    push_args = {"remote_name": remote, "branch": branch}
    logger.info(f"Pushing to {remote}/{branch}")

    result = await call_mcp_tool("DoltPush", push_args, mcp_tools)
    if result.get("success"):
        result["remote"] = remote
        result["branch"] = branch
    return result


@task(name="auto_commit_and_push")
async def auto_commit_and_push(
    mcp_tools: list,
    commit_message: str,
    author: str | None = None,
    tables: list | None = None,
    remote: str = "origin",
    branch: str = "main",
) -> Dict[str, Any]:
    """Automated Dolt workflow: status -> add -> commit -> push"""
    logger = get_run_logger()

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

    result = await call_mcp_tool("DoltAutoCommitAndPush", auto_args, mcp_tools)
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
    Dolt Operations Flow

    Demonstrates version control operations using MCP tools:

    Operations:
    - "status": Check repository status
    - "add": Stage changes
    - "commit": Commit changes (requires commit_message)
    - "push": Push to remote
    - "auto": Full workflow - add, commit, push (requires commit_message)

    Parameters:
    - operation: Which Dolt operation to perform
    - commit_message: Required for "commit" and "auto" operations
    - author: Optional author for commits
    - tables: Optional list of specific tables to operate on
    - remote: Remote name for push operations (default: "origin")
    - branch: Branch name for push operations (default: "main")

    Environment Variables:
    - MCP_DOLT_BRANCH: Dolt branch to use (default: "main")
    - MCP_DOLT_NAMESPACE: Namespace to use (default: "legacy")
    """
    logger = get_run_logger()
    logger.info(f"Starting Dolt operation: {operation}")

    try:
        # Step 1: Setup MCP connection using proven working pattern
        logger.info("🔧 Setting up MCP connection...")
        mcp_setup = await setup_cogni_mcp_connection()

        if not mcp_setup.get("success"):
            logger.error(f"❌ MCP setup failed: {mcp_setup.get('error')}")
            return {"status": "failed", "error": mcp_setup.get("error")}

        logger.info(f"✅ MCP setup successful: {mcp_setup['tools_count']} tools available")
        mcp_tools = mcp_setup["tools"]

        # Step 2: Execute the requested operation
        if operation == "status":
            result = await check_dolt_status(mcp_tools)

        elif operation == "add":
            result = await stage_dolt_changes(mcp_tools, tables=tables)

        elif operation == "commit":
            if not commit_message:
                return {"status": "failed", "error": "commit_message required for commit operation"}
            result = await commit_dolt_changes(
                mcp_tools, commit_message=commit_message, author=author
            )

        elif operation == "push":
            result = await push_dolt_changes(mcp_tools, remote=remote, branch=branch)

        elif operation == "auto":
            if not commit_message:
                return {"status": "failed", "error": "commit_message required for auto operation"}
            result = await auto_commit_and_push(
                mcp_tools,
                commit_message=commit_message,
                author=author,
                tables=tables,
                remote=remote,
                branch=branch,
            )

        else:
            return {"status": "failed", "error": f"Unknown operation: {operation}"}

        if result.get("success"):
            logger.info(f"Dolt operation '{operation}' completed successfully")
            return {"status": "success", "operation": operation, "result": result}
        else:
            logger.error(f"Dolt operation '{operation}' failed: {result.get('error')}")
            return {"status": "failed", "operation": operation, "error": result.get("error")}

    except Exception as e:
        logger.error(f"Dolt operations flow failed: {e}")
        return {"status": "failed", "error": str(e)}


if __name__ == "__main__":
    # For direct testing - demonstrates different operations
    print("Testing Dolt operations...")

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
