"""
Dolt Version Control Tools for Manual Operations

This module provides tools for agents to manually perform Dolt version control operations
when auto_commit=False mode is being used in StructuredMemoryBank.

Tools included:
- dolt_repo_tool: Commit working set changes to Dolt
- dolt_push_tool: Push changes to remote repositories
"""

import logging
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank

logger = logging.getLogger(__name__)


class DoltAddInput(BaseModel):
    """Input model for the dolt_add tool."""

    tables: Optional[List[str]] = Field(
        default=None,
        description="Optional list of specific tables to add. If not provided, all changes will be staged.",
    )


class DoltAddOutput(BaseModel):
    """Output model for the dolt_add tool."""

    success: bool = Field(..., description="Whether the add operation succeeded")
    message: str = Field(..., description="Human-readable result message")
    active_branch: str = Field(..., description="Current active branch")
    error: Optional[str] = Field(default=None, description="Error message if operation failed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of operation")


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


class DoltCommitOutput(BaseModel):
    """Output model for the dolt_commit tool."""

    success: bool = Field(..., description="Whether the commit operation succeeded")
    commit_hash: Optional[str] = Field(
        default=None, description="The Dolt commit hash if successful"
    )
    message: str = Field(..., description="Human-readable result message")
    tables_committed: Optional[List[str]] = Field(
        default=None, description="List of tables that were committed"
    )
    active_branch: str = Field(..., description="Current active branch")
    error: Optional[str] = Field(default=None, description="Error message if operation failed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of operation")


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


class DoltPushOutput(BaseModel):
    """Output model for the dolt_push tool."""

    success: bool = Field(..., description="Whether the push operation succeeded")
    message: str = Field(..., description="Human-readable result message")
    remote_name: str = Field(..., description="Name of the remote that was pushed to")
    branch: str = Field(..., description="Branch that was pushed")
    force: bool = Field(..., description="Whether force push was used")
    set_upstream: bool = Field(..., description="Whether upstream tracking was set up")
    active_branch: str = Field(..., description="Current active branch")
    error: Optional[str] = Field(default=None, description="Error message if operation failed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of operation")


class DoltStatusInput(BaseModel):
    """Input model for the dolt_status tool."""

    # MVP: No input parameters needed for basic status


class DoltStatusOutput(BaseModel):
    """Output model for the dolt_status tool."""

    success: bool = Field(..., description="Whether the status operation succeeded")
    active_branch: str = Field(..., description="Current active branch")
    is_clean: bool = Field(..., description="True if working tree is clean")
    staged_tables: List[str] = Field(default=[], description="Tables with staged changes")
    unstaged_tables: List[str] = Field(default=[], description="Tables with unstaged changes")
    untracked_tables: List[str] = Field(default=[], description="New untracked tables")
    total_changes: int = Field(..., description="Total number of changes")
    ahead: int = Field(default=0, description="Commits ahead of remote")
    behind: int = Field(default=0, description="Commits behind remote")
    conflicts: List[str] = Field(default=[], description="Tables with conflicts")
    message: str = Field(..., description="Human-readable status summary")
    error: Optional[str] = Field(default=None, description="Error message if operation failed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of operation")


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


class DoltPullOutput(BaseModel):
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


class DoltBranchOutput(BaseModel):
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


class DoltListBranchesOutput(BaseModel):
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


class DoltCheckoutOutput(BaseModel):
    """Output model for the dolt_checkout tool."""

    success: bool = Field(..., description="Whether the checkout operation succeeded")
    message: str = Field(..., description="Human-readable result message")
    active_branch: str = Field(..., description="Current active branch")
    error: Optional[str] = Field(default=None, description="Error message if operation failed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of operation")


class DoltDiffInput(BaseModel):
    """Input model for the dolt_diff tool."""

    mode: Optional[str] = Field(
        default="working",
        description="Diff mode. 'working' for unstaged changes, 'staged' for staged changes. Overridden if from/to are set.",
        enum=["working", "staged"],
    )
    from_revision: Optional[str] = Field(
        default=None, description="The starting revision (e.g., 'HEAD', 'main')."
    )
    to_revision: Optional[str] = Field(
        default=None, description="The ending revision (e.g., 'WORKING', 'STAGED')."
    )


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


