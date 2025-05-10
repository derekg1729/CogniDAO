"""
Schema definitions for Cogni Memory Architecture.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from pydantic import BaseModel, Field


class MemoryBlock(BaseModel):
    """
    A memory block represents a single piece of content extracted from Logseq.
    It contains the text, metadata, and optional embedding.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    tags: List[str]
    source_file: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    source_uri: Optional[str] = None  # For traceability (e.g., logseq://date#block-id)
    embedding: Optional[List[float]] = None  # Optional because archive storage doesn't need embeddings
    metadata: Optional[Dict[str, Any]] = None  # For additional metadata

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding the embedding to save space."""
        result = self.model_dump(exclude={"embedding"} if self.embedding else {})
        # Convert datetime objects to ISO format strings for JSON serialization
        result["created_at"] = result["created_at"].isoformat()
        result["updated_at"] = result["updated_at"].isoformat()
        return result


class MemoryBlockBatch(BaseModel):
    """A batch of memory blocks for bulk operations."""
    blocks: List[MemoryBlock]


class QueryRequest(BaseModel):
    """Request model for memory queries."""
    query_text: str
    n_results: int = 5
    include_archived: bool = False
    filter_tags: Optional[List[str]] = None


class QueryResult(BaseModel):
    """Result model for memory queries."""
    query_text: str
    blocks: List[MemoryBlock]
    total_results: int


class IndexMetadata(BaseModel):
    """Metadata for archive indexes."""
    version: str = "1.0.0"
    updated_at: datetime = Field(default_factory=datetime.now)
    block_count: int = 0


class ArchiveIndex(BaseModel):
    """Archive index structure."""
    metadata: IndexMetadata
    blocks: Dict[str, Dict[str, Any]]  # Map of block IDs to block metadata 