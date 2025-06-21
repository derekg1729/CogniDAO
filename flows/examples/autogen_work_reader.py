#!/usr/bin/env python3
"""
AutoGen Work Reader - Multi-Agent MCP Demo
==========================================

Demonstrates multi-agent chat integration with MCP tools:
1. Setup MCP connection via SSE helper
2. Create specialized agents for work item analysis
3. Run collaborative agent workflow
4. Return structured results

This focuses purely on the agent orchestration aspect.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from prefect import flow
from prefect.logging import get_run_logger

# AutoGen MCP Integration
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient

# Import path handling for shared components (addressing STYLE-01 partially)
current_dir = Path(__file__).parent
workspace_root = current_dir.parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

# New SSE MCP helper
from utils.mcp_setup import configure_existing_mcp, MCPConnectionError  # noqa: E402

# AutoGen MCP tool adapters
from autogen_ext.tools.mcp import SseMcpToolAdapter, SseServerParams  # noqa: E402

# Prompt templates
from infra_core.prompt_templates import (  # noqa: E402
    render_work_reader_prompt,
    render_priority_analyzer_prompt,
    render_summary_writer_prompt,
    render_cogni_leader_prompt,
)

# Configure logging
logging.basicConfig(level=logging.INFO)


# NO @task – Prefect can't pickle live session
async def create_work_analysis_agents(
    autogen_tools: List[Any], tool_specs: str, work_items_context: str
) -> Dict[str, Any]:
    """Create specialized agents for work item analysis with MCP tool access"""
    logger = get_run_logger()

    try:
        # Setup OpenAI client
        model_client = OpenAIChatCompletionClient(model="gpt-4o")
        logger.info("OpenAI client configured")

        # Create specialized agents
        agents = []

        # Agent 1: Work Item Reader
        work_reader = AssistantAgent(
            name="work_reader",
            model_client=model_client,
            tools=autogen_tools,
            system_message=render_work_reader_prompt(tool_specs, work_items_context),
        )
        agents.append(work_reader)

        # Agent 2: Priority Analyzer
        priority_analyzer = AssistantAgent(
            name="priority_analyzer",
            model_client=model_client,
            tools=autogen_tools,
            system_message=render_priority_analyzer_prompt(tool_specs, work_items_context),
        )
        agents.append(priority_analyzer)

        # Agent 3: Summary Writer
        summary_writer = AssistantAgent(
            name="summary_writer",
            model_client=model_client,
            system_message=render_summary_writer_prompt(tool_specs, work_items_context),
        )
        agents.append(summary_writer)

        # Agent 4: Strategic Cogni Leader
        cogni_leader = AssistantAgent(
            name="cogni_leader",
            model_client=model_client,
            tools=autogen_tools,
            system_message=render_cogni_leader_prompt(tool_specs, work_items_context),
        )
        agents.append(cogni_leader)

        logger.info(f"Created {len(agents)} specialized agents for work analysis")

        return {
            "success": True,
            "agents_count": len(agents),
            "agents": agents,  # Note: This is for internal flow use, not serialization
            "agent_names": [agent.name for agent in agents],
        }

    except Exception as e:
        logger.error(f"Agent creation failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "agents_count": 0,
            "agents": [],
            "agent_names": [],
        }


async def run_collaborative_analysis(agents: List[Any], work_items_context: str) -> Dict[str, Any]:
    """Run collaborative multi-agent analysis of work items"""
    logger = get_run_logger()

    if not agents:
        return {"success": False, "error": "No agents provided"}

    try:
        # Create team for collaborative work
        team = RoundRobinGroupChat(
            participants=agents, termination_condition=MaxMessageTermination(max_messages=8)
        )

        logger.info(f"Starting collaborative analysis with {len(agents)} agents")

        # Define analysis task
        analysis_task = f"""Please work together to analyze the current work items:

1) **Work Reader**: Use GetActiveWorkItems to read current active work items
2) **Priority Analyzer**: Analyze the priorities and dependencies  
3) **Summary Writer**: Create a brief, actionable summary
4) **Cogni Leader**: Provide strategic insights and next steps

Context provided:
{work_items_context}

