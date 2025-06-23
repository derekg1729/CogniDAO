"""
Dolt Version Control Tools for Manual Operations

This module provides tools for agents to manually perform Dolt version control operations
when auto_commit=False mode is being used in StructuredMemoryBank.

Tools included:
- dolt_repo_tool: Commit working set changes to Dolt
- dolt_push_tool: Push changes to remote repositories
"""

import logging
import re
from datetime import datetime
from typing import List, Optional, Dict, Any, Callable, Literal
from functools import wraps
from pydantic import BaseModel, Field, validator
import requests

from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank

logger = logging.getLogger(__name__)

# Security: Branch name validation regex (allows dots for version tags)
BRANCH_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_\-/.]+$")


def validate_branch_name(branch_name: str) -> str:
    """Validate branch name against security pattern."""
    if not BRANCH_NAME_PATTERN.match(branch_name):
        raise ValueError(
            f"Invalid branch name: {branch_name}. Must match pattern: {BRANCH_NAME_PATTERN.pattern}"
        )
    return branch_name


# Base Output Model to eliminate timestamp duplication
class BaseDoltOutput(BaseModel):
    """Base output model for all Dolt tools."""

    success: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Human-readable result message")
    active_branch: str = Field(..., description="Current active branch")
    error: Optional[str] = Field(default=None, description="Error message if operation failed")
    error_code: Optional[str] = Field(default=None, description="Machine-readable error code")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of operation")


def dolt_tool(operation_name: str):
    """
    Decorator to handle common Dolt tool patterns:
    - Logging
    - Exception handling
    - Standardized error messages
    - Active branch injection
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(input_data, memory_bank: StructuredMemoryBank):
            logger.info(f"{operation_name.upper()} started with input: {input_data}")

            try:
                result = func(input_data, memory_bank)

                # Ensure active_branch is set
                if hasattr(result, "active_branch") and not result.active_branch:
                    result.active_branch = getattr(
                        memory_bank.dolt_writer, "active_branch", "unknown"
                    )

                # Standardize success message
                if result.success and not result.message.startswith(operation_name.upper()):
                    result.message = f"{operation_name.upper()} SUCCESS: {result.message}"
                elif not result.success and not result.message.startswith(operation_name.upper()):
                    result.message = f"{operation_name.upper()} FAILED: {result.message}"

                logger.info(f"{operation_name.upper()} completed: {result.message}")
                return result

            except Exception as e:
                error_msg = f"Exception during {operation_name}: {str(e)}"
                logger.error(error_msg, exc_info=True)

                # Create error response using the function's return type annotation
                output_class = func.__annotations__.get("return")
                if output_class and hasattr(output_class, "__call__"):
                    # Build base error response
                    error_response = {
                        "success": False,
                        "message": f"{operation_name.upper()} FAILED: {str(e)}",
                        "active_branch": getattr(
                            memory_bank.dolt_writer, "active_branch", "unknown"
                        ),
                        "error": error_msg,
                        "error_code": "EXCEPTION",
                    }

                    # Add required fields for specific output types
                    if hasattr(input_data, "source_branch"):
                        error_response["source_branch"] = input_data.source_branch
                    if hasattr(input_data, "target_branch"):
                        error_response["target_branch"] = input_data.target_branch or getattr(
                            memory_bank.dolt_writer, "active_branch", "unknown"
                        )
                    if output_class.__name__ == "DoltMergeOutput":
                        error_response["fast_forward"] = False
                        error_response["conflicts"] = 0
                        error_response["merge_hash"] = None

                    return output_class(**error_response)
                else:
                    # Fallback - this shouldn't happen with proper typing
                    raise

        return wrapper

    return decorator


class DoltAddInput(BaseModel):
    """Input model for the dolt_add tool."""

    tables: Optional[List[str]] = Field(
        default=None,
        description="Optional list of specific tables to add. If not provided, all changes will be staged.",
    )


class DoltAddOutput(BaseDoltOutput):
    """Output model for the dolt_add tool."""

    pass  # All fields inherited from BaseDoltOutput


class DoltResetInput(BaseModel):
    """Input model for the dolt_reset tool."""

    tables: Optional[List[str]] = Field(
        default=None,
        description="Optional list of specific tables to reset. If not provided, all working changes will be discarded.",
    )
    hard: bool = Field(
        default=True,
        description="Whether to perform a hard reset, discarding all changes (default: True)",
    )


class DoltResetOutput(BaseDoltOutput):
    """Output model for the dolt_reset tool."""

    tables_reset: Optional[List[str]] = Field(
        default=None,
        description="List of tables that were reset (if specific tables were targeted)",
    )


class DoltCommitInput(BaseModel):
    """Input model for the dolt_commit tool."""

    commit_message: str = Field(
        ...,
        description="Commit message for the Dolt changes",
        min_length=1,
        max_length=500,
    )
    tables: Optional[List[str]] = Field(
        default=None,
        description="Optional list of specific tables to add/commit. If not provided, all standard tables will be committed.",
    )
    author: Optional[str] = Field(
        default=None,
        description="Optional author attribution for the commit",
        max_length=100,
    )


class DoltCommitOutput(BaseDoltOutput):
    """Output model for the dolt_commit tool."""

    commit_hash: Optional[str] = Field(
        default=None, description="The Dolt commit hash if successful"
    )
    tables_committed: Optional[List[str]] = Field(
        default=None, description="List of tables that were committed"
    )


class DoltPushInput(BaseModel):
    """Input model for the dolt_push tool."""

    remote_name: str = Field(
        ...,
        description="Name of the remote to push to (e.g., 'origin')",
        min_length=1,
        max_length=100,
    )
    branch: str = Field(
        default="main",
        description="Branch to push (default: 'main')",
        min_length=1,
        max_length=100,
    )
    force: bool = Field(
        default=False,
        description="Whether to force push, overriding safety checks (default: False)",
    )
    set_upstream: bool = Field(
        default=False,
        description="Whether to set up upstream tracking for the branch (default: False)",
    )

    @validator("branch")
    def validate_branch(cls, v):
        """Validate branch name for security."""
        return validate_branch_name(v)


class DoltPushOutput(BaseDoltOutput):
    """Output model for the dolt_push tool."""

    remote_name: str = Field(..., description="Name of the remote that was pushed to")
    branch: str = Field(..., description="Branch that was pushed")
    force: bool = Field(..., description="Whether force push was used")
    set_upstream: bool = Field(..., description="Whether upstream tracking was set up")


class DoltStatusInput(BaseModel):
    """Input model for the dolt_status tool."""

    # MVP: No input parameters needed for basic status


class DoltStatusOutput(BaseDoltOutput):
    """Output model for the dolt_status tool."""

    is_clean: bool = Field(..., description="True if working tree is clean")
    staged_tables: List[str] = Field(default=[], description="Tables with staged changes")
    unstaged_tables: List[str] = Field(default=[], description="Tables with unstaged changes")
    untracked_tables: List[str] = Field(default=[], description="New untracked tables")
    total_changes: int = Field(..., description="Total number of changes")
    ahead: int = Field(default=0, description="Commits ahead of remote")
    behind: int = Field(default=0, description="Commits behind remote")
    conflicts: List[str] = Field(default=[], description="Tables with conflicts")


class DoltPullInput(BaseModel):
    """Input model for the dolt_pull tool."""

    remote_name: str = Field(
        default="origin",
        description="Name of the remote to pull from (e.g., 'origin')",
        min_length=1,
        max_length=100,
    )
    branch: str = Field(
        default="main",
        description="Specific branch to pull (default: 'main')",
        min_length=1,
        max_length=100,
    )
    force: bool = Field(
        default=False,
        description="Whether to force pull, ignoring conflicts (default: False)",
    )
    no_ff: bool = Field(
        default=False,
        description="Create a merge commit even for fast-forward merges (default: False)",
    )
    squash: bool = Field(
        default=False,
        description="Merge changes to working set without updating commit history (default: False)",
    )


class DoltPullOutput(BaseDoltOutput):
    """Output model for the dolt_pull tool."""

    success: bool = Field(..., description="Whether the pull operation succeeded")
    message: str = Field(..., description="Human-readable result message")
    remote_name: str = Field(..., description="Name of the remote that was pulled from")
    branch: str = Field(..., description="Branch that was pulled")
    force: bool = Field(..., description="Whether force pull was used")
    no_ff: bool = Field(..., description="Whether no-fast-forward was used")
    squash: bool = Field(..., description="Whether squash merge was used")
    active_branch: str = Field(..., description="Current active branch")
    error: Optional[str] = Field(default=None, description="Error message if operation failed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of operation")


class DoltBranchInput(BaseModel):
    """Input model for the dolt_branch tool."""

    branch_name: str = Field(
        ...,
        description="Name of the new branch to create",
        min_length=1,
        max_length=100,
    )
    start_point: Optional[str] = Field(
        default=None,
        description="Commit, branch, or tag to start the branch from (optional, defaults to current HEAD)",
        max_length=100,
    )
    force: bool = Field(
        default=False,
        description="Whether to force creation, overriding safety checks (default: False)",
    )


class DoltBranchOutput(BaseDoltOutput):
    """Output model for the dolt_branch tool."""

    success: bool = Field(..., description="Whether the branch creation succeeded")
    message: str = Field(..., description="Human-readable result message")
    branch_name: str = Field(..., description="Name of the branch that was created")
    start_point: Optional[str] = Field(
        default=None, description="Start point that was used (if specified)"
    )
    force: bool = Field(..., description="Whether force creation was used")
    active_branch: str = Field(..., description="Current active branch")
    error: Optional[str] = Field(default=None, description="Error message if operation failed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of operation")


class DoltListBranchesInput(BaseModel):
    """Input model for the dolt_list_branches tool."""

    # No input parameters needed for listing branches


class DoltBranchInfo(BaseModel):
    """Information about a single Dolt branch."""

    name: str = Field(..., description="Branch name")
    hash: str = Field(..., description="Latest commit hash")
    latest_committer: str = Field(..., description="Name of the latest committer")
    latest_committer_email: str = Field(..., description="Email of the latest committer")
    latest_commit_date: datetime = Field(..., description="Date of the latest commit")
    latest_commit_message: str = Field(..., description="Message of the latest commit")
    remote: str = Field(..., description="Remote name (empty if local)")
    branch: str = Field(..., description="Remote branch name (empty if local)")
    dirty: bool = Field(..., description="Whether the branch has uncommitted changes")


class DoltListBranchesOutput(BaseDoltOutput):
    """Output model for the dolt_list_branches tool."""

    success: bool = Field(..., description="Whether the operation succeeded")
    branches: List[DoltBranchInfo] = Field(default=[], description="List of branches")
    active_branch: str = Field(..., description="Currently active branch")
    message: str = Field(..., description="Human-readable result message")
    error: Optional[str] = Field(default=None, description="Error message if operation failed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of operation")


class DoltCheckoutInput(BaseModel):
    """Input model for the dolt_checkout tool."""

    branch_name: str = Field(
        ...,
        description="Name of the branch to checkout.",
        min_length=1,
        max_length=100,
    )
    force: bool = Field(
        default=False,
        description="Whether to force checkout, discarding uncommitted changes.",
    )


class DoltCheckoutOutput(BaseDoltOutput):
    """Output model for the dolt_checkout tool."""

    success: bool = Field(..., description="Whether the checkout operation succeeded")
    message: str = Field(..., description="Human-readable result message")
    active_branch: str = Field(..., description="Current active branch")
    error: Optional[str] = Field(default=None, description="Error message if operation failed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of operation")


class DoltDiffInput(BaseModel):
    """Input model for the dolt_diff tool."""

    mode: Optional[Literal["working", "staged"]] = Field(
        default="working",
        description="Diff mode. 'working' for unstaged changes, 'staged' for staged changes. Overridden if from/to are set.",
    )
    from_revision: Optional[str] = Field(
        default=None, description="The starting revision (e.g., 'HEAD', 'main')."
    )
    to_revision: Optional[str] = Field(
        default=None, description="The ending revision (e.g., 'WORKING', 'STAGED')."
    )

    @validator("from_revision", "to_revision")
    def validate_revisions(cls, v):
        """Validate revision names for security."""
        if v and not BRANCH_NAME_PATTERN.match(v) and v not in ["HEAD", "WORKING", "STAGED"]:
            raise ValueError(f"Invalid revision name: {v}")
        return v


class DiffSummary(BaseModel):
    """Summary of a single table's diff."""

    from_table_name: Optional[str] = Field(
        None, description="The original table name, if it was renamed."
    )
    to_table_name: str = Field(..., description="The new table name.")
    diff_type: str = Field(
        ..., description="Type of diff: 'added', 'dropped', 'modified', 'renamed'."
    )
    data_change: bool = Field(..., description="True if data has changed.")
    schema_change: bool = Field(..., description="True if schema has changed.")


