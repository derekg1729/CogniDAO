"""
GetMemoryLinksTool: Agent-facing tool for retrieving memory links.

This tool provides a simple interface for agents to retrieve memory links
with optional filtering. It wraps the core get_memory_links function for consistent
error handling and format.
"""

from datetime import datetime
import logging

from ..base.cogni_tool import CogniTool
from ..memory_core.get_memory_links_core import (
    get_memory_links_core,
    GetMemoryLinksInput as CoreGetMemoryLinksInput,
    GetMemoryLinksOutput as CoreGetMemoryLinksOutput,
)

# Setup logging
logger = logging.getLogger(__name__)


class GetMemoryLinksInput(CoreGetMemoryLinksInput):
    """Input model for retrieving memory links.
    Inherits from the core input model with full filtering capabilities."""

    pass


class GetMemoryLinksOutput(CoreGetMemoryLinksOutput):
    """Output model for get memory links operation.
    Inherits from the core output model."""

    pass


def get_memory_links(input_data: GetMemoryLinksInput, memory_bank) -> GetMemoryLinksOutput:
    """
    Retrieve memory links with optional filtering.
    This is a thin wrapper around the core function that provides consistent error handling.

    Args:
        input_data: GetMemoryLinksInput containing the retrieval parameters
        memory_bank: An instance of StructuredMemoryBank

    Returns:
        GetMemoryLinksOutput with the retrieved links or error information
    """
    logger.debug(f"Agent-facing get_memory_links called with input: {input_data}")

    try:
        # Simply pass through to the core implementation
        result = get_memory_links_core(input_data, memory_bank)
        return GetMemoryLinksOutput(**result.model_dump())
    except Exception as e:
        error_msg = f"Agent-facing get_memory_links failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return GetMemoryLinksOutput(success=False, error=error_msg, timestamp=datetime.now())


# Convenience function for simple link retrieval (backward compatibility)
def get_memory_links_tool(
    relation_filter: str = None, memory_bank=None, **kwargs
) -> GetMemoryLinksOutput:
    """
    Convenience function for link retrieval with filters.

    Args:
        relation_filter: Filter by specific relation type
        memory_bank: Memory bank instance
        **kwargs: Additional parameters passed to GetMemoryLinksInput

    Returns:
        GetMemoryLinksOutput with the retrieved links
    """
    try:
        # Use kwargs directly for filtering
        input_data = GetMemoryLinksInput(relation_filter=relation_filter, **kwargs)
        return get_memory_links(input_data, memory_bank)
    except Exception as e:
        error_msg = f"Validation error: {str(e)}"
        logger.error(error_msg)
        return GetMemoryLinksOutput(success=False, error=error_msg, timestamp=datetime.now())


# Create the tool instance
get_memory_links_tool_instance = CogniTool(
    name="GetMemoryLinks",
    description="Retrieves memory links with optional filtering parameters.",
    input_model=GetMemoryLinksInput,
    output_model=GetMemoryLinksOutput,
    function=get_memory_links,
    memory_linked=True,
)
