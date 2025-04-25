"""
Common models shared across different schema types.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field

# Canonical relation types defined for links between MemoryBlocks
RelationType = Literal["related_to", "subtask_of", "depends_on", "child_of", "mentions"]

class BlockLink(BaseModel):
    """Defines a directed link between two MemoryBlocks."""
    to_id: str = Field(..., description="ID of the target block in the link")
    relation: RelationType = Field(..., description="The type of relationship between the blocks")

class ConfidenceScore(BaseModel):
    """Represents confidence scores, potentially from human or AI sources."""
    human: Optional[float] = Field(None, ge=0, le=1, description="Optional human confidence score (0.0 to 1.0)")
    ai: Optional[float] = Field(None, ge=0, le=1, description="Optional AI-generated confidence score (0.0 to 1.0)")

# Node schema record model for registration in Dolt
class NodeSchemaRecord(BaseModel):
    """Pydantic model for records in the `node_schemas` Dolt table."""
    node_type: str = Field(..., description="Corresponds to MemoryBlock.type (e.g., 'task', 'project')")
    schema_version: int = Field(..., description="Version number for this schema")
    json_schema: dict = Field(..., description="JSON schema output from Pydantic model.model_json_schema()")
    created_at: str = Field(..., description="When this schema version was registered") 