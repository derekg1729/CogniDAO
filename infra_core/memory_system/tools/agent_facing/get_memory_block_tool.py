"""
GetMemoryBlockTool: Agent-facing tool for retrieving a specific memory block by ID.

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
    """Input model for retrieving a specific memory block by ID.
    Inherits from the core input model."""

    pass


class GetMemoryBlockOutput(CoreGetMemoryBlockOutput):
    """Output model for the get memory block operation.
    Inherits from the core output model."""

    pass


def get_memory_block(input_data: GetMemoryBlockInput, memory_bank) -> GetMemoryBlockOutput:
    """
    Retrieve a specific memory block by ID.
    This is a thin wrapper around the core function that provides consistent error handling.

    Args:
        input_data: GetMemoryBlockInput containing the block_id
        memory_bank: An instance of StructuredMemoryBank

    Returns:
        GetMemoryBlockOutput with the retrieved block or error information
    """
    logger.debug(f"Agent-facing get_memory_block called for ID: {input_data.block_id}")

    try:
        # Simply pass through to the core implementation
        result = get_memory_block_core(input_data, memory_bank)
        return GetMemoryBlockOutput(**result.model_dump())
    except Exception as e:
        error_msg = f"Error in get_memory_block wrapper: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return GetMemoryBlockOutput(
            success=False, block=None, error=error_msg, timestamp=datetime.now()
        )


# Create the tool instance
get_memory_block_tool = CogniTool(
    name="GetMemoryBlock",
    description="Retrieves a specific memory block by its unique ID.",
    input_model=GetMemoryBlockInput,
    output_model=GetMemoryBlockOutput,
    function=get_memory_block,
    memory_linked=True,
)
