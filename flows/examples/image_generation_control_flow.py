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
from typing import Dict, Any, List

# Prefect imports
from prefect import flow, get_run_logger

# AutoGen imports
from autogen_core import AgentId, AgentProxy
from autogen_core.models import OpenAIModelClient
from autogen_ext.tools.mcp import SseMcpToolAdapter, SseServerParams

# Control Flow imports
from autogen_ext.application import SingleThreadedAgentRuntime
from autogen_ext.application.proxyagent import ProxyAgent

# Cogni imports
from utils.mcp_setup import configure_existing_mcp
from infra_core.prompt_templates import render_image_creator_prompt, render_image_refiner_prompt

# Configure logging
logger = logging.getLogger(__name__)


async def create_image_generation_team(
    autogen_tools: List, tool_specs: str, task_context: str, creative_brief: str
) -> Dict[str, Any]:
    """
    Create and run Image Generation team using Control Flow architecture

    Args:
        autogen_tools: List of AutoGen MCP tool adapters
        tool_specs: Formatted tool specifications string
        task_context: Context information for the task
        creative_brief: Creative description for image generation

    Returns:
        Team execution results with generated images and refinements
    """
    logger.info("🎨 Creating Image Generation Control Flow team...")

    # Setup OpenAI client
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")

    model_client = OpenAIModelClient(
        model="gpt-4o-mini",
        api_key=openai_api_key,
    )

    # Create runtime and agents
    runtime = SingleThreadedAgentRuntime()

    # Image Creator Agent - Initial generation specialist
    image_creator_prompt = render_image_creator_prompt(
        tool_specs=tool_specs, task_context=task_context
    )

    image_creator_agent = ProxyAgent(
        AgentId("image_creator", "image_gen_team"),
        runtime,
        name="ImageCreator",
        model_client=model_client,
        tools=autogen_tools,
        system_message=image_creator_prompt,
        max_consecutive_auto_replies=3,
    )

    # Image Refiner Agent - Enhancement specialist
    image_refiner_prompt = render_image_refiner_prompt(
        tool_specs=tool_specs, task_context=task_context
    )

    image_refiner_agent = ProxyAgent(
        AgentId("image_refiner", "image_gen_team"),
        runtime,
        name="ImageRefiner",
        model_client=model_client,
        tools=autogen_tools,
        system_message=image_refiner_prompt,
        max_consecutive_auto_replies=3,
    )

    logger.info("✅ Image Generation team created successfully")
    logger.info(f"   🎨 Image Creator: {len(autogen_tools)} tools available")
    logger.info(f"   ✨ Image Refiner: {len(autogen_tools)} tools available")

    try:
        # Start runtime
        runtime.start()
        logger.info("🚀 Control Flow runtime started")

        # Execute Image Generation workflow
        workflow_result = await execute_image_generation_workflow(
            image_creator_agent, image_refiner_agent, creative_brief
        )

        return {
            "success": True,
            "team_type": "image_generation_control_flow",
            "agents_created": 2,
            "tools_available": len(autogen_tools),
            "workflow_result": workflow_result,
            "creative_brief": creative_brief,
        }

    except Exception as e:
        logger.error(f"❌ Image Generation team execution failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "team_type": "image_generation_control_flow",
        }
    finally:
        # Cleanup
        runtime.stop()
        logger.info("🛑 Control Flow runtime stopped")


