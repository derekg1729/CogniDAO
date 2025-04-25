"""
Knowledge metadata schema for MemoryBlocks of type "knowledge".
"""

from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field

from ..registry import register_metadata

class KnowledgeMetadata(BaseModel):
    """
    Metadata schema for MemoryBlocks of type "knowledge".
    Structure for knowledge/fact blocks.
    """
    source: Optional[str] = Field(
        None, 
        description="Source of the knowledge (e.g., research paper, website, observation)"
    )
    validity: Optional[Literal["confirmed", "speculative", "outdated"]] = Field(
        None, 
        description="Current validity status of this knowledge"
    )
    domain: Optional[str] = Field(
        None, 
        description="Knowledge domain or category"
    )
    last_verified: Optional[datetime] = Field(
        None, 
        description="When this knowledge was last verified as accurate"
    )
    confidence_level: Optional[float] = Field(
        None, 
        ge=0, 
        le=1, 
        description="Confidence in this knowledge (0-1)"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "source": "Cogni Research Team",
                    "validity": "confirmed",
                    "domain": "memory-systems",
                    "last_verified": "2023-11-01T09:15:00",
                    "confidence_level": 0.95
                }
            ]
        }
    }

# Register this metadata model with the registry
register_metadata("knowledge", KnowledgeMetadata) 