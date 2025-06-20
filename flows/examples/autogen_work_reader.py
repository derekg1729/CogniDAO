#!/usr/bin/env python3
"""
AutoGen Work Reader - Multi-Agent MCP Demo
==========================================

Demonstrates multi-agent chat integration with MCP tools:
1. Setup MCP connection (injected via dependency)
2. Create specialized agents for work item analysis
3. Run collaborative agent workflow
4. Return structured results

This focuses purely on the agent orchestration aspect.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

from prefect import flow, task
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

# Shared tasks for MCP connection (dependency injection approach)
from flows.presence.shared_tasks import setup_cogni_mcp_connection, read_work_items_context  # noqa: E402

# Prompt templates
from infra_core.prompt_templates import (  # noqa: E402
    render_work_reader_prompt,
    render_priority_analyzer_prompt,
    render_summary_writer_prompt,
    render_cogni_leader_prompt,
)

# Configure logging
logging.basicConfig(level=logging.INFO)


@task(name="create_work_analysis_agents")
async def create_work_analysis_agents(
    mcp_tools: List[Dict[str, Any]], tool_specs: str, work_items_context: str
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
            tools=mcp_tools,
            system_message=render_work_reader_prompt(tool_specs, work_items_context),
        )
        agents.append(work_reader)

        # Agent 2: Priority Analyzer
        priority_analyzer = AssistantAgent(
            name="priority_analyzer",
            model_client=model_client,
            tools=mcp_tools,
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
            tools=mcp_tools,
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


@task(name="run_collaborative_analysis")
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
    1. Setup MCP connection (dependency injected)
    2. Load work items context
    3. Create specialized analysis agents
    4. Run collaborative analysis workflow
    5. Return structured results

    This is focused purely on agent orchestration with MCP tools.
    """
    logger = get_run_logger()
    logger.info("Starting AutoGen multi-agent work analysis")

    try:
        # Step 1: Setup MCP connection (dependency injected)
        mcp_setup = await setup_cogni_mcp_connection()

        if not mcp_setup.get("success"):
            logger.error(f"MCP setup failed: {mcp_setup.get('error')}")
            return {"status": "failed", "error": mcp_setup.get("error")}

        logger.info(f"MCP connection established: {mcp_setup['tools_count']} tools available")

        # Step 2: Load work items context
        work_items_context = await read_work_items_context(branch="main")

        if work_items_context.get("success"):
            logger.info(f"Work items loaded: {work_items_context.get('count', 0)} items")
            context_summary = work_items_context.get("work_items_summary", "No context available")
        else:
            logger.warning(f"Work items loading failed: {work_items_context.get('error')}")
            context_summary = "Work items context unavailable"

        # Step 3: Create specialized agents
        agent_setup = await create_work_analysis_agents(
            mcp_tools=mcp_setup["tools"],
            tool_specs=mcp_setup.get("tool_specs", "Tool specs not available"),
            work_items_context=context_summary,
        )

        if not agent_setup.get("success"):
            logger.error(f"Agent creation failed: {agent_setup.get('error')}")
            return {"status": "failed", "error": agent_setup.get("error")}

        logger.info(f"Agents created: {agent_setup['agent_names']}")

        # Step 4: Run collaborative analysis
        analysis_result = await run_collaborative_analysis(
            agents=agent_setup["agents"], work_items_context=context_summary
        )

        if not analysis_result.get("success"):
            logger.error(f"Analysis failed: {analysis_result.get('error')}")
            return {"status": "failed", "error": analysis_result.get("error")}

        logger.info("Multi-agent analysis completed successfully")

        # Return structured, serializable results
        return {
            "status": "success",
            "mcp_tools_count": mcp_setup["tools_count"],
            "agents_count": agent_setup["agents_count"],
            "work_items_count": work_items_context.get("count", 0),
            "analysis_result": analysis_result["message"],
            "agent_names": agent_setup["agent_names"],
        }

    except Exception as e:
        logger.error(f"AutoGen work reader flow failed: {e}")
        return {"status": "failed", "error": str(e)}


if __name__ == "__main__":
    # For direct testing
    print("Running autogen_work_reader_flow directly...")
    asyncio.run(autogen_work_reader_flow())
