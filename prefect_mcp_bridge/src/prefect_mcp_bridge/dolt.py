"""
Dolt operations as Prefect tasks using MCP HTTP endpoints
"""

from prefect import task
from typing import Dict, Any, Optional, Sequence
from .client import MCPClient


@task(name="dolt_add")
def dolt_add_task(
    tables: Optional[Sequence[str]] = None, mcp_client: Optional[MCPClient] = None
) -> Dict[str, Any]:
    """
    Prefect task wrapper for dolt.add MCP endpoint

    Args:
        tables: Optional sequence of specific tables to add (defaults to all changes)
        mcp_client: Optional MCPClient instance (creates new one if not provided)

    Returns:
        MCP response containing add operation results
    """
    client = mcp_client or MCPClient()

    payload = {}
    if tables:
        payload["tables"] = list(tables)

    try:
        result = client.call("dolt.add", payload)
        return result
    except Exception as e:
        raise Exception(f"Dolt add operation failed: {e}") from e


@task(name="dolt_commit")
def dolt_commit_task(
    message: str,
    branch: Optional[str] = None,
    author: Optional[str] = None,
    tables: Optional[Sequence[str]] = None,
    mcp_client: Optional[MCPClient] = None,
) -> Dict[str, Any]:
    """
    Prefect task wrapper for dolt.commit MCP endpoint

    Args:
        message: Commit message (required)
        branch: Branch to commit to (optional, uses current branch if not specified)
        author: Author attribution for the commit
        tables: Optional sequence of specific tables to commit
        mcp_client: Optional MCPClient instance (creates new one if not provided)

    Returns:
        MCP response containing commit hash and operation results
    """
    client = mcp_client or MCPClient()

    payload = {"commit_message": message}

    if branch:
        payload["branch"] = branch
    if author:
        payload["author"] = author
    if tables:
        payload["tables"] = list(tables)

    try:
        result = client.call("dolt.commit", payload)
        return result
    except Exception as e:
        raise Exception(f"Dolt commit operation failed: {e}") from e


@task(name="dolt_push")
def dolt_push_task(
    branch: Optional[str] = None,
    remote_name: Optional[str] = "origin",
    force: bool = False,
    mcp_client: Optional[MCPClient] = None,
) -> Dict[str, Any]:
    """
    Prefect task wrapper for dolt.push MCP endpoint

    Args:
        branch: Branch to push (optional, uses current branch if not specified)
        remote_name: Name of remote to push to (defaults to 'origin')
        force: Whether to force push
        mcp_client: Optional MCPClient instance (creates new one if not provided)

    Returns:
        MCP response containing push operation results
    """
    client = mcp_client or MCPClient()

    payload = {"remote_name": remote_name, "force": force}

    if branch:
        payload["branch"] = branch

    try:
        result = client.call("dolt.push", payload)
        return result
    except Exception as e:
        raise Exception(f"Dolt push operation failed: {e}") from e


def dolt_add_commit_push_task(
    message: str,
    branch: Optional[str] = None,
    author: Optional[str] = None,
    tables: Optional[Sequence[str]] = None,
    remote_name: Optional[str] = "origin",
    force_push: bool = False,
    mcp_client: Optional[MCPClient] = None,
) -> Dict[str, Any]:
    """
    Convenience function that performs add -> commit -> push in sequence

    Args:
        message: Commit message (required)
        branch: Branch to work with (optional, uses current branch)
        author: Author attribution for the commit
        tables: Optional sequence of specific tables to process
        remote_name: Name of remote to push to (defaults to 'origin')
        force_push: Whether to force push
        mcp_client: Optional MCPClient instance (creates new one if not provided)

    Returns:
        Dict containing results from all three operations
    """
    client = mcp_client or MCPClient()

    try:
        add_result = dolt_add_task(tables=tables, mcp_client=client)

        commit_result = dolt_commit_task(
            message=message, branch=branch, author=author, tables=tables, mcp_client=client
        )

        push_result = dolt_push_task(
            branch=branch, remote_name=remote_name, force=force_push, mcp_client=client
        )

        return {"add": add_result, "commit": commit_result, "push": push_result, "success": True}

    except Exception as e:
        return {"error": str(e), "success": False}
