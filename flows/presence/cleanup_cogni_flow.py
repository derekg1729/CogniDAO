#!/usr/bin/env python3
"""
Cleanup Cogni Flow for Prefect Container
========================================

Cleanup-focused Prefect flow that uses our PROVEN working MCP integration.
Based on simple_working_flow.py that achieved 21/21 tools discovery.

Goal: 2 agents focused on system cleanup - identify test artifacts for deletion and migrate legacy blocks to proper namespaces.
Enhanced with bulk operations for efficient cleanup.
"""

import sys
from pathlib import Path

# Ensure proper Python path for container environment
# In container: working dir is /workspace/flows/presence, but infra_core is at /workspace/infra_core
current_dir = Path(__file__).parent
workspace_root = current_dir.parent.parent  # Go up two levels: flows/presence -> flows -> workspace
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

import asyncio  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
from datetime import datetime  # noqa: E402
from typing import Any, Dict  # noqa: E402

from prefect import flow, task  # noqa: E402
from prefect.logging import get_run_logger  # noqa: E402

# AutoGen MCP Integration - Using PROVEN working pattern
from autogen_agentchat.agents import AssistantAgent  # noqa: E402
from autogen_agentchat.teams import RoundRobinGroupChat  # noqa: E402
from autogen_agentchat.conditions import MaxMessageTermination  # noqa: E402
from autogen_agentchat.ui import Console  # noqa: E402
from autogen_ext.models.openai import OpenAIChatCompletionClient  # noqa: E402
from autogen_ext.tools.mcp import StdioServerParams, mcp_server_tools  # noqa: E402

# Dolt integration for work item context
from infra_core.memory_system.dolt_reader import DoltMySQLReader  # noqa: E402
from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig  # noqa: E402

# Prompt template integration
from infra_core.prompt_templates import PromptTemplateManager  # noqa: E402
from infra_core.prompt_templates import render_test_artifact_detector_prompt  # noqa: E402
from infra_core.prompt_templates import render_namespace_migrator_prompt  # noqa: E402
from infra_core.prompt_templates import render_dolt_commit_agent_prompt  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO)

# Cleanup Configuration
MCP_DOLT_BRANCH = "feat/cleanup"
MCP_DOLT_NAMESPACE = "legacy"


@task(name="read_current_work_items")
async def read_current_work_items() -> Dict[str, Any]:
    """Read current work items using DoltMySQLReader for agent context"""
    logger = get_run_logger()

    try:
        # Setup Dolt connection
        config = DoltConnectionConfig()
        reader = DoltMySQLReader(config)

        logger.info("🔍 Reading current work items from work_items_core view...")

        # Read latest work items (limit 10 for context)
        work_items = reader.read_work_items_core_view(limit=10, branch="feat/cleanup")

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


