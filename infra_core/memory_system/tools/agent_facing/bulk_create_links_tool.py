"""
BulkCreateLinksTool: Agent-facing tool for creating multiple memory block links in a single operation.

This tool provides efficient bulk creation of block links with independent success tracking,
allowing partial success scenarios where some links succeed and others fail.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
import logging

from ...schemas.common import BlockIdType, RelationType
from ..base.cogni_tool import CogniTool
from ..helpers.block_validation import ensure_block_exists
from ...link_manager import LinkError
from ...relation_registry import get_inverse_relation, is_valid_relation

# Setup logging
logger = logging.getLogger(__name__)


class LinkSpec(BaseModel):
    """Specification for a single link to be created."""

    # Required fields
    from_id: BlockIdType = Field(..., description="ID of the source block")
    to_id: BlockIdType = Field(..., description="ID of the target block")
    relation: RelationType = Field(..., description="Type of relationship between blocks")

    # Optional fields
    priority: int = Field(0, description="Priority of the link (higher = more important)", ge=0)
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata about the link"
    )
    created_by: Optional[str] = Field(
        None, description="Optional identifier for creator (agent name or user ID)"
    )
    bidirectional: bool = Field(
        False, description="Whether to create an inverse link automatically"
    )

    @validator("relation")
    def validate_relation_type(cls, value):
        """Validate that the relation type is valid."""
        if not is_valid_relation(value):
            raise ValueError(f"Invalid relation type: {value}")
        return value

    @validator("bidirectional")
    def validate_bidirectional_relation(cls, bidirectional, values):
        """Validate that bidirectional links use relations with defined inverses."""
        if bidirectional and "relation" in values:
            from ...relation_registry import RELATION_ALIASES

            relation = values["relation"]
            # Resolve any aliases first (e.g., depends_on -> is_blocked_by)
            canonical_relation = RELATION_ALIASES.get(relation, relation)
            inverse = get_inverse_relation(canonical_relation)
            # Check if the relation has a meaningful inverse (not just returning itself)
            # Relations like "related_to" and "mentions" return themselves as inverse
            if inverse == canonical_relation and canonical_relation not in ["duplicate_of"]:
                raise ValueError(
                    f"Relation '{relation}' does not have a defined inverse and cannot be used bidirectionally"
                )
        return bidirectional


class BulkCreateLinksInput(BaseModel):
    """Input model for bulk creating memory block links."""

    links: List[LinkSpec] = Field(
        ...,
        min_length=1,
        max_length=5000,  # Higher limit for links than blocks
        description="List of link specifications to create",
    )

    # Control options
    stop_on_first_error: bool = Field(
        False,
        description="If True, stop processing on first error. If False, continue and report all results.",
    )
    validate_blocks_exist: bool = Field(
        True, description="Whether to validate that referenced blocks exist before creating links"
    )


class LinkResult(BaseModel):
    """Result for a single link creation."""

    success: bool = Field(..., description="Whether this link was created successfully")
    from_id: BlockIdType = Field(..., description="Source block ID")
    to_id: BlockIdType = Field(..., description="Target block ID")
    relation: str = Field(..., description="Relation type")
    error: Optional[str] = Field(None, description="Error message if creation failed")
    bidirectional: bool = Field(False, description="Whether this was a bidirectional link")
    links_created: int = Field(
        1, description="Number of actual links created (1 or 2 for bidirectional)"
    )
    timestamp: datetime = Field(..., description="When this link creation was attempted")


class BulkCreateLinksOutput(BaseModel):
    """Output model for bulk link creation results."""

    success: bool = Field(
        ..., description="Whether ALL links were created successfully (failed_count == 0)"
    )
    partial_success: bool = Field(
        ..., description="Whether at least one link was created successfully"
    )
    total_links: int = Field(..., description="Total number of link specs attempted")
    successful_links: int = Field(..., description="Number of link specs created successfully")
    failed_links: int = Field(..., description="Number of link specs that failed to create")
    total_actual_links: int = Field(
        ..., description="Total number of actual links created (including bidirectional)"
    )
    results: List[LinkResult] = Field(..., description="Individual results for each link spec")
    active_branch: str = Field(..., description="Current active branch")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="When the bulk operation completed"
    )


def bulk_create_links(input_data: BulkCreateLinksInput, memory_bank) -> BulkCreateLinksOutput:
    """
    Create multiple memory block links with independent success tracking.

    Each link creation is independent - if one fails, others can still succeed.
    This allows for partial success scenarios which are common in bulk operations.

    Args:
        input_data: Input data containing list of link specifications
        memory_bank: StructuredMemoryBank instance for persistence

    Returns:
        BulkCreateLinksOutput containing overall status and individual results
    """
    logger.info(f"Starting bulk creation of {len(input_data.links)} links")

    # Get the LinkManager
    link_manager = getattr(memory_bank, "link_manager", None)
    if not link_manager:
        error_msg = "LinkManager not available on memory bank"
        logger.error(error_msg)
        return BulkCreateLinksOutput(
            success=False,
            partial_success=False,
            total_links=len(input_data.links),
            successful_links=0,
            failed_links=len(input_data.links),
            total_actual_links=0,
            results=[
                LinkResult(
                    success=False,
                    from_id=link_spec.from_id,
                    to_id=link_spec.to_id,
                    relation=link_spec.relation,
                    error=error_msg,
                    timestamp=datetime.now(),
                )
                for link_spec in input_data.links
            ],
            active_branch=memory_bank.dolt_writer.active_branch,
            timestamp=datetime.now(),
        )

    results = []
    successful_count = 0
    failed_count = 0
    total_actual_links_created = 0

    # Validate block existence if requested
    if input_data.validate_blocks_exist:
        logger.info("Validating block existence for all referenced blocks")
        all_block_ids = set()
        for link_spec in input_data.links:
            all_block_ids.add(link_spec.from_id)
            all_block_ids.add(link_spec.to_id)

        for block_id in all_block_ids:
            try:
                ensure_block_exists(block_id, memory_bank)
            except KeyError as e:
                error_msg = f"Block validation failed: {str(e)}"
                logger.error(error_msg)
                return BulkCreateLinksOutput(
                    success=False,
                    partial_success=False,
                    total_links=len(input_data.links),
                    successful_links=0,
                    failed_links=len(input_data.links),
                    total_actual_links=0,
                    results=[
                        LinkResult(
                            success=False,
                            from_id=link_spec.from_id,
                            to_id=link_spec.to_id,
                            relation=link_spec.relation,
                            error=error_msg,
                            timestamp=datetime.now(),
                        )
                        for link_spec in input_data.links
                    ],
                    active_branch=memory_bank.dolt_writer.active_branch,
                    timestamp=datetime.now(),
                )

    for i, link_spec in enumerate(input_data.links):
        if logger.isEnabledFor(logging.DEBUG):  # Gate debug logging
            logger.debug(
                f"Processing link {i + 1}/{len(input_data.links)}: {link_spec.from_id} -> {link_spec.to_id} ({link_spec.relation})"
            )

        try:
            # Prepare links for bulk_upsert
            links_to_create = [
                (link_spec.from_id, link_spec.to_id, link_spec.relation, link_spec.metadata)
            ]

            # Add inverse link if bidirectional
            if link_spec.bidirectional:
                inverse_relation = get_inverse_relation(link_spec.relation)
                if inverse_relation and inverse_relation != link_spec.relation:
                    links_to_create.append(
                        (link_spec.to_id, link_spec.from_id, inverse_relation, link_spec.metadata)
                    )

            # Create the links using bulk_upsert
            created_links = link_manager.bulk_upsert(links_to_create)

            # Create result record
            link_result = LinkResult(
                success=True,
                from_id=link_spec.from_id,
                to_id=link_spec.to_id,
                relation=link_spec.relation,
                bidirectional=link_spec.bidirectional,
                links_created=len(created_links),
                timestamp=datetime.now(),
            )

            results.append(link_result)
            successful_count += 1
            total_actual_links_created += len(created_links)

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Successfully created {len(created_links)} link(s) for spec {i + 1}")

        except LinkError as e:
            # Handle LinkManager-specific errors
            error_msg = f"Link creation failed: {str(e)}"
            logger.warning(f"Failed to create link {i + 1}: {error_msg}")

            link_result = LinkResult(
                success=False,
                from_id=link_spec.from_id,
                to_id=link_spec.to_id,
                relation=link_spec.relation,
                error=error_msg,
                bidirectional=link_spec.bidirectional,
                timestamp=datetime.now(),
            )

            results.append(link_result)
            failed_count += 1

            # Stop on first error if requested
            if input_data.stop_on_first_error:
                logger.info("Stopping bulk operation on first error as requested")
                break

        except Exception as e:
            # Handle unexpected errors during link processing
            error_msg = f"Unexpected error processing link {i + 1}: {str(e)}"
            logger.error(error_msg, exc_info=True)

            link_result = LinkResult(
                success=False,
                from_id=link_spec.from_id,
                to_id=link_spec.to_id,
                relation=link_spec.relation,
                error=error_msg,
                bidirectional=link_spec.bidirectional,
                timestamp=datetime.now(),
            )

            results.append(link_result)
            failed_count += 1

            # Stop on first error if requested
            if input_data.stop_on_first_error:
                logger.info("Stopping bulk operation on unexpected error as requested")
                break

    # Clear success semantics
    overall_success = failed_count == 0  # True only if ALL links succeeded
    partial_success = successful_count > 0  # True if ANY links succeeded

    logger.info(
        f"Bulk link creation completed: {successful_count} successful, {failed_count} failed, "
        f"{len(input_data.links) - len(results)} skipped, {total_actual_links_created} actual links created"
    )

    return BulkCreateLinksOutput(
        success=overall_success,
        partial_success=partial_success,
        total_links=len(input_data.links),
        successful_links=successful_count,
        failed_links=failed_count,
        total_actual_links=total_actual_links_created,
        results=results,
        active_branch=memory_bank.dolt_writer.active_branch,
        timestamp=datetime.now(),
    )


# Create the tool instance
bulk_create_links_tool = CogniTool(
    name="BulkCreateLinks",
    description="Create multiple memory block links in a single operation with independent success tracking",
    input_model=BulkCreateLinksInput,
    output_model=BulkCreateLinksOutput,
    function=bulk_create_links,
    memory_linked=True,
)
