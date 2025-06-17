#!/usr/bin/env python3
"""
AI Education Team Flow for Prefect Container
============================================

Education-focused Prefect flow that uses our PROVEN working MCP integration.
Based on simple_working_flow.py that achieved 21/21 tools discovery.

Goal: 4 agents focused on AI education - read education knowledge graph, analyze learning needs, and improve educational content.
Enhanced with DoltMySQLReader and root knowledge graph integration.
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
from infra_core.prompt_templates import render_education_researcher_prompt  # noqa: E402
from infra_core.prompt_templates import render_curriculum_analyst_prompt  # noqa: E402
from infra_core.prompt_templates import render_education_reporter_prompt  # noqa: E402
from infra_core.prompt_templates import render_cogni_education_leader_prompt  # noqa: E402
from infra_core.prompt_templates import render_dolt_commit_agent_prompt  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO)

# AI Education Graph Root - GUID for the foundational knowledge block
AI_EDUCATION_ROOT_GUID = "44bff8a7-6518-4514-92f9-49622fc72484"


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
        work_items = reader.read_work_items_core_view(limit=10, branch="ai-education-team")

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
async def setup_simple_mcp_connection() -> Dict[str, Any]:
    """Setup MCP connection and generate tool specifications for agents"""
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
                "DOLT_BRANCH": "ai-education-team",  # Configure AI education team branch
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


@task(name="run_ai_education_team_with_outro")
async def run_ai_education_team_with_outro(
    mcp_setup: Dict[str, Any], work_items_context: Dict[str, Any]
) -> Dict[str, Any]:
    """Run 4 AI education agents to analyze knowledge graph, assess learning needs, and improve educational content - All in one simple task using proven working pattern"""
    logger = get_run_logger()

    if not mcp_setup.get("success"):
        return {"success": False, "error": "MCP setup failed"}

    try:
        # Setup OpenAI client
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

        # Create 4 AI education agents with education focus AND tool specifications
        agents = []

        # Agent 1: Education Knowledge Reader - Starts by reading root knowledge graph
        education_researcher = AssistantAgent(
            name="education_researcher",
            model_client=model_client,
            tools=cogni_tools,
            system_message=render_education_researcher_prompt(tool_specs_text, work_items_summary),
        )
        agents.append(education_researcher)

        # Agent 2: Curriculum Analyst - Analyzes learning patterns and needs
        curriculum_analyst = AssistantAgent(
            name="curriculum_analyst",
            model_client=model_client,
            tools=cogni_tools,
            system_message=render_curriculum_analyst_prompt(tool_specs_text, work_items_summary),
        )
        agents.append(curriculum_analyst)

        # Agent 3: Education Reporter - Documents findings and creates reports
        education_reporter = AssistantAgent(
            name="education_reporter",
            model_client=model_client,
            tools=cogni_tools,
            system_message=render_education_reporter_prompt(tool_specs_text, work_items_summary),
        )
        agents.append(education_reporter)

        # Agent 4: Omnipresent Cogni Leader - Education Strategy Focus
        cogni_leader = AssistantAgent(
            name="cogni_leader",
            model_client=model_client,
            tools=cogni_tools,
            system_message=render_cogni_education_leader_prompt(
                tool_specs_text, work_items_summary
            ),
        )
        agents.append(cogni_leader)

        # Create simple team
        team = RoundRobinGroupChat(
            participants=agents,
            termination_condition=MaxMessageTermination(max_messages=8),  # Increased for 4 agents
        )

        logger.info("🚀 Starting 4-agent work item summary with omnipresent Cogni leader...")

        # AI Education Team task with knowledge graph focus
        education_task = f"""Please work together as the AI Education Team to create a well-organized, linked knowledge graph with small, focused memory blocks:

## MEMORY BLOCK REQUIREMENTS:
- Keep ALL memory blocks SMALL and CONCISE - ONE topic per block
- Use Ultra-concise titles (1-5 words) to represent the block topic
- Use BULK TOOLS to create Blocks and links to created single-topic blocks linked together

## TEAM WORKFLOW:
1) **EDUCATION RESEARCHER**: Start by reading the AI Education Root Knowledge Block ({AI_EDUCATION_ROOT_GUID}) to understand current state. Map existing content to BEGINNER (96adf1d9-d6f7-43d3-9d33-2f4e16a5fa2d) → INTERMEDIATE (5ae04999-1931-4530-8fa8-eaf7929ed83c) → ADVANCED (3ea67d6d-0e57-47e3-92ad-5daa6b1b8e3d) progression.

2) **CURRICULUM ANALYST**: Create small memory blocks for missing BEGINNER (96adf1d9-d6f7-43d3-9d33-2f4e16a5fa2d), INTERMEDIATE (5ae04999-1931-4530-8fa8-eaf7929ed83c), and ADVANCED (3ea67d6d-0e57-47e3-92ad-5daa6b1b8e3d) concepts. Use CreateBlockLink to establish prerequisite relationships (beginner → intermediate → advanced).

3) **EDUCATION REPORTER**: Document findings in small, focused memory blocks. Use BulkCreateLinks to efficiently connect multiple concepts to their learning levels. Link everything back to the education graph root.

4) **COGNI LEADER**: Create learning level blocks ("BEGINNER Level": 96adf1d9-d6f7-43d3-9d33-2f4e16a5fa2d, "INTERMEDIATE Level": 5ae04999-1931-4530-8fa8-eaf7929ed83c, "ADVANCED Level": 3ea67d6d-0e57-47e3-92ad-5daa6b1b8e3d) if they don't exist. Use BulkCreateLinks to connect concepts to their appropriate levels. Create strategic knowledge blocks with your insights.

## LINKING STRATEGY:
- Create "depends_on" links for prerequisite relationships
- Create "related_to" links for complementary concepts  
- Link concepts to their appropriate learning levels (BEGINNER: 96adf1d9-d6f7-43d3-9d33-2f4e16a5fa2d / INTERMEDIATE: 5ae04999-1931-4530-8fa8-eaf7929ed83c / ADVANCED: 3ea67d6d-0e57-47e3-92ad-5daa6b1b8e3d)
- Link all new content back to the education knowledge graph root: {AI_EDUCATION_ROOT_GUID}

You have the following context about recent work items:
{work_items_summary}

Focus: Building the most effective, accessible, and comprehensive AI education ecosystem with clear learning progressions and well-linked, small memory blocks.

Important: Use the tool specifications provided in your system message to ensure correct input formats and avoid validation errors."""

        # Run the education team
        await Console(team.run_stream(task=education_task))

        logger.info("✅ AI Education Team analysis with Cogni leader completed successfully!")

        # === OUTRO ROUTINE: Dolt Operations (Simplified) ===
        logger.info("🔄 Starting outro routine: Systematic Dolt operations...")

        # Create dedicated Dolt commit agent using the same MCP connection
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
        logger.error(f"❌ Enhanced flow with outro failed: {e}")
        return {"success": False, "error": str(e)}


# Outro routine now integrated into the main task above for simplicity


@flow(name="ai_education_team_flow", log_prints=True)
async def ai_education_team_flow() -> Dict[str, Any]:
    """
    AI Education Team Flow - Enhanced with Knowledge Graph Integration & Education Strategy

    Uses proven working AutoGen pattern to run 4 education-focused agents + Dolt operations:
    1. Read current work items context using DoltMySQLReader
    2. Setup MCP connection with proven stdio transport
    3. Run unified education team workflow that includes:
       - **Education Researcher** reading root knowledge graph ({AI_EDUCATION_ROOT_GUID})
       - **Curriculum Analyst** analyzing learning gaps and opportunities
       - **Education Reporter** documenting findings and progress
       - **Omnipresent Cogni Leader** providing education strategy insights
       - **Integrated Dolt operations** for automatic persistence

    All using the PROVEN working import pattern with education knowledge graph focus.
    """
    logger = get_run_logger()
    logger.info("🎯 Starting AI Education Team Flow with Knowledge Graph Integration")
    logger.info(
        "🔧 Using PROVEN working stdio MCP transport + Education Knowledge Graph + Strategic AI"
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

        # Step 2: Setup MCP connection
        mcp_setup = await setup_simple_mcp_connection()

        if not mcp_setup.get("success"):
            logger.error(f"❌ MCP setup failed: {mcp_setup.get('error')}")
            return {"status": "failed", "error": mcp_setup.get("error")}

        logger.info(f"✅ MCP setup successful: {mcp_setup['tools_count']} tools available")

        # Step 3: Run AI education team with integrated outro routine
        summary_result = await run_ai_education_team_with_outro(mcp_setup, work_items_context)

        if not summary_result.get("success"):
            logger.error(f"❌ Agent summary with outro failed: {summary_result.get('error')}")
            return {"status": "failed", "error": summary_result.get("error")}

        logger.info(
            "🤖 Education Team and Cogni Leader have provided strategic insights and Dolt operations completed!"
        )

        # Final success
        logger.info(
            "🎉 FLOW SUCCESS: AI Education Team flow with Knowledge Graph integration completed!"
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
    # For testing the AI Education Team flow locally
    import asyncio

    asyncio.run(ai_education_team_flow())
