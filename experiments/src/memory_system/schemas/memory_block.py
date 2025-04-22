"""
Pydantic schemas for the Memory Block system within the /experiments POC.
"""

from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
import uuid
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

class MemoryBlock(BaseModel):
    """
    The primary data structure for representing a unit of memory in the Cogni system experiment.
    Aligns with the design specified in project-CogniMemorySystem-POC.json.
    """
    # No schema_version needed for this experimental version
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Globally unique ID for this memory block")
    type: Literal["knowledge", "task", "project", "doc"] = Field(..., description="Block type used to determine structure and relationships")
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