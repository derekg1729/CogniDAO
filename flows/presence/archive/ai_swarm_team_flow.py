#!/usr/bin/env python3
"""
AI Swarm Team Prefect Flow
===========================

Deployable Prefect flow for AI agent swarms with Cogni memory access.
Uses the proven stdio MCP transport for reliable operation.

Based on successful commit 77a6b4b integration.
"""

import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from prefect import flow, task
from prefect.logging import get_run_logger

# Import our working AI swarm template
try:
    from .ai_swarm_team_template import CogniAISwarmTemplate, DEMO_TASKS
except ImportError:
    # For direct execution
    from ai_swarm_team_template import CogniAISwarmTemplate, DEMO_TASKS

# Configure logging
logging.basicConfig(level=logging.INFO)


@task(name="run_ai_swarm_collaboration")
async def run_ai_swarm_collaboration(task_description: str) -> Dict[str, Any]:
    """
    Run AI swarm team collaboration with Cogni memory access

    Args:
        task_description: The task for the AI swarm to work on

    Returns:
        Results from the swarm collaboration
    """
    logger = get_run_logger()
    logger.info("🚀 Starting AI Swarm Team Collaboration Task")

    try:
        # Initialize swarm template
        swarm = CogniAISwarmTemplate()

        # Run the swarm collaboration
        success = await swarm.run_swarm_demo(task_description)

        if success:
            result = {
                "status": "success",
                "task_completed": True,
                "agents_count": len(swarm.agents),
                "tools_available": len(swarm.cogni_tools),
                "timestamp": datetime.now().isoformat(),
            }
            logger.info("✅ AI Swarm Team collaboration completed successfully")
        else:
            result = {
                "status": "failed",
                "task_completed": False,
                "error": "Swarm collaboration failed",
                "timestamp": datetime.now().isoformat(),
            }
            logger.error("❌ AI Swarm Team collaboration failed")

        return result

    except Exception as e:
        logger.error(f"❌ AI Swarm collaboration task failed: {e}")
        return {
            "status": "error",
            "task_completed": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


@task(name="save_swarm_results")
async def save_swarm_results(
    results: Dict[str, Any], task_name: str, output_dir: Optional[str] = None
) -> Path:
    """
    Save AI swarm collaboration results to file

    Args:
        results: Results from the swarm collaboration
        task_name: Name of the task that was performed
        output_dir: Optional output directory

    Returns:
        Path to saved file
    """
    logger = get_run_logger()

    # Default output directory
    if output_dir is None:
        output_dir = "./swarm_results"

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_task_name = task_name.replace(" ", "_").lower()
    filename = f"ai_swarm_{safe_task_name}_results_{timestamp}.json"
    file_path = output_path / filename

    # Save results
    import json

    with open(file_path, "w") as f:
        json.dump(
            {
                "task_name": task_name,
                "results": results,
                "saved_at": datetime.now().isoformat(),
            },
            f,
            indent=2,
            default=str,
        )

    logger.info(f"💾 Saved AI swarm results to: {file_path}")
    return file_path


@flow(name="ai_swarm_team_flow", log_prints=True)
async def ai_swarm_team_flow(
    task_name: str = "memory_organization",
    custom_task: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deployable Prefect Flow: AI Swarm Team with Cogni Memory

    Orchestrates multiple AI agents working together with shared memory access.

    Args:
        task_name: Name of predefined task to run (or 'custom' for custom_task)
        custom_task: Custom task description (if task_name is 'custom')
        output_dir: Optional output directory for results

    Returns:
        Flow execution results
    """
    logger = get_run_logger()
    logger.info("🎯 Starting AI Swarm Team Prefect Flow")
    logger.info("🔧 Flow Configuration:")
    logger.info("   - Transport: Stdio MCP (reliable, no networking issues)")
    logger.info("   - Expected Tools: 21 Cogni MCP tools")
    logger.info("   - Agents: Memory Manager, Coordinator, Technical Specialist")

    try:
        # Determine task to run
        if task_name == "custom" and custom_task:
            task_description = custom_task
            display_task_name = "custom"
        elif task_name in DEMO_TASKS:
            task_description = DEMO_TASKS[task_name]
            display_task_name = task_name
        else:
            # Default to memory organization
            task_description = DEMO_TASKS["memory_organization"]
            display_task_name = "memory_organization"

        logger.info(f"📝 Running task: {display_task_name}")

        # Run AI swarm collaboration
        collaboration_results = await run_ai_swarm_collaboration(task_description)

        # Save results
        output_file = await save_swarm_results(collaboration_results, display_task_name, output_dir)

        # Return comprehensive flow results
        flow_results = {
            "flow_name": "ai_swarm_team_flow",
            "status": "success" if collaboration_results.get("status") == "success" else "failed",
            "task_name": display_task_name,
            "collaboration_results": collaboration_results,
            "output_file": str(output_file),
            "timestamp": datetime.now().isoformat(),
            "approach": "AI Swarm Team + Cogni Memory via stdio MCP",
            "agents_count": collaboration_results.get("agents_count", 0),
            "tools_available": collaboration_results.get("tools_available", 0),
        }

        if collaboration_results.get("status") == "success":
            logger.info("🎉 FLOW SUCCESS: AI Swarm Team Flow completed successfully")
            logger.info(
                f"📊 Results: {collaboration_results.get('agents_count', 0)} agents, "
                f"{collaboration_results.get('tools_available', 0)} tools"
            )
        else:
            logger.error(f"💥 FLOW FAILED: {collaboration_results.get('error', 'Unknown error')}")

        return flow_results

    except Exception as e:
        logger.error("💥 FLOW FAILURE: AI Swarm Team Flow encountered unexpected error")
        logger.error(f"❌ Error: {str(e)}")

        # Return error results
        return {
            "flow_name": "ai_swarm_team_flow",
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


# Convenience functions for different scenarios
@flow(name="ai_swarm_project_planning")
async def ai_swarm_project_planning_flow(output_dir: Optional[str] = None):
    """AI Swarm Team: Project Planning Flow"""
    return await ai_swarm_team_flow("project_planning", output_dir=output_dir)


@flow(name="ai_swarm_technical_research")
async def ai_swarm_technical_research_flow(output_dir: Optional[str] = None):
    """AI Swarm Team: Technical Research Flow"""
    return await ai_swarm_team_flow("technical_research", output_dir=output_dir)


@flow(name="ai_swarm_memory_organization")
async def ai_swarm_memory_organization_flow(output_dir: Optional[str] = None):
    """AI Swarm Team: Memory Organization Flow"""
    return await ai_swarm_team_flow("memory_organization", output_dir=output_dir)


if __name__ == "__main__":
    # For local testing
    import sys

    if len(sys.argv) > 1:
        task_name = sys.argv[1]
    else:
        task_name = "memory_organization"

    print(f"🎯 Running AI Swarm Team Flow with task: {task_name}")
    asyncio.run(ai_swarm_team_flow(task_name))
