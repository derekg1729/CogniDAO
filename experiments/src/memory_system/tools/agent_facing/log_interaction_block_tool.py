"""
LogInteractionBlockTool: Agent-facing tool for logging interactions as memory blocks.

This tool provides a clean interface for agents to log interactions while maintaining
proper metadata, tagging, and schema validation.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from ...tools.base.cogni_tool import CogniTool
from ...tools.memory_core.create_memory_block_tool import (
    create_memory_block,
    CreateMemoryBlockInput,
)
from memory_system.schemas.metadata.log import LogMetadata

# Setup logging
logger = logging.getLogger(__name__)


class LogInteractionBlockInput(BaseModel):
    """Input model for logging an interaction."""

    input_text: str = Field(..., description="The input text from the interaction")
    output_text: str = Field(..., description="The output text from the interaction")
    session_id: Optional[str] = Field(None, description="Optional session ID for tracking")
    model: Optional[str] = Field(None, description="Optional model name/version")
    token_count: Optional[Dict[str, int]] = Field(None, description="Optional token counts")
    latency_ms: Optional[float] = Field(None, description="Optional latency in milliseconds")
    tags: Optional[list[str]] = Field(default_factory=list, description="Optional additional tags")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Optional additional metadata"
    )
    parent_block: Optional[str] = Field(
        None, description="Optional ID of the parent block (e.g., task, interaction)"
    )
    created_by: Optional[str] = Field(
        "agent", description="Identifier for creator (agent name or user ID)"
    )


class LogInteractionBlockOutput(BaseModel):
    """Output model for interaction logging results."""

    success: bool = Field(..., description="Whether the logging was successful")
    id: Optional[str] = Field(None, description="ID of the created block if successful")
    error: Optional[str] = Field(None, description="Error message if logging failed")
    timestamp: datetime = Field(
        ..., description="Timestamp of the logging attempt or successful creation"
    )


def log_interaction_block(
    input_data: LogInteractionBlockInput, memory_bank
) -> LogInteractionBlockOutput:
    """
    Log an interaction as a memory block with enhanced metadata and tagging.

    Args:
        input_data: Input data for the interaction
        memory_bank: StructuredMemoryBank instance for persistence

    Returns:
        LogInteractionBlockOutput containing logging status, ID, error message, and timestamp
    """
    # Capture consistent timestamp for this logging attempt
    log_timestamp = datetime.now()

    try:
        # Format block text
        block_text = f"[Interaction Record]\nInput: {input_data.input_text}\nOutput: {input_data.output_text}"

        # Prepare tags and metadata
        tags = input_data.tags or []
        if input_data.session_id:
            tags.append(f"session:{input_data.session_id}")
        # Use consistent timestamp for date tag
        tags.append(f"date:{log_timestamp.strftime('%Y%m%d')}")
        tags.append("type:log")

        log_metadata = LogMetadata(
            # Use consistent timestamp and input creator
            timestamp=log_timestamp,
            agent=input_data.created_by,
            input=input_data.input_text,
            output=input_data.output_text,
            tool="LogInteractionBlockTool",
            session_id=input_data.session_id,
            parent_block=input_data.parent_block,
        )

        metadata = log_metadata.model_dump()

        if input_data.model:
            metadata["model"] = input_data.model
        if input_data.token_count:
            metadata["token_count"] = input_data.token_count
        if input_data.latency_ms:
            metadata["latency_ms"] = input_data.latency_ms
        if input_data.metadata:
            metadata.update(input_data.metadata)

        # Create the input for create_memory_block
        block_input = CreateMemoryBlockInput(
            type="log",
            text=block_text,
            tags=tags,
            metadata=metadata,
            state="draft",
            visibility="internal",
            created_by=input_data.created_by,
        )

        # Log the input for debugging
        logger.debug(f"Creating memory block with input: {block_input.model_dump()}")

        # Use the core create_memory_block function
        result = create_memory_block(block_input, memory_bank)

        if result.success:
            logger.info(f"Successfully created memory block with ID: {result.id}")
            # Use the actual block creation timestamp from the result
            return LogInteractionBlockOutput(success=True, id=result.id, timestamp=result.timestamp)
        else:
            error_msg = result.error or "Unknown error creating memory block"
            logger.error(f"Failed to create memory block: {error_msg}")
            return LogInteractionBlockOutput(
                success=False,
                error=error_msg,
                timestamp=log_timestamp,  # Use consistent timestamp for failure
            )

    except Exception as e:
        error_msg = f"Error logging interaction: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return LogInteractionBlockOutput(success=False, error=error_msg, timestamp=log_timestamp)


# Create the tool instance
log_interaction_block_tool = CogniTool(
    name="LogInteractionBlock",
    description="Logs an interaction as a memory block with enhanced metadata and tagging",
    input_model=LogInteractionBlockInput,
    output_model=LogInteractionBlockOutput,
    function=log_interaction_block,
    memory_linked=True,
)
