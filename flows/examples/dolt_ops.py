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


@task(name="check_dolt_status")
async def check_dolt_status() -> Dict[str, Any]:
    """Check current Dolt repository status using MCP tools"""
    logger = get_run_logger()

    # Environment-configurable server parameters
    mcp_command = os.getenv("MCP_SERVER_COMMAND", "python")
    mcp_args = os.getenv("MCP_SERVER_ARGS", "-m,services.mcp_server.app.mcp_server").split(",")

    logger.info("Checking Dolt repository status")

    try:
        server_params = StdioServerParameters(command=mcp_command, args=mcp_args, env=None)

        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call DoltStatus tool
                result = await session.call_tool("DoltStatus", {})

                logger.info("Dolt status checked successfully")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"   Status: {result.content}")

                return {"success": True, "status_result": result.content, "tool_used": "DoltStatus"}

    except Exception as e:
        logger.error(f"Dolt status check failed: {e}")
        return {"success": False, "error": str(e), "tool_used": "DoltStatus"}


@task(name="stage_dolt_changes")
async def stage_dolt_changes(tables: list | None = None) -> Dict[str, Any]:
    """Stage Dolt changes using MCP tools"""
    logger = get_run_logger()

    # Environment-configurable server parameters
    mcp_command = os.getenv("MCP_SERVER_COMMAND", "python")
    mcp_args = os.getenv("MCP_SERVER_ARGS", "-m,services.mcp_server.app.mcp_server").split(",")

    add_args = {}
    if tables:
        add_args["tables"] = tables
        logger.info(f"Staging specific tables: {tables}")
    else:
        logger.info("Staging all changes")

    try:
        server_params = StdioServerParameters(command=mcp_command, args=mcp_args, env=None)

        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call DoltAdd tool
                result = await session.call_tool("DoltAdd", add_args)

                logger.info("Changes staged successfully")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"   Add result: {result.content}")

                return {
                    "success": True,
                    "add_result": result.content,
                    "tables_staged": tables or "all",
                    "tool_used": "DoltAdd",
                }

    except Exception as e:
        logger.error(f"Dolt add failed: {e}")
        return {"success": False, "error": str(e), "tool_used": "DoltAdd"}


@task(name="commit_dolt_changes")
async def commit_dolt_changes(commit_message: str, author: str | None = None) -> Dict[str, Any]:
    """Commit Dolt changes using MCP tools"""
    logger = get_run_logger()

    # Environment-configurable server parameters
    mcp_command = os.getenv("MCP_SERVER_COMMAND", "python")
    mcp_args = os.getenv("MCP_SERVER_ARGS", "-m,services.mcp_server.app.mcp_server").split(",")

    commit_args = {"commit_message": commit_message}
    if author:
        commit_args["author"] = author

    logger.info(f"Committing changes: '{commit_message}'")

    try:
        server_params = StdioServerParameters(command=mcp_command, args=mcp_args, env=None)

        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call DoltCommit tool
                result = await session.call_tool("DoltCommit", commit_args)

                logger.info("Changes committed successfully")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"   Commit result: {result.content}")

                return {
                    "success": True,
                    "commit_result": result.content,
                    "commit_message": commit_message,
                    "author": author,
                    "tool_used": "DoltCommit",
                }

    except Exception as e:
        logger.error(f"Dolt commit failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "commit_message": commit_message,
            "tool_used": "DoltCommit",
        }


@task(name="push_dolt_changes")
async def push_dolt_changes(remote: str = "origin", branch: str = "main") -> Dict[str, Any]:
    """Push Dolt changes using MCP tools"""
    logger = get_run_logger()

    # Environment-configurable server parameters
    mcp_command = os.getenv("MCP_SERVER_COMMAND", "python")
    mcp_args = os.getenv("MCP_SERVER_ARGS", "-m,services.mcp_server.app.mcp_server").split(",")

    push_args = {"remote_name": remote, "branch": branch}

    logger.info(f"Pushing to {remote}/{branch}")

    try:
        server_params = StdioServerParameters(command=mcp_command, args=mcp_args, env=None)

        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call DoltPush tool
                result = await session.call_tool("DoltPush", push_args)

                logger.info("Changes pushed successfully")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"   Push result: {result.content}")

                return {
                    "success": True,
                    "push_result": result.content,
                    "remote": remote,
                    "branch": branch,
                    "tool_used": "DoltPush",
                }

    except Exception as e:
        logger.error(f"Dolt push failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "remote": remote,
            "branch": branch,
            "tool_used": "DoltPush",
        }


@task(name="auto_commit_and_push")
async def auto_commit_and_push(
    commit_message: str,
    author: str | None = None,
    tables: list | None = None,
    remote: str = "origin",
    branch: str = "main",
) -> Dict[str, Any]:
    """Automated Dolt workflow: status -> add -> commit -> push"""
    logger = get_run_logger()

    # Environment-configurable server parameters
    mcp_command = os.getenv("MCP_SERVER_COMMAND", "python")
    mcp_args = os.getenv("MCP_SERVER_ARGS", "-m,services.mcp_server.app.mcp_server").split(",")

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

    try:
        server_params = StdioServerParameters(command=mcp_command, args=mcp_args, env=None)

        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call DoltAutoCommitAndPush tool
                result = await session.call_tool("DoltAutoCommitAndPush", auto_args)

                logger.info("Automated Dolt workflow completed successfully")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"   Workflow result: {result.content}")

                return {
                    "success": True,
                    "workflow_result": result.content,
                    "commit_message": commit_message,
                    "author": author,
                    "tables": tables,
                    "remote": remote,
                    "branch": branch,
                    "tool_used": "DoltAutoCommitAndPush",
                }

    except Exception as e:
        logger.error(f"Automated Dolt workflow failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "commit_message": commit_message,
            "tool_used": "DoltAutoCommitAndPush",
        }


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
    - MCP_SERVER_COMMAND: Command to run MCP server (default: "python")
    - MCP_SERVER_ARGS: Comma-separated args (default: "-m,services.mcp_server.app.mcp_server")
    """
    logger = get_run_logger()
    logger.info(f"Starting Dolt operation: {operation}")

    try:
        if operation == "status":
            result = await check_dolt_status()

        elif operation == "add":
            result = await stage_dolt_changes(tables=tables)

        elif operation == "commit":
            if not commit_message:
                return {"status": "failed", "error": "commit_message required for commit operation"}
            result = await commit_dolt_changes(commit_message=commit_message, author=author)

        elif operation == "push":
            result = await push_dolt_changes(remote=remote, branch=branch)

        elif operation == "auto":
            if not commit_message:
                return {"status": "failed", "error": "commit_message required for auto operation"}
            result = await auto_commit_and_push(
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
