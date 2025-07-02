"""
CreateMemoryBlockTool: Agent-facing tool for creating different types of general memory blocks.

This tool provides a unified interface for creating doc, knowledge, and log memory blocks,
ensuring correct type, metadata structure, and schema validation.
"""

from typing import Optional, List, Literal, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from ...schemas.common import BlockIdType
from ..base.cogni_tool import CogniTool
from ..memory_core.create_memory_block_tool import (
    create_memory_block,
    CreateMemoryBlockInput as CoreCreateMemoryBlockInput,
)

logger = logging.getLogger(__name__)


class CreateMemoryBlockAgentInput(BaseModel):
    """Input schema for creating general memory blocks (doc, knowledge, log)."""

    # Required fields
    type: Literal["doc", "knowledge", "log"] = Field(
        ..., description="Type of memory block to create"
    )
    content: str = Field(..., description="Main content/text of the memory block")

    # Namespace field for multi-tenant support
    namespace_id: str = Field(
        "legacy", description="Namespace ID for multi-tenant organization (defaults to 'legacy')"
    )

    # Common optional fields (available for all types via BaseUserMetadata)
    title: Optional[str] = Field(None, description="Title of the memory block")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tags for categorization")

    # Doc-specific fields
    audience: Optional[str] = Field(None, description="Target audience for doc blocks")
    section: Optional[str] = Field(None, description="Section or category for doc blocks")
    doc_version: Optional[str] = Field(None, description="Version for doc blocks")
    completed: Optional[bool] = Field(None, description="Completion status for doc blocks")

    # Knowledge-specific fields
    subject: Optional[str] = Field(
        None, description="Primary subject or domain for knowledge blocks"
    )
    keywords: Optional[List[str]] = Field(None, description="Keywords for knowledge blocks")
    source: Optional[str] = Field(None, description="Source of the knowledge")
    confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Confidence level (0.0 to 1.0)"
    )

    # Log-specific fields
    log_level: Optional[Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]] = Field(
        None, description="Severity level for log blocks"
    )
    component: Optional[str] = Field(None, description="System component for log blocks")
    input_text: Optional[str] = Field(None, description="Input text for log blocks")
    output_text: Optional[str] = Field(None, description="Output text for log blocks")
    model: Optional[str] = Field(None, description="Model name/version for log blocks")
    token_count: Optional[Dict[str, int]] = Field(None, description="Token counts for log blocks")
    latency_ms: Optional[float] = Field(None, description="Latency in milliseconds for log blocks")
    event_timestamp: Optional[datetime] = Field(None, description="Event timestamp for log blocks")

    # System fields (optional overrides)
    x_agent_id: Optional[str] = Field(None, description="Agent ID override")
    x_tool_id: Optional[str] = Field(None, description="Tool ID override")
    x_parent_block_id: Optional[BlockIdType] = Field(None, description="Parent block ID")
    x_session_id: Optional[str] = Field(None, description="Session ID")

    # Additional metadata
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata"
    )


class CreateMemoryBlockAgentOutput(BaseModel):
    """Output schema for CreateMemoryBlock tool."""

    success: bool = Field(..., description="Whether the creation was successful")
    id: Optional[BlockIdType] = Field(None, description="ID of the created memory block")
    block_type: str = Field(..., description="Type of the created block")
    active_branch: str = Field(..., description="Current active branch")
    error: Optional[str] = Field(None, description="Error message if creation failed")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="When the operation completed"
    )


def create_memory_block_agent(
    input_data: CreateMemoryBlockAgentInput, memory_bank
) -> CreateMemoryBlockAgentOutput:
    """
    Agent-facing wrapper for creating general memory blocks.

    This function handles the conversion from agent input to core memory block creation,
    mapping type-specific metadata fields appropriately.
    """
    try:
        # Prepare type-specific metadata
        metadata = {}

        # Add type-specific metadata based on block type
        if input_data.type == "doc":
            # Doc-specific fields
            if input_data.title is not None:
                metadata["title"] = input_data.title
            if input_data.audience is not None:
                metadata["audience"] = input_data.audience
            if input_data.section is not None:
                metadata["section"] = input_data.section
            if input_data.doc_version is not None:
                metadata["version"] = input_data.doc_version  # Maps to DocMetadata.version
            if input_data.completed is not None:
                metadata["completed"] = input_data.completed

        elif input_data.type == "knowledge":
            # Knowledge-specific fields
            if input_data.title is not None:
                metadata["title"] = input_data.title
            if input_data.subject is not None:
                metadata["subject"] = input_data.subject
            if input_data.keywords is not None:
                metadata["keywords"] = input_data.keywords
            if input_data.source is not None:
                metadata["source"] = input_data.source
            if input_data.confidence is not None:
                metadata["confidence"] = input_data.confidence

        elif input_data.type == "log":
            # Log-specific fields - DON'T include title since logs shouldn't need user titles
            if input_data.log_level is not None:
                metadata["log_level"] = input_data.log_level
            if input_data.component is not None:
                metadata["component"] = input_data.component
            if input_data.input_text is not None:
                metadata["input_text"] = input_data.input_text
            if input_data.output_text is not None:
                metadata["output_text"] = input_data.output_text
            if input_data.model is not None:
                metadata["model"] = input_data.model
            if input_data.token_count is not None:
                metadata["token_count"] = input_data.token_count
            if input_data.latency_ms is not None:
                metadata["latency_ms"] = input_data.latency_ms
            if input_data.event_timestamp is not None:
                metadata["event_timestamp"] = input_data.event_timestamp

        # Add system metadata
        metadata["x_tool_id"] = input_data.x_tool_id or "CreateMemoryBlockTool"
        if input_data.x_agent_id is not None:
            metadata["x_agent_id"] = input_data.x_agent_id
        if input_data.x_parent_block_id is not None:
            metadata["x_parent_block_id"] = input_data.x_parent_block_id
        if input_data.x_session_id is not None:
            metadata["x_session_id"] = input_data.x_session_id

        # Add any additional metadata
        if input_data.metadata:
            metadata.update(input_data.metadata)

        # Create the core input
        core_input = CoreCreateMemoryBlockInput(
            type=input_data.type,
            text=input_data.content,
            namespace_id=input_data.namespace_id,
            tags=input_data.tags or [],
            metadata=metadata,
        )

        # Call the core create function
        result = create_memory_block(core_input, memory_bank)

        # Convert core result to agent output
        return CreateMemoryBlockAgentOutput(
            success=result.success,
            id=result.id,
            block_type=input_data.type,
            active_branch=result.active_branch,
            error=result.error,
            timestamp=result.timestamp,
        )

    except Exception as e:
        logger.error(f"Error in create_memory_block_agent wrapper: {e}")
        return CreateMemoryBlockAgentOutput(
            success=False,
            id=None,
            block_type=input_data.type,
            active_branch=memory_bank.dolt_writer.active_branch,
            error=f"Error in create_memory_block_agent wrapper: {str(e)}",
            timestamp=datetime.now(),
        )


# Create the CogniTool instance
create_memory_block_agent_tool = CogniTool(
    name="CreateMemoryBlock",
    description="Create different types of general memory blocks (doc, knowledge, log)",
    input_model=CreateMemoryBlockAgentInput,
    output_model=CreateMemoryBlockAgentOutput,
    function=create_memory_block_agent,
    memory_linked=True,
)