async def execute_image_generation_workflow(
    image_creator_agent: AgentProxy, image_refiner_agent: AgentProxy, creative_brief: str
) -> Dict[str, Any]:
    """
    Execute the collaborative image generation workflow

    Args:
        image_creator_agent: Image Creator agent proxy
        image_refiner_agent: Image Refiner agent proxy
        creative_brief: Creative description for generation

    Returns:
        Workflow execution results
    """
    logger.info("🎯 Starting Image Generation workflow...")

    # Phase 1: Initial Image Creation
    logger.info("📝 Phase 1: Initial Image Creation")

    creation_message = f"""Creative Brief: {creative_brief}

Your mission:
1. Analyze the creative brief for artistic intent and technical requirements
2. Craft an optimized prompt with appropriate artistic language
3. Select the best tool and parameters for this specific request
4. Generate the initial image(s)
5. Evaluate results and provide detailed feedback for the Image Refiner Agent

Focus on creating a strong foundation that captures the creative vision while providing clear direction for refinement."""

    creation_response = await image_creator_agent.on_messages(
        [{"role": "user", "content": creation_message}]
    )

    logger.info("✅ Phase 1 completed - Initial image creation")

    # Phase 2: Image Analysis and Refinement Planning
    logger.info("🔍 Phase 2: Image Analysis and Refinement Planning")

    refinement_planning_message = f"""Initial Creation Results:
{creation_response[-1]["content"] if creation_response else "No creation response available"}

Your mission:
1. Analyze the initial image(s) for quality, composition, and artistic merit
2. Identify specific enhancement opportunities
3. Develop a refinement strategy that will elevate the visual impact
4. Select optimal tools and parameters for targeted improvements
5. Provide a clear plan for iterative enhancement

Focus on building upon the Image Creator's foundation to achieve exceptional results."""

    refinement_plan_response = await image_refiner_agent.on_messages(
        [{"role": "user", "content": refinement_planning_message}]
    )

    logger.info("✅ Phase 2 completed - Refinement planning")

    # Phase 3: Collaborative Enhancement
    logger.info("🎨 Phase 3: Collaborative Enhancement Execution")

    enhancement_message = f"""Refinement Plan:
{refinement_plan_response[-1]["content"] if refinement_plan_response else "No refinement plan available"}

Execute your refinement strategy:
1. Apply the planned enhancements using optimal tools and parameters
2. Monitor results and adjust approach as needed
3. Perform additional iterations if beneficial
4. Document the refinement process and final results
5. Provide recommendations for future similar projects

Deliver exceptional visual content that exceeds the original creative brief."""

    enhancement_response = await image_refiner_agent.on_messages(
        [{"role": "user", "content": enhancement_message}]
    )

    logger.info("✅ Phase 3 completed - Collaborative enhancement")

    # Compile workflow results
    workflow_summary = {
        "phase_1_creation": creation_response[-1]["content"] if creation_response else None,
        "phase_2_planning": refinement_plan_response[-1]["content"]
        if refinement_plan_response
        else None,
        "phase_3_enhancement": enhancement_response[-1]["content"]
        if enhancement_response
        else None,
        "total_phases": 3,
        "workflow_status": "completed",
    }

    logger.info("🎉 Image Generation workflow completed successfully!")
    return workflow_summary


@flow(name="image_generation_control_flow", log_prints=True)
async def image_generation_control_flow(
    creative_brief: str = "A majestic dragon soaring through a mystical forest at sunset, digital art style with vibrant colors and ethereal lighting",
) -> Dict[str, Any]:
    """
    Main Prefect flow for Image Generation Control Flow system

    Args:
        creative_brief: Creative description for image generation

    Returns:
        Flow execution results
    """
    logger = get_run_logger()
    logger.info("🎨 Starting Image Generation Control Flow")
    logger.info(f"🎯 Creative Brief: {creative_brief}")

    try:
        # Configuration
        # Note: Update these URLs based on your MCP server deployment
        luma_sse_url = os.getenv("LUMA_MCP_SSE_URL", "http://localhost:8931/sse")
        veo2_sse_url = os.getenv("VEO2_MCP_SSE_URL", "http://localhost:8932/sse")

        logger.info(f"🔗 Luma MCP SSE URL: {luma_sse_url}")
        logger.info(f"🔗 Veo2 MCP SSE URL: {veo2_sse_url}")

        # Step 1: Setup SSE MCP connections for image generation
        # For now, let's start with Luma MCP connection
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

            logger.info("🎉 Image Generation Control Flow completed!")

            return {
                "success": team_result.get("success", False),
                "flow_type": "image_generation_control_flow",
                "luma_tools_count": len(sdk_tools),
                "autogen_adapters": len(autogen_tools),
                "creative_brief": creative_brief,
                "team_result": team_result,
                "architecture": "control_flow_two_agent_collaboration",
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
