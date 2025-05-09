"""
CreateDocMemoryBlockTool: Agent-facing tool for creating 'doc' type memory blocks.

This tool provides a simplified interface for agents to create documentation blocks,
ensuring correct type, metadata structure, and schema validation.
"""

from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from ...schemas.memory_block import ConfidenceScore
from ...schemas.common import BlockLink
from ..base.cogni_tool import CogniTool
from ..memory_core.create_memory_block_tool import (
    create_memory_block,
    CreateMemoryBlockInput as CoreCreateMemoryBlockInput,
    CreateMemoryBlockOutput as CoreCreateMemoryBlockOutput,
)

# Setup logging
logger = logging.getLogger(__name__)


class CreateDocMemoryBlockInput(BaseModel):
    """Input model for creating a 'doc' type memory block."""

    title: str = Field(..., description="Title of the document, will be stored in metadata.")
    content: str = Field(..., description="Main content/text of the document.")

    # Fields from DocMetadata
    audience: Optional[str] = Field(None, description="Intended audience for the document.")
    section: Optional[str] = Field(None, description="Section or category the document belongs to.")
    doc_version: Optional[str] = Field(
        None, description="Version of the documentation (metadata field 'version')."
    )  # Renamed to avoid conflict with Pydantic's model_version
    last_reviewed: Optional[datetime] = Field(
        None, description="When the document was last reviewed."
    )
    doc_format: Optional[Literal["markdown", "html", "text", "code"]] = Field(
        None,
        description="Format of the document content (metadata field 'format').",  # Renamed
    )
    completed: Optional[bool] = Field(
        False, description="Whether the document is complete/finalized."
    )

    # Common fields from CoreCreateMemoryBlockInput (excluding 'type' and 'metadata' which are handled)
    source_file: Optional[str] = Field(None, description="Optional source file or markdown name.")
    tags: List[str] = Field(
        default_factory=list, max_length=20, description="Optional tags for filtering."
    )
    state: Optional[Literal["draft", "published", "archived"]] = Field(
        "draft", description="Initial state of the block."
    )
    visibility: Optional[Literal["internal", "public", "restricted"]] = Field(
        "internal", description="Visibility level of the block."
    )
    confidence: Optional[ConfidenceScore] = Field(
        None, description="Optional confidence scores for the block."
    )
    created_by: Optional[str] = Field(
        "agent", description="Identifier for creator (agent name or user ID)."
    )
    links: Optional[List[BlockLink]] = Field(
        default_factory=list, description="Optional links to other blocks."
    )


class CreateDocMemoryBlockOutput(CoreCreateMemoryBlockOutput):
    """Output model for creating a 'doc' memory block. Inherits from core output."""

    pass


def create_doc_memory_block(
    input_data: CreateDocMemoryBlockInput, memory_bank
) -> CreateDocMemoryBlockOutput:
    """
    Create a 'doc' type memory block with structured metadata.
    """
    logger.debug(f"Attempting to create 'doc' memory block with title: {input_data.title}")

    # Prepare metadata for the 'doc' block
    doc_specific_metadata = {
        "title": input_data.title,
        "audience": input_data.audience,
        "section": input_data.section,
        "version": input_data.doc_version,  # maps to DocMetadata.version
        "last_reviewed": input_data.last_reviewed,
        "format": input_data.doc_format,  # maps to DocMetadata.format
        "completed": input_data.completed,
    }
    # Filter out None values from doc_specific_metadata to keep it clean
    final_metadata = {k: v for k, v in doc_specific_metadata.items() if v is not None}

    # Add x_tool_id to identify this agent-facing tool
    final_metadata["x_tool_id"] = "CreateDocMemoryBlockTool"

    core_input = CoreCreateMemoryBlockInput(
        type="doc",  # Automatically set type to "doc"
        text=input_data.content,
        metadata=final_metadata,
        source_file=input_data.source_file,
        tags=input_data.tags,
        state=input_data.state,
        visibility=input_data.visibility,
        confidence=input_data.confidence,
        created_by=input_data.created_by,
        links=input_data.links,
    )

    try:
        result = create_memory_block(core_input, memory_bank)
        # The result is already CoreCreateMemoryBlockOutput, which CreateDocMemoryBlockOutput inherits from
        return CreateDocMemoryBlockOutput(**result.model_dump())
    except Exception as e:
        error_msg = f"Error in create_doc_memory_block wrapper: {str(e)}"
        logger.error(error_msg, exc_info=True)
        # Ensure a consistent error response structure
        return CreateDocMemoryBlockOutput(
            success=False,
            error=error_msg,
            timestamp=datetime.now(),  # Core tool's error response also includes timestamp
        )


# Create the tool instance
create_doc_memory_block_tool = CogniTool(
    name="CreateDocMemoryBlock",
    description="Creates a new 'doc' type memory block with specific document metadata (title, version, etc.).",
    input_model=CreateDocMemoryBlockInput,
    output_model=CreateDocMemoryBlockOutput,
    function=create_doc_memory_block,
    memory_linked=True,
)