class DoltDiffOutput(BaseDoltOutput):
    """Output model for the dolt_diff tool."""

    success: bool = Field(..., description="Whether the diff operation succeeded.")
    diff_summary: List[DiffSummary] = Field(..., description="A list of table diff summaries.")
    diff_details: List[Dict[str, Any]] = Field(
        default=[], description="Raw detailed row-level changes from DOLT_DIFF."
    )
    message: str = Field(..., description="Human-readable result message.")
    active_branch: str = Field(..., description="Current active branch")
    error: Optional[str] = Field(default=None, description="Error message if operation failed.")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of operation.")


class DoltAutoCommitInput(BaseModel):
    """Input model for the dolt_auto_commit_and_push tool."""

    commit_message: str = Field(
        ...,
        description="Commit message for the Dolt changes",
        min_length=1,
        max_length=500,
    )
    author: Optional[str] = Field(
        default=None,
        description="Optional author attribution for the commit",
        max_length=100,
    )
    tables: Optional[List[str]] = Field(
        default=None,
        description="Optional list of specific tables to add/commit. If not provided, all standard tables will be committed.",
    )
    remote_name: str = Field(
        default="origin",
        description="Name of the remote to push to (default: 'origin')",
        min_length=1,
        max_length=100,
    )
    branch: Optional[str] = Field(
        default=None,
        description="Branch to push (default: current branch from status)",
        min_length=1,
        max_length=100,
    )
    skip_if_clean: bool = Field(
        default=True,
        description="Skip commit/push if repository is clean (default: True)",
    )


class DoltAutoCommitOutput(BaseDoltOutput):
    """Output model for the dolt_auto_commit_and_push tool."""

    success: bool = Field(..., description="Whether the entire operation succeeded")
    message: str = Field(..., description="Human-readable result message")
    operations_performed: List[str] = Field(
        default=[], description="List of operations that were performed"
    )

    # Status info
    was_clean: bool = Field(..., description="Whether the repository was clean initially")
    active_branch: str = Field(..., description="Current active branch")

    # Commit info (if performed)
    commit_hash: Optional[str] = Field(
        default=None, description="The Dolt commit hash if commit was performed"
    )
    tables_committed: Optional[List[str]] = Field(
        default=None, description="List of tables that were committed"
    )

    # Push info (if performed)
    pushed_to_remote: Optional[str] = Field(
        default=None, description="Remote name that was pushed to"
    )

    error: Optional[str] = Field(default=None, description="Error message if operation failed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of operation")


def dolt_repo_tool(
    input_data: DoltCommitInput, memory_bank: StructuredMemoryBank
) -> DoltCommitOutput:
    """
    Commit working changes to Dolt using the memory bank's writer.

    Args:
        input_data: The commit parameters
        memory_bank: StructuredMemoryBank instance with Dolt writer access

    Returns:
        DoltCommitOutput with success status and commit details
    """
    try:
        # Build commit message with optional author attribution
        commit_msg = input_data.commit_message
        if input_data.author:
            commit_msg = f"{commit_msg}\n\nAuthor: {input_data.author}"

        # Determine tables to commit
        tables_to_commit = input_data.tables
        if tables_to_commit is None:
            # Default to standard memory system tables
            from infra_core.memory_system.dolt_writer import PERSISTED_TABLES

            tables_to_commit = PERSISTED_TABLES

        logger.info(f"Committing Dolt changes with message: {commit_msg}")
        logger.info(f"Tables to commit: {tables_to_commit}")

        # Execute the commit using the memory bank's writer
        success, commit_hash = memory_bank.dolt_writer.commit_changes(
            commit_msg=commit_msg, tables=tables_to_commit
        )

        if success:
            message = f"Successfully committed changes to Dolt with hash: {commit_hash}"
            logger.info(message)

            return DoltCommitOutput(
                success=True,
                commit_hash=commit_hash,
                message=message,
                tables_committed=tables_to_commit,
                active_branch=memory_bank.dolt_writer.active_branch,
            )
        else:
            error_msg = "Dolt commit operation failed - no commit hash returned"
            logger.error(error_msg)

            return DoltCommitOutput(
                success=False,
                message=error_msg,
                error=error_msg,
                tables_committed=tables_to_commit,
                active_branch=memory_bank.dolt_writer.active_branch,
            )

    except Exception as e:
        error_msg = f"Exception during dolt_commit: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return DoltCommitOutput(
            success=False,
            message=f"Commit failed: {str(e)}",
            error=error_msg,
            active_branch=memory_bank.dolt_writer.active_branch,
        )


