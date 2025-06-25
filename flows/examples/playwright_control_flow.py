#!/usr/bin/env python3
"""
Playwright Control Flow - Two-Person AutoGen Navigation Team
============================================================

Demonstrates Control Flow agent architecture with:
1. Navigator Agent - Executes web navigation and interactions
2. Observer Agent - Monitors, guides, and validates navigation
3. Playwright MCP integration via SSE transport
4. XML Jinja template-based agent prompts
5. Collaborative two-agent workflow

This moves beyond the legacy "1flow, 1agent" format to a proper Control Flow
architecture with specialized agent roles.
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

# Import path handling for shared components
current_dir = Path(__file__).parent
workspace_root = current_dir.parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

# Shared MCP helper
from utils.mcp_setup import configure_existing_mcp, MCPConnectionError  # noqa: E402

# AutoGen MCP tool adapters
from autogen_ext.tools.mcp import SseMcpToolAdapter, SseServerParams  # noqa: E402

# Playwright prompt templates
from infra_core.prompt_templates import (  # noqa: E402
    render_playwright_navigator_prompt,
    render_playwright_observer_prompt,
)

# Configure logging
logging.basicConfig(level=logging.INFO)


async def create_playwright_navigation_team(
    autogen_tools: List[Any], tool_specs: str, task_context: str, target_url: str
) -> Dict[str, Any]:
    """Create specialized two-person team for playwright navigation"""
    logger = get_run_logger()

    try:
        # Setup OpenAI client
        model_client = OpenAIChatCompletionClient(model="gpt-4o")
        logger.info("✅ OpenAI client configured for Control Flow agents")

        # Create specialized agents
        agents = []

        # Agent 1: Navigator - The hands-on web navigator
        navigator = AssistantAgent(
            name="playwright_navigator",
            model_client=model_client,
            tools=autogen_tools,
            system_message=render_playwright_navigator_prompt(tool_specs, task_context, target_url),
        )
        agents.append(navigator)

        # Agent 2: Observer - The strategic guide and validator
        observer = AssistantAgent(
            name="playwright_observer",
            model_client=model_client,
            tools=autogen_tools,  # Both agents have access to tools
            system_message=render_playwright_observer_prompt(tool_specs, task_context, target_url),
        )
        agents.append(observer)

        logger.info(f"🤖 Created Control Flow team: {len(agents)} agents")
        for agent in agents:
            logger.info(f"   👤 {agent.name}")

        return {
            "success": True,
            "agents_count": len(agents),
            "agents": agents,  # For internal flow use
            "agent_names": [agent.name for agent in agents],
            "architecture": "control_flow_two_person_team",
        }

    except Exception as e:
        logger.error(f"❌ Control Flow team creation failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "agents_count": 0,
            "agents": [],
            "agent_names": [],
        }


async def run_navigation_mission(
    agents: List[Any], task_context: str, navigation_objective: str
) -> Dict[str, Any]:
    """Run collaborative navigation mission with Navigator and Observer"""
    logger = get_run_logger()

    if not agents:
        return {"success": False, "error": "No agents provided for navigation mission"}

    try:
        # Create Control Flow team for collaborative navigation
        team = RoundRobinGroupChat(
            participants=agents, termination_condition=MaxMessageTermination(max_messages=12)
        )

        logger.info(f"🚀 Starting navigation mission with {len(agents)} agents")

        # Define navigation mission brief
        mission_brief = f"""Control Flow Navigation Mission Brief:

**Objective**: {navigation_objective}

**Team Roles**:
- **Navigator**: Execute web navigation, interact with elements, extract data
- **Observer**: Guide strategy, validate results, ensure quality completion

**Mission Context**:
{task_context}

**Collaboration Protocol**:
1. Observer analyzes the objective and provides initial navigation strategy
2. Navigator executes the navigation steps with real-time reporting
3. Observer validates each step and guides course corrections
4. Both agents work together to achieve the objective efficiently

**Success Criteria**:
- Successfully navigate to target pages/elements
- Extract or interact with required information
- Provide comprehensive mission report
- Demonstrate effective two-agent collaboration

