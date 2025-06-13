#!/usr/bin/env python3
"""
COMMENTED OUT - Deployable CrewAI MCP Prefect Flow
THIS FILE IS TEMPORARILY DISABLED DUE TO DEPENDENCY CONFLICTS

The crewai-tools[mcp] dependency in the underlying PoC causes chromadb<0.6.0 constraints
that conflict with our MCP server requiring chromadb>=1.0.8

Will be re-enabled once dependency conflicts are resolved.
"""

# Wraps our tested CrewAI MCP proof-of-concept in a Prefect flow for deployment testing
#
# Based on tested crewai_mcp_poc.py with native MCP integration

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from prefect import flow
from prefect.logging import get_run_logger

# COMMENTED OUT - CAUSES DEPENDENCY CONFLICTS
# Import our tested PoC
# from .crewai_mcp_poc import CrewAIMCPProofOfConcept

# Configure logging
logging.basicConfig(level=logging.INFO)

# ALL TASKS COMMENTED OUT DUE TO DEPENDENCY CONFLICTS
"""
@task(name="run_crewai_mcp_poc")
async def run_crewai_mcp_poc() -> Dict[str, Any]:
    Run the CrewAI MCP proof-of-concept

    Returns:
        Results from the CrewAI MCP integration test
    logger = get_run_logger()
    logger.info("🚀 Starting CrewAI MCP Proof-of-Concept")

    try:
        # Initialize and run our tested PoC
        poc = CrewAIMCPProofOfConcept()
        result = await poc.run_proof_of_concept()

        logger.info("✅ CrewAI MCP PoC completed successfully")
        return result

    except Exception as e:
        logger.error(f"❌ CrewAI MCP PoC failed: {e}")
        return {"error": str(e), "status": "failed"}


@task(name="save_poc_results")
async def save_poc_results(results: Dict[str, Any], output_dir: Optional[str] = None) -> Path:
    Save PoC results to file

    Args:
        results: Results from the PoC
        output_dir: Optional output directory

    Returns:
        Path to saved file
    logger = get_run_logger()

    # Default output directory
    if output_dir is None:
        output_dir = "/workspace/data/agents/presence/thoughts"

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"crewai_mcp_poc_results_{timestamp}.json"
    file_path = output_path / filename

    # Save results
    import json

    with open(file_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"💾 Saved PoC results to: {file_path}")
    return file_path


@flow(name="crewai_mcp_poc_flow", log_prints=True)
async def crewai_mcp_poc_flow(output_dir: Optional[str] = None) -> Dict[str, Any]:
    Deployable Prefect Flow: CrewAI MCP Proof-of-Concept

    Tests native MCP integration using CrewAI MCPServerAdapter
    instead of broken HTTP glue approach

    Args:
        output_dir: Optional output directory for results

    Returns:
        Flow execution results
    logger = get_run_logger()
    logger.info("🎯 Starting CrewAI MCP Prefect Flow")

    # Run the PoC
    poc_results = await run_crewai_mcp_poc()

    # Save results
    output_file = await save_poc_results(poc_results, output_dir)

    # Return comprehensive results
    # Handle both boolean (success) and dict (error) results from PoC
    is_success = poc_results is True or (
        isinstance(poc_results, dict) and "error" not in poc_results
    )

    flow_results = {
        "flow_name": "crewai_mcp_poc_flow",
        "status": "completed" if is_success else "failed",
        "poc_results": poc_results,
        "output_file": str(output_file),
        "timestamp": datetime.now().isoformat(),
        "approach": "Native MCP Integration via CrewAI MCPServerAdapter",
    }

    if isinstance(poc_results, dict) and "error" in poc_results:
        logger.error(f"❌ Flow completed with errors: {poc_results['error']}")
    else:
        logger.info("✅ CrewAI MCP Flow completed successfully")

    return flow_results
"""


@flow(name="crewai_mcp_poc_flow_disabled", log_prints=True)
async def crewai_mcp_poc_flow(output_dir: Optional[str] = None) -> Dict[str, Any]:
    """DISABLED Flow - CrewAI MCP dependency conflicts"""
    logger = get_run_logger()
    logger.info("❌ CrewAI MCP Flow is disabled due to dependency conflicts")

    return {
        "flow_name": "crewai_mcp_poc_flow",
        "status": "disabled",
        "reason": "crewai-tools[mcp] dependency conflicts with chromadb versions",
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    # For local testing - DISABLED
    asyncio.run(crewai_mcp_poc_flow())