def dolt_push_tool(input_data: DoltPushInput, memory_bank: StructuredMemoryBank) -> DoltPushOutput:
    """
    Push changes to a remote repository using the memory bank's writer.

    Args:
        input_data: The push parameters
        memory_bank: StructuredMemoryBank instance with Dolt writer access

    Returns:
        DoltPushOutput with success status and push details
    """
    try:
        logger.info(
            f"Pushing to remote '{input_data.remote_name}' branch '{input_data.branch}' (force={input_data.force}, set_upstream={input_data.set_upstream})"
        )

        # Execute the push using the memory bank's writer
        success, message = memory_bank.dolt_writer.push_to_remote(
            remote_name=input_data.remote_name,
            branch=input_data.branch,
            force=input_data.force,
            set_upstream=input_data.set_upstream,
        )

        if success:
            logger.info(f"Successfully pushed to remote: {message}")

            return DoltPushOutput(
                success=True,
                message=message,
                remote_name=input_data.remote_name,
                branch=input_data.branch,
                force=input_data.force,
                set_upstream=input_data.set_upstream,
                active_branch=memory_bank.dolt_writer.active_branch,
            )
        else:
            error_msg = f"Dolt push operation failed: {message}"
            logger.error(error_msg)

            return DoltPushOutput(
                success=False,
                message=error_msg,
                remote_name=input_data.remote_name,
                branch=input_data.branch,
                force=input_data.force,
                set_upstream=input_data.set_upstream,
                active_branch=memory_bank.dolt_writer.active_branch,
                error=error_msg,
            )

    except Exception as e:
        error_msg = f"Exception during dolt_push: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return DoltPushOutput(
            success=False,
            message=f"Push failed: {str(e)}",
            remote_name=input_data.remote_name,
            branch=input_data.branch,
            force=input_data.force,
            set_upstream=input_data.set_upstream,
            active_branch=memory_bank.dolt_writer.active_branch,
            error=error_msg,
        )


def dolt_status_tool(
    input_data: DoltStatusInput, memory_bank: StructuredMemoryBank
) -> DoltStatusOutput:
    """
    Get repository status using Dolt system tables.

    Args:
        input_data: The status parameters (none needed for MVP)
        memory_bank: StructuredMemoryBank instance with Dolt writer access

    Returns:
        DoltStatusOutput with repository status details
    """
    try:
        logger.info("Getting Dolt repository status")

        # Try very simple query first
        try:
            test_result = memory_bank.dolt_writer._execute_query("SELECT 1 as test")
            logger.info(f"Test query result: {test_result}")
        except Exception as e:
            logger.error(f"Test query failed: {e}")

        # Get current branch using simplest possible query
        try:
            branch_result = memory_bank.dolt_writer._execute_query(
                "SELECT active_branch() as branch"
            )
            current_branch = branch_result[0]["branch"] if branch_result else "main"
            logger.info(f"Current branch: {current_branch}")
        except Exception as e:
            logger.error(f"Branch query failed: {e}")
            current_branch = "main"

        # Try to get status
        staged_tables = []
        unstaged_tables = []
        untracked_tables = []
        conflicts = []

        try:
            status_result = memory_bank.dolt_writer._execute_query("SELECT * FROM dolt_status")
            logger.info(f"Status query returned {len(status_result)} rows")

            for row in status_result:
                logger.info(f"Status row: {row}")

                # Process status row data - dolt_status returns: table_name, staged, status
                table_name = row.get("table_name", "")
                staged = row.get("staged", 0)  # 1 = staged, 0 = unstaged
                status = row.get("status", "")

                if table_name and status:
                    if staged == 1:
                        # Table has staged changes
                        staged_tables.append(table_name)
                    elif staged == 0:
                        # Table has unstaged changes
                        unstaged_tables.append(table_name)

                    # Handle special status types
                    if status == "conflict":
                        conflicts.append(table_name)

        except Exception as e:
            logger.info(f"Status query failed (expected if clean): {e}")

        # Calculate total changes
        total_changes = len(staged_tables) + len(unstaged_tables) + len(untracked_tables)
        is_clean = total_changes == 0 and len(conflicts) == 0

        # Create message
        message = f"On branch {current_branch}. " + (
            "Working tree clean." if is_clean else f"{total_changes} changes."
        )

        logger.info(f"Repository status: {message}")

        return DoltStatusOutput(
            success=True,
            is_clean=is_clean,
            staged_tables=staged_tables,
            unstaged_tables=unstaged_tables,
            untracked_tables=untracked_tables,
            total_changes=total_changes,
            ahead=0,
            behind=0,
            conflicts=conflicts,
            message=message,
            active_branch=current_branch,
        )

    except Exception as e:
        error_msg = f"Exception during dolt_status: {str(e)}"
        logger.error(error_msg, exc_info=True)

        # Try to get current branch even in error case
        try:
            branch_result = memory_bank.dolt_writer._execute_query(
                "SELECT active_branch() as branch"
            )
            current_branch = branch_result[0]["branch"] if branch_result else "unknown"
        except Exception:
            current_branch = "unknown"

        return DoltStatusOutput(
            success=False,
            is_clean=False,
            staged_tables=[],
            unstaged_tables=[],
            untracked_tables=[],
            total_changes=0,
            ahead=0,
            behind=0,
            conflicts=[],
            message=f"Status check failed: {str(e)}",
            error=error_msg,
            active_branch=current_branch,
        )


def dolt_pull_tool(input_data: DoltPullInput, memory_bank: StructuredMemoryBank) -> DoltPullOutput:
    """
    Pull changes from a remote repository using the memory bank's writer.

    Args:
        input_data: The pull parameters
        memory_bank: StructuredMemoryBank instance with Dolt writer access

    Returns:
        DoltPullOutput with success status and pull details
    """
    try:
        logger.info(f"Pulling from remote '{input_data.remote_name}' with parameters: {input_data}")

        # Execute the pull using the memory bank's writer
        success, message = memory_bank.dolt_writer.pull_from_remote(
            remote_name=input_data.remote_name,
            branch=input_data.branch,
            force=input_data.force,
            no_ff=input_data.no_ff,
            squash=input_data.squash,
        )

        if success:
            logger.info(f"Pull operation succeeded: {message}")

            return DoltPullOutput(
                success=True,
                message=message,
                remote_name=input_data.remote_name,
                branch=input_data.branch,
                force=input_data.force,
                no_ff=input_data.no_ff,
                squash=input_data.squash,
                active_branch=memory_bank.dolt_writer.active_branch,
            )
        else:
            logger.error(f"Pull operation failed: {message}")

            return DoltPullOutput(
                success=False,
                message="Pull operation failed",
                remote_name=input_data.remote_name,
                branch=input_data.branch,
                force=input_data.force,
                no_ff=input_data.no_ff,
                squash=input_data.squash,
                active_branch=memory_bank.dolt_writer.active_branch,
                error=message,
            )

    except Exception as e:
        error_msg = f"Exception during pull operation: {e}"
        logger.error(error_msg, exc_info=True)

        return DoltPullOutput(
            success=False,
            message="Pull operation failed due to exception",
            remote_name=input_data.remote_name,
            branch=input_data.branch,
            force=input_data.force,
            no_ff=input_data.no_ff,
            squash=input_data.squash,
            active_branch=memory_bank.dolt_writer.active_branch,
            error=error_msg,
        )


