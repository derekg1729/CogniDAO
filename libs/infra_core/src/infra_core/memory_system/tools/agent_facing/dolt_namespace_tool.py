"""
Dolt Namespace Management Tools

This module provides tools for agents to manage and query namespaces in the memory system.
Follows the same patterns as dolt_repo_tool.py for consistency.

Tools included:
- list_namespaces_tool: List all available namespaces with their metadata
"""

import logging
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from ..base.cogni_tool import CogniTool

logger = logging.getLogger(__name__)


# Base Output Model (reused from dolt_repo_tool pattern)
class BaseNamespaceOutput(BaseModel):
    """Base output model for all namespace tools."""

    success: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Human-readable result message")
    active_branch: str = Field(..., description="Current active branch")
    error: Optional[str] = Field(default=None, description="Error message if operation failed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of operation")


class ListNamespacesInput(BaseModel):
    """Input model for the list_namespaces tool."""

    # No input parameters needed for listing namespaces


class NamespaceInfo(BaseModel):
    """Information about a single namespace."""

    id: str = Field(..., description="Namespace ID")
    name: str = Field(..., description="Human-readable namespace name")
    slug: str = Field(..., description="URL-safe namespace identifier")
    owner_id: str = Field(..., description="ID of the namespace owner")
    created_at: datetime = Field(..., description="When namespace was created")
    description: Optional[str] = Field(None, description="Optional namespace description")
    is_active: bool = Field(True, description="Whether the namespace is active")


class ListNamespacesOutput(BaseNamespaceOutput):
    """Output model for the list_namespaces tool."""

    namespaces: List[NamespaceInfo] = Field(default=[], description="List of namespaces")
    total_count: int = Field(..., description="Total number of namespaces")


def list_namespaces_tool(
    input_data: ListNamespacesInput, memory_bank: StructuredMemoryBank
) -> ListNamespacesOutput:
    """
    List all available namespaces with their metadata.

    Args:
        input_data: The listing parameters (currently no parameters needed)
        memory_bank: StructuredMemoryBank instance with Dolt reader access

    Returns:
        ListNamespacesOutput with list of namespaces and status
    """
    try:
        logger.info("Listing available namespaces")

        # Get current branch for context
        try:
            branch_result = memory_bank.dolt_reader._execute_query(
                "SELECT active_branch() as branch"
            )
            current_branch = branch_result[0]["branch"] if branch_result else "unknown"
        except Exception:
            current_branch = "unknown"

        # Query all namespaces from the database
        query = """
        SELECT 
            id, 
            name, 
            slug, 
            owner_id, 
            created_at, 
            description,
            COALESCE(is_active, TRUE) as is_active
        FROM namespaces 
        ORDER BY name
        """

        namespace_rows = memory_bank.dolt_reader._execute_query(query)

        # Convert to NamespaceInfo objects
        namespaces = []
        for row in namespace_rows:
            namespace_info = NamespaceInfo(
                id=row["id"],
                name=row["name"],
                slug=row["slug"],
                owner_id=row["owner_id"],
                created_at=row["created_at"],
                description=row.get("description"),
                is_active=bool(row.get("is_active", True)),
            )
            namespaces.append(namespace_info)

        # Build success message
        total_count = len(namespaces)
        message = f"Found {total_count} namespaces" if total_count > 0 else "No namespaces found"

        logger.info(f"{message}. Current branch: {current_branch}")

        return ListNamespacesOutput(
            success=True,
            namespaces=namespaces,
            total_count=total_count,
            message=message,
            active_branch=current_branch,
        )

    except Exception as e:
        error_msg = f"Exception during namespace listing: {str(e)}"
        logger.error(error_msg, exc_info=True)

        # Get current branch for error response
        try:
            branch_result = memory_bank.dolt_reader._execute_query(
                "SELECT active_branch() as branch"
            )
            current_branch = branch_result[0]["branch"] if branch_result else "unknown"
        except Exception:
            current_branch = "unknown"

        return ListNamespacesOutput(
            success=False,
            namespaces=[],
            total_count=0,
            active_branch=current_branch,
            message=f"Failed to list namespaces: {str(e)}",
            error=error_msg,
        )


# Create the tool instance
list_namespaces_tool_instance = CogniTool(
    name="ListNamespaces",
    description="List all available namespaces with their metadata",
    input_model=ListNamespacesInput,
    output_model=ListNamespacesOutput,
    function=list_namespaces_tool,
    memory_linked=True,
)
