"""
Create Block Link Tool - Agent-Facing Implementation.

This tool allows agents to create links between memory blocks using
human-readable relation names and with helpful error messages.
"""

from typing import Dict, List, Optional, Any
from uuid import UUID
from pydantic import BaseModel, Field, validator
from datetime import datetime

import logging

from ..base.cogni_tool import CogniTool
from infra_core.memory_system.tools.memory_core.create_block_link_tool import (
    create_block_link,
    CreateBlockLinkInput,
)
from ..helpers.relation_helpers import (
    resolve_relation_alias,
    validate_bidirectional_relation,
    get_human_readable_name,
)

# Setup logging
logger = logging.getLogger(__name__)


class CreateBlockLinkAgentInput(BaseModel):
    """
    Agent-friendly input model for creating a block link.

    This model uses more intuitive field names and provides
    validation with helpful error messages.
    """

    source_block_id: str = Field(
        ...,
        description="ID of the source block (the 'from' block)",
    )

    target_block_id: str = Field(
        ...,
        description="ID of the target block (the 'to' block)",
    )

    relation: str = Field(
        ...,
        description=(
            "Type of relationship between blocks. Can be a canonical relation type "
            "(e.g., 'depends_on', 'is_blocked_by'), a human-readable form ('depends on'), "
            "or an alias ('blocked_by')"
        ),
    )

    bidirectional: bool = Field(
        False,
        description=(
            "Whether to create the inverse relationship automatically. "
            "For example, if relation is 'depends_on' and bidirectional=True, "
            "it will also create the inverse 'blocks' relation."
        ),
    )

    priority: int = Field(
        0,
        description="Priority of the link (higher numbers = more important)",
        ge=0,
        le=100,
    )

    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata about the link (key-value pairs)",
    )

    @validator("source_block_id", "target_block_id")
    def validate_uuid_format(cls, value):
        """Validate that IDs are in UUID format."""
        try:
            UUID(value)
            return value
        except ValueError:
            raise ValueError(f"Invalid UUID format: {value}")

    @validator("relation")
    def validate_relation_type(cls, value):
        """Validate and normalize the relation type."""
        try:
            # This will raise ValueError if relation is invalid
            canonical_relation = resolve_relation_alias(value)
            return canonical_relation
        except ValueError as e:
            raise ValueError(str(e))

    @validator("bidirectional", "relation")
    def validate_bidirectional_setting(cls, bidirectional, values):
        """Validate that bidirectional links use relations with defined inverses."""
        if bidirectional and "relation" in values:
            try:
                validate_bidirectional_relation(values["relation"])
            except ValueError as e:
                raise ValueError(str(e))
        return bidirectional


class CreateBlockLinkAgentOutput(BaseModel):
    """
    Agent-friendly output model for block link creation result.

    This model presents results in an easy-to-understand format for agents.
    """

    success: bool = Field(
        ...,
        description="Whether the operation was successful",
    )

    message: str = Field(
        ...,
        description="Human-readable result message",
    )

    created_links: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Details of the created links in a simplified format",
    )

    error_details: Optional[str] = Field(
        None,
        description="Detailed error information if operation failed",
    )


