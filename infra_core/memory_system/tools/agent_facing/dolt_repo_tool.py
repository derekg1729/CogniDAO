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


class DoltPushOutput(BaseModel):
    """Output model for the dolt_push tool."""

    success: bool = Field(..., description="Whether the push operation succeeded")
    message: str = Field(..., description="Human-readable result message")
    remote_name: str = Field(..., description="Name of the remote that was pushed to")
    branch: str = Field(..., description="Branch that was pushed")
    force: bool = Field(..., description="Whether force push was used")
    error: Optional[str] = Field(default=None, description="Error message if operation failed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of operation")


class DoltStatusInput(BaseModel):
    """Input model for the dolt_status tool."""

    # MVP: No input parameters needed for basic status


class DoltStatusOutput(BaseModel):
    """Output model for the dolt_status tool."""

    current_branch: str = Field(..., description="Current active branch")
    is_clean: bool = Field(..., description="True if working tree is clean")
    staged_tables: List[str] = Field(default=[], description="Tables with staged changes")
    unstaged_tables: List[str] = Field(default=[], description="Tables with unstaged changes")
    untracked_tables: List[str] = Field(default=[], description="New untracked tables")
    total_changes: int = Field(..., description="Total number of changes")
    ahead: int = Field(default=0, description="Commits ahead of remote")
    behind: int = Field(default=0, description="Commits behind remote")
    conflicts: List[str] = Field(default=[], description="Tables with conflicts")
    message: str = Field(..., description="Human-readable status summary")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of operation")


class DoltPullInput(BaseModel):
    """Input model for the dolt_pull tool."""

    remote_name: str = Field(
        default="origin",
        description="Name of the remote to pull from (e.g., 'origin')",
        min_length=1,
        max_length=100,
    )
    branch: Optional[str] = Field(
        default=None,
        description="Specific branch to pull (optional, defaults to tracking branch)",
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
    branch: Optional[str] = Field(default=None, description="Branch that was pulled (if specified)")
    force: bool = Field(..., description="Whether force pull was used")
    no_ff: bool = Field(..., description="Whether no-fast-forward was used")
    squash: bool = Field(..., description="Whether squash merge was used")
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
            )
        else:
            error_msg = "Dolt commit operation failed - no commit hash returned"
            logger.error(error_msg)

            return DoltCommitOutput(
                success=False,
                message=error_msg,
                error=error_msg,
                tables_committed=tables_to_commit,
            )

    except Exception as e:
        error_msg = f"Exception during dolt_commit: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return DoltCommitOutput(
            success=False,
            message=f"Commit failed: {str(e)}",
            error=error_msg,
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
            f"Pushing to remote '{input_data.remote_name}' branch '{input_data.branch}' (force={input_data.force})"
        )

        # Execute the push using the memory bank's writer
        success, message = memory_bank.dolt_writer.push_to_remote(
            remote_name=input_data.remote_name, branch=input_data.branch, force=input_data.force
        )

        if success:
            logger.info(f"Successfully pushed to remote: {message}")

            return DoltPushOutput(
                success=True,
                message=message,
                remote_name=input_data.remote_name,
                branch=input_data.branch,
                force=input_data.force,
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
                # Process status rows if any exist

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
            current_branch=current_branch,
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
            current_branch="unknown",
            is_clean=False,
            total_changes=0,
            message=f"Status check failed: {str(e)}",
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
        logger.info(
            f"Pulling from remote '{input_data.remote_name}'"
            + (f" branch '{input_data.branch}'" if input_data.branch else "")
            + f" (force={input_data.force}, no_ff={input_data.no_ff}, squash={input_data.squash})"
        )

        # Execute the pull using the memory bank's writer
        success, message = memory_bank.dolt_writer.pull_from_remote(
            remote_name=input_data.remote_name,
            branch=input_data.branch,
            force=input_data.force,
            no_ff=input_data.no_ff,
            squash=input_data.squash,
        )

        if success:
            logger.info(f"Successfully pulled from remote: {message}")

            return DoltPullOutput(
                success=True,
                message=message,
                remote_name=input_data.remote_name,
                branch=input_data.branch,
                force=input_data.force,
                no_ff=input_data.no_ff,
                squash=input_data.squash,
            )
        else:
            error_msg = f"Dolt pull operation failed: {message}"
            logger.error(error_msg)

            return DoltPullOutput(
                success=False,
                message=error_msg,
                remote_name=input_data.remote_name,
                branch=input_data.branch,
                force=input_data.force,
                no_ff=input_data.no_ff,
                squash=input_data.squash,
                error=error_msg,
            )

    except Exception as e:
        error_msg = f"Exception during dolt_pull: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return DoltPullOutput(
            success=False,
            message=f"Pull failed: {str(e)}",
            remote_name=input_data.remote_name,
            branch=input_data.branch,
            force=input_data.force,
            no_ff=input_data.no_ff,
            squash=input_data.squash,
            error=error_msg,
        )
