"""
Image Generation Control Flow - Cogni-Image-Generators

A sophisticated two-agent AutoGen Control Flow system for collaborative image generation
using Luma and Veo2 MCP tools. Features Image Creator and Image Refiner agents working
together to produce exceptional visual content.

Architecture:
- Image Creator Agent: Initial generation, prompt engineering, tool selection
- Image Refiner Agent: Enhancement, modification, iterative improvement
- MCP Integration: Luma and Veo2 image generation tools via SSE transport
- Control Flow: Structured collaboration with clear handoffs

Example Usage:
    python flows/examples/image_generation_control_flow.py
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

# Image generation prompt templates
from infra_core.prompt_templates import (  # noqa: E402
    render_image_creator_prompt,
    render_image_refiner_prompt,
)

# Configure logging
logging.basicConfig(level=logging.INFO)


async def create_image_generation_team(
    autogen_tools: List[Any], tool_specs: str, task_context: str, creative_brief: str
) -> Dict[str, Any]:
    """Create specialized two-agent team for image generation"""
    logger = get_run_logger()

    try:
        # Setup OpenAI client
        model_client = OpenAIChatCompletionClient(model="gpt-4o-mini")
        logger.info("✅ OpenAI client configured for Control Flow agents")

        # Create specialized agents
        agents = []

        # Agent 1: Image Creator - The initial generation specialist
        image_creator = AssistantAgent(
            name="image_creator",
            model_client=model_client,
            tools=autogen_tools,
            system_message=render_image_creator_prompt(tool_specs, task_context),
        )
        agents.append(image_creator)

        # Agent 2: Image Refiner - The enhancement and refinement specialist
        image_refiner = AssistantAgent(
            name="image_refiner",
            model_client=model_client,
            tools=autogen_tools,
            system_message=render_image_refiner_prompt(tool_specs, task_context),
        )
        agents.append(image_refiner)

        logger.info(f"🤖 Created Control Flow team: {len(agents)} agents")
        for agent in agents:
            logger.info(f"   👤 {agent.name}")

        return {
            "success": True,
            "agents_count": len(agents),
            "agents": agents,  # For internal flow use
            "agent_names": [agent.name for agent in agents],
            "architecture": "control_flow_two_agent_team",
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


async def run_image_generation_mission(
    agents: List[Any], task_context: str, creative_brief: str
) -> Dict[str, Any]:
    """Run collaborative image generation mission with Creator and Refiner"""
    logger = get_run_logger()

    if not agents:
        return {"success": False, "error": "No agents provided for image generation mission"}

    try:
        # Create Control Flow team for collaborative image generation
        team = RoundRobinGroupChat(
            participants=agents, termination_condition=MaxMessageTermination(max_messages=12)
        )

        logger.info(f"🚀 Starting image generation mission with {len(agents)} agents")

        # Define image generation mission brief
        mission_brief = f"""Control Flow Image Generation Mission Brief:

**Creative Brief**: {creative_brief}

**Team Roles**:
- **Image Creator**: Analyze creative brief, craft optimized prompts, select tools, generate initial images
- **Image Refiner**: Evaluate results, identify enhancement opportunities, apply refinements, iterate for quality

**Mission Context**:
{task_context}

**Collaboration Protocol**:
1. Image Creator analyzes the creative brief and develops generation strategy
2. Image Creator executes initial image generation with optimal prompts and tools
3. Image Refiner evaluates the results and provides detailed enhancement plan
4. Image Refiner applies targeted refinements and improvements
5. Both agents collaborate iteratively until exceptional results are achieved

**Success Criteria**:
- Generate high-quality images that capture the creative vision
- Apply effective enhancements and refinements
- Demonstrate clear two-agent collaboration workflow
- Provide comprehensive documentation of the generation process

