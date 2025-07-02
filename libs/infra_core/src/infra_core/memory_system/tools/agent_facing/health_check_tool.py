"""
HealthCheckTool: Agent-facing tool for checking system health status.

This tool provides a simple health check interface that verifies memory bank
and link manager initialization without requiring any input parameters.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.tools.base.cogni_tool import CogniTool

# Setup logging
logger = logging.getLogger(__name__)


class HealthCheckInput(BaseModel):
    """Input model for health check tool."""

    # No input parameters needed for health check


class HealthCheckOutput(BaseModel):
    """Output model for health check tool."""

    healthy: bool = Field(..., description="Whether all systems are healthy")
    memory_bank_status: str = Field(..., description="Status of memory bank initialization")
    link_manager_status: str = Field(..., description="Status of link manager initialization")
    timestamp: str = Field(..., description="ISO format timestamp of the health check")


def health_check_core(
    input_data: HealthCheckInput, memory_bank: Optional[StructuredMemoryBank] = None
) -> HealthCheckOutput:
    """
    Core health check function that verifies system component status.

    Args:
        input_data: Empty input model (no parameters needed)
        memory_bank: Optional memory bank (for non-memory-linked usage)

    Returns:
        HealthCheckOutput with system status information
    """
    try:
        # Import here to avoid circular imports
        from services.mcp_server.app.mcp_server import (
            get_memory_bank,
            get_link_manager,
            get_pm_links,
        )

        # Check memory bank status
        memory_bank_instance = get_memory_bank()
        memory_bank_ok = memory_bank_instance is not None

        # Check link manager status
        link_manager_instance = get_link_manager()
        pm_links_instance = get_pm_links()
        link_manager_ok = link_manager_instance is not None and pm_links_instance is not None

        # Overall health status
        overall_healthy = memory_bank_ok and link_manager_ok

        return HealthCheckOutput(
            healthy=overall_healthy,
            memory_bank_status="initialized" if memory_bank_ok else "not_initialized",
            link_manager_status="initialized" if link_manager_ok else "not_initialized",
            timestamp=datetime.now().isoformat(),
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheckOutput(
            healthy=False,
            memory_bank_status="error",
            link_manager_status="error",
            timestamp=datetime.now().isoformat(),
        )


# Create the CogniTool instance
health_check_tool = CogniTool(
    name="HealthCheck",
    description="Check if the memory bank is initialized",
    input_model=HealthCheckInput,
    output_model=HealthCheckOutput,
    function=health_check_core,
    memory_linked=False,  # Health check doesn't need memory bank parameter
)
