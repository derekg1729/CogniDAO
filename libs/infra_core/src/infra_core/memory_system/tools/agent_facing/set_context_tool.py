"""
SetContextTool: Session context management for namespace and branch switching.

This tool allows agents to change the default namespace/branch context for the
session, reducing the need for environment variable juggling and making it easier
to work across different namespaces and branches.

Key capabilities:
- Switch default namespace for all subsequent MCP operations
- Switch active branch for version control operations
- Persist context changes for the duration of the session
- Provide context information and validation
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
import logging
import os

from ...structured_memory_bank import StructuredMemoryBank
from ..base.cogni_tool import CogniTool

# Setup logging
logger = logging.getLogger(__name__)


class SetContextInput(BaseModel):
    """Input model for setting session context."""

    namespace_id: Optional[str] = Field(
        None, description="Namespace to set as default (None = no change)"
    )
    branch_name: Optional[str] = Field(
        None, description="Branch to checkout and set as active (None = no change)"
    )
    validate_namespace: bool = Field(
        True, description="Whether to validate that the namespace exists"
    )
    validate_branch: bool = Field(True, description="Whether to validate that the branch exists")


class SetContextOutput(BaseModel):
    """Output model for context setting results."""

    success: bool = Field(..., description="Whether the context change was successful")
    previous_namespace: Optional[str] = Field(None, description="Previous namespace context")
    current_namespace: Optional[str] = Field(None, description="Current namespace context")
    previous_branch: Optional[str] = Field(None, description="Previous active branch")
    current_branch: Optional[str] = Field(None, description="Current active branch")
    namespace_changed: bool = Field(False, description="Whether namespace was changed")
    branch_changed: bool = Field(False, description="Whether branch was changed")
    message: str = Field("", description="Human-readable result message")
    error: Optional[str] = Field(None, description="Error message if context change failed")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Timestamp of the operation"
    )


def set_context_core(
    input_data: SetContextInput, memory_bank: StructuredMemoryBank
) -> SetContextOutput:
    """
    Set the session context for namespace and/or branch.

    This function changes the default context that will be used for subsequent
    MCP operations, allowing agents to work across different namespaces and branches
    without constantly specifying them in each call.

    Args:
        input_data: Input parameters for context setting
        memory_bank: StructuredMemoryBank instance for validation and operations

    Returns:
        SetContextOutput containing the context change results
    """
    try:
        logger.info("🔧 Setting session context")

        # Get current context
        previous_namespace = os.environ.get("DOLT_NAMESPACE")
        previous_branch = memory_bank.branch

        current_namespace = previous_namespace
        current_branch = previous_branch
        namespace_changed = False
        branch_changed = False

        # Handle namespace change
        if input_data.namespace_id is not None:
            logger.info(
                f"Changing namespace from '{previous_namespace}' to '{input_data.namespace_id}'"
            )

            # Validate namespace exists if requested
            if input_data.validate_namespace:
                namespace_query = "SELECT COUNT(*) as count FROM namespaces WHERE id = %s"
                result = memory_bank.dolt_reader._execute_query(
                    namespace_query, (input_data.namespace_id,)
                )

                if not result or result[0]["count"] == 0:
                    return SetContextOutput(
                        success=False,
                        previous_namespace=previous_namespace,
                        current_namespace=current_namespace,
                        previous_branch=previous_branch,
                        current_branch=current_branch,
                        message=f"Namespace '{input_data.namespace_id}' not found",
                        error=f"Namespace '{input_data.namespace_id}' does not exist in the database",
                        timestamp=datetime.now(),
                    )

            # Set the namespace environment variable for this session
            os.environ["DOLT_NAMESPACE"] = input_data.namespace_id
            current_namespace = input_data.namespace_id
            namespace_changed = True

            logger.info(f"✅ Namespace context changed to '{current_namespace}'")

        # Handle branch change
        if input_data.branch_name is not None:
            logger.info(f"Changing branch from '{previous_branch}' to '{input_data.branch_name}'")

            # Validate branch exists if requested
            if input_data.validate_branch:
                branch_query = "SELECT COUNT(*) as count FROM dolt_branches WHERE name = %s"
                try:
                    result = memory_bank.dolt_reader._execute_query(
                        branch_query, (input_data.branch_name,)
                    )

                    if not result or result[0]["count"] == 0:
                        return SetContextOutput(
                            success=False,
                            previous_namespace=previous_namespace,
                            current_namespace=current_namespace,
                            previous_branch=previous_branch,
                            current_branch=current_branch,
                            message=f"Branch '{input_data.branch_name}' not found",
                            error=f"Branch '{input_data.branch_name}' does not exist",
                            timestamp=datetime.now(),
                        )
                except Exception as e:
                    logger.warning(f"Could not validate branch existence: {e}")

            # Switch to the new branch
            try:
                # Use the memory bank's checkout functionality
                memory_bank.dolt_writer.checkout_branch(input_data.branch_name)

                # Re-initialize persistent connections with new branch
                memory_bank.use_persistent_connections(input_data.branch_name)

                current_branch = input_data.branch_name
                branch_changed = True

                logger.info(f"✅ Branch context changed to '{current_branch}'")
            except Exception as e:
                return SetContextOutput(
                    success=False,
                    previous_namespace=previous_namespace,
                    current_namespace=current_namespace,
                    previous_branch=previous_branch,
                    current_branch=current_branch,
                    message=f"Failed to checkout branch '{input_data.branch_name}'",
                    error=f"Branch checkout failed: {str(e)}",
                    timestamp=datetime.now(),
                )

        # Build success message
        changes = []
        if namespace_changed:
            changes.append(f"namespace to '{current_namespace}'")
        if branch_changed:
            changes.append(f"branch to '{current_branch}'")

        if changes:
            message = f"Successfully changed {' and '.join(changes)}"
        else:
            message = "No context changes requested - current context maintained"

        logger.info(f"✅ Context setting complete: {message}")

        return SetContextOutput(
            success=True,
            previous_namespace=previous_namespace,
            current_namespace=current_namespace,
            previous_branch=previous_branch,
            current_branch=current_branch,
            namespace_changed=namespace_changed,
            branch_changed=branch_changed,
            message=message,
            timestamp=datetime.now(),
        )

    except Exception as e:
        error_msg = f"Context setting failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return SetContextOutput(
            success=False,
            previous_namespace=os.environ.get("DOLT_NAMESPACE"),
            current_namespace=os.environ.get("DOLT_NAMESPACE"),
            previous_branch=memory_bank.branch,
            current_branch=memory_bank.branch,
            message="Context setting failed",
            error=error_msg,
            timestamp=datetime.now(),
        )


# Create the tool instance
set_context_tool = CogniTool(
    name="SetContext",
    description="Set the default namespace and/or branch context for the MCP session",
    input_model=SetContextInput,
    output_model=SetContextOutput,
    function=set_context_core,
    memory_linked=True,
)
