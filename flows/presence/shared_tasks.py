#!/usr/bin/env python3
"""
Shared Tasks for Cogni Prefect Flows
====================================

Common task functions used across multiple presence flows to eliminate code duplication.
All flows use the same MCP setup pattern, so this centralizes that logic.
"""

import sys
from pathlib import Path
import os
import logging
from typing import Any, Dict

# Ensure proper Python path for container environment
current_dir = Path(__file__).parent
workspace_root = current_dir.parent.parent  # Go up two levels: flows/presence -> flows -> workspace
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

from prefect import task  # noqa: E402
from prefect.logging import get_run_logger  # noqa: E402

# AutoGen MCP Integration - Using PROVEN working pattern
from autogen_ext.tools.mcp import StdioServerParams, mcp_server_tools  # noqa: E402

# Dolt integration for work item context
from infra_core.memory_system.dolt_reader import DoltMySQLReader  # noqa: E402
from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig  # noqa: E402

# Prompt template integration
from infra_core.prompt_templates import PromptTemplateManager  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO)


@task(name="setup_cogni_mcp_connection")
async def setup_cogni_mcp_connection(
    branch: str = None, namespace: str = None, read_timeout_seconds: int = 30
) -> Dict[str, Any]:
    """
    Setup Cogni MCP connection and generate tool specifications for agents

    This is the shared task that replaces all the duplicate setup_simple_mcp_connection
    functions across the different flows.

    Args:
        branch: Dolt branch to use (defaults to MCP_DOLT_BRANCH env var or 'main')
        namespace: Namespace to use (defaults to MCP_DOLT_NAMESPACE env var or 'legacy')
        read_timeout_seconds: Timeout for MCP server communication (default: 30)

    Returns:
        Dict containing:
        - success: Whether the setup was successful
        - tools_count: Number of tools discovered
        - tools: List of MCP tool objects
        - tool_names: List of tool names
        - tool_specs: Generated tool specifications text for agent prompts
        - error: Error message if setup failed
    """
    logger = get_run_logger()

    try:
        # CRITICAL: Use container-aware path resolution
        # In container: /workspace/services/mcp_server/app/mcp_server.py
        cogni_mcp_path = Path("/workspace/services/mcp_server/app/mcp_server.py")

        if not cogni_mcp_path.exists():
            logger.error(f"❌ Cogni MCP server not found at: {cogni_mcp_path}")
            return {"success": False, "error": "MCP server file not found"}

        logger.info(f"🔧 Using MCP server at: {cogni_mcp_path}")

        # Use provided parameters or fall back to environment variables or defaults
        mcp_branch = branch or os.environ.get("MCP_DOLT_BRANCH", "main")
        mcp_namespace = namespace or os.environ.get("MCP_DOLT_NAMESPACE", "legacy")

        logger.info(f"🎯 MCP Configuration - Branch: '{mcp_branch}', Namespace: '{mcp_namespace}'")

        # StdioServerParams for Cogni MCP server - PROVEN working config
        server_params = StdioServerParams(
            command="python",
            args=[str(cogni_mcp_path)],
            env={
                # Python path fix for container - CRITICAL
                "PYTHONPATH": "/workspace",  # Add workspace to Python path
                # Dolt connection config
                "DOLT_HOST": "dolt-db",  # Container network hostname
                "DOLT_PORT": "3306",
                "DOLT_USER": "root",
                "DOLT_ROOT_PASSWORD": "kXMnM6firYohXzK+2r0E0DmSjOl6g3A2SmXc6ALDOlA=",
                "DOLT_DATABASE": "cogni-dao-memory",
                "MYSQL_DATABASE": "cogni-dao-memory",
                "DOLT_BRANCH": mcp_branch,  # Configurable branch
                "DOLT_NAMESPACE": mcp_namespace,  # Configurable namespace
                "CHROMA_PATH": "/tmp/chroma",
                "CHROMA_COLLECTION_NAME": "cogni_mcp_collection",
            },
            read_timeout_seconds=read_timeout_seconds,
        )

        logger.info("🔧 Setting up Cogni MCP tools via stdio...")
        cogni_tools = await mcp_server_tools(server_params)

        logger.info(f"✅ Cogni MCP tools setup complete: {len(cogni_tools)} tools")
        logger.info(f"🔧 Available tools: {[tool.name for tool in cogni_tools]}")

        # Generate tool specifications using template manager
        template_manager = PromptTemplateManager()
        tool_specs_text = template_manager.generate_tool_specs_from_mcp_tools(cogni_tools)

        logger.info(f"📋 Generated tool specs: {len(cogni_tools)} tools documented")

        return {
            "success": True,
            "tools_count": len(cogni_tools),
            "tools": cogni_tools,
            "tool_names": [tool.name for tool in cogni_tools],
            "tool_specs": tool_specs_text,
        }

    except Exception as e:
        logger.error(f"❌ Failed to setup Cogni MCP tools: {e}")
        return {"success": False, "error": str(e)}


@task(name="read_work_items_context")
async def read_work_items_context(branch: str = "main", limit: int = 10) -> Dict[str, Any]:
    """
    Read current work items using DoltMySQLReader for agent context

    This is the shared task that replaces the duplicate read_current_work_items
    functions across the different flows.

    Args:
        branch: Dolt branch to read from (default: "main")
        limit: Maximum number of work items to read (default: 10)

    Returns:
        Dict containing:
        - success: Whether the read was successful
        - work_items: List of work item records
        - work_items_summary: Formatted summary text for agent prompts
        - count: Number of work items found
        - error: Error message if read failed
    """
    logger = get_run_logger()

    try:
        # Setup Dolt connection
        config = DoltConnectionConfig()
        reader = DoltMySQLReader(config)

        logger.info(
            f"🔍 Reading work items from work_items_core view (branch: {branch}, limit: {limit})..."
        )

        # Read work items from specified branch
        work_items = reader.read_work_items_core_view(limit=limit, branch=branch)

        if work_items:
            logger.info(f"✅ Found {len(work_items)} work items for agent context")

            # Create summary for agent prompts
            summary_lines = ["## Current Work Items Context:"]
            for item in work_items:
                item_line = f"- {item['work_item_type'].upper()}: {item['id']} | {item['state']} | by {item['created_by']} | {item['created_at']}"
                summary_lines.append(item_line)

            work_items_summary = "\n".join(summary_lines)

            return {
                "success": True,
                "work_items": work_items,
                "work_items_summary": work_items_summary,
                "count": len(work_items),
            }
        else:
            logger.info("📝 No work items found in work_items_core view")
            return {
                "success": True,
                "work_items": [],
                "work_items_summary": "## Current Work Items Context:\n- No active work items found in the system.",
                "count": 0,
            }

    except Exception as e:
        logger.error(f"❌ Failed to read work items: {e}")
        return {
            "success": False,
            "error": str(e),
            "work_items_summary": "## Current Work Items Context:\n- Error reading work items from database.",
            "count": 0,
        }
