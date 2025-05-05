"""
Doc metadata schema for MemoryBlocks of type "doc".
"""

from typing import Optional, Literal
from datetime import datetime
from pydantic import Field

# Import BaseMetadata
from .base import BaseMetadata
from ..registry import register_metadata


class DocMetadata(BaseMetadata):
    """
    Metadata schema for MemoryBlocks of type "doc".
    Basic structure for documentation blocks.
    """

    audience: Optional[str] = Field(
        None, description="Intended audience for the document (e.g., 'developers', 'users')"
    )
    section: Optional[str] = Field(None, description="Section or category the document belongs to")
    version: Optional[str] = Field(None, description="Version of the documentation")
    last_reviewed: Optional[datetime] = Field(
        None, description="When the document was last reviewed"
    )
    format: Optional[Literal["markdown", "html", "text", "code"]] = Field(
        None, description="Format of the document content"
    )
    completed: bool = Field(False, description="Whether the document is complete/finalized")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "audience": "developers",
                    "section": "api-reference",
                    "version": "1.0.0",
                    "last_reviewed": "2023-10-15T14:30:00",
                    "format": "markdown",
                    "completed": True,
                }
            ]
        }
    }


# Register this metadata model with the registry
register_metadata("doc", DocMetadata)