@task(name="setup_simple_mcp_connection")
async def setup_simple_mcp_connection(branch: str = None, namespace: str = None) -> Dict[str, Any]:
    """Setup MCP connection and generate tool specifications for agents

    Args:
        branch: Dolt branch to use (defaults to MCP_DOLT_BRANCH env var or 'ai-education-team')
        namespace: Namespace to use (defaults to MCP_DOLT_NAMESPACE env var or 'legacy')
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

        # StdioServerParams for Cogni MCP server - PROVEN working config
        # Use provided parameters or fall back to environment variables or defaults
        mcp_branch = branch or os.environ.get("MCP_DOLT_BRANCH", "ai-education-team")
        mcp_namespace = namespace or os.environ.get("MCP_DOLT_NAMESPACE", "legacy")

        logger.info(f"🎯 MCP Configuration - Branch: '{mcp_branch}', Namespace: '{mcp_namespace}'")

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
            read_timeout_seconds=30,
        )

        logger.info("🔧 Setting up Cogni MCP tools via stdio...")
        cogni_tools = await mcp_server_tools(server_params)

        logger.info(f"✅ Cogni MCP tools setup complete: {len(cogni_tools)} tools")
        logger.info(f"🔧 Available tools: {[tool.name for tool in cogni_tools]}")

        # 🔧 NEW: Generate tool specifications using template manager
        template_manager = PromptTemplateManager()
        tool_specs_text = template_manager.generate_tool_specs_from_mcp_tools(cogni_tools)

        logger.info(f"📋 Generated tool specs: {len(cogni_tools)} tools documented")

        return {
            "success": True,
            "tools_count": len(cogni_tools),
            "tools": cogni_tools,
            "tool_names": [tool.name for tool in cogni_tools],
            "tool_specs": tool_specs_text,  # NEW: Tool specifications for agents
        }

    except Exception as e:
        logger.error(f"❌ Failed to setup Cogni MCP tools: {e}")
        return {"success": False, "error": str(e)}


@task(name="run_cleanup_team_with_outro")
async def run_cleanup_team_with_outro(
    mcp_setup: Dict[str, Any], work_items_context: Dict[str, Any]
) -> Dict[str, Any]:
    """Run 2 cleanup agents to identify test artifacts and migrate legacy blocks - All in one simple task using proven working pattern"""
    logger = get_run_logger()

    if not mcp_setup.get("success"):
        return {"success": False, "error": "MCP setup failed"}

    try:
        # Setup OpenAI client - Helicone observability handled automatically by sitecustomize.py
        model_client = OpenAIChatCompletionClient(model="gpt-4o")
        logger.info("✅ OpenAI client configured")

        cogni_tools = mcp_setup["tools"]
        tool_specs_text = mcp_setup.get(
            "tool_specs", "## Available MCP Tools: (tool specs not available)"
        )

        # Get work items context for agent prompts
        work_items_summary = work_items_context.get(
            "work_items_summary", "## Current Work Items Context:\\n- No context available."
        )

        # Create 2 cleanup agents with system cleanup focus AND tool specifications
        agents = []

        # Agent 1: Test Artifact Detector - Finds and deletes test artifacts
        test_detector = AssistantAgent(
            name="test_artifact_detector",
            model_client=model_client,
            tools=cogni_tools,
            system_message=render_test_artifact_detector_prompt(
                tool_specs_text, work_items_summary
            ),
        )
        agents.append(test_detector)

        # Agent 2: Namespace Migrator - Moves legacy blocks to proper namespaces
        namespace_migrator = AssistantAgent(
            name="namespace_migrator",
            model_client=model_client,
            tools=cogni_tools,
            system_message=render_namespace_migrator_prompt(tool_specs_text, work_items_summary),
        )
        agents.append(namespace_migrator)

        # Create simple team
        team = RoundRobinGroupChat(
            participants=agents,
            termination_condition=MaxMessageTermination(max_messages=6),  # 3 rounds each
        )

        logger.info("🚀 Starting 2-agent cleanup team...")

        # Cleanup Team task with system cleanup focus
        cleanup_task = """Please work together as the Cogni Cleanup Team to organize and clean up the memory system:

## CLEANUP GOALS:

1) **TEST ARTIFACT DETECTOR**: Find and delete blocks created during testing
   - Look for "test" tags, test agent creators, obvious test content
   - Use QueryMemoryBlocksSemantic to search for test-related content
   - Use BulkDeleteBlocks for efficient cleanup (max 10 at a time for safety)
   - Report what was removed

2) **NAMESPACE MIGRATOR**: Move all legacy blocks to proper namespaces
   - AI/Education content → "ai-education" namespace  
   - Work items & project management → "cogni-project-management" namespace
   - Use GetMemoryBlock with namespace_id="legacy" to find legacy blocks
   - Use BulkUpdateNamespace for efficient migration (max 20 at a time)
   - Report migration statistics

## SUCCESS CRITERIA:
- All test artifacts identified and removed
- Legacy namespace cleaned out (minimal remaining blocks)
- Blocks properly categorized in appropriate namespaces
- Clear summary of cleanup actions taken

## SAFETY RULES:
- NEVER delete blocks with "keep" tag
- When in doubt about deletion, preserve the block
- Use bulk operations efficiently but safely
- Process in manageable batches

