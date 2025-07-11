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

from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.tools.base.cogni_tool import CogniTool

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


class DoltMergeInput(BaseModel):
    """Input model for the dolt_merge tool."""

    source_branch: str = Field(
        ...,
        description="Name of the branch to merge into the current branch",
        min_length=1,
        max_length=100,
    )
    squash: bool = Field(
        default=False,
        description="Whether to squash all commits from source branch into single commit (default: False)",
    )
    no_ff: bool = Field(
        default=False,
        description="Create a merge commit even for fast-forward merges (default: False)",
    )
    commit_message: Optional[str] = Field(
        default=None,
        description="Custom commit message for the merge (optional)",
        max_length=500,
    )

    @validator("source_branch")
    def validate_source_branch(cls, v):
        return validate_branch_name(v)


class DoltMergeOutput(BaseDoltOutput):
    """Output model for the dolt_merge tool."""

    source_branch: str = Field(..., description="Name of the branch that was merged")
    target_branch: str = Field(..., description="Name of the branch that was merged into")
    squash: bool = Field(..., description="Whether squash merge was used")
    no_ff: bool = Field(..., description="Whether no-fast-forward was used")
    fast_forward: bool = Field(..., description="Whether the merge was a fast-forward")
    conflicts: int = Field(default=0, description="Number of conflicts encountered")
    merge_hash: Optional[str] = Field(
        default=None, description="Hash of the merge commit if successful"
    )
    commit_message: Optional[str] = Field(
        default=None, description="Custom commit message that was used"
    )


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

    owner: str = Field(
        ...,
        description="DoltHub owner/organization name",
        min_length=1,
        max_length=100,
    )
    database: str = Field(
        ...,
        description="Database name on DoltHub",
        min_length=1,
        max_length=100,
    )
    api_token: str = Field(
        ...,
        description="DoltHub API token for authentication",
        min_length=1,
        max_length=200,
    )
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
    page_token: Optional[str] = Field(
        default=None,
        description="Pagination token for retrieving next page",
        max_length=200,
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

    pull_requests: List[DoltPullRequestInfo] = Field(
        default=[], description="List of pull requests"
    )
    total_count: int = Field(..., description="Total number of PRs returned in this page")
    status_filter: str = Field(..., description="Status filter that was applied")
    next_page_token: Optional[str] = Field(
        default=None, description="Token for retrieving next page (if available)"
    )
    owner: str = Field(..., description="DoltHub owner/organization name")
    database: str = Field(..., description="Database name on DoltHub")


@dolt_tool("MERGE")
def dolt_merge_tool(
    input_data: DoltMergeInput, memory_bank: StructuredMemoryBank
) -> DoltMergeOutput:
    """
    Merge a branch into the current branch using the memory bank's writer.

    Args:
        input_data: The merge parameters
        memory_bank: StructuredMemoryBank instance with Dolt writer access

    Returns:
        DoltMergeOutput with success status and merge details
    """
    try:
        logger.info(f"Merging branch '{input_data.source_branch}' with parameters: {input_data}")

        # Get current branch for target_branch field
        current_branch = memory_bank.dolt_writer.active_branch

        # Execute the merge using the memory bank's writer
        success, message = memory_bank.dolt_writer.merge_branch(
            source_branch=input_data.source_branch,
            squash=input_data.squash,
            no_ff=input_data.no_ff,
            commit_message=input_data.commit_message,
        )

        if success:
            logger.info(f"Merge operation succeeded: {message}")

            # Parse merge result information from message
            fast_forward = "(fast-forward)" in message
            conflicts = 0  # If successful, no conflicts
            merge_hash = None  # Would need to extract from Dolt result if available

            return DoltMergeOutput(
                success=True,
                message=message,
                source_branch=input_data.source_branch,
                target_branch=current_branch,
                squash=input_data.squash,
                no_ff=input_data.no_ff,
                fast_forward=fast_forward,
                conflicts=conflicts,
                merge_hash=merge_hash,
                commit_message=input_data.commit_message,
                active_branch=memory_bank.dolt_writer.active_branch,
            )
        else:
            logger.error(f"Merge operation failed: {message}")

            # Parse conflict information from error message
            conflicts = 1 if "conflicts" in message.lower() else 0

            return DoltMergeOutput(
                success=False,
                message="Merge operation failed",
                source_branch=input_data.source_branch,
                target_branch=current_branch,
                squash=input_data.squash,
                no_ff=input_data.no_ff,
                fast_forward=False,
                conflicts=conflicts,
                merge_hash=None,
                commit_message=input_data.commit_message,
                active_branch=memory_bank.dolt_writer.active_branch,
                error=message,
            )

    except Exception as e:
        error_msg = f"Exception during dolt_merge: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return DoltMergeOutput(
            success=False,
            message=f"Merge failed: {str(e)}",
            source_branch=input_data.source_branch,
            target_branch=memory_bank.dolt_writer.active_branch,
            squash=input_data.squash,
            no_ff=input_data.no_ff,
            fast_forward=False,
            conflicts=0,
            merge_hash=None,
            commit_message=input_data.commit_message,
            active_branch=memory_bank.dolt_writer.active_branch,
            error=error_msg,
        )


