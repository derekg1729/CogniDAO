"""
Validation models for verifying task completion and acceptance criteria.
"""

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, validator


class ValidationResult(BaseModel):
    """
    Result of validating a single acceptance criterion.
    Used in the validation_report to track individual validation results.
    """

    criterion: str = Field(..., description="The acceptance criterion being validated")
    status: Literal["pass", "fail"] = Field(
        ..., description="Whether the criterion passed validation"
    )
    notes: Optional[str] = Field(None, description="Optional notes about the validation result")


class ValidationReport(BaseModel):
    """
    Structured report of validation results for executable memory blocks.
    Created when a task or other executable is reviewed and contains
    evidence that all acceptance criteria have been met.
    """

    validated_by: str = Field(..., description="User or agent ID who performed the validation")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="When the validation was performed"
    )
    results: List[ValidationResult] = Field(
        ..., description="List of validation results for each acceptance criterion"
    )

    @validator("results")
    def validate_results_not_empty(cls, v):
        """Ensure results list contains at least one result."""
        if not v:
            raise ValueError("Validation report must contain at least one result")
        return v

    class Config:
        # Prevent users from adding undefined fields
        extra = "forbid"
