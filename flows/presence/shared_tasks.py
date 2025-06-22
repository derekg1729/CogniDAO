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

# Import additional modules needed for automated outro
import json  # noqa: E402
from autogen_core import CancellationToken  # noqa: E402
from autogen_ext.models.openai import OpenAIChatCompletionClient  # noqa: E402
from autogen_core.models import UserMessage  # noqa: E402

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
        # CRITICAL: Use environment-aware path resolution
        # Try container path first, then fallback to local development path
        cogni_mcp_path = Path("/workspace/services/mcp_server/app/mcp_server.py")

        if not cogni_mcp_path.exists():
            # Fallback to local development path (relative to workspace root)
            cogni_mcp_path = workspace_root / "services" / "mcp_server" / "app" / "mcp_server.py"

        if not cogni_mcp_path.exists():
            logger.error("❌ Cogni MCP server not found at container path or local path")
            logger.error("   Container path: /workspace/services/mcp_server/app/mcp_server.py")
            logger.error(
                f"   Local path: {workspace_root / 'services' / 'mcp_server' / 'app' / 'mcp_server.py'}"
            )
            return {"success": False, "error": "MCP server file not found"}

        logger.info(f"🔧 Using MCP server at: {cogni_mcp_path}")

        # Use provided parameters or fall back to environment variables or defaults
        mcp_branch = branch or os.environ.get("MCP_DOLT_BRANCH", "main")
        mcp_namespace = namespace or os.environ.get("MCP_DOLT_NAMESPACE", "legacy")

        logger.info(f"🎯 MCP Configuration - Branch: '{mcp_branch}', Namespace: '{mcp_namespace}'")

        # StdioServerParams for Cogni MCP server - PROVEN working config
        # Use environment-aware configuration
        server_env = {
            **os.environ,  # Include existing environment
            # Dolt connection config - use env vars with fallbacks
            "DOLT_HOST": os.getenv("DOLT_HOST", "localhost"),
            "DOLT_PORT": os.getenv("DOLT_PORT", "3306"),
            "DOLT_USER": os.getenv("DOLT_USER", "root"),
            "DOLT_ROOT_PASSWORD": os.getenv(
                "DOLT_ROOT_PASSWORD", "kXMnM6firYohXzK+2r0E0DmSjOl6g3A2SmXc6ALDOlA="
            ),
            "DOLT_DATABASE": "cogni-dao-memory",
            "MYSQL_DATABASE": "cogni-dao-memory",
            "DOLT_BRANCH": mcp_branch,  # Configurable branch
            "DOLT_NAMESPACE": mcp_namespace,  # Configurable namespace
            "CHROMA_PATH": os.getenv("CHROMA_PATH", "/tmp/chroma"),
            "CHROMA_COLLECTION_NAME": "cogni_mcp_collection",
        }

        # Add workspace root to Python path for both container and local
        if str(workspace_root) not in server_env.get("PYTHONPATH", ""):
            existing_pythonpath = server_env.get("PYTHONPATH", "")
            server_env["PYTHONPATH"] = (
                f"{workspace_root}:{existing_pythonpath}"
                if existing_pythonpath
                else str(workspace_root)
            )

        server_params = StdioServerParams(
            command="python",
            args=[str(cogni_mcp_path)],
            env=server_env,
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


@task(name="automated_dolt_outro")
async def automated_dolt_outro(
    mcp_tools: list, model_client: OpenAIChatCompletionClient, flow_context: str = "Flow completed"
) -> Dict[str, Any]:
    """
    Automated Dolt outro routine using direct MCP calls + AI summary generation

    This replaces the duplicate outro code across all flows with a clean, automated approach:
    1. Direct MCP calls to get Dolt status and diff
    2. AI completion to generate concise PR summary
    3. Auto-commit and push with generated message

    Args:
        mcp_tools: List of MCP tool objects from setup_cogni_mcp_connection
        model_client: OpenAI client instance for AI completion
        flow_context: Context description for the commit message (e.g., "AI Education Team flow completed")

    Returns:
        Dict containing:
        - success: Whether the outro was successful
        - commit_message: Generated commit message
        - auto_commit_result: Result from DoltAutoCommitAndPush
        - error: Error message if outro failed
    """
    logger = get_run_logger()
    logger.info("🔄 Starting automated Dolt outro routine...")

    try:
        # Helper function to call MCP tools (inlined from removed duplicate)
        async def call_tool(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
            """Call MCP tool using AutoGen interface"""
            try:
                # Find the tool by name
                target_tool = None
                for tool in mcp_tools:
                    if tool.name == tool_name:
                        target_tool = tool
                        break

                if not target_tool:
                    return {"success": False, "error": f"Tool '{tool_name}' not found"}

                # Call the tool using AutoGen's run_json method
                cancellation_token = CancellationToken()
                tool_input = {"input": json.dumps(tool_args)}
                result = await target_tool.run_json(tool_input, cancellation_token)
                result_content = target_tool.return_value_as_string(result)

                return {"success": True, "result": result_content, "tool_used": tool_name}

            except Exception as e:
                return {"success": False, "error": str(e), "tool_used": tool_name}

        # Step 1: Get Dolt status
        logger.info("📊 Reading Dolt repository status...")
        status_result = await call_tool("DoltStatus", {})

        if not status_result.get("success"):
            logger.warning(f"⚠️ Status check failed: {status_result.get('error')}")
            status_info = "Status unavailable"
        else:
            status_info = status_result.get("result", "No status data")

        # Step 2: Get Dolt diff
        logger.info("📋 Reading staged changes diff...")
        diff_result = await call_tool("DoltDiff", {"mode": "staged"})

        if not diff_result.get("success"):
            logger.warning(f"⚠️ Diff check failed: {diff_result.get('error')}")
            diff_info = "Diff unavailable"
        else:
            diff_info = diff_result.get("result", "No diff data")

        # Step 3: Generate AI summary using direct OpenAI call
        logger.info("🤖 Generating AI commit message summary...")

        summary_prompt = f"""Based on this Dolt repository status and diff, create a concise commit message that summarizes the data changes:

## Repository Status:
{status_info}

## Staged Changes:
{diff_info}

## Flow Context:
{flow_context}

Generate a clear, concise commit message (1-2 sentences) that describes what data was changed or added. Focus on the actual data changes, not the process."""

        try:
            response = await model_client.create(
                [UserMessage(content=summary_prompt, source="user")]
            )

            commit_message = response.content.strip()
            logger.info(f"✅ Generated commit message: {commit_message}")

        except Exception as e:
            logger.warning(f"⚠️ AI summary generation failed: {e}")
            commit_message = f"data: {flow_context} - automated commit"

        # Step 4: Auto-commit and push
        logger.info("🚀 Executing auto-commit and push...")

        auto_result = await call_tool(
            "DoltAutoCommitAndPush",
            {"commit_message": commit_message, "author": "automated-outro"},
        )

        if auto_result.get("success"):
            logger.info("✅ Automated Dolt outro completed successfully!")
            return {
                "success": True,
                "commit_message": commit_message,
                "auto_commit_result": auto_result.get("result"),
                "status_info": status_info,
                "diff_info": diff_info,
            }
        else:
            logger.error(f"❌ Auto-commit failed: {auto_result.get('error')}")
            return {
                "success": False,
                "error": f"Auto-commit failed: {auto_result.get('error')}",
                "commit_message": commit_message,
            }

    except Exception as e:
        logger.error(f"❌ Automated outro failed: {e}")
        return {"success": False, "error": str(e)}