def create_block_link_agent(
    input_data: CreateBlockLinkAgentInput, memory_bank
) -> CreateBlockLinkAgentOutput:
    """
    Agent-facing tool to create a link between two memory blocks.

    Args:
        input_data: Input data containing link creation parameters
        memory_bank: Memory system interface

    Returns:
        CreateBlockLinkAgentOutput with human-friendly results
    """
    logger.info(
        f"Agent creating link: {input_data.source_block_id} -> {input_data.target_block_id} "
        f"with relation '{input_data.relation}' (bidirectional={input_data.bidirectional})"
    )

    try:
        # Use the input data directly (already validated by auto-generator)
        agent_input = input_data

        # Create core input model
        core_input = CreateBlockLinkInput(
            from_id=agent_input.source_block_id,
            to_id=agent_input.target_block_id,
            relation=agent_input.relation,  # Already resolved by validator
            priority=agent_input.priority,
            link_metadata=agent_input.metadata,
            is_bidirectional=agent_input.bidirectional,
        )

        # Call core tool
        result = create_block_link(core_input, memory_bank)

        if result.success:
            # Format successful result
            human_readable_relation = get_human_readable_name(agent_input.relation)

            # Build links for display
            simplified_links = []
            for link in result.links:
                # Default values if we can't determine them
                from_id = input_data.source_block_id
                to_id = input_data.target_block_id
                rel = input_data.relation
                created_at = datetime.now()

                # Try to extract values from the link
                try:
                    # First check for from_id (which might be stored as _from_id for tests)
                    if hasattr(link, "_from_id"):
                        from_id = getattr(link, "_from_id")
                    # For to_id, we should have this always
                    if hasattr(link, "to_id"):
                        to_id = str(link.to_id)
                    # For relation
                    if hasattr(link, "relation"):
                        rel = get_human_readable_name(link.relation)
                    # For created_at
                    if hasattr(link, "created_at"):
                        created_at = link.created_at
                except Exception as e:
                    logger.warning(f"Error extracting link data: {e}")

                # Determine from_id if not explicitly set
                # For bidirectional links, we need to infer based on the to_id
                if not hasattr(link, "_from_id"):
                    # If link.to_id matches the target_block_id, then from_id is source_block_id
                    # Otherwise, it's the inverse link from target_block_id to source_block_id
                    if str(to_id) == input_data.target_block_id:
                        from_id = input_data.source_block_id
                    else:
                        from_id = input_data.target_block_id

                # Create the link dict
                link_dict = {
                    "from_id": from_id,
                    "to_id": to_id,
                    "relation": rel,
                    "created_at": created_at.isoformat() if created_at else None,
                }
                simplified_links.append(link_dict)

            # Generate appropriate message
            if agent_input.bidirectional:
                message = (
                    f"Successfully created bidirectional link between blocks. "
                    f"Primary relation: '{human_readable_relation}'"
                )
            else:
                message = (
                    f"Successfully created link from source to target "
                    f"with relation '{human_readable_relation}'"
                )

            return CreateBlockLinkAgentOutput(
                success=True,
                message=message,
                created_links=simplified_links,
            )
        else:
            # Format error result with friendly message
            error_type = result.error_type.upper() if result.error_type else "UNKNOWN_ERROR"

            # Map error types to friendly messages
            error_messages = {
                "VALIDATION_ERROR": "Invalid link parameters",
                "NOT_FOUND": "One or both blocks don't exist",
                "CYCLE_DETECTED": "Creating this link would create a dependency cycle",
                "DUPLICATE_LINK": "This link already exists",
                "UNKNOWN_ERROR": "Failed to create link",
            }

            # Use the error message from the mapping or fall back to "Failed to create link"
            message = error_messages.get(error_type, "Failed to create link")

            return CreateBlockLinkAgentOutput(
                success=False,
                message=message,
                error_details=result.error,
            )

    except ValueError as e:
        # Handle validation errors (including UUID and relation validation)
        logger.warning(f"Validation error in agent create_block_link: {e}")
        return CreateBlockLinkAgentOutput(
            success=False,
            message="Invalid parameters",
            error_details=str(e),
        )
    except Exception as e:
        # Handle any other unexpected errors
        logger.error(f"Unexpected error in agent create_block_link: {e}", exc_info=True)
        return CreateBlockLinkAgentOutput(
            success=False,
            message="An unexpected error occurred",
            error_details=str(e),
        )


# Create the tool instance
create_block_link_tool = CogniTool(
    name="CreateBlockLink",
    description="Create a link between memory blocks, enabling task dependencies, parent-child relationships, and other connections",
    input_model=CreateBlockLinkAgentInput,
    output_model=CreateBlockLinkAgentOutput,
    function=create_block_link_agent,
    memory_linked=True,
)
