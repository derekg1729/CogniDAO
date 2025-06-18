"""
Contains functions for writing MemoryBlock objects to a Dolt database.

This module provides secure MySQL connector-based write access to a running
Dolt SQL server, supporting branch switching and using parameterized queries
for security.

The DoltMySQLWriter class uses the same DoltConnectionConfig as the reader
for consistent configuration.

This version uses the Property-Schema Split approach, writing metadata as typed
properties to the block_properties table instead of JSON metadata column.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional, Tuple, List
import warnings

import mysql.connector
from mysql.connector import Error

# --- Path Setup --- START
# Must happen before importing local modules
script_dir = Path(__file__).parent
project_root_dir = script_dir.parent.parent.parent  # Navigate up THREE levels
if str(project_root_dir) not in sys.path:
    sys.path.insert(0, str(project_root_dir))
# --- Path Setup --- END

# Import schema using path relative to project root
try:
    from infra_core.memory_system.schemas.memory_block import MemoryBlock
    from infra_core.memory_system.property_mapper import PropertyMapper
    from infra_core.memory_system.dolt_mysql_base import (
        DoltMySQLBase,
        DEFAULT_PROTECTED_BRANCH,
        MainBranchProtectionError,
    )
except ImportError as e:
    # Add more context to the error message
    raise ImportError(
        f"Could not import required schemas or configs from infra_core/memory_system. "
        f"Project root added to path: {project_root_dir}. Check structure. Error: {e}"
    )

# Setup standard Python logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Standard tables that store memory block data and should be included in commits/rollbacks
PERSISTED_TABLES = ["memory_blocks", "block_properties", "block_links"]


class DoltMySQLWriter(DoltMySQLBase):
    """Dolt writer that connects to remote Dolt SQL server via MySQL connector.

    Provides write operations using parameterized queries for better security.
    Works with the same DoltConnectionConfig as DoltMySQLReader.
    """

    def _get_connection(self):
        """Get a new MySQL connection to the Dolt SQL server with transaction control."""
        try:
            conn = mysql.connector.connect(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
                charset="utf8mb4",
                autocommit=False,  # We want transaction control for writes
                connection_timeout=10,
                use_unicode=True,
                raise_on_warnings=True,
            )
            return conn
        except Error as e:
            raise Exception(f"Failed to connect to Dolt SQL server: {e}")

    def write_memory_block(
        self,
        block: MemoryBlock,
        branch: str = DEFAULT_PROTECTED_BRANCH,
        auto_commit: bool = False,
        preserve_nulls: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """Write a memory block to the Dolt SQL server."""
        # Use persistent connection if available, otherwise create new one
        if self._use_persistent and self._persistent_connection:
            connection = self._persistent_connection
            connection_is_persistent = True
        else:
            connection = self._get_connection()
            connection_is_persistent = False

        commit_hash = None

        try:
            # Safely ensure branch and check protection (prevents bypass attacks)
            self._ensure_branch_and_check_protection(connection, "write_memory_block", branch)
            cursor = connection.cursor(dictionary=True)

            # Step 1: Write to memory_blocks table using REPLACE INTO for idempotency
            memory_blocks_query = """
            REPLACE INTO memory_blocks (
                id, namespace_id, type, schema_version, text, state, visibility, block_version,
                parent_id, has_children, tags, source_file, source_uri, confidence,
                created_by, created_at, updated_at, embedding
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """

            # Prepare values, handling JSON serialization
            values = (
                block.id,
                block.namespace_id,
                block.type,
                getattr(block, "schema_version", None),
                block.text,
                getattr(block, "state", "draft"),
                getattr(block, "visibility", "internal"),
                getattr(block, "block_version", 1),
                getattr(block, "parent_id", None),
                getattr(block, "has_children", False),
                json.dumps(block.tags) if block.tags is not None else json.dumps([]),
                block.source_file,
                block.source_uri,
                json.dumps(block.confidence.model_dump()) if block.confidence else None,
                block.created_by,
                block.created_at,
                block.updated_at,
                json.dumps(block.embedding) if block.embedding else None,
            )

            # 🔍 DEBUG: Log the actual SQL values being passed to the database
            logger.error(
                f"🔍 DEBUG: DoltMySQLWriter SQL values - ID: {values[0]}, namespace_id: {values[1]}"
            )
            logger.error(
                f"🔍 DEBUG: DoltMySQLWriter block.namespace_id before SQL: {block.namespace_id}"
            )

            cursor.execute(memory_blocks_query, values)

            # Step 2: Handle metadata properties using PropertyMapper
            if hasattr(block, "metadata") and block.metadata:
                # Decompose metadata into properties
                properties = PropertyMapper.decompose_metadata(
                    block_id=block.id, metadata_dict=block.metadata, preserve_nulls=preserve_nulls
                )

                # Clear existing properties for this block
                cursor.execute("DELETE FROM block_properties WHERE block_id = %s", (block.id,))

                # Insert new properties
                if properties:
                    property_query = """
                    INSERT INTO block_properties (
                        block_id, property_name, property_value_text, property_value_number,
                        property_value_json, property_type, is_computed, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """

                    for prop in properties:
                        property_values = (
                            prop.block_id,
                            prop.property_name,
                            prop.property_value_text,
                            prop.property_value_number,
                            json.dumps(prop.property_value_json)
                            if prop.property_value_json is not None
                            else None,
                            prop.property_type,
                            prop.is_computed,
                            prop.created_at,
                            prop.updated_at,
                        )
                        cursor.execute(property_query, property_values)

            if auto_commit:
                # Use Dolt SQL functions to add and commit
                cursor.execute("CALL DOLT_ADD('memory_blocks', 'block_properties')")
                cursor.fetchall()  # Consume any results from DOLT_ADD
                cursor.execute("CALL DOLT_COMMIT('-m', %s)", (f"Write memory block {block.id}",))
                cursor.fetchall()  # Consume any results from DOLT_COMMIT

                # Get commit hash
                cursor.execute("SELECT DOLT_HASHOF_DB('HEAD') AS commit_hash")
                result = cursor.fetchone()
                if result:
                    commit_hash = result["commit_hash"]
            else:
                # Just commit the MySQL transaction, don't commit to Dolt
                connection.commit()

            cursor.close()
            logger.info(f"Successfully wrote block {block.id} via MySQL connection")
            return True, commit_hash

        except MainBranchProtectionError:
            # Let branch protection errors propagate to caller for specific handling
            raise
        except Exception as e:
            if not connection_is_persistent:
                connection.rollback()
            logger.error(f"Failed to write block {block.id}: {e}", exc_info=True)
            return False, None
        finally:
            # Only close if it's not a persistent connection
            if not connection_is_persistent:
                connection.close()

    def delete_memory_block(
        self, block_id: str, branch: str = DEFAULT_PROTECTED_BRANCH, auto_commit: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """Delete a memory block from the Dolt SQL server."""
        connection = self._get_connection()
        commit_hash = None

        try:
            # Safely ensure branch and check protection (prevents bypass attacks)
            self._ensure_branch_and_check_protection(connection, "delete_memory_block", branch)
            cursor = connection.cursor(dictionary=True)

            # Delete from both tables
            cursor.execute("DELETE FROM block_properties WHERE block_id = %s", (block_id,))
            cursor.execute("DELETE FROM memory_blocks WHERE id = %s", (block_id,))

            if auto_commit:
                # Use Dolt SQL functions to add and commit
                cursor.execute("CALL DOLT_ADD('memory_blocks', 'block_properties')")
                cursor.fetchall()  # Consume any results from DOLT_ADD
                cursor.execute("CALL DOLT_COMMIT('-m', %s)", (f"Delete memory block {block_id}",))
                cursor.fetchall()  # Consume any results from DOLT_COMMIT

                # Get commit hash
                cursor.execute("SELECT DOLT_HASHOF_DB('HEAD') AS commit_hash")
                result = cursor.fetchone()
                if result:
                    commit_hash = result["commit_hash"]
            else:
                # Just commit the MySQL transaction, don't commit to Dolt
                connection.commit()

            cursor.close()
            logger.info(f"Successfully deleted block {block_id} via MySQL connection")
            return True, commit_hash

        except Exception as e:
            connection.rollback()
            logger.error(f"Failed to delete block {block_id}: {e}", exc_info=True)
            return False, None
        finally:
            connection.close()

    def commit_changes(
        self, commit_msg: str, tables: List[str] = None, branch: str = None
    ) -> Tuple[bool, Optional[str]]:
        """Commit working changes to Dolt via MySQL connection.

        Args:
            commit_msg: Commit message
            tables: Optional list of tables to commit (default: all staged changes)
            branch: Optional explicit branch to commit on (default: current active branch)
        """
        # Use persistent connection if available, otherwise create new one
        if self._use_persistent and self._persistent_connection:
            connection = self._persistent_connection
            connection_is_persistent = True
        else:
            connection = self._get_connection()
            connection_is_persistent = False

        commit_hash = None

        try:
            # Determine the target branch
            if branch is not None:
                # Explicit branch specified - ensure we're on it and check protection
                self._ensure_branch_and_check_protection(connection, "commit_changes", branch)
                if self._use_persistent:
                    self._current_branch = branch
            else:
                # No explicit branch - use current branch but check protection
                if connection_is_persistent:
                    current_branch = self._current_branch or self.active_branch
                else:
                    current_branch = self.active_branch
                    self._ensure_branch(connection, current_branch)
                self._check_branch_protection("commit_changes", current_branch)

            cursor = connection.cursor(dictionary=True)

            # NOTE: Staging should be handled by the `add_to_staging` method.
            # This method should only be responsible for committing.

            # Commit changes
            cursor.execute("CALL DOLT_COMMIT('-m', %s)", (commit_msg,))
            cursor.fetchall()  # Consume any results from DOLT_COMMIT

            # Get commit hash
            cursor.execute("SELECT DOLT_HASHOF_DB('HEAD') AS commit_hash")
            result = cursor.fetchone()
            if result:
                commit_hash = result["commit_hash"]

            cursor.close()
            logger.info(f"Successfully committed changes: {commit_msg}")
            return True, commit_hash

        except Exception as e:
            logger.error(f"Failed to commit changes: {e}", exc_info=True)
            return False, None
        finally:
            # Only close if it's not a persistent connection
            if not connection_is_persistent:
                connection.close()

    def add_to_staging(self, tables: List[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Add working changes to the staging area for the current session.
        This is a critical step before committing.
        """
        if self._use_persistent and self._persistent_connection:
            connection = self._persistent_connection
            connection_is_persistent = True
            # For persistent connections, we can check protection immediately since branch is already set
            current_branch = self._current_branch or self.active_branch
            self._check_branch_protection("add_to_staging", current_branch)
        else:
            logger.warning(
                "add_to_staging called without a persistent connection. Branch context may be lost."
            )
            connection = self._get_connection()
            connection_is_persistent = False
            # For non-persistent connections, check protection after we know the current branch
            current_branch = self.active_branch
            self._check_branch_protection("add_to_staging", current_branch)

        try:
            cursor = connection.cursor(dictionary=True)

            if tables:
                placeholders = ", ".join(["%s"] * len(tables))
                query = f"CALL DOLT_ADD({placeholders})"
                cursor.execute(query, tuple(tables))
            else:
                # Use '-A' to stage all changes, which is safer and more comprehensive than '.'
                query = "CALL DOLT_ADD('-A')"
                cursor.execute(query)

            # The result MUST be consumed before committing the transaction.
            result = cursor.fetchall()
            status_row = result[0] if result else None

            # The transaction must be committed for the staging to take effect.
            connection.commit()

            # The procedure returns a 'status' column, 0 for success
            if status_row and status_row.get("status") == 0:
                logger.info(f"Successfully staged changes for tables: {tables or 'ALL'}")
                return True, f"Successfully staged changes for tables: {tables or 'ALL'}"
            else:
                # Even if the status is not 0, it might have partially succeeded or just have nothing to stage
                # Dolt CLI returns 0 even if there's nothing to stage, so we will too.
                # Assuming success if no exception is thrown, which is the common case.
                logger.info(
                    f"Staged changes for tables: {tables or 'ALL'}. DOLT_ADD returned: {result}"
                )
                return True, f"Staged changes for tables: {tables or 'ALL'}"

        except Exception as e:
            logger.error(f"Failed to stage changes: {e}", exc_info=True)
            return False, str(e)
        finally:
            if not connection_is_persistent:
                connection.close()

    def reset(self, hard: bool = False, tables: List[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Reset working changes in Dolt using DOLT_RESET command.

        Args:
            hard: If True, use --hard flag (discard working changes). If False, use --soft flag (unstage only).
            tables: List of table names to reset. If None, resets all changes.

        Returns:
            Tuple of (success: bool, message: Optional[str])
        """
        # Use persistent connection if available, otherwise create new one
        if self._use_persistent and self._persistent_connection:
            connection = self._persistent_connection
            connection_is_persistent = True
        else:
            connection = self._get_connection()
            connection_is_persistent = False

        try:
            cursor = connection.cursor(dictionary=True)

            # Build DOLT_RESET command arguments
            reset_args = []

            # Add flag
            if hard:
                reset_args.append("--hard")
            else:
                reset_args.append("--soft")

            # Add tables if specified
            if tables:
                reset_args.extend(tables)

            # Execute DOLT_RESET with proper parameterization
            placeholders = ", ".join(["%s"] * len(reset_args))
            query = f"CALL DOLT_RESET({placeholders})"
            cursor.execute(query, tuple(reset_args))
            cursor.fetchall()  # Consume any results

            cursor.close()

            # Build success message
            reset_type = "hard" if hard else "soft"
            if tables:
                message = f"Successfully performed {reset_type} reset on {len(tables)} table(s): {', '.join(tables)}"
            else:
                message = f"Successfully performed {reset_type} reset on all changes"

            logger.info(message)
            return True, message

        except Exception as e:
            error_msg = f"Failed to reset changes: {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
        finally:
            if not connection_is_persistent:
                connection.close()

    def discard_changes(self, tables: List[str] = None) -> bool:
        """
        Discard uncommitted changes in Dolt working set.

        DEPRECATED: Use reset(hard=True, tables=tables) instead.

        Args:
            tables: List of table names to discard changes for. If None, discards all changes.

        Returns:
            True if discard was successful, False otherwise.
        """
        warnings.warn(
            "discard_changes() is deprecated. Use reset(hard=True, tables=tables) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        success, _ = self.reset(hard=True, tables=tables)
        return success

    def get_diff_summary(self, from_revision: str, to_revision: str) -> List[dict]:
        """
        Gets a summary of differences between two revisions using DOLT_DIFF_SUMMARY.

        Args:
            from_revision: The starting revision (e.g., 'HEAD', 'main').
            to_revision: The ending revision (e.g., 'WORKING', 'STAGED').

        Returns:
            A list of dictionaries, where each dictionary represents a changed table.
        """
        # Use persistent connection if available, otherwise create a new one
        if self._use_persistent and self._persistent_connection:
            connection = self._persistent_connection
            connection_is_persistent = True
        else:
            connection = self._get_connection()
            connection_is_persistent = False

        try:
            cursor = connection.cursor(dictionary=True)

            query = "SELECT * FROM DOLT_DIFF_SUMMARY(%s, %s)"
            cursor.execute(query, (from_revision, to_revision))

            diff_summary = cursor.fetchall()

            cursor.close()
            logger.info(
                f"Successfully retrieved diff summary from {from_revision} to {to_revision}"
            )
            return diff_summary

        except Error as e:
            logger.error(f"Failed to get diff summary: {e}", exc_info=True)
            # Optionally re-raise or handle as appropriate
            raise
        finally:
            if not connection_is_persistent:
                connection.close()

    def push_to_remote(
        self,
        remote_name: str,
        branch: str = DEFAULT_PROTECTED_BRANCH,
        force: bool = False,
        set_upstream: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """
        Push changes to a remote repository using Dolt's DOLT_PUSH function.

        Args:
            remote_name: Name of the remote to push to (e.g., 'origin')
            branch: Branch to push (default: "main")
            force: Whether to force push, overriding safety checks (default: False)
            set_upstream: Whether to set up upstream tracking for the branch (default: False)

        Returns:
            Tuple of (success: bool, message: Optional[str])
        """
        # Use persistent connection if available, otherwise create new one
        if self._use_persistent and self._persistent_connection:
            connection = self._persistent_connection
            connection_is_persistent = True
        else:
            connection = self._get_connection()
            connection_is_persistent = False

        try:
            # Safely ensure branch and check protection (prevents bypass attacks)
            self._ensure_branch_and_check_protection(connection, "push_to_remote", branch)
            cursor = connection.cursor(dictionary=True)

            # Build push command arguments list
            push_args = []

            # Add flags first
            if force:
                push_args.append("--force")
            if set_upstream:
                push_args.append("--set-upstream")

            # Add remote and branch
            push_args.extend([remote_name, branch])

            logger.info(
                f"Pushing branch '{branch}' to remote '{remote_name}' (force={force}, set_upstream={set_upstream})"
            )

            # Execute the push using DOLT_PUSH function
            # DOLT_PUSH supports various argument combinations
            if len(push_args) == 2:  # Just remote and branch
                cursor.execute("CALL DOLT_PUSH(%s, %s)", (push_args[0], push_args[1]))
            elif len(push_args) == 3:  # One flag + remote + branch
                cursor.execute(
                    "CALL DOLT_PUSH(%s, %s, %s)", (push_args[0], push_args[1], push_args[2])
                )
            elif len(push_args) == 4:  # Two flags + remote + branch
                cursor.execute(
                    "CALL DOLT_PUSH(%s, %s, %s, %s)",
                    (push_args[0], push_args[1], push_args[2], push_args[3]),
                )

            result = cursor.fetchall()  # Consume any results from DOLT_PUSH

            # Check if push was successful by examining the result
            # DOLT_PUSH typically returns status information
            message = f"Successfully pushed branch '{branch}' to remote '{remote_name}'"

            # If there are results, check for success indicators
            if result:
                # Log the result for debugging
                logger.info(f"DOLT_PUSH result: {result}")

            cursor.close()
            logger.info(message)
            return True, message

        except Exception as e:
            error_msg = f"Failed to push to remote '{remote_name}': {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
        finally:
            # Only close if it's not a persistent connection
            if not connection_is_persistent:
                connection.close()

    def pull_from_remote(
        self,
        remote_name: str = "origin",
        branch: str = DEFAULT_PROTECTED_BRANCH,
        force: bool = False,
        no_ff: bool = False,
        squash: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """
        Pull changes from a remote repository using Dolt's DOLT_PULL function.

        Args:
            remote_name: Name of the remote to pull from (e.g., 'origin')
            branch: Specific branch to pull (optional, defaults to tracking branch)
            force: Whether to force pull, ignoring conflicts (default: False)
            no_ff: Create a merge commit even for fast-forward merges (default: False)
            squash: Merge changes to working set without updating commit history (default: False)

        Returns:
            Tuple of (success: bool, message: Optional[str])
        """
        connection = self._get_connection()

        try:
            cursor = connection.cursor(dictionary=True)

            # Build pull command arguments list
            pull_args = []

            # Add flags before remote name
            if force:
                pull_args.append("--force")
            if no_ff:
                pull_args.append("--no-ff")
            if squash:
                pull_args.append("--squash")

            # Add remote name
            pull_args.append(remote_name)

            # Add branch if specified
            if branch:
                pull_args.append(branch)

            logger.info(
                f"Pulling from remote '{remote_name}'"
                + (f" branch '{branch}'" if branch else "")
                + f" (force={force}, no_ff={no_ff}, squash={squash})"
            )

            # Execute the pull using DOLT_PULL function
            # DOLT_PULL supports various argument combinations
            if len(pull_args) == 1:  # Just remote name
                cursor.execute("CALL DOLT_PULL(%s)", (pull_args[0],))
            elif len(pull_args) == 2:  # Remote + branch or remote + flag
                cursor.execute("CALL DOLT_PULL(%s, %s)", (pull_args[0], pull_args[1]))
            elif len(pull_args) == 3:  # Flag + remote + branch
                cursor.execute(
                    "CALL DOLT_PULL(%s, %s, %s)", (pull_args[0], pull_args[1], pull_args[2])
                )
            elif len(pull_args) == 4:  # Multiple flags + remote + branch
                cursor.execute(
                    "CALL DOLT_PULL(%s, %s, %s, %s)",
                    (pull_args[0], pull_args[1], pull_args[2], pull_args[3]),
                )
            elif len(pull_args) == 5:  # All flags + remote + branch
                cursor.execute(
                    "CALL DOLT_PULL(%s, %s, %s, %s, %s)",
                    (pull_args[0], pull_args[1], pull_args[2], pull_args[3], pull_args[4]),
                )

            result = cursor.fetchall()

            # Check if pull was successful by examining the result
            # DOLT_PULL typically returns status information about fast_forward and conflicts
            success = True
            message = f"Successfully pulled from remote '{remote_name}'"

            if branch:
                message += f" branch '{branch}'"

            # If there are results, check for conflicts or other information
            if result:
                logger.info(f"DOLT_PULL result: {result}")
                # Extract useful information from result
                for row in result:
                    if isinstance(row, dict):
                        if "conflicts" in row and row["conflicts"] and row["conflicts"] > 0:
                            success = False
                            message = f"Pull completed with {row['conflicts']} conflicts that need resolution"
                        elif "fast_forward" in row:
                            if row["fast_forward"]:
                                message += " (fast-forward)"
                            else:
                                message += " (merge commit created)"

            cursor.close()

            if success:
                logger.info(message)
            else:
                logger.warning(message)

            return success, message

        except Exception as e:
            error_str = str(e)
            # "Everything up-to-date" is actually a success condition, not an error
            # TODO: This is a hack to get around the fact that Dolt doesn't return a success code for this
            if "Everything up-to-date" in error_str:
                logger.info(f"Pull from remote '{remote_name}': Everything up-to-date")
                return True, "Everything up-to-date"

            error_msg = f"Failed to pull from remote '{remote_name}': {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
        finally:
            connection.close()

    def create_branch(
        self,
        branch_name: str,
        start_point: str = None,
        force: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a new branch using Dolt's DOLT_BRANCH function.

        Args:
            branch_name: Name of the new branch to create
            start_point: Commit, branch, or tag to start the branch from (optional, defaults to current HEAD)
            force: Whether to force creation, overriding safety checks (default: False)

        Returns:
            Tuple of (success: bool, message: Optional[str])
        """
        connection = self._get_connection()

        try:
            cursor = connection.cursor(dictionary=True)

            # Build branch command arguments list
            branch_args = []

            # Add force flag if specified
            if force:
                branch_args.append("--force")

            # Add branch name
            branch_args.append(branch_name)

            # Add start point if specified
            if start_point:
                branch_args.append(start_point)

            logger.info(
                f"Creating branch '{branch_name}'"
                + (f" from '{start_point}'" if start_point else " from current HEAD")
                + f" (force={force})"
            )

            # Execute the branch creation using DOLT_BRANCH function
            if len(branch_args) == 1:  # Just branch name
                cursor.execute("CALL DOLT_BRANCH(%s)", (branch_args[0],))
            elif len(branch_args) == 2:  # Branch name + start point OR force + branch name
                cursor.execute("CALL DOLT_BRANCH(%s, %s)", (branch_args[0], branch_args[1]))
            elif len(branch_args) == 3:  # Force + branch name + start point
                cursor.execute(
                    "CALL DOLT_BRANCH(%s, %s, %s)", (branch_args[0], branch_args[1], branch_args[2])
                )

            result = cursor.fetchall()

            # Build success message after successful execution
            message = f"Successfully created branch '{branch_name}'"
            if start_point:
                message += f" from '{start_point}'"

            # If there are results, check for success indicators
            if result:
                logger.info(f"DOLT_BRANCH result: {result}")
                # Check if result indicates an error
                # Dolt typically returns empty result for successful branch creation
                # If there's error content, it might indicate a problem
                for row in result:
                    if isinstance(row, dict) and any(
                        "error" in str(v).lower() for v in row.values() if v
                    ):
                        error_msg = f"Branch creation failed: {row}"
                        logger.error(error_msg)
                        cursor.close()
                        return False, error_msg

            cursor.close()
            logger.info(message)
            return True, message

        except Exception as e:
            error_msg = f"Failed to create branch '{branch_name}': {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
        finally:
            connection.close()

    def checkout_branch(
        self,
        branch_name: str,
        force: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """
        Checkout an existing branch using Dolt's DOLT_CHECKOUT function.

        This method enables persistent connection mode and switches to the specified branch.
        All subsequent operations on this writer will use the checked-out branch.

        Args:
            branch_name: Name of the branch to checkout
            force: Whether to force checkout, discarding uncommitted changes (default: False)

        Returns:
            Tuple of (success: bool, message: Optional[str])
        """
        try:
            logger.info(
                f"Checking out branch '{branch_name}' (force={force}) with persistent connection"
            )

            # Close any existing persistent connection first
            if self._use_persistent:
                self.close_persistent_connection()

            # Use persistent connection to establish and maintain branch state
            self.use_persistent_connection(branch_name)

            # If force is specified, we need to handle it differently since persistent connection
            # doesn't support force flag in use_persistent_connection
            if force:
                logger.warning(
                    "Force checkout with persistent connection - may need manual conflict resolution"
                )

            message = f"Successfully checked out branch '{branch_name}' with persistent connection"
            logger.info(message)
            return True, message

        except Exception as e:
            error_msg = f"Failed to checkout branch '{branch_name}': {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

    def write_block_proof(
        self,
        block_id: str,
        operation: str,
        commit_hash: str,
        branch: str = DEFAULT_PROTECTED_BRANCH,
    ) -> bool:
        """
        Write a block operation proof to the block_proofs table.

        Args:
            block_id: The ID of the block
            operation: The operation type ('create', 'update', 'delete')
            commit_hash: The Dolt commit hash for this operation
            branch: The Dolt branch to write to

        Returns:
            True if proof was stored successfully, False otherwise
        """
        connection = self._get_connection()

        try:
            # Safely ensure branch and check protection (prevents bypass attacks)
            self._ensure_branch_and_check_protection(connection, "write_block_proof", branch)
            cursor = connection.cursor(dictionary=True)

            # Insert proof record with current timestamp
            insert_query = """
            INSERT INTO block_proofs (block_id, commit_hash, operation, timestamp)
            VALUES (%s, %s, %s, NOW())
            """

            cursor.execute(insert_query, (block_id, commit_hash, operation))
            connection.commit()

            cursor.close()
            logger.info(
                f"Stored block proof: {operation} operation for block {block_id} with commit {commit_hash}"
            )
            return True

        except Exception as e:
            connection.rollback()
            logger.error(f"Failed to store block proof for {block_id}: {e}", exc_info=True)
            return False
        finally:
            connection.close()


# --- Backward Compatibility Stubs (DO NOT USE) ---


def write_memory_block_to_dolt(
    block: MemoryBlock, db_path: str, auto_commit: bool = False, preserve_nulls: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    DEPRECATED STUB: This function has been replaced by DoltMySQLWriter.write_memory_block().

    The old file-based API is no longer supported for security reasons.
    Use DoltMySQLWriter with a DoltConnectionConfig instead.
    """
    warnings.warn(
        "write_memory_block_to_dolt() is deprecated. Use DoltMySQLWriter.write_memory_block() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Use DoltMySQLWriter for MySQL-based access
    from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

    config = DoltConnectionConfig()
    writer = DoltMySQLWriter(config)
    return writer.write_memory_block(block, "main", auto_commit, preserve_nulls)


def delete_memory_block_from_dolt(
    block_id: str, db_path: str, auto_commit: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    DEPRECATED STUB: This function has been replaced by DoltMySQLWriter.delete_memory_block().
    """
    warnings.warn(
        "delete_memory_block_from_dolt() is deprecated. Use DoltMySQLWriter.delete_memory_block() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Use DoltMySQLWriter for MySQL-based access
    from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

    config = DoltConnectionConfig()
    writer = DoltMySQLWriter(config)
    return writer.delete_memory_block(block_id, "main", auto_commit)


def commit_working_changes(
    db_path: str, commit_msg: str, tables: List[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    DEPRECATED STUB: This function has been replaced by DoltMySQLWriter.commit_changes().
    """
    warnings.warn(
        "commit_working_changes() is deprecated. Use DoltMySQLWriter.commit_changes() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Use DoltMySQLWriter for MySQL-based access
    from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

    config = DoltConnectionConfig()
    writer = DoltMySQLWriter(config)
    return writer.commit_changes(commit_msg, tables)


def discard_working_changes(db_path: str, tables: List[str] = None) -> bool:
    """
    DEPRECATED STUB: This function has been replaced by DoltMySQLWriter.discard_changes().
    """
    warnings.warn(
        "discard_working_changes() is deprecated. Use DoltMySQLWriter.discard_changes() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Use DoltMySQLWriter for MySQL-based access
    from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

    config = DoltConnectionConfig()
    writer = DoltMySQLWriter(config)
    return writer.discard_changes(tables)