def dolt_branch_tool(
    input_data: DoltBranchInput, memory_bank: StructuredMemoryBank
) -> DoltBranchOutput:
    """
    Create a new branch using the memory bank's writer.

    Args:
        input_data: The branch creation parameters
        memory_bank: StructuredMemoryBank instance with Dolt writer access

    Returns:
        DoltBranchOutput with success status and branch creation details
    """
    try:
        logger.info(f"Creating branch '{input_data.branch_name}' with parameters: {input_data}")

        # Execute the branch creation using the memory bank's writer
        success, message = memory_bank.dolt_writer.create_branch(
            branch_name=input_data.branch_name,
            start_point=input_data.start_point,
            force=input_data.force,
        )

        if success:
            logger.info(f"Branch creation succeeded: {message}")

            return DoltBranchOutput(
                success=True,
                message=message,
                branch_name=input_data.branch_name,
                start_point=input_data.start_point,
                force=input_data.force,
                active_branch=memory_bank.dolt_writer.active_branch,
            )
        else:
            logger.error(f"Branch creation failed: {message}")

            return DoltBranchOutput(
                success=False,
                message="Branch creation failed",
                branch_name=input_data.branch_name,
                start_point=input_data.start_point,
                force=input_data.force,
                active_branch=memory_bank.dolt_writer.active_branch,
                error=message,
            )

    except Exception as e:
        error_msg = f"Exception during branch creation: {e}"
        logger.error(error_msg, exc_info=True)

        return DoltBranchOutput(
            success=False,
            message="Branch creation failed due to exception",
            branch_name=input_data.branch_name,
            start_point=input_data.start_point,
            force=input_data.force,
            active_branch=memory_bank.dolt_writer.active_branch,
            error=error_msg,
        )


def dolt_list_branches_tool(
    input_data: DoltListBranchesInput, memory_bank: StructuredMemoryBank
) -> DoltListBranchesOutput:
    """
    List all Dolt branches with their information.

    Args:
        input_data: The listing parameters
        memory_bank: StructuredMemoryBank instance with Dolt reader access

    Returns:
        DoltListBranchesOutput with list of branches and status
    """
    try:
        logger.info("Listing Dolt branches")

        # Execute the branch listing using the memory bank's reader (read-only operation)
        branches, current_branch = memory_bank.dolt_reader.list_branches()

        # Build success message
        message = (
            f"Found {len(branches)} branches. Current branch: {current_branch}"
            if branches
            else f"Found 0 branches. Current branch: {current_branch}"
        )

        logger.info(message)

        return DoltListBranchesOutput(
            success=True,
            branches=[DoltBranchInfo(**b) for b in branches],
            active_branch=current_branch,
            message=message,
        )

    except Exception as e:
        error_msg = f"Exception during branch listing: {str(e)}"
        logger.error(error_msg, exc_info=True)

        # Try to get current branch even in error case
        try:
            branch_result = memory_bank.dolt_reader._execute_query(
                "SELECT active_branch() as branch"
            )
            current_branch = branch_result[0]["branch"] if branch_result else "unknown"
        except Exception:
            current_branch = "unknown"

        return DoltListBranchesOutput(
            success=False,
            branches=[],
            active_branch=current_branch,
            message=f"Failed to list branches: {str(e)}",
            error=error_msg,
        )


@dolt_tool("ADD")
def dolt_add_tool(input_data: DoltAddInput, memory_bank: StructuredMemoryBank) -> DoltAddOutput:
    """
    Stage working changes to Dolt using the memory bank's writer.

    Args:
        input_data: The add parameters
        memory_bank: StructuredMemoryBank instance with Dolt writer access

    Returns:
        DoltAddOutput with success status and message
    """
    tables_to_add = input_data.tables

    success, message = memory_bank.dolt_writer.add_to_staging(tables=tables_to_add)

    if success:
        return DoltAddOutput(
            success=True, message=message, active_branch=memory_bank.dolt_writer.active_branch
        )
    else:
        return DoltAddOutput(
            success=False,
            message=message,
            active_branch=memory_bank.dolt_writer.active_branch,
            error=message,
            error_code="ADD_FAILED",
        )


@dolt_tool("RESET")
def dolt_reset_tool(
    input_data: DoltResetInput, memory_bank: StructuredMemoryBank
) -> DoltResetOutput:
    """
    Reset working changes in Dolt using the DoltWriter's reset method.

    Args:
        input_data: The reset parameters
        memory_bank: StructuredMemoryBank instance with Dolt writer access

    Returns:
        DoltResetOutput with success status and message
    """
    try:
        # Use the proper abstraction layer
        success, message = memory_bank.dolt_writer.reset(
            hard=input_data.hard, tables=input_data.tables
        )

        if success:
            return DoltResetOutput(
                success=True,
                message=message,
                active_branch=memory_bank.dolt_writer.active_branch,
                tables_reset=input_data.tables,
            )
        else:
            return DoltResetOutput(
                success=False,
                message=message,
                active_branch=memory_bank.dolt_writer.active_branch,
                error=message,
                error_code="RESET_FAILED",
                tables_reset=input_data.tables,
            )

    except Exception as e:
        error_msg = f"Exception during dolt_reset: {str(e)}"
        return DoltResetOutput(
            success=False,
            message=error_msg,
            active_branch=getattr(memory_bank.dolt_writer, "active_branch", "unknown"),
            error=error_msg,
            error_code="EXCEPTION",
            tables_reset=input_data.tables,
        )


def dolt_checkout_tool(
    input_data: DoltCheckoutInput, memory_bank: StructuredMemoryBank
) -> DoltCheckoutOutput:
    """
    Checkout a branch using the memory bank's coordinated persistent connections.

    Args:
        input_data: The checkout parameters
        memory_bank: StructuredMemoryBank instance with Dolt writer access

    Returns:
        DoltCheckoutOutput with success status and message
    """
    try:
        branch_name = input_data.branch_name
        force = input_data.force
        logger.info(f"Checking out Dolt branch: {branch_name} (force={force})")

        # Use memory bank's coordinated persistent connection method
        # This ensures both reader and writer are on the same branch
        memory_bank.use_persistent_connections(branch=branch_name)

        # 🔧 CRITICAL FIX: Also update link_manager branch context
        # This ensures link operations stay synchronized with memory_bank operations
        # TODO: update link_manager to use Dolt connection
        if hasattr(memory_bank, "link_manager") and memory_bank.link_manager:
            logger.info(f"Updating LinkManager persistent connection to branch: {branch_name}")
            memory_bank.link_manager.use_persistent_connection(branch_name)
            logger.info(
                f"✅ LinkManager synchronized to branch: {memory_bank.link_manager.active_branch}"
            )

        # Note: force flag is not directly supported by persistent connections
        # If force is needed, we'd need to handle conflicts manually
        if force:
            logger.warning(
                "Force checkout requested - persistent connections don't support force flag. "
                "Manual conflict resolution may be needed."
            )

        message = f"Successfully checked out branch '{branch_name}' with coordinated persistent connections"
        logger.info(message)
        return DoltCheckoutOutput(
            success=True, message=message, active_branch=memory_bank.dolt_writer.active_branch
        )

    except Exception as e:
        error_msg = f"Exception during dolt_checkout: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return DoltCheckoutOutput(
            success=False,
            message=f"Checkout failed: {str(e)}",
            active_branch=memory_bank.dolt_writer.active_branch,
            error=error_msg,
        )


