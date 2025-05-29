"""
GetMemoryBlockTool: Agent-facing tool for retrieving memory blocks by ID.

This tool provides a simple interface for agents to retrieve memory blocks
directly by their ID. It wraps the core get_memory_block function for consistent
error handling and format.
"""

from datetime import datetime
import logging

from ..base.cogni_tool import CogniTool
from ..memory_core.get_memory_block_core import (
    get_memory_block_core,
    GetMemoryBlockInput as CoreGetMemoryBlockInput,
    GetMemoryBlockOutput as CoreGetMemoryBlockOutput,
)

# Setup logging
logger = logging.getLogger(__name__)


class GetMemoryBlockInput(CoreGetMemoryBlockInput):
    """Input model for retrieving memory blocks.
    Inherits from the core input model with full filtering capabilities."""

    pass


class GetMemoryBlockOutput(CoreGetMemoryBlockOutput):
    """Output model for get memory block operation.
    Inherits from the core output model."""

    pass


def get_memory_block(input_data: GetMemoryBlockInput, memory_bank) -> GetMemoryBlockOutput:
    """
    Retrieve memory blocks by ID(s) or with filtering.
    This is a thin wrapper around the core function that provides consistent error handling.

    Args:
        input_data: GetMemoryBlockInput containing the retrieval parameters
        memory_bank: An instance of StructuredMemoryBank

    Returns:
        GetMemoryBlockOutput with the retrieved blocks or error information
    """
    logger.debug(f"Agent-facing get_memory_block called with input: {input_data}")

    try:
        # Simply pass through to the core implementation
        result = get_memory_block_core(input_data, memory_bank)
        return GetMemoryBlockOutput(**result.model_dump())
    except Exception as e:
        error_msg = f"Agent-facing get_memory_block failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return GetMemoryBlockOutput(success=False, error=error_msg, timestamp=datetime.now())


# Convenience function for single block retrieval by ID (backward compatibility)
def get_memory_block_tool(block_id: str = None, memory_bank=None, **kwargs) -> GetMemoryBlockOutput:
    """
    Convenience function for single block retrieval by ID.

    Args:
        block_id: ID of the block to retrieve
        memory_bank: Memory bank instance
        **kwargs: Additional parameters passed to GetMemoryBlockInput

    Returns:
        GetMemoryBlockOutput with the retrieved block(s)
    """
    try:
        if block_id:
            # Convert single ID to list for consistent API
            input_data = GetMemoryBlockInput(block_ids=[block_id], **kwargs)
        else:
            # Use kwargs directly for filtering
            input_data = GetMemoryBlockInput(**kwargs)
        return get_memory_block(input_data, memory_bank)
    except Exception as e:
        error_msg = f"Validation error: {str(e)}"
        logger.error(error_msg)
        return GetMemoryBlockOutput(success=False, error=error_msg, timestamp=datetime.now())


# Create the tool instance
get_memory_block_tool_instance = CogniTool(
    name="GetMemoryBlock",
    description="Retrieves memory blocks by ID(s) or with filtering parameters.",
    input_model=GetMemoryBlockInput,
    output_model=GetMemoryBlockOutput,
    function=get_memory_block,
    memory_linked=True,
)
