"""
MemoryBlock: Core data structure for the Memory System.
"""

from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
import uuid
import logging
from pydantic import BaseModel, Field, field_validator

from .common import ConfidenceScore

# Setup logging
logger = logging.getLogger(__name__)


class MemoryBlock(BaseModel):
    """
    The primary data structure for representing a unit of memory in the Cogni system experiment.
    Aligns with the design specified in project-CogniMemorySystem-POC.json.
    Includes schema versioning support (Task 2.0).

    NOTE: As of Property-Schema Split implementation, metadata is stored in the
    block_properties table rather than as a JSON field on this model.
    """

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Globally unique ID for this memory block",
    )
    namespace_id: str = Field(
        default="legacy", description="Foreign key to namespaces.id for multi-tenant organization"
    )
    type: Literal["knowledge", "task", "project", "doc", "interaction", "log", "epic", "bug"] = (
        Field(..., description="Block type used to determine structure and relationships")
    )
    schema_version: Optional[int] = Field(
        None,
        description="Version of the schema this block adheres to (links to node_schemas table)",
    )
    text: str = Field(..., description="Primary content or description of the block")
    state: Optional[Literal["draft", "published", "archived"]] = Field(
        None, description="Current state of the block"
    )
    visibility: Optional[Literal["internal", "public", "restricted"]] = Field(
        None, description="Visibility level of the block"
    )
    block_version: Optional[int] = Field(None, description="Version number of this block")

    # Parent/Child hierarchy fields for Notion-like navigation
    parent_id: Optional[str] = Field(
        None,
        description="ID of the parent block in the hierarchy (foreign key to memory_blocks.id)",
    )
    has_children: bool = Field(
        False, description="Whether this block has child blocks (denormalized for fast lookups)"
    )

    tags: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Optional tags for filtering, theming, or metadata",
    )
    # NOTE: metadata reconstructed from block_properties table via PropertyMapper
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom metadata based on block type (reconstructed from block_properties)",
    )
    source_file: Optional[str] = Field(None, description="Optional source markdown or file name")
    source_uri: Optional[str] = Field(None, description="Optional source link or Logseq block URI")
    confidence: Optional[ConfidenceScore] = Field(
        None, description="Confidence scores for this memory block"
    )
    created_by: Optional[str] = Field(
        None, description="Optional identifier for creator (agent name or user ID)"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="ISO timestamp of block creation"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="ISO timestamp of last update"
    )
    embedding: Optional[List[float]] = Field(
        None, description="Optional vector embedding of the block's content"
    )

    def __init__(self, **data):
        """Initialize MemoryBlock with debug logging for namespace_id tracking."""
        namespace_id_input = data.get("namespace_id", "NOT_PROVIDED")
        logger.debug(
            f"🔍 DEBUG: MemoryBlock.__init__ called with namespace_id='{namespace_id_input}'"
        )

        super().__init__(**data)

        logger.debug(
            f"🔍 DEBUG: MemoryBlock.__init__ completed with self.namespace_id='{self.namespace_id}'"
        )
        logger.debug(f"🔍 DEBUG: MemoryBlock ID: {self.id}")

    @field_validator("state")
    def validate_state(cls, v):
        """Validate that state is one of the allowed values."""
        if v is not None and v not in ["draft", "published", "archived"]:
            raise ValueError(
                f"Invalid state value: {v}. Must be one of: draft, published, archived"
            )
        return v

    @field_validator("visibility")
    def validate_visibility(cls, v):
        """Validate that visibility is one of the allowed values."""
        if v is not None and v not in ["internal", "public", "restricted"]:
            raise ValueError(
                f"Invalid visibility value: {v}. Must be one of: internal, public, restricted"
            )
        return v

    @field_validator("block_version")
    def validate_block_version(cls, v):
        """Validate that block_version is a positive integer."""
        if v is not None:
            if not isinstance(v, int):
                raise ValueError("block_version must be an integer")
            if v < 0:
                raise ValueError("block_version must be a positive integer")
        return v

    @field_validator("embedding")
    def validate_embedding(cls, v):
        """Validate that embedding is a list of floats with correct size."""
        if v is not None:
            if not isinstance(v, list):
                raise ValueError("embedding must be a list of floats")
            if not all(isinstance(x, (int, float)) for x in v):
                raise ValueError("embedding must contain only numbers")
            if len(v) != 384:  # Standard size for many embedding models
                raise ValueError("embedding must have exactly 384 dimensions")
            # Convert any integers to floats
            return [float(x) for x in v]
        return v

    @field_validator("tags")
    def validate_tags(cls, v):
        """Validate that tags list doesn't exceed max length."""
        if v is not None and len(v) > 20:
            raise ValueError("tags list cannot contain more than 20 items")
        return v

    @field_validator("parent_id")
    def validate_parent_id(cls, v):
        """Validate that parent_id is a valid UUID format when provided."""
        if v is not None:
            try:
                # Validate UUID format
                uuid.UUID(v)
            except ValueError:
                raise ValueError("parent_id must be a valid UUID format")
        return v

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding embedding for smaller transmission size."""
        result = self.model_dump(exclude={"embedding"} if self.embedding else {})
        # Convert datetime objects to ISO format strings for JSON serialization
        if isinstance(result.get("created_at"), datetime):
            result["created_at"] = result["created_at"].isoformat()
        if isinstance(result.get("updated_at"), datetime):
            result["updated_at"] = result["updated_at"].isoformat()
        # Pydantic v2 automatically handles nested model serialization
        return result

    def __setattr__(self, name, value):
        """Override __setattr__ to update updated_at when state, visibility, block_version, parent_id, or has_children changes."""
        if (
            name in ["state", "visibility", "block_version", "parent_id", "has_children"]
            and getattr(self, name, None) != value
        ):
            self.updated_at = datetime.now()
        super().__setattr__(name, value)

    @property
    def is_valid_metadata(self) -> bool:
        """
        Legacy property for backward compatibility.

        NOTE: With Property-Schema Split, metadata validation occurs during
        PropertyMapper.decompose_metadata() when properties are written to
        the block_properties table, not on the MemoryBlock model itself.
        """
        # Always return True since metadata validation happens in PropertyMapper
        return True