Begin mission execution!"""

        # Run the collaborative navigation mission
        await Console(team.run_stream(task=mission_brief))

        logger.info("✅ Navigation mission completed successfully")

        return {
            "success": True,
            "agents_used": len(agents),
            "mission_type": "control_flow_navigation",
            "objective": navigation_objective,
            "architecture": "two_person_collaborative_team",
            "message": "Control Flow navigation mission completed successfully",
        }

    except Exception as e:
        logger.error(f"❌ Navigation mission failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "agents_used": len(agents) if agents else 0,
            "mission_type": "control_flow_navigation",
        }


@flow(name="playwright_control_flow", log_prints=True)
async def playwright_control_flow(
    target_url: str = "http://host.docker.internal:3000",
) -> Dict[str, Any]:
    """
    Playwright Control Flow Agent System

    Demonstrates modern Control Flow architecture with:
    - Two-person specialized agent team (Navigator + Observer)
    - Playwright MCP integration via SSE transport
    - XML Jinja template-based agent system messages
    - Collaborative workflow beyond legacy "1flow, 1agent" format

    Parameters:
    - target_url: The target URL to test (default: http://host.docker.internal:3000)

    Environment Variables:
    - PLAYWRIGHT_MCP_SSE_URL: SSE URL for Playwright MCP server
    """
    logger = get_run_logger()
    logger.info("🚀 Starting Playwright Control Flow Agent System")

    try:
        # Configuration
        sse_url = os.getenv("PLAYWRIGHT_MCP_SSE_URL", "http://toolhive:24162/sse")
        navigation_objective = f"Test the CogniDAO application starting from the home page at {target_url}, verify core functionality including memory blocks display, chat interface, navigation, and explore page functionality"

        logger.info(f"🔗 Playwright MCP SSE URL: {sse_url}")
        logger.info(f"🎯 Target URL: {target_url}")
        logger.info(f"🎯 Navigation Objective: {navigation_objective}")

        # Step 1: Setup SSE MCP connection for Playwright
        async with configure_existing_mcp(sse_url) as (session, sdk_tools):
            logger.info(f"📡 Playwright MCP connection established: {len(sdk_tools)} tools")

            # Generate tool specifications for agent prompts
            tool_specs = f"""## Available Playwright MCP Tools:
**CRITICAL: All tools expect a single 'input' parameter containing JSON string**

Tools Available ({len(sdk_tools)} total):
""" + "\n".join(f"• {tool.name}: {tool.description}" for tool in sdk_tools[:10])

            if len(sdk_tools) > 10:
                tool_specs += f"\n... and {len(sdk_tools) - 10} more playwright tools"

            # Step 2: Create AutoGen MCP tool adapters
            sse_params = SseServerParams(url=sse_url)
            autogen_tools = [
                SseMcpToolAdapter(server_params=sse_params, tool=tool, session=session)
                for tool in sdk_tools
            ]

            logger.info(f"🔧 Created {len(autogen_tools)} AutoGen tool adapters")

            # Step 3: Create Control Flow navigation team
            task_context = f"""Task Context: Web Navigation Mission
Target URL: {target_url}
Tools: {len(autogen_tools)} Playwright MCP tools available
Objective: {navigation_objective}
"""

            team_result = await create_playwright_navigation_team(
                autogen_tools, tool_specs, task_context, target_url
            )

            if not team_result.get("success"):
                logger.error(f"❌ Failed to create Control Flow team: {team_result.get('error')}")
                return {
                    "status": "failed",
                    "error": team_result.get("error"),
                    "stage": "team_creation",
                }

            logger.info(
                f"✅ Control Flow team created: {team_result['architecture']} with {team_result['agents_count']} agents"
            )

            # Step 4: Execute navigation mission
            mission_result = await run_navigation_mission(
                team_result["agents"], task_context, navigation_objective
            )

            # Return comprehensive results
            return {
                "status": "success",
                "playwright_mcp_connection": {
                    "tools_count": len(sdk_tools),
                    "connection_url": sse_url,
                    "connection_type": "sse_transport",
                },
                "control_flow_team": team_result,
                "navigation_mission": mission_result,
                "architecture_info": {
                    "type": "control_flow_two_person_team",
                    "legacy_format": False,
                    "template_type": "xml_jinja",
                    "collaboration_model": "navigator_observer_pattern",
                },
                "summary": {
                    "tools_available": len(sdk_tools),
                    "agents_created": team_result.get("agents_count", 0),
                    "mission_success": mission_result.get("success", False),
                    "target_url": target_url,
                    "objective": navigation_objective,
                },
            }

    except MCPConnectionError as e:
        logger.error(f"❌ Playwright MCP connection error: {e}")
        return {"status": "failed", "error": str(e), "stage": "mcp_connection"}
    except Exception as e:
        logger.error(f"❌ Control Flow system failed: {e}")
        return {"status": "failed", "error": str(e), "stage": "system_execution"}


if __name__ == "__main__":
    # For direct testing
    print("🤖 Running Playwright Control Flow Agent System...")
    print("This demonstrates a two-person AutoGen team with Playwright MCP on port 24162")
    asyncio.run(playwright_control_flow())