Work systematically and report your progress!"""

        # Run the cleanup team
        await Console(team.run_stream(task=cleanup_task))

        logger.info("✅ Cleanup team analysis completed successfully!")

        # === OUTRO ROUTINE: Dolt Operations (Simplified) ===
        logger.info("🔄 Starting outro routine: Systematic Dolt operations...")

        # Create dedicated Dolt commit agent using the same MCP connection
        # Note: Using the same model_client instance ensures Helicone observability for all agents
        dolt_commit_agent = AssistantAgent(
            name="dolt_commit_agent",
            model_client=model_client,
            tools=cogni_tools,
            system_message=render_dolt_commit_agent_prompt(tool_specs_text),
        )

        # Create simple team for Dolt operations
        dolt_team = RoundRobinGroupChat(
            participants=[dolt_commit_agent],
            termination_condition=MaxMessageTermination(max_messages=5),
        )

        logger.info("🚀 Starting Dolt commit operations...")

        # Run Dolt operations
        await Console(dolt_team.run_stream(task="Begin the dolt commit and push process."))

        logger.info("✅ Outro routine completed successfully!")

        return {
            "success": True,
            "agents_count": len(agents),
            "tools_count": len(cogni_tools),
            "work_items_count": work_items_context.get("count", 0),
            "outro_success": True,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Cleanup flow with outro failed: {e}")
        return {"success": False, "error": str(e)}


# Outro routine now integrated into the main task above for simplicity


@flow(name="cleanup_team_flow", log_prints=True)
async def cleanup_team_flow() -> Dict[str, Any]:
    """
    Cleanup Team Flow - System Maintenance and Organization

    Uses proven working AutoGen pattern to run 2 cleanup-focused agents + Dolt operations:
    1. Read current work items context using DoltMySQLReader
    2. Setup MCP connection with proven stdio transport
    3. Run unified cleanup team workflow that includes:
       - **Test Artifact Detector** identifying and removing test artifacts
       - **Namespace Migrator** moving legacy blocks to proper namespaces
       - **Integrated Dolt operations** for automatic persistence

    All using the PROVEN working import pattern with system cleanup focus.
    """
    logger = get_run_logger()
    logger.info("🎯 Starting Cleanup Team Flow for System Maintenance")
    logger.info("🔧 Using PROVEN working stdio MCP transport + System Cleanup Operations")

    # Get branch and namespace configuration for this flow run

    logger.info(
        f"🔧 FLOW CONFIGURATION: Working on Branch='{MCP_DOLT_BRANCH}', Namespace='{MCP_DOLT_NAMESPACE}'"
    )
    logger.info(
        f"🔧 Environment variables: MCP_DOLT_BRANCH={os.environ.get('MCP_DOLT_BRANCH', 'NOT_SET')}, MCP_DOLT_NAMESPACE={os.environ.get('MCP_DOLT_NAMESPACE', 'NOT_SET')}"
    )

    try:
        # Step 1: Read current work items for context
        work_items_context = await read_current_work_items()

        if work_items_context.get("success"):
            logger.info(f"✅ Work items context loaded: {work_items_context.get('count', 0)} items")
        else:
            logger.warning(
                f"⚠️ Work items context failed: {work_items_context.get('error', 'Unknown error')}"
            )
        # Step 2: Setup MCP connection with explicit branch and namespace
        mcp_setup = await setup_simple_mcp_connection(
            branch=MCP_DOLT_BRANCH, namespace=MCP_DOLT_NAMESPACE
        )

        if not mcp_setup.get("success"):
            logger.error(f"❌ MCP setup failed: {mcp_setup.get('error')}")
            return {"status": "failed", "error": mcp_setup.get("error")}

        logger.info(f"✅ MCP setup successful: {mcp_setup['tools_count']} tools available")

        # Step 3: Run cleanup team with integrated outro routine
        summary_result = await run_cleanup_team_with_outro(mcp_setup, work_items_context)

        if not summary_result.get("success"):
            logger.error(f"❌ Agent summary with outro failed: {summary_result.get('error')}")
            return {"status": "failed", "error": summary_result.get("error")}

        logger.info(
            "🤖 Cleanup Team and Cogni Leader have provided strategic insights and Dolt operations completed!"
        )

        # Final success
        logger.info(
            "🎉 FLOW SUCCESS: Cleanup Team flow with Knowledge Graph integration completed!"
        )
        return {
            "status": "success",
            "tools_count": summary_result.get("tools_count", 0),
            "agents_count": summary_result.get("agents_count", 0),
            "work_items_count": summary_result.get("work_items_count", 0),
            "outro_success": summary_result.get("outro_success", False),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Enhanced flow failed: {e}")
        return {"status": "failed", "error": str(e)}
    finally:
        # Ensure the MCP client is disconnected at the end of the flow
        if "mcp_setup" in locals() and mcp_setup.get("client"):
            await mcp_setup["client"].disconnect()


if __name__ == "__main__":
    # For testing the Cleanup Team flow locally
    import asyncio

    asyncio.run(cleanup_team_flow())
