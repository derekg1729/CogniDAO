"""
CreateNamespaceTool: Agent-facing tool for creating new namespaces.

This tool provides a unified interface for creating namespace records in the database,
ensuring proper validation and following established patterns.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, model_validator
import logging

from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank

# Setup logging
logger = logging.getLogger(__name__)


class CreateNamespaceInput(BaseModel):
    """Input model for creating a new namespace."""

    # Required fields
    id: str = Field(
        ..., description="Unique namespace identifier (e.g., 'cogni-project-management')"
    )
    name: str = Field(
        ..., description="Human-readable namespace name (e.g., 'Cogni Project Management')"
    )

    # Optional fields with defaults
    slug: Optional[str] = Field(
        None, description="URL-safe namespace identifier (defaults to id if not provided)"
    )
    owner_id: str = Field("system", description="ID of the namespace owner (defaults to 'system')")
    description: Optional[str] = Field(None, description="Optional description of the namespace")
    is_active: bool = Field(True, description="Whether the namespace is active (defaults to True)")

    @model_validator(mode="after")
    def set_slug_default(self) -> "CreateNamespaceInput":
        """Set slug to id if not provided."""
        if self.slug is None:
            self.slug = self.id
        return self


class CreateNamespaceOutput(BaseModel):
    """Output model for namespace creation results."""

    success: bool = Field(..., description="Whether the operation succeeded")
    namespace_id: Optional[str] = Field(None, description="ID of the created namespace")
    message: str = Field(..., description="Human-readable result message")
    active_branch: str = Field(..., description="Current active branch")
    error: Optional[str] = Field(default=None, description="Error message if operation failed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of operation")


def create_namespace_tool(
    input_data: CreateNamespaceInput, memory_bank: StructuredMemoryBank
) -> CreateNamespaceOutput:
    """
    Create a new namespace in the database.

    Args:
        input_data: Input data for creating the namespace
        memory_bank: StructuredMemoryBank instance for database access

    Returns:
        CreateNamespaceOutput containing creation status, ID, and timestamp
    """
    logger.info(f"Attempting to create namespace: {input_data.id}")

    try:
        # Get current branch for context
        try:
            branch_result = memory_bank.dolt_reader._execute_query(
                "SELECT active_branch() as branch"
            )
            current_branch = branch_result[0]["branch"] if branch_result else "unknown"
        except Exception:
            current_branch = "unknown"

        # Check if namespace already exists
        existing_query = "SELECT id FROM namespaces WHERE id = %s"
        existing = memory_bank.dolt_reader._execute_query(existing_query, (input_data.id,))

        if existing:
            error_msg = f"Namespace '{input_data.id}' already exists"
            logger.error(error_msg)
            return CreateNamespaceOutput(
                success=False,
                namespace_id=None,
                message=error_msg,
                active_branch=current_branch,
                error=error_msg,
            )

        # Insert the new namespace
        insert_query = """
        INSERT INTO namespaces (id, name, slug, owner_id, created_at, description, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        created_at = datetime.utcnow()
        params = (
            input_data.id,
            input_data.name,
            input_data.slug,
            input_data.owner_id,
            created_at,
            input_data.description,
            input_data.is_active,
        )

        rows_affected = memory_bank.dolt_writer._execute_update(insert_query, params)

        if rows_affected > 0:
            success_msg = f"Successfully created namespace '{input_data.id}'"
            logger.info(success_msg)
            return CreateNamespaceOutput(
                success=True,
                namespace_id=input_data.id,
                message=success_msg,
                active_branch=current_branch,
            )
        else:
            error_msg = f"Failed to create namespace '{input_data.id}' - no rows affected"
            logger.error(error_msg)
            return CreateNamespaceOutput(
                success=False,
                namespace_id=None,
                message=error_msg,
                active_branch=current_branch,
                error=error_msg,
            )

    except Exception as e:
        error_msg = f"Exception during namespace creation: {str(e)}"
        logger.error(error_msg, exc_info=True)

        # Get current branch for error response
        try:
            branch_result = memory_bank.dolt_reader._execute_query(
                "SELECT active_branch() as branch"
            )
            current_branch = branch_result[0]["branch"] if branch_result else "unknown"
        except Exception:
            current_branch = "unknown"

        return CreateNamespaceOutput(
            success=False,
            namespace_id=None,
            message=f"Failed to create namespace: {str(e)}",
            active_branch=current_branch,
            error=error_msg,
        )