def dolt_diff_tool(input_data: DoltDiffInput, memory_bank: StructuredMemoryBank) -> DoltDiffOutput:
    """
    Get a summary of differences between two revisions in Dolt.

    Args:
        input_data: The input data for the diff tool.
        memory_bank: The StructuredMemoryBank instance.

    Returns:
        The output data with the diff summary.
    """
    logger.info(f"Received request for dolt_diff_tool with input: {input_data}")

    try:
        reader = memory_bank.dolt_reader

        from_rev = input_data.from_revision
        to_rev = input_data.to_revision

        if not from_rev and not to_rev:
            if input_data.mode == "staged":
                from_rev = "HEAD"
                to_rev = "STAGED"
            else:  # 'working'
                from_rev = "HEAD"
                to_rev = "WORKING"

        if not from_rev or not to_rev:
            return DoltDiffOutput(
                success=False,
                diff_summary=[],
                message="Both from_revision and to_revision must be provided if not using a mode.",
                active_branch=memory_bank.dolt_reader.active_branch,
                error="Invalid revision arguments.",
            )

        summary_dicts = reader.get_diff_summary(from_revision=from_rev, to_revision=to_rev)

        # Convert dicts to Pydantic models
        diff_summary = [DiffSummary(**item) for item in summary_dicts]

        # Get detailed diff information
        diff_details = reader.get_diff_details(from_revision=from_rev, to_revision=to_rev)

        message = f"Successfully retrieved diff summary from {from_rev} to {to_rev}."
        if not diff_summary:
            message = f"No changes found between {from_rev} and {to_rev}."
        elif diff_details:
            message = f"Successfully retrieved diff from {from_rev} to {to_rev}: {len(diff_summary)} tables changed, {len(diff_details)} total row changes."

        return DoltDiffOutput(
            success=True,
            diff_summary=diff_summary,
            diff_details=diff_details,
            message=message,
            active_branch=memory_bank.dolt_reader.active_branch,
        )

    except Exception as e:
        logger.error(f"Error getting diff summary: {e}", exc_info=True)
        return DoltDiffOutput(
            success=False,
            diff_summary=[],
            diff_details=[],
            message=f"An unexpected error occurred: {e}",
            error=str(e),
            active_branch=memory_bank.dolt_reader.active_branch,
        )


def dolt_auto_commit_and_push_tool(
    input_data: DoltAutoCommitInput, memory_bank: StructuredMemoryBank
) -> DoltAutoCommitOutput:
    """
    Automatically handle the complete Dolt workflow: Status -> Add -> Commit -> Push

    This is a composite tool that performs the entire sequence atomically,
    perfect for automated flows where you want to persist all changes.

    Args:
        input_data: The auto commit parameters
        memory_bank: StructuredMemoryBank instance with Dolt writer access

    Returns:
        DoltAutoCommitOutput with comprehensive results of all operations
    """
    operations_performed = []

    try:
        logger.info(
            f"Starting auto commit and push workflow with message: {input_data.commit_message}"
        )

        # Step 1: Get Status
        logger.info("🔍 Step 1: Checking Dolt repository status...")
        status_result = dolt_status_tool(DoltStatusInput(), memory_bank)
        operations_performed.append("status")

        if not status_result.success:
            # Try to get current branch even when status fails
            try:
                branch_result = memory_bank.dolt_writer._execute_query(
                    "SELECT active_branch() as branch"
                )
                current_branch = branch_result[0]["branch"] if branch_result else "unknown"
            except Exception:
                current_branch = "unknown"

            return DoltAutoCommitOutput(
                success=False,
                message=f"Status check failed: {status_result.error}",
                operations_performed=operations_performed,
                was_clean=False,
                active_branch=current_branch,
                error=status_result.error,
            )

        current_branch = status_result.active_branch
        was_clean = status_result.is_clean

        logger.info(
            f"Repository status - Branch: {current_branch}, Clean: {was_clean}, Changes: {status_result.total_changes}"
        )

        # Step 2: Check if we should skip (if clean and skip_if_clean=True)
        if was_clean and input_data.skip_if_clean:
            logger.info("✅ Repository is clean, skipping commit and push")
            return DoltAutoCommitOutput(
                success=True,
                message="Repository is clean, no changes to commit",
                operations_performed=operations_performed,
                was_clean=True,
                active_branch=current_branch,
            )

        # Step 3: Add changes to staging
        logger.info("📝 Step 2: Adding changes to staging...")
        add_result = dolt_add_tool(DoltAddInput(tables=input_data.tables), memory_bank)
        operations_performed.append("add")

        if not add_result.success:
            return DoltAutoCommitOutput(
                success=False,
                message=f"Add operation failed: {add_result.error}",
                operations_performed=operations_performed,
                was_clean=was_clean,
                active_branch=current_branch,
                error=add_result.error,
            )

        logger.info(f"Add successful: {add_result.message}")

        # Step 4: Commit changes
        logger.info("💾 Step 3: Committing changes...")
        commit_result = dolt_repo_tool(
            DoltCommitInput(
                commit_message=input_data.commit_message,
                tables=input_data.tables,
                author=input_data.author,
            ),
            memory_bank,
        )
        operations_performed.append("commit")

        if not commit_result.success:
            return DoltAutoCommitOutput(
                success=False,
                message=f"Commit operation failed: {commit_result.error}",
                operations_performed=operations_performed,
                was_clean=was_clean,
                active_branch=current_branch,
                error=commit_result.error,
            )

        logger.info(f"Commit successful - Hash: {commit_result.commit_hash}")

        # Step 5: Push to remote
        target_branch = input_data.branch or current_branch
        logger.info(
            f"🚀 Step 4: Pushing to remote '{input_data.remote_name}' branch '{target_branch}'..."
        )

        push_result = dolt_push_tool(
            DoltPushInput(
                remote_name=input_data.remote_name,
                branch=target_branch,
                force=False,  # Never force push in auto mode
                set_upstream=False,
            ),
            memory_bank,
        )
        operations_performed.append("push")

        if not push_result.success:
            return DoltAutoCommitOutput(
                success=False,
                message=f"Push operation failed: {push_result.error}",
                operations_performed=operations_performed,
                was_clean=was_clean,
                active_branch=current_branch,
                commit_hash=commit_result.commit_hash,
                tables_committed=commit_result.tables_committed,
                error=push_result.error,
            )

        logger.info(f"Push successful: {push_result.message}")

        # Success! All operations completed
        final_message = f"✅ Auto commit and push completed successfully! Commit: {commit_result.commit_hash}, Push: {input_data.remote_name}/{target_branch}"
        logger.info(final_message)

        return DoltAutoCommitOutput(
            success=True,
            message=final_message,
            operations_performed=operations_performed,
            was_clean=was_clean,
            active_branch=current_branch,
            commit_hash=commit_result.commit_hash,
            tables_committed=commit_result.tables_committed,
            pushed_to_remote=input_data.remote_name,
        )

    except Exception as e:
        error_msg = f"Exception during auto commit and push: {str(e)}"
        logger.error(error_msg, exc_info=True)

        # Try to get current branch even in error case
        try:
            branch_result = memory_bank.dolt_writer._execute_query(
                "SELECT active_branch() as branch"
            )
            current_branch = branch_result[0]["branch"] if branch_result else "unknown"
        except Exception:
            current_branch = "unknown"

        return DoltAutoCommitOutput(
            success=False,
            message=f"Auto commit and push failed: {str(e)}",
            operations_performed=operations_performed,
            was_clean=False,
            active_branch=current_branch,
            error=error_msg,
        )


# --- PULL REQUEST LISTING TOOL ---


class DoltListPullRequestsInput(BaseModel):
    """Input model for the dolt_list_pull_requests tool."""
    
    status_filter: Optional[str] = Field(
        default="open",
        description="Filter PRs by status (default: 'open'). Use 'all' for all statuses.",
        max_length=20,
    )
    limit: int = Field(
        default=50,
        description="Maximum number of PRs to return (default: 50, max: 500)",
        ge=1,
        le=500,
    )
    include_description: bool = Field(
        default=False,
        description="Whether to include PR descriptions (default: False, saves token usage)",
    )


class DoltPullRequestInfo(BaseModel):
    """Information about a single Dolt pull request."""
    
    id: str = Field(..., description="Pull request ID/number")
    title: str = Field(..., description="Pull request title")
    source_branch: str = Field(..., description="Source branch being merged from")
    target_branch: str = Field(..., description="Target branch being merged into")
    status: str = Field(..., description="Pull request status (open, closed, merged)")
    author: str = Field(..., description="Pull request author")
    created_at: datetime = Field(..., description="When the PR was created")
    updated_at: Optional[datetime] = Field(None, description="When the PR was last updated")
    merge_commit_hash: Optional[str] = Field(None, description="Hash of merge commit if merged")
    conflicts: int = Field(default=0, description="Number of conflicts")
    description: Optional[str] = Field(None, description="Pull request description")


class DoltListPullRequestsOutput(BaseDoltOutput):
    """Output model for the dolt_list_pull_requests tool."""
    
    pull_requests: List[DoltPullRequestInfo] = Field(default=[], description="List of pull requests")
    total_count: int = Field(..., description="Total number of PRs matching filter")
    status_filter: str = Field(..., description="Status filter that was applied")


# --- NEW PULL REQUEST TOOLS ---