class DoltDiffOutput(BaseModel):
    """Output model for the dolt_diff tool."""

    success: bool = Field(..., description="Whether the diff operation succeeded.")
    diff_summary: List[DiffSummary] = Field(..., description="A list of table diff summaries.")
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


class DoltAutoCommitOutput(BaseModel):
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
            tables_to_commit = ["memory_blocks", "block_properties", "block_links"]

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
            active_branch=current_branch,
            is_clean=is_clean,
            staged_tables=staged_tables,
            unstaged_tables=unstaged_tables,
            untracked_tables=untracked_tables,
            total_changes=total_changes,
            conflicts=conflicts,
            message=message,
        )

    except Exception as e:
        error_msg = f"Exception during dolt_status: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return DoltStatusOutput(
            success=False,
            active_branch="unknown",
            is_clean=False,
            total_changes=0,
            message=f"Status check failed: {str(e)}",
            error=error_msg,
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
        return DoltListBranchesOutput(
            success=False,
            branches=[],
            active_branch="unknown",
            message=f"Failed to list branches: {str(e)}",
            error=error_msg,
        )


def dolt_add_tool(input_data: DoltAddInput, memory_bank: StructuredMemoryBank) -> DoltAddOutput:
    """
    Stage working changes to Dolt using the memory bank's writer.

    Args:
        input_data: The add parameters
        memory_bank: StructuredMemoryBank instance with Dolt writer access

    Returns:
        DoltAddOutput with success status and message
    """
    try:
        tables_to_add = input_data.tables
        logger.info(f"Staging Dolt changes for tables: {tables_to_add or 'ALL'}")

        success, message = memory_bank.dolt_writer.add_to_staging(tables=tables_to_add)

        if success:
            logger.info(message)
            return DoltAddOutput(
                success=True, message=message, active_branch=memory_bank.dolt_writer.active_branch
            )
        else:
            error_msg = f"Dolt add operation failed: {message}"
            logger.error(error_msg)
            return DoltAddOutput(
                success=False,
                message=error_msg,
                active_branch=memory_bank.dolt_writer.active_branch,
                error=error_msg,
            )

    except Exception as e:
        error_msg = f"Exception during dolt_add: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return DoltAddOutput(
            success=False,
            message=f"Add failed: {str(e)}",
            active_branch=memory_bank.dolt_writer.active_branch,
            error=error_msg,
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
        writer = memory_bank.dolt_writer

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
                active_branch=memory_bank.dolt_writer.active_branch,
                error="Invalid revision arguments.",
            )

        summary_dicts = writer.get_diff_summary(from_revision=from_rev, to_revision=to_rev)

        # Convert dicts to Pydantic models
        diff_summary = [DiffSummary(**item) for item in summary_dicts]

        message = f"Successfully retrieved diff summary from {from_rev} to {to_rev}."
        if not diff_summary:
            message = f"No changes found between {from_rev} and {to_rev}."

        return DoltDiffOutput(
            success=True,
            diff_summary=diff_summary,
            message=message,
            active_branch=memory_bank.dolt_writer.active_branch,
        )

    except Exception as e:
        logger.error(f"Error getting diff summary: {e}", exc_info=True)
        return DoltDiffOutput(
            success=False,
            diff_summary=[],
            message=f"An unexpected error occurred: {e}",
            error=str(e),
            active_branch=memory_bank.dolt_writer.active_branch,
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
            return DoltAutoCommitOutput(
                success=False,
                message=f"Status check failed: {status_result.error}",
                operations_performed=operations_performed,
                was_clean=False,
                active_branch="unknown",
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

        return DoltAutoCommitOutput(
            success=False,
            message=f"Auto commit and push failed: {str(e)}",
            operations_performed=operations_performed,
            was_clean=False,
            active_branch="unknown",
            error=error_msg,
        )