Focus on actionable insights and clear next steps."""

        # Run the collaborative analysis
        await Console(team.run_stream(task=analysis_task))

        logger.info("Collaborative analysis completed successfully")

        return {
            "success": True,
            "agents_used": len(agents),
            "task_completed": "work_items_analysis",
            "message": "Multi-agent analysis completed successfully",
        }

    except Exception as e:
        logger.error(f"Collaborative analysis failed: {e}")
        return {"success": False, "error": str(e), "agents_used": len(agents) if agents else 0}


@flow(name="autogen_work_reader_flow", log_prints=True)
async def autogen_work_reader_flow() -> Dict[str, Any]:
    """
    AutoGen Multi-Agent Work Analysis Flow

    Demonstrates collaborative agent workflow with MCP tool integration:
    1. Setup SSE MCP connection via shared helper
    2. Load work items context via MCP tools
    3. Create specialized analysis agents
    4. Run collaborative analysis workflow
    5. Return structured results

    This is focused purely on agent orchestration with MCP tools.
    """
    logger = get_run_logger()
    logger.info("Starting AutoGen multi-agent work analysis")

    try:
        # Step 1: Setup SSE MCP connection via shared helper
        sse_url = os.getenv("COGNI_MCP_SSE_URL", "http://toolhive:24160/sse")

        async with configure_existing_mcp(sse_url) as (session, sdk_tools):
            logger.info(f"MCP SSE connection established: {len(sdk_tools)} tools available")

            # Step 2: Create AutoGen MCP tool adapters using existing session
            sse_params = SseServerParams(url=sse_url)

            # Create AutoGen tool adapters that reuse the existing session
            autogen_tools = [
                SseMcpToolAdapter(server_params=sse_params, tool=tool, session=session)
                for tool in sdk_tools
            ]

            logger.info(f"Created {len(autogen_tools)} AutoGen MCP tool adapters")

            # Step 3: Generate simple tool specs text
            tool_specs_lines = ["## Available MCP Tools:"]
            for tool in sdk_tools[:12]:  # Limit to first 12 tools
                tool_line = f"• {tool.name}: {tool.description or 'No description'}"
                tool_specs_lines.append(tool_line)

            tool_specs_text = "\n".join(tool_specs_lines)

            # Step 4: Load work items context via MCP tools directly
            logger.info("Loading work items context via GetActiveWorkItems MCP tool")

            try:
                ### DIRECTLY CALLING MCP TOOLS!! A GOOD MODEL!

                # Call GetActiveWorkItems directly using the session. No parsing yet.
                context_summary = await session.call_tool("GetActiveWorkItems", {"input": "{}"})

            except Exception as e:
                logger.warning(f"Failed to load work items via MCP: {e}")
                context_summary = "Work items context unavailable due to MCP error"

            # Step 5: Create specialized agents (no task-await)
            agent_setup = await create_work_analysis_agents(
                autogen_tools=autogen_tools,
                tool_specs=tool_specs_text,
                work_items_context=context_summary,
            )

            if not agent_setup.get("success"):
                logger.error(f"Agent creation failed: {agent_setup.get('error')}")
                return {"status": "failed", "error": agent_setup.get("error")}

            logger.info(f"Agents created: {agent_setup['agent_names']}")

            # Step 6: Run collaborative analysis (no task-await)
            analysis_result = await run_collaborative_analysis(
                agents=agent_setup["agents"], work_items_context=context_summary
            )

            if not analysis_result.get("success"):
                logger.error(f"Analysis failed: {analysis_result.get('error')}")
                return {"status": "failed", "error": analysis_result.get("error")}

            logger.info("Multi-agent analysis completed successfully – committing data to Dolt")

            # Auto-commit analysis results to Dolt using shared outro helper
            logger.info("🔄 Importing automated_dolt_outro helper...")
            from utils.mcp_outro import automated_dolt_outro

            logger.info("🚀 Calling automated_dolt_outro...")
            try:
                outro_result = await automated_dolt_outro(session, flow_context="work-reader flow")
                logger.info(f"✅ Outro completed successfully: {outro_result}")
            except Exception as e:
                logger.error(f"❌ Outro failed: {type(e).__name__}: {e}")
                import traceback

                logger.error(f"   Full traceback: {traceback.format_exc()}")
                # Continue with flow, but include error in outro result
                outro_result = {
                    "commit_message": f"ERROR: {str(e)}",
                    "push_result": f"Failed: {str(e)}",
                }

            # Return structured, serializable results
            return {
                "status": "success",
                "mcp_tools_count": len(sdk_tools),
                "agents_count": agent_setup["agents_count"],
                "analysis_result": analysis_result["message"],
                "agent_names": agent_setup["agent_names"],
                "outro": outro_result,
            }

    except MCPConnectionError as e:
        logger.error(f"MCP connection failed: {e}")
        return {"status": "failed", "error": f"MCP connection failed: {e}"}
    except Exception as e:
        logger.error(f"AutoGen work reader flow failed: {e}")
        return {"status": "failed", "error": str(e)}


if __name__ == "__main__":
    # For direct testing
    print("Running autogen_work_reader_flow directly...")
    asyncio.run(autogen_work_reader_flow())
