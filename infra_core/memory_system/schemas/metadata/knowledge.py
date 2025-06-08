"""
Knowledge memory block metadata schema.
"""

from typing import Optional, List
from pydantic import Field

from .base_user import BaseUserMetadata
from ..registry import register_metadata


class KnowledgeMetadata(BaseUserMetadata):
    """Metadata for knowledge-type memory blocks."""

    subject: Optional[str] = Field(None, description="Primary subject or domain of the knowledge")
    keywords: Optional[List[str]] = Field(
        None, description="Keywords or tags related to this knowledge"
    )
    source: Optional[str] = Field(
        None, description="Source of the knowledge (e.g., documentation, research, experience)"
    )
    confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Confidence level in the accuracy of this knowledge (0.0 to 1.0)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "source": "Cogni Research Team",
                    "confidence": 0.95,
                }
            ]
        }
    }


# Register this metadata model with the registry
register_metadata("knowledge", KnowledgeMetadata)
