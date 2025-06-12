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
    from .autogen_mcp_cogni_simple import AutoGenCogniMCPIntegration
except ImportError:
    # For direct execution
    pass

# Configure logging
logging.basicConfig(level=logging.INFO)


@task
async def run_autogen_cogni_integration() -> Dict[str, Any]:
    """Run AutoGen Cogni MCP integration with fail-fast approach"""
    logger = get_run_logger()

    logger.info("🎯 Starting AutoGen Cogni MCP Integration")
    logger.info("🔍 Expected: 21 Cogni MCP tools via SSE transport")

    integration = AutoGenCogniMCPIntegration()

    try:
        # Run the simplified demonstration - following minimal pattern
        logger.info("🔧 Running simplified AutoGen Cogni MCP demonstration...")
        result = await integration.run_demonstration()

        if not result["success"]:
            # Surface the specific error details prominently
            logger.error("❌ CRITICAL FAILURE: MCP Connection Failed")
            logger.error(f"🔍 Root Cause: {result['error']}")

            # Show minimal debug state
            debug_state = integration.get_debug_state()
            logger.error(f"🔍 Tools Discovered: {debug_state['cogni_tools_count']} (expected 21)")

            raise Exception(f"MCP Connection Failed: {result['error']}")

        logger.info(f"✅ SUCCESS: {result['tools_count']} MCP tools connected")
        logger.info(f"🔗 Endpoint: {result['endpoint']}")
        logger.info(f"🔧 Tools: {result['tools']}")

        return {
            "success": True,
            "tools_discovered": result["tools_count"],
            "endpoint": result["endpoint"],
            "tools": result["tools"],
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        # Final catch-all - keep it simple
        logger.error(f"❌ AutoGen Cogni MCP Integration FAILED: {str(e)}")
        raise e


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

    Raises:
        Exception: If critical integration failures occur
    """
    logger = get_run_logger()
    logger.info("🎯 Starting AutoGen Cogni MCP Prefect Flow")
    logger.info("🔍 Flow Configuration:")
    logger.info("   - Transport: SSE to containerized MCP server")
    logger.info("   - Expected Tools: 21 Cogni MCP tools")
    logger.info("   - Failure Mode: FAIL FAST on MCP connection issues")

    try:
        # Run the integration (will raise exception on failure)
        integration_results = await run_autogen_cogni_integration()

        # Save results
        output_file = await save_integration_results(integration_results, output_dir)

        # Return comprehensive results
        flow_results = {
            "flow_name": "autogen_cogni_mcp_flow",
            "status": "success",
            "integration_results": integration_results,
            "output_file": str(output_file),
            "timestamp": datetime.now().isoformat(),
            "approach": "AutoGen + Cogni Memory via MCP SSE transport",
            "tools_discovered": integration_results.get("tools_discovered", 0),
            "target_tools": 21,
        }

        logger.info("🎉 FLOW SUCCESS: AutoGen Cogni MCP Flow completed successfully")
        logger.info(
            f"📊 Final Results: {integration_results.get('tools_discovered', 0)}/21 tools discovered"
        )

        return flow_results

    except Exception as e:
        logger.error("💥 FLOW FAILURE: AutoGen Cogni MCP Flow failed")
        logger.error(f"❌ Error: {str(e)}")
        logger.error("🔍 This flow is configured to FAIL FAST on MCP connection issues")
        logger.error("🔧 Next Steps:")
        logger.error("   1. Check MCP server container status")
        logger.error("   2. Verify SSE endpoint configuration")
        logger.error("   3. Test container-to-container networking")

        # Re-raise to fail the flow
        raise


if __name__ == "__main__":
    # For local testing
    asyncio.run(autogen_cogni_mcp_flow())