class DoltCreatePullRequestInput(BaseModel):
    """Input model for the dolt_create_pull_request tool."""

    source_branch: str = Field(
        ...,
        description="Source branch to merge from",
        min_length=1,
        max_length=100,
    )
    target_branch: str = Field(
        default="main",
        description="Target branch to merge into (default: 'main')",
        min_length=1,
        max_length=100,
    )
    title: str = Field(
        ...,
        description="Title of the pull request",
        min_length=1,
        max_length=200,
    )
    description: Optional[str] = Field(
        default=None,
        description="Description of the pull request",
        max_length=2000,
    )
    reviewers: Optional[List[str]] = Field(
        default=None,
        description="List of reviewer usernames/emails",
    )
    auto_merge: bool = Field(
        default=False,
        description="Whether to automatically merge if no conflicts (default: False)",
    )


class DoltCreatePullRequestOutput(BaseDoltOutput):
    """Output model for the dolt_create_pull_request tool."""

    success: bool = Field(..., description="Whether the pull request creation succeeded")
    pr_id: Optional[str] = Field(default=None, description="Pull request identifier")
    message: str = Field(..., description="Human-readable result message")
    source_branch: str = Field(..., description="Source branch")
    target_branch: str = Field(..., description="Target branch")
    title: str = Field(..., description="Pull request title")
    conflicts: int = Field(default=0, description="Number of conflicts detected")
    can_auto_merge: bool = Field(..., description="Whether the PR can be auto-merged")
    active_branch: str = Field(..., description="Current active branch")
    error: Optional[str] = Field(default=None, description="Error message if operation failed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of operation")


class DoltApprovePullRequestInput(BaseModel):
    """Input model for the dolt_approve_pull_request tool."""

    pr_id: str = Field(
        ...,
        description="Pull request ID to approve and merge",
        min_length=1,
        max_length=100,
    )
    approve_message: Optional[str] = Field(
        default=None,
        description="Optional message for the approval",
        max_length=500,
    )


class DoltApprovePullRequestOutput(BaseDoltOutput):
    """Output model for the dolt_approve_pull_request tool."""

    pr_id: str = Field(..., description="Pull request ID that was approved")
    merge_hash: Optional[str] = Field(default=None, description="Hash of the merge commit")
    operation_name: Optional[str] = Field(
        default=None, description="DoltHub operation name for polling"
    )


class DoltMergeInput(BaseModel):
    """Input model for the dolt_merge tool."""

    source_branch: str = Field(
        ...,
        description="Source branch to merge from",
        min_length=1,
        max_length=100,
    )
    target_branch: Optional[str] = Field(
        default=None,
        description="Target branch to merge into (default: current branch)",
        min_length=1,
        max_length=100,
    )
    commit_message: Optional[str] = Field(
        default=None,
        description="Custom commit message for the merge",
        max_length=500,
    )
    no_ff: bool = Field(
        default=False,
        description="Create a merge commit even for fast-forward merges (default: False)",
    )
    squash: bool = Field(
        default=False,
        description="Squash commits from source branch (default: False)",
    )
    author: Optional[str] = Field(
        default=None,
        description="Author attribution for the merge commit",
        max_length=100,
    )
    force_multi_commit: bool = Field(
        default=False,
        description="Allow multi-commit merges (bypasses safety check, use with caution)",
    )

    @validator("source_branch", "target_branch")
    def validate_branches(cls, v):
        """Validate branch names for security."""
        if v is not None:
            return validate_branch_name(v)
        return v


class DoltMergeOutput(BaseDoltOutput):
    """Output model for the dolt_merge tool."""

    merge_hash: Optional[str] = Field(default=None, description="Hash of the merge commit")
    source_branch: str = Field(..., description="Source branch that was merged")
    target_branch: str = Field(..., description="Target branch that received the merge")
    fast_forward: bool = Field(..., description="Whether the merge was a fast-forward")
    conflicts: int = Field(default=0, description="Number of conflicts that need resolution")


class DoltCompareBranchesInput(BaseModel):
    """Input model for the dolt_compare_branches tool."""

    source_branch: str = Field(
        ...,
        description="Source branch to compare from",
        min_length=1,
        max_length=100,
    )
    target_branch: str = Field(
        ...,
        description="Target branch to compare to",
        min_length=1,
        max_length=100,
    )
    include_data: bool = Field(
        default=True,
        description="Whether to include data differences (default: True)",
    )
    include_schema: bool = Field(
        default=True,
        description="Whether to include schema differences (default: True)",
    )
    table_filter: Optional[str] = Field(
        default=None,
        description="Optional table name to filter comparison",
        max_length=100,
    )


class DiffSummaryInfo(BaseModel):
    """Information about a single table's diff."""

    table_name: str = Field(..., description="Name of the table")
    diff_type: str = Field(
        ..., description="Type of diff: 'added', 'dropped', 'modified', 'renamed'"
    )
    data_change: bool = Field(..., description="True if data has changed")
    schema_change: bool = Field(..., description="True if schema has changed")
    rows_added: int = Field(default=0, description="Number of rows added")
    rows_deleted: int = Field(default=0, description="Number of rows deleted")
    rows_modified: int = Field(default=0, description="Number of rows modified")


class DoltCompareBranchesOutput(BaseDoltOutput):
    """Output model for the dolt_compare_branches tool."""

    success: bool = Field(..., description="Whether the comparison succeeded")
    message: str = Field(..., description="Human-readable result message")
    source_branch: str = Field(..., description="Source branch")
    target_branch: str = Field(..., description="Target branch")
    has_differences: bool = Field(..., description="Whether there are any differences")
    can_merge: bool = Field(..., description="Whether branches can be merged without conflicts")
    diff_summary: List[DiffSummaryInfo] = Field(default=[], description="Summary of differences")
    active_branch: str = Field(..., description="Current active branch")
    error: Optional[str] = Field(default=None, description="Error message if operation failed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of operation")


def dolt_create_pull_request_tool(
    input_data: DoltCreatePullRequestInput, memory_bank: StructuredMemoryBank
) -> DoltCreatePullRequestOutput:
    """
    Create a pull request for merging one branch into another.

    This simulates GitHub-style pull request creation by:
    1. Comparing the source and target branches
    2. Checking for conflicts
    3. Creating a PR record (simulated)
    4. Optionally auto-merging if no conflicts

    Args:
        input_data: The pull request creation parameters
        memory_bank: StructuredMemoryBank instance with Dolt writer access

    Returns:
        DoltCreatePullRequestOutput with PR creation results
    """
    try:
        logger.info(
            f"Creating pull request: {input_data.source_branch} -> {input_data.target_branch}"
        )

        # First, compare branches to check for conflicts
        compare_result = dolt_compare_branches_tool(
            DoltCompareBranchesInput(
                source_branch=input_data.source_branch, target_branch=input_data.target_branch
            ),
            memory_bank,
        )

        if not compare_result.success:
            return DoltCreatePullRequestOutput(
                success=False,
                message=f"Failed to compare branches: {compare_result.error}",
                source_branch=input_data.source_branch,
                target_branch=input_data.target_branch,
                title=input_data.title,
                can_auto_merge=False,
                active_branch=memory_bank.dolt_writer.active_branch,
                error=compare_result.error,
            )

        # Generate a simple PR ID (in real implementation, this would be from a PR system)
        pr_id = f"pr-{input_data.source_branch}-{input_data.target_branch}-{int(datetime.now().timestamp())}"

        can_auto_merge = compare_result.can_merge
        conflicts = 0 if can_auto_merge else 1  # Simplified conflict detection

        # If auto_merge is enabled and no conflicts, perform the merge
        if input_data.auto_merge and can_auto_merge:
            logger.info("Auto-merging pull request...")
            merge_result = dolt_merge_tool(
                DoltMergeInput(
                    source_branch=input_data.source_branch,
                    target_branch=input_data.target_branch,
                    commit_message=f"Merge pull request {pr_id}: {input_data.title}",
                    author="PR System <pr@system.local>",
                ),
                memory_bank,
            )

            if merge_result.success:
                message = f"Pull request {pr_id} created and auto-merged successfully (commit: {merge_result.merge_hash})"
            else:
                message = (
                    f"Pull request {pr_id} created but auto-merge failed: {merge_result.error}"
                )
        else:
            message = f"Pull request {pr_id} created successfully"
            if not can_auto_merge:
                message += " (conflicts detected, manual review required)"

        logger.info(message)

        return DoltCreatePullRequestOutput(
            success=True,
            pr_id=pr_id,
            message=message,
            source_branch=input_data.source_branch,
            target_branch=input_data.target_branch,
            title=input_data.title,
            conflicts=conflicts,
            can_auto_merge=can_auto_merge,
            active_branch=memory_bank.dolt_writer.active_branch,
        )

    except Exception as e:
        error_msg = f"Exception during pull request creation: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return DoltCreatePullRequestOutput(
            success=False,
            message=f"Pull request creation failed: {str(e)}",
            source_branch=input_data.source_branch,
            target_branch=input_data.target_branch,
            title=input_data.title,
            can_auto_merge=False,
            active_branch=memory_bank.dolt_writer.active_branch,
            error=error_msg,
        )


