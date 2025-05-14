"""
Common models shared across different schema types.
"""

from datetime import datetime
from typing import Any, Dict, Literal, Optional, get_args
from pydantic import BaseModel, Field, validator, constr

# Canonical relation types defined for links between MemoryBlocks
RelationType = Literal[
    "related_to",
    "subtask_of",
    "depends_on",
    "child_of",
    "mentions",
    "parent_of",
    "belongs_to_epic",
    "epic_contains",
    "blocks",
    "is_blocked_by",
    "bug_affects",
    "has_bug",
]

# Canonical UUID-v4 pattern for MemoryBlock IDs
BlockIdType = constr(
    pattern=r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$", strip_whitespace=True
)


class BlockLink(BaseModel):
    """Defines a directed link between two MemoryBlocks."""

    to_id: str = Field(..., description="ID of the target block in the link")
    relation: RelationType = Field(..., description="The type of relationship between the blocks")
    priority: Optional[int] = Field(
        0, description="Priority of the link (higher numbers = higher priority)"
    )
    link_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata about the link"
    )
    created_by: Optional[str] = Field(None, description="ID of the agent/user who created the link")
    created_at: datetime = Field(
        default_factory=datetime.now, description="When the link was created"
    )

    @validator("priority")
    def validate_priority(cls, v):
        """Ensure priority is non-negative."""
        if v is not None and v < 0:
            raise ValueError("Priority must be non-negative")
        return v

    @validator("relation")
    def validate_relation(cls, v):
        """Ensure relation type is canonical."""
        valid_relations = get_args(RelationType)
        if v not in valid_relations:
            raise ValueError(f"Relation must be one of {valid_relations}")
        return v


class ConfidenceScore(BaseModel):
    """Represents confidence scores, potentially from human or AI sources."""

    human: Optional[float] = Field(
        None, ge=0, le=1, description="Optional human confidence score (0.0 to 1.0)"
    )
    ai: Optional[float] = Field(
        None, ge=0, le=1, description="Optional AI-generated confidence score (0.0 to 1.0)"
    )


# Node schema record model for registration in Dolt
class NodeSchemaRecord(BaseModel):
    """Pydantic model for records in the `node_schemas` Dolt table."""

    node_type: str = Field(
        ..., description="Corresponds to MemoryBlock.type (e.g., 'task', 'project')"
    )
    schema_version: int = Field(..., description="Version number for this schema")
    json_schema: dict = Field(
        ..., description="JSON schema output from Pydantic model.model_json_schema()"
    )
    created_at: str = Field(..., description="When this schema version was registered")