# === COGNI TOOL INSTANCES FOR BATCH 2 - CORE DOLT TOOLS ===

# Core Dolt Tools - Batch 2 (6 tools) for MCP Auto-Generation
# These CogniTool instances enable proper parameter schema visibility
# instead of the generic {"type": "object", "properties": {}} pattern

# 1. DoltCommit Tool
dolt_commit_tool_instance = CogniTool(
    name="DoltCommit",
    description="Commit working changes to Dolt using the memory bank's writer",
    input_model=DoltCommitInput,
    output_model=DoltCommitOutput,
    function=dolt_repo_tool,
    memory_linked=True,
)

# 2. DoltAdd Tool
dolt_add_tool_instance = CogniTool(
    name="DoltAdd",
    description="Stage working changes in Dolt for the current session",
    input_model=DoltAddInput,
    output_model=DoltAddOutput,
    function=dolt_add_tool,
    memory_linked=True,
)

# 3. DoltStatus Tool
dolt_status_tool_instance = CogniTool(
    name="DoltStatus",
    description="Get repository status using Dolt system tables",
    input_model=DoltStatusInput,
    output_model=DoltStatusOutput,
    function=dolt_status_tool,
    memory_linked=True,
)

# 4. DoltCheckout Tool
dolt_checkout_tool_instance = CogniTool(
    name="DoltCheckout",
    description="Checkout a Dolt branch, making it active for the current session",
    input_model=DoltCheckoutInput,
    output_model=DoltCheckoutOutput,
    function=dolt_checkout_tool,
    memory_linked=True,
)

# 5. DoltReset Tool
dolt_reset_tool_instance = CogniTool(
    name="DoltReset",
    description="Reset working changes in Dolt for the current session",
    input_model=DoltResetInput,
    output_model=DoltResetOutput,
    function=dolt_reset_tool,
    memory_linked=True,
)

# 6. DoltPush Tool
dolt_push_tool_instance = CogniTool(
    name="DoltPush",
    description="Push changes to a remote repository using Dolt",
    input_model=DoltPushInput,
    output_model=DoltPushOutput,
    function=dolt_push_tool,
    memory_linked=True,
)


# === COGNI TOOL INSTANCES FOR BATCH 3 - ADVANCED DOLT TOOLS ===

# Advanced Dolt Tools - Batch 3 (6 tools) for MCP Auto-Generation
# These CogniTool instances enable proper parameter schema visibility
# instead of the generic {"type": "object", "properties": {}} pattern

# 1. DoltPull Tool
dolt_pull_tool_instance = CogniTool(
    name="DoltPull",
    description="Pull changes from a remote repository using Dolt",
    input_model=DoltPullInput,
    output_model=DoltPullOutput,
    function=dolt_pull_tool,
    memory_linked=True,
)

# 2. DoltBranch Tool
dolt_branch_tool_instance = CogniTool(
    name="DoltBranch",
    description="Create a new branch using Dolt",
    input_model=DoltBranchInput,
    output_model=DoltBranchOutput,
    function=dolt_branch_tool,
    memory_linked=True,
)

# 3. DoltListBranches Tool
dolt_list_branches_tool_instance = CogniTool(
    name="DoltListBranches",
    description="List all Dolt branches with their information",
    input_model=DoltListBranchesInput,
    output_model=DoltListBranchesOutput,
    function=dolt_list_branches_tool,
    memory_linked=True,
)

# 4. DoltDiff Tool
dolt_diff_tool_instance = CogniTool(
    name="DoltDiff",
    description="Get a summary of differences between two revisions in Dolt",
    input_model=DoltDiffInput,
    output_model=DoltDiffOutput,
    function=dolt_diff_tool,
    memory_linked=True,
)

# 5. DoltAutoCommitAndPush Tool
dolt_auto_commit_and_push_tool_instance = CogniTool(
    name="DoltAutoCommitAndPush",
    description="Automatically handle the complete Dolt workflow: Status -> Add -> Commit -> Push",
    input_model=DoltAutoCommitInput,
    output_model=DoltAutoCommitOutput,
    function=dolt_auto_commit_and_push_tool,
    memory_linked=True,
)

# 6. DoltMerge Tool
dolt_merge_tool_instance = CogniTool(
    name="DoltMerge",
    description="Merge a branch into the current branch using Dolt",
    input_model=DoltMergeInput,
    output_model=DoltMergeOutput,
    function=dolt_merge_tool,
    memory_linked=True,
)