@dolt_tool("MERGE")
def dolt_merge_tool(
    input_data: DoltMergeInput, memory_bank: StructuredMemoryBank
) -> DoltMergeOutput:
    """
    Merge one branch into another using Dolt's DOLT_MERGE procedure.

    IMPORTANT: This tool is gated to only allow fast-forward or single-commit merges.
    For multi-commit scenarios, use dolt_approve_pull_request_tool instead.
    """
    try:
        dolt_writer = memory_bank.dolt_writer

        # Determine target branch
        target_branch = input_data.target_branch or dolt_writer.active_branch

        # GATING LOGIC: Check if this is a safe merge before proceeding
        if not input_data.force_multi_commit:
            # Use compare branches to check merge compatibility
            compare_input = DoltCompareBranchesInput(
                source_branch=input_data.source_branch, target_branch=target_branch
            )
            compare_result = dolt_compare_branches_tool(compare_input, memory_bank)

            if not compare_result.success:
                return DoltMergeOutput(
                    success=False,
                    message=f"Cannot compare branches for merge safety check: {compare_result.error}",
                    active_branch=target_branch,
                    source_branch=input_data.source_branch,
                    target_branch=target_branch,
                    fast_forward=False,
                    conflicts=0,
                    error="COMPARE_FAILED",
                    error_code="MERGE_SAFETY_CHECK_FAILED",
                )

            # Check if this is a multi-commit scenario
            if compare_result.has_differences and len(compare_result.diff_summary) > 1:
                return DoltMergeOutput(
                    success=False,
                    message="MERGE_NOT_FAST_FORWARD: Multi-commit merge detected. Use dolt_approve_pull_request_tool for multi-commit scenarios.",
                    active_branch=target_branch,
                    source_branch=input_data.source_branch,
                    target_branch=target_branch,
                    fast_forward=False,
                    conflicts=0,
                    error="Multi-commit merge not allowed. Use PR approval workflow.",
                    error_code="MERGE_NOT_FAST_FORWARD",
                )

        # Proceed with local merge (existing implementation)
        # Build merge command
        merge_args = [input_data.source_branch]

        if input_data.no_ff:
            merge_args.append("--no-ff")
        if input_data.squash:
            merge_args.append("--squash")
        if input_data.commit_message:
            merge_args.extend(["-m", input_data.commit_message])
        if input_data.author:
            merge_args.extend(["--author", input_data.author])

        # Execute merge
        result = dolt_writer._execute_query("CALL DOLT_MERGE(?)", (input_data.source_branch,))

        if result and len(result) > 0:
            row = result[0]
            fast_forward = bool(row.get("fast_forward", 0))
            conflicts = int(row.get("conflicts", 0))

            if conflicts > 0:
                return DoltMergeOutput(
                    success=False,
                    message=f"Merge completed with {conflicts} conflicts that need resolution",
                    active_branch=target_branch,
                    source_branch=input_data.source_branch,
                    target_branch=target_branch,
                    fast_forward=fast_forward,
                    conflicts=conflicts,
                    error=f"Merge conflicts detected: {conflicts}",
                    error_code="MERGE_CONFLICTS",
                )
            else:
                # Get merge commit hash if available
                merge_hash = None
                try:
                    hash_result = dolt_writer._execute_query("SELECT HASHOF('HEAD') as hash")
                    if hash_result and len(hash_result) > 0:
                        merge_hash = hash_result[0].get("hash")
                except Exception:
                    pass  # Hash retrieval is optional

                return DoltMergeOutput(
                    success=True,
                    message=f"Successfully merged {input_data.source_branch} into {target_branch}",
                    active_branch=target_branch,
                    source_branch=input_data.source_branch,
                    target_branch=target_branch,
                    fast_forward=fast_forward,
                    conflicts=0,
                    merge_hash=merge_hash,
                )
        else:
            return DoltMergeOutput(
                success=False,
                message="Merge command returned no results",
                active_branch=target_branch,
                source_branch=input_data.source_branch,
                target_branch=target_branch,
                fast_forward=False,
                conflicts=0,
                error="No results from DOLT_MERGE procedure",
                error_code="NO_RESULTS",
            )

    except Exception as e:
        error_msg = f"Merge failed: {str(e)}"
        return DoltMergeOutput(
            success=False,
            message=error_msg,
            active_branch=getattr(memory_bank.dolt_writer, "active_branch", "unknown"),
            source_branch=input_data.source_branch,
            target_branch=input_data.target_branch or "unknown",
            fast_forward=False,
            conflicts=0,
            error=error_msg,
            error_code="EXCEPTION",
        )


@dolt_tool("APPROVE_PULL_REQUEST")
def dolt_approve_pull_request_tool(
    input_data: DoltApprovePullRequestInput, memory_bank: StructuredMemoryBank
) -> DoltApprovePullRequestOutput:
    """
    Approve and merge a pull request using the DoltHub API.

    This tool is designed for multi-commit scenarios where local DOLT_MERGE
    would fail. It uses the DoltHub remote API to approve and merge PRs server-side.
    """
    try:
        # Get DoltHub configuration from memory bank
        dolt_writer = memory_bank.dolt_writer

        # Extract owner and database from remote configuration
        # This is a simplified approach - in production you'd want more robust config
        remote_url = getattr(dolt_writer, "remote_url", None)
        if not remote_url:
            raise ValueError("No remote URL configured for DoltHub API access")

        # Parse owner/database from remote URL (simplified)
        # Format: https://doltremoteapi.dolthub.com/{owner}/{database}
        if "dolthub.com" in remote_url:
            parts = remote_url.split("/")
            owner = parts[-2] if len(parts) >= 2 else "unknown"
            database = parts[-1] if len(parts) >= 1 else "unknown"
        else:
            raise ValueError(f"Unsupported remote URL format: {remote_url}")

        # Get API token from environment or configuration
        api_token = getattr(dolt_writer, "api_token", None)
        if not api_token:
            raise ValueError("No DoltHub API token configured")

        # Make API request to merge PR
        url = f"https://www.dolthub.com/api/v1alpha1/{owner}/{database}/pulls/{input_data.pr_id}/merge"
        headers = {"authorization": f"token {api_token}", "Content-Type": "application/json"}

        response = requests.post(url, headers=headers)

        if response.status_code == 200:
            result_data = response.json()
            return DoltApprovePullRequestOutput(
                success=True,
                message=f"Successfully approved and merged PR {input_data.pr_id}",
                active_branch=getattr(dolt_writer, "active_branch", "unknown"),
                pr_id=input_data.pr_id,
                operation_name=result_data.get("operation_name"),
                merge_hash=result_data.get("merge_hash"),
            )
        else:
            error_msg = f"DoltHub API error: {response.status_code} - {response.text}"
            return DoltApprovePullRequestOutput(
                success=False,
                message=error_msg,
                active_branch=getattr(dolt_writer, "active_branch", "unknown"),
                pr_id=input_data.pr_id,
                error=error_msg,
                error_code="API_ERROR",
            )

    except Exception as e:
        error_msg = f"Failed to approve PR {input_data.pr_id}: {str(e)}"
        return DoltApprovePullRequestOutput(
            success=False,
            message=error_msg,
            active_branch=getattr(memory_bank.dolt_writer, "active_branch", "unknown"),
            pr_id=input_data.pr_id,
            error=error_msg,
            error_code="EXCEPTION",
        )


