#!/usr/bin/env python3
"""
Deployable AutoGen MCP Cogni Prefect Flow
Wraps our tested AutoGen MCP Cogni integration in a Prefect flow for deployment testing

Based on working autogen_mcp_cogni_simple.py with native MCP integration
Follows proven pattern from crewai_mcp_flow.py
"""

import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from prefect import flow, task
from prefect.logging import get_run_logger

# Import our tested integration
try:
    from .autogen_mcp_cogni_simple import AutoGenCogniSimple
except ImportError:
    # For direct execution
    from autogen_mcp_cogni_simple import AutoGenCogniSimple

# Configure logging
logging.basicConfig(level=logging.INFO)


@task(name="run_autogen_cogni_integration")
async def run_autogen_cogni_integration() -> Dict[str, Any]:
    """
    Run the AutoGen Cogni MCP integration

    Returns:
        Results from the AutoGen Cogni memory integration test
    """
    logger = get_run_logger()
    logger.info("🚀 Starting AutoGen Cogni MCP Integration")

    try:
        # Initialize and run our tested integration
        integration = AutoGenCogniSimple()
        result = await integration.run_simple_test()

        logger.info("✅ AutoGen Cogni MCP Integration completed successfully")
        return {
            "status": "success",
            "integration_successful": result,
            "tools_discovered": len(integration.cogni_tools) if integration.cogni_tools else 0,
            "agent_created": integration.agent is not None,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ AutoGen Cogni MCP Integration failed: {e}")
        return {"error": str(e), "status": "failed", "timestamp": datetime.now().isoformat()}


@task(name="save_integration_results")
async def save_integration_results(
    results: Dict[str, Any], output_dir: Optional[str] = None
) -> Path:
    """
    Save integration results to file

    Args:
        results: Results from the integration test
        output_dir: Optional output directory

    Returns:
        Path to saved file
    """
    logger = get_run_logger()

    # Default output directory - use local path for testing
    if output_dir is None:
        output_dir = "./test_results"

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"autogen_cogni_integration_results_{timestamp}.json"
    file_path = output_path / filename

    # Save results
    import json

    with open(file_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"💾 Saved integration results to: {file_path}")
    return file_path


@flow(name="autogen_cogni_mcp_flow", log_prints=True)
async def autogen_cogni_mcp_flow(output_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Deployable Prefect Flow: AutoGen Cogni MCP Integration

    Tests AutoGen with Cogni memory system via MCP protocol
    using SSE transport to containerized MCP server (with stdio fallback)

    Args:
        output_dir: Optional output directory for results

    Returns:
        Flow execution results
    """
    logger = get_run_logger()
    logger.info("🎯 Starting AutoGen Cogni MCP Prefect Flow")

    # Run the integration
    integration_results = await run_autogen_cogni_integration()

    # Save results
    output_file = await save_integration_results(integration_results, output_dir)

    # Return comprehensive results
    is_success = (
        integration_results.get("status") == "success"
        and integration_results.get("integration_successful") is True
    )

    flow_results = {
        "flow_name": "autogen_cogni_mcp_flow",
        "status": "completed" if is_success else "failed",
        "integration_results": integration_results,
        "output_file": str(output_file),
        "timestamp": datetime.now().isoformat(),
        "approach": "AutoGen + Cogni Memory via MCP SSE transport (stdio fallback)",
        "tools_discovered": integration_results.get("tools_discovered", 0),
        "target_tools": 21,  # We know 21 tools should be available
    }

    if not is_success:
        logger.error(
            f"❌ Flow completed with errors: {integration_results.get('error', 'Unknown error')}"
        )
    else:
        logger.info(
            f"✅ AutoGen Cogni MCP Flow completed successfully - {integration_results.get('tools_discovered', 0)}/21 tools discovered"
        )

    return flow_results


if __name__ == "__main__":
    # For local testing
    asyncio.run(autogen_cogni_mcp_flow())
