"""
MemoryBlock: Core data structure for the Memory System.
"""

from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
import uuid
from pydantic import BaseModel, Field

from .common import BlockLink, ConfidenceScore

class MemoryBlock(BaseModel):
    """
    The primary data structure for representing a unit of memory in the Cogni system experiment.
    Aligns with the design specified in project-CogniMemorySystem-POC.json.
    Includes schema versioning support (Task 2.0).
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Globally unique ID for this memory block")
    type: Literal["knowledge", "task", "project", "doc", "interaction"] = Field(..., description="Block type used to determine structure and relationships")
    schema_version: Optional[int] = Field(None, description="Version of the schema this block adheres to (links to node_schemas table)")
    text: str = Field(..., description="Primary content or description of the block")
    tags: List[str] = Field(default_factory=list, description="Optional tags for filtering, theming, or metadata")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata based on block type")
    links: List[BlockLink] = Field(default_factory=list, description="Directed outgoing edges connecting this block to others")
    source_file: Optional[str] = Field(None, description="Optional source markdown or file name")
    source_uri: Optional[str] = Field(None, description="Optional source link or Logseq block URI")
    confidence: Optional[ConfidenceScore] = Field(None, description="Confidence scores for this memory block")
    created_by: Optional[str] = Field(None, description="Optional identifier for creator (agent name or user ID)")
    created_at: datetime = Field(default_factory=datetime.now, description="ISO timestamp of block creation")
    updated_at: datetime = Field(default_factory=datetime.now, description="ISO timestamp of last update")
    embedding: Optional[List[float]] = Field(None, description="Optional vector embedding of the block's content")

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

    # Ensure updated_at is set on modification/instantiation
    def model_post_init(self, __context: Any) -> None:
        self.updated_at = datetime.now()

    @property
    def is_valid_metadata(self) -> bool:
        """Check if the metadata conforms to the schema for this block type."""
        from .registry import validate_metadata 
        return validate_metadata(self.type, self.metadata) 