Begin image generation mission!"""

        # Run the collaborative image generation mission
        await Console(team.run_stream(task=mission_brief))

        logger.info("✅ Image generation mission completed successfully")

        return {
            "success": True,
            "agents_used": len(agents),
            "mission_type": "control_flow_image_generation",
            "creative_brief": creative_brief,
            "architecture": "two_agent_collaborative_team",
            "message": "Control Flow image generation mission completed successfully",
        }

    except Exception as e:
        logger.error(f"❌ Image generation mission failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "agents_used": len(agents) if agents else 0,
            "mission_type": "control_flow_image_generation",
        }


@flow(name="image_generation_control_flow", log_prints=True)
async def image_generation_control_flow(
    creative_brief: str = "A majestic dragon soaring through a mystical forest at sunset, digital art style with vibrant colors and ethereal lighting",
) -> Dict[str, Any]:
    """
    Image Generation Control Flow Agent System

    Demonstrates modern Control Flow architecture with:
    - Two-agent specialized team (Image Creator + Image Refiner)
    - Luma/Veo2 MCP integration via SSE transport
    - XML Jinja template-based agent system messages
    - Collaborative workflow beyond legacy "1flow, 1agent" format

    Parameters:
    - creative_brief: The creative description for image generation

    Environment Variables:
    - LUMA_MCP_SSE_URL: SSE URL for Luma MCP server
    - VEO2_MCP_SSE_URL: SSE URL for Veo2 MCP server
    """
    logger = get_run_logger()
    logger.info("🚀 Starting Image Generation Control Flow Agent System")

    try:
        # Configuration
        luma_sse_url = os.getenv("LUMA_MCP_SSE_URL", "http://localhost:58897/sse")
        veo2_sse_url = os.getenv("VEO2_MCP_SSE_URL", "http://localhost:8932/sse")

        logger.info(f"🔗 Luma MCP SSE URL: {luma_sse_url}")
        logger.info(f"🔗 Veo2 MCP SSE URL: {veo2_sse_url}")
        logger.info(f"🎯 Creative Brief: {creative_brief}")

        # Step 1: Setup SSE MCP connection for Luma image generation
        async with configure_existing_mcp(luma_sse_url) as (session, sdk_tools):
            logger.info(f"📡 Luma MCP connection established: {len(sdk_tools)} tools")

            # Generate tool specifications for agent prompts
            tool_specs = f"""## Available Image Generation MCP Tools:
**CRITICAL: All tools expect a single 'input' parameter containing JSON string**

Tools Available ({len(sdk_tools)} total):
""" + "\n".join(f"• {tool.name}: {tool.description}" for tool in sdk_tools[:15])

            if len(sdk_tools) > 15:
                tool_specs += f"\n... and {len(sdk_tools) - 15} more image generation tools"

            # Step 2: Create AutoGen MCP tool adapters
            sse_params = SseServerParams(url=luma_sse_url)
            autogen_tools = [
                SseMcpToolAdapter(server_params=sse_params, tool=tool, session=session)
                for tool in sdk_tools
            ]

            logger.info(f"🔧 Created {len(autogen_tools)} AutoGen tool adapters")

            # Step 3: Create Control Flow image generation team
            task_context = f"""Task Context: Creative Image Generation Mission
Tools: {len(autogen_tools)} Luma image generation MCP tools available
Objective: Transform creative brief into exceptional visual content through collaborative generation and refinement
Creative Brief: {creative_brief}
"""

            team_result = await create_image_generation_team(
                autogen_tools, tool_specs, task_context, creative_brief
            )

            if not team_result.get("success"):
                return {
                    "success": False,
                    "error": f"Team creation failed: {team_result.get('error')}",
                    "flow_type": "image_generation_control_flow",
                }

            # Step 4: Execute the collaborative image generation mission
            mission_result = await run_image_generation_mission(
                team_result["agents"], task_context, creative_brief
            )

            logger.info("🎉 Image Generation Control Flow completed!")

            return {
                "success": mission_result.get("success", False),
                "flow_type": "image_generation_control_flow",
                "luma_tools_count": len(sdk_tools),
                "autogen_adapters": len(autogen_tools),
                "creative_brief": creative_brief,
                "team_result": team_result,
                "mission_result": mission_result,
                "architecture": "control_flow_two_agent_collaboration",
            }

    except MCPConnectionError as e:
        logger.error(f"❌ MCP connection failed: {e}")
        return {
            "success": False,
            "error": f"MCP connection failed: {e}",
            "flow_type": "image_generation_control_flow",
        }
    except Exception as e:
        logger.error(f"❌ Image Generation Control Flow failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "flow_type": "image_generation_control_flow",
        }


if __name__ == "__main__":
    """Direct execution for testing"""
    print("🎨 Running Image Generation Control Flow directly...")

    # Set test creative brief
    test_brief = "A serene Japanese garden at dawn with cherry blossoms, koi pond reflections, and soft morning mist, photorealistic style"

    result = asyncio.run(image_generation_control_flow(test_brief))

    print("\n🎉 Image Generation Control Flow Results:")
    print(f"Success: {result.get('success', False)}")
    print(f"Tools Count: {result.get('luma_tools_count', 0)}")
    print(f"Creative Brief: {result.get('creative_brief', 'None')}")

    if result.get("success"):
        print("✅ Image generation completed successfully!")
    else:
        print(f"❌ Error: {result.get('error', 'Unknown error')}")