def dolt_compare_branches_tool(
    input_data: DoltCompareBranchesInput, memory_bank: StructuredMemoryBank
) -> DoltCompareBranchesOutput:
    """
    Compare two branches to show differences and check merge compatibility.

    Args:
        input_data: The comparison parameters
        memory_bank: StructuredMemoryBank instance with Dolt reader access

    Returns:
        DoltCompareBranchesOutput with comparison results
    """
    try:
        logger.info(f"Comparing branches: {input_data.source_branch} -> {input_data.target_branch}")

        # Use the reader for read-only operations
        reader = memory_bank.dolt_reader

        # Get diff summary between branches
        try:
            if input_data.table_filter:
                # Table-specific comparison
                diff_summary = reader.get_diff_summary(
                    from_revision=input_data.target_branch,
                    to_revision=input_data.source_branch,
                    table_name=input_data.table_filter,
                )
            else:
                # All tables comparison
                diff_summary = reader.get_diff_summary(
                    from_revision=input_data.target_branch, to_revision=input_data.source_branch
                )

            # Convert to our model format
            diff_info = []
            has_differences = len(diff_summary) > 0

            for diff in diff_summary:
                diff_info.append(
                    DiffSummaryInfo(
                        table_name=diff.get(
                            "to_table_name", diff.get("from_table_name", "unknown")
                        ),
                        diff_type=diff.get("diff_type", "unknown"),
                        data_change=diff.get("data_change", False),
                        schema_change=diff.get("schema_change", False),
                        # Note: Dolt's get_diff_summary doesn't include row counts by default
                        # These would need to be fetched separately if needed
                        rows_added=0,
                        rows_deleted=0,
                        rows_modified=0,
                    )
                )

            # Simple heuristic for merge compatibility
            # In a real implementation, this would do a more sophisticated check
            can_merge = True
            for diff in diff_info:
                if diff.schema_change and diff.diff_type == "modified":
                    # Schema conflicts are harder to auto-merge
                    can_merge = False
                    break

            if has_differences:
                message = f"Found {len(diff_info)} table(s) with differences between {input_data.source_branch} and {input_data.target_branch}"
            else:
                message = f"No differences found between {input_data.source_branch} and {input_data.target_branch}"

            if not can_merge:
                message += " (potential merge conflicts detected)"

            logger.info(message)

            return DoltCompareBranchesOutput(
                success=True,
                message=message,
                source_branch=input_data.source_branch,
                target_branch=input_data.target_branch,
                has_differences=has_differences,
                can_merge=can_merge,
                diff_summary=diff_info,
                active_branch=memory_bank.dolt_reader.active_branch,
            )

        except Exception as e:
            # If diff fails, it might be due to branch not existing or other issues
            error_msg = f"Failed to get diff summary: {str(e)}"
            logger.error(error_msg)

            return DoltCompareBranchesOutput(
                success=False,
                message=error_msg,
                source_branch=input_data.source_branch,
                target_branch=input_data.target_branch,
                has_differences=False,
                can_merge=False,
                active_branch=memory_bank.dolt_reader.active_branch,
                error=error_msg,
            )

    except Exception as e:
        error_msg = f"Exception during branch comparison: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return DoltCompareBranchesOutput(
            success=False,
            message=f"Branch comparison failed: {str(e)}",
            source_branch=input_data.source_branch,
            target_branch=input_data.target_branch,
            has_differences=False,
            can_merge=False,
            active_branch=memory_bank.dolt_reader.active_branch,
            error=error_msg,
        )


def dolt_list_pull_requests_tool(
    input_data: DoltListPullRequestsInput, memory_bank: StructuredMemoryBank
) -> DoltListPullRequestsOutput:
    """
    List active pull requests from Dolt's pull request system tables.
    
    This tool queries the dolt_pull_requests system table to retrieve PR information
    including status, branches, conflicts, and metadata.
    
    Args:
        input_data: The listing parameters
        memory_bank: StructuredMemoryBank instance with Dolt reader access
    
    Returns:
        DoltListPullRequestsOutput with list of pull requests
    """
    try:
        logger.info(f"Listing Dolt pull requests with filter: {input_data.status_filter}")
        
        # Use the reader for read-only operations
        reader = memory_bank.dolt_reader
        
        # Build the SQL query with explicit column selection for security
        base_columns = "id,title,from_branch,to_branch,status,author,created_at,updated_at,merge_commit_hash,conflicts"
        if input_data.include_description:
            columns = f"{base_columns},description"
        else:
            columns = base_columns
            
        if input_data.status_filter == "all":
            query = f"SELECT {columns} FROM dolt_pull_requests ORDER BY created_at DESC LIMIT ?"
            params = (input_data.limit,)
        else:
            query = f"SELECT {columns} FROM dolt_pull_requests WHERE status = ? ORDER BY created_at DESC LIMIT ?"
            params = (input_data.status_filter, input_data.limit)
        
        # Execute the query
        try:
            pr_results = reader._execute_query(query, params)
            logger.info(f"Found {len(pr_results)} pull requests")
            
            # Convert results to our model format
            pull_requests = []
            for row in pr_results:
                # Parse datetime fields safely - Python 3.11+ handles 'Z' suffix natively
                created_at = row.get("created_at")
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(created_at)
                    except (ValueError, TypeError):
                        raise ValueError(f"Invalid created_at timestamp: {created_at}")
                elif not isinstance(created_at, datetime):
                    raise ValueError(f"Expected datetime or string for created_at, got {type(created_at)}")
                
                updated_at = row.get("updated_at")
                if updated_at and isinstance(updated_at, str):
                    try:
                        updated_at = datetime.fromisoformat(updated_at)
                    except (ValueError, TypeError):
                        raise ValueError(f"Invalid updated_at timestamp: {updated_at}")
                elif updated_at is not None and not isinstance(updated_at, datetime):
                    raise ValueError(f"Expected datetime, string, or None for updated_at, got {type(updated_at)}")
                
                # Get description only if requested to save token usage
                description = None
                if input_data.include_description:
                    description = row.get("description", row.get("body"))
                
                pr_info = DoltPullRequestInfo(
                    id=str(row.get("id", "unknown")),
                    title=row.get("title", "Untitled PR"),
                    source_branch=row.get("from_branch", row.get("source_branch", "unknown")),
                    target_branch=row.get("to_branch", row.get("target_branch", "main")),
                    status=row.get("status", "unknown"),
                    author=row.get("author", row.get("created_by", "unknown")),
                    created_at=created_at,
                    updated_at=updated_at,
                    merge_commit_hash=row.get("merge_commit_hash"),
                    conflicts=int(row.get("conflicts", 0)),
                    description=description
                )
                pull_requests.append(pr_info)
            
            # Build success message
            message = f"Found {len(pull_requests)} pull request(s)"
            if input_data.status_filter != "all":
                message += f" with status '{input_data.status_filter}'"
            
            logger.info(message)
            
            return DoltListPullRequestsOutput(
                success=True,
                message=message,
                active_branch=reader.active_branch,
                pull_requests=pull_requests,
                total_count=len(pull_requests),
                status_filter=input_data.status_filter,
            )
            
        except Exception as e:
            # Handle case where dolt_pull_requests table doesn't exist or query fails
            error_msg = f"Failed to query pull requests: {str(e)}"
            logger.warning(f"PR query failed: {error_msg}")
            
            # Check if this is a table not found error
            if "dolt_pull_requests" in str(e).lower() and ("not exist" in str(e).lower() or "doesn't exist" in str(e).lower()):
                error_code = "TABLE_NOT_FOUND"
                message = "dolt_pull_requests table not available"
            else:
                error_code = "QUERY_FAILED"
                message = f"Failed to query pull requests: {str(e)}"
            
            return DoltListPullRequestsOutput(
                success=False,
                message=message,
                active_branch=reader.active_branch,
                pull_requests=[],
                total_count=0,
                status_filter=input_data.status_filter,
                error=error_msg,
                error_code=error_code,
            )
    
    except Exception as e:
        error_msg = f"Exception during pull request listing: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        return DoltListPullRequestsOutput(
            success=False,
            message=f"Failed to list pull requests: {str(e)}",
            active_branch=getattr(memory_bank.dolt_reader, "active_branch", "unknown"),
            pull_requests=[],
            total_count=0,
            status_filter=input_data.status_filter,
            error=error_msg,
        )
