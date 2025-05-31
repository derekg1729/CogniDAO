"""
Common models shared across different schema types.
"""

from datetime import datetime
from typing import Any, Dict, Optional, get_args, Literal
from pydantic import BaseModel, Field, validator, constr, model_validator

# Import RelationType from relation_registry instead of defining it here
from infra_core.memory_system.relation_registry import RelationType

# Canonical UUID-v4 pattern for MemoryBlock IDs
BlockIdType = constr(
    pattern=r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$", strip_whitespace=True
)


class BlockLink(BaseModel):
    """Defines a directed link between two MemoryBlocks."""

    to_id: str = Field(..., description="ID of the target block in the link")
    from_id: str = Field(..., description="ID of the source block in the link")
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


# Block property record model for storing individual block properties
class BlockProperty(BaseModel):
    """Pydantic model for records in the `block_properties` Dolt table."""

    block_id: str = Field(
        ...,
        description="ID of the memory block this property belongs to (foreign key to memory_blocks.id)",
    )
    property_name: str = Field(
        ..., description="Name of the property (e.g., 'title', 'status', 'priority')"
    )
    property_value_text: Optional[str] = Field(
        None, description="Text value of the property (for text, bool, date, select types)"
    )
    property_value_number: Optional[float] = Field(
        None, description="Numeric value of the property (for number type)"
    )
    property_value_json: Optional[Any] = Field(
        None, description="JSON value of the property (for json, multi_select types)"
    )
    property_type: Literal["text", "number", "json", "bool", "date", "select", "multi_select"] = (
        Field(..., description="Type of the property value")
    )
    is_computed: bool = Field(False, description="Whether this property is computed/AI-generated")
    created_at: datetime = Field(
        default_factory=datetime.now, description="When this property was created"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="When this property was last updated"
    )

    @model_validator(mode="after")
    def validate_exactly_one_value_column(self):
        """
        Enforce CHECK constraint: exactly one of (property_value_text, property_value_number, property_value_json)
        must be not-NULL.

        This fails early before hitting the Dolt database, keeping invariants consistent.
        """
        text_val = self.property_value_text
        number_val = self.property_value_number
        json_val = self.property_value_json

        # Count how many values are not None
        non_null_count = sum(1 for val in [text_val, number_val, json_val] if val is not None)

        if non_null_count == 0:
            raise ValueError(
                "Exactly one of property_value_text, property_value_number, or property_value_json must be not-NULL"
            )
        elif non_null_count > 1:
            raise ValueError(
                f"Only one property value column can be not-NULL, but found {non_null_count} non-NULL values: "
                f"text={text_val is not None}, number={number_val is not None}, json={json_val is not None}"
            )

        return self
