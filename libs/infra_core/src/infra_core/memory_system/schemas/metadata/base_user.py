from infra_core.memory_system.schemas.metadata.base import BaseMetadata
from pydantic import Field
from typing import Optional


class BaseUserMetadata(BaseMetadata):
    """
    User-defined metadata fields shared across MemoryBlock types.
    Inherits system-level fields from BaseMetadata.
    """

    title: str = Field(..., description="Short, descriptive title of the memory block")
    description: Optional[str] = Field(
        None, description="Brief explanation or summary of the block's contents"
    )
    owner: Optional[str] = Field(None, description="User ID of the block's primary owner")

    class Config:
        extra = "forbid"
