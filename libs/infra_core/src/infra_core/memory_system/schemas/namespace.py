"""
Namespace model for multi-tenant memory organization.
"""

from datetime import datetime
from typing import Optional
import uuid
from pydantic import BaseModel, Field


class Namespace(BaseModel):
    """
    Namespace model for organizing memory blocks in a multi-tenant system.
    Follows the DRY, FK-based design pattern specified by Cogni advisor.

    Maps to the namespaces table in the database schema.
    """

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Globally unique namespace ID",
    )
    name: str = Field(..., description="Human-readable namespace name")
    slug: str = Field(..., description="URL-safe namespace identifier")
    owner_id: str = Field(..., description="ID of the namespace owner")
    created_at: datetime = Field(
        default_factory=datetime.now, description="When namespace was created"
    )
    description: Optional[str] = Field(None, description="Optional namespace description")
