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

# Shared tasks and new SSE pattern imports
from utils.setup_connection_to_cogni_mcp import configure_cogni_mcp, MCPConnectionError  # noqa: E402
from utils.cogni_memory_mcp_outro import automated_dolt_outro  # noqa: E402

# Prompt template integration
from infra_core.prompt_templates import render_education_researcher_prompt  # noqa: E402
from infra_core.prompt_templates import render_curriculum_analyst_prompt  # noqa: E402
from infra_core.prompt_templates import render_education_reporter_prompt  # noqa: E402
from infra_core.prompt_templates import render_cogni_education_leader_prompt  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO)

# AI Education Graph Root - GUID for the foundational knowledge block
AI_EDUCATION_ROOT_GUID = "44bff8a7-6518-4514-92f9-49622fc72484"
MCP_DOLT_BRANCH = "ai-education-team"
MCP_DOLT_NAMESPACE = "legacy"


# Duplicate tasks removed - now using shared_tasks.py:
# - read_current_work_items -> read_work_items_context
# - setup_simple_mcp_connection -> setup_cogni_mcp_connection


@task(name="run_ai_education_team_with_outro", cache_policy=None)
async def run_ai_education_team_with_outro(
    autogen_tools: list, tool_specs_text: str, session, work_items_context: Dict[str, Any]
) -> Dict[str, Any]:
    """Run 4 AI education agents to analyze knowledge graph, assess learning needs, and improve educational content - All in one simple task using proven working pattern"""
    logger = get_run_logger()

    if not autogen_tools:
        return {"success": False, "error": "No MCP tools available"}

    try:
        # Setup OpenAI client - Helicone observability handled automatically by sitecustomize.py
        model_client = OpenAIChatCompletionClient(model="gpt-4o")
        logger.info("✅ OpenAI client configured")

        cogni_tools = autogen_tools
        tool_specs_text = tool_specs_text

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

        logger.info("📝 Calling shared automated_dolt_outro helper…")
        outro = await automated_dolt_outro(session, flow_context="AI-Education flow")

        return {
            "success": True,
            "agents_count": len(agents),
            "tools_count": len(cogni_tools),
            "outro": outro,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Enhanced flow with outro failed: {e}")
        return {"success": False, "error": str(e)}


# Outro routine now integrated into the main task above for simplicity


@flow(name="ai_education_team_flow", log_prints=True)
async def ai_education_team_flow() -> Dict[str, Any]:
    """AI-Education flow – now using SSE MCP + shared outro"""
    logger = get_run_logger()
    logger.info("🚀 Starting AI-Education flow (SSE edition)")

    # Pick branch / namespace from env *or* fallback constants
    branch = os.getenv("MCP_DOLT_BRANCH", "ai-education-team")
    namespace = os.getenv("MCP_DOLT_NAMESPACE", "legacy")
    sse_url = os.getenv("COGNI_MCP_SSE_URL", "http://toolhive:24160/sse")

    try:
        # Step 1: Skip work items reading for now (legacy pattern causing MySQL connection issues)
        work_items_context = {
            "success": True,
            "work_items_summary": "Work items context skipped for SSE testing",
        }

        # Step 2: Setup SSE MCP connection with branch/namespace switching
        async with configure_cogni_mcp(sse_url=sse_url, branch=branch, namespace=namespace) as (
            session,
            sdk_tools,
        ):
            logger.info("🔗 MCP attached (%d tools) on %s/%s", len(sdk_tools), branch, namespace)

            # --- build AutoGen adapters exactly like autogen_work_reader_flow ---
            from autogen_ext.tools.mcp import SseMcpToolAdapter, SseServerParams

            autogen_tools = [
                SseMcpToolAdapter(SseServerParams(url=sse_url), t, session) for t in sdk_tools
            ]

            tool_specs_text = "\n".join(
                [f"• {t.name}: {t.description or 'No description'}" for t in sdk_tools[:12]]
            )

            # Step 3: Run AI education team with integrated outro routine
            summary_result = await run_ai_education_team_with_outro(
                autogen_tools, tool_specs_text, session, work_items_context
            )

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
                "tools_count": len(sdk_tools),
                "agents_count": summary_result.get("agents_count", 0),
                "work_items_count": work_items_context.get("count", 0),
                "outro": summary_result.get("outro", {}),
                "timestamp": datetime.now().isoformat(),
            }

    except MCPConnectionError as e:
        logger.error(f"❌ MCP connection failed: {e}")
        return {"status": "failed", "error": f"MCP connection failed: {e}"}
    except Exception as e:
        logger.error(f"❌ Enhanced flow failed: {e}")
        return {"status": "failed", "error": str(e)}


if __name__ == "__main__":
    # For testing the AI Education Team flow locally
    import asyncio

    asyncio.run(ai_education_team_flow())
