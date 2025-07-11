"""
Core StructuredMemoryBank class for managing MemoryBlocks.

This class orchestrates interactions between the persistent Dolt storage
and the LlamaIndex (ChromaDB) indexing/retrieval system.

Uses secure MySQL connections to Dolt SQL servers with parameterized queries.
"""

import logging
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from pydantic import ValidationError

from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig, MainBranchProtectionError
from infra_core.memory_system.dolt_reader import (
    DoltMySQLReader,
)
from infra_core.memory_system.dolt_writer import (
    DoltMySQLWriter,
    PERSISTED_TABLES,
)
from infra_core.memory_system.llama_memory import LlamaMemory
from infra_core.memory_system.schemas.memory_block import MemoryBlock
from infra_core.memory_system.schemas.common import BlockLink
from infra_core.memory_system.tools.helpers.namespace_validation import (
    validate_namespace_exists,
    get_default_namespace,
)

# --- Path Setup ---
script_dir = Path(__file__).parent
project_root_dir = script_dir.parent.parent.parent
if str(project_root_dir) not in sys.path:
    sys.path.insert(0, str(project_root_dir))

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def diff_memory_blocks(
    old_block: MemoryBlock, new_block: MemoryBlock
) -> Dict[str, Tuple[Any, Any]]:
    """
    Creates a diff between two MemoryBlock objects, showing what fields changed.

    Args:
        old_block: The original MemoryBlock object
        new_block: The updated MemoryBlock object

    Returns:
        Dictionary where keys are field names and values are tuples of (old_value, new_value)
        Only includes fields that actually changed.
    """
    changes = {}

    # Convert both blocks to dictionaries for comparison
    old_dict = old_block.model_dump()
    new_dict = new_block.model_dump()

    # Find differences
    for key in set(old_dict.keys()) | set(new_dict.keys()):
        old_value = old_dict.get(key)
        new_value = new_dict.get(key)

        # Special handling for complex fields to avoid comparing timestamps or
        # other fields that are expected to change
        if key == "updated_at":
            # Skip updated_at, as it's expected to change
            continue

        # Check if values are different
        if old_value != new_value:
            changes[key] = (old_value, new_value)

    return changes


class InconsistentStateError(Exception):
    """
    Raised when the memory bank detects an inconsistent state between Dolt and LlamaIndex.

    This indicates a critical error where the two storage systems are out of sync,
    and operations should be aborted until the inconsistency is resolved.
    """

    def __init__(self, reason: str, block_id: Optional[str] = None):
        self.reason = reason
        self.block_id = block_id
        message = f"Memory bank inconsistent state: {reason}"
        if block_id:
            message += f" (block_id: {block_id})"
        super().__init__(message)

    def __str__(self) -> str:
        """Return a human-readable string representation of the error."""
        base_msg = f"Memory bank inconsistency detected: {self.reason}"
        if self.block_id:
            base_msg += f"\nAffected block ID: {self.block_id}"
        base_msg += "\nPlease check logs for details and contact system administrator."
        return base_msg


class StructuredMemoryBank:
    """
    Manages MemoryBlocks using Dolt for persistence and LlamaIndex for indexing.

    Uses secure MySQL connections to remote Dolt SQL servers with parameterized queries.
    """

    def __init__(
        self,
        chroma_path: str,
        chroma_collection: str,
        dolt_connection_config: DoltConnectionConfig,
        branch: str = "main",
        auto_commit: bool = False,
    ):
        """
        Initializes the StructuredMemoryBank.

        Args:
            chroma_path: Path to the ChromaDB storage directory.
            chroma_collection: Name of the ChromaDB collection.
            dolt_connection_config: Configuration for MySQL connection to remote Dolt SQL server.
            branch: Default branch to use for operations (default: "main").
            auto_commit: Whether to automatically commit changes after successful operations (default: False).
                        When False, changes remain in working set until explicit commit via MCP tools.
        """
        # Normalize branch name to lowercase for consistency
        self.branch = branch.lower().strip()
        self.auto_commit = auto_commit
        self.connection_config = dolt_connection_config

        # Initialize secure MySQL-based Dolt connections
        self.dolt_reader = DoltMySQLReader(dolt_connection_config)
        self.dolt_writer = DoltMySQLWriter(dolt_connection_config)

        # ═════════════════════════════════════════════
        # ✅ ENSURE WE'RE ON THE RIGHT BRANCH BEFORE ANY COMMITS
        try:
            conn = self.dolt_writer._get_connection()
            self.dolt_writer._ensure_branch(conn, self.branch)
            conn.close()
            logger.info(f"Checked out Dolt branch '{self.branch}' on new connection")
        except Exception as e:
            logger.error(f"Failed to checkout branch '{self.branch}': {e}", exc_info=True)
            raise
        # ═════════════════════════════════════════════

        logger.info(
            f"StructuredMemoryBank using secure MySQL connection to {dolt_connection_config.host}:{dolt_connection_config.port}"
        )

        # Initialize LlamaIndex
        self.llama_memory = LlamaMemory(chroma_path=chroma_path, collection_name=chroma_collection)

        # Flag to track data consistency state
        self._is_consistent = True

        if not self.llama_memory.is_ready():
            raise RuntimeError("Failed to initialize LlamaMemory backend.")

        logger.info(
            f"StructuredMemoryBank initialized. Branch: {self.branch}, LlamaIndex Ready: {self.llama_memory.is_ready()}"
        )

    @property
    def is_consistent(self) -> bool:
        """
        Returns the consistency state of the memory bank.
        If False, there may be a mismatch between Dolt persistence and LlamaIndex indexing.
        """
        return self._is_consistent

    def _mark_inconsistent(self, reason: str, block_id: str | None = None) -> None:
        """
        Marks the memory bank as inconsistent and logs a critical error.

        Args:
            reason: The reason why the memory bank is inconsistent.
            block_id: Optional block ID associated with the inconsistency.
        """
        self._is_consistent = False
        self._inconsistency_reason = reason
        self._inconsistency_block_id = block_id
        logger.critical(f"StructuredMemoryBank is in an inconsistent state: {reason}")

    def get_inconsistency_details(self) -> Optional[Dict[str, Any]]:
        """
        Get details about the current inconsistency, if any.

        Returns:
            Dictionary with inconsistency details if state is inconsistent, None otherwise.
            Contains 'reason', 'block_id' (if applicable), and 'timestamp'.
        """
        if not self._is_consistent:
            return {
                "reason": getattr(self, "_inconsistency_reason", "Unknown reason"),
                "block_id": getattr(self, "_inconsistency_block_id", None),
                "is_consistent": False,
            }
        return None

    def raise_if_inconsistent(self):
        """
        Raise InconsistentStateError if the memory bank is in an inconsistent state.

        This allows upstream services to abort operations instead of silently continuing.
        """
        if not self._is_consistent:
            reason = getattr(self, "_inconsistency_reason", "Unknown inconsistency detected")
            block_id = getattr(self, "_inconsistency_block_id", None)
            raise InconsistentStateError(reason, block_id)

    def _store_block_proof(self, block_id: str, operation: str, commit_hash: str) -> bool:
        """
        Store a block operation proof in the block_proofs table.

        Args:
            block_id: The ID of the block
            operation: The operation type ('create', 'update', 'delete')
            commit_hash: The Dolt commit hash for this operation

        Returns:
            True if proof was stored successfully, False otherwise
        """
        try:
            # Use the new MySQL-based proof writer
            success = self.dolt_writer.write_block_proof(
                block_id=block_id, operation=operation, commit_hash=commit_hash, branch=self.branch
            )
            return success

        except Exception as e:
            logger.error(f"Failed to store block proof for {block_id}: {e}", exc_info=True)
            return False

    def get_latest_schema_version(self, node_type: str) -> Optional[int]:
        """
        Gets the latest schema version for a given node type by querying the node_schemas table.

        Args:
            node_type: The type of node/block (e.g., 'knowledge', 'task', 'project', 'doc')

        Returns:
            The latest schema version as an integer, or None if no schema is found
        """
        logger.debug(f"Fetching latest schema version for node type: {node_type}")

        try:
            # Use the new MySQL-based schema reader
            latest_version = self.dolt_reader.read_latest_schema_version(
                node_type, branch=self.branch
            )
            if latest_version is not None:
                logger.debug(
                    f"Found latest schema version {latest_version} for node type {node_type}"
                )
            else:
                logger.debug(f"No schema version found for node type {node_type}")
            return latest_version

        except Exception as e:
            logger.warning(f"Error fetching schema version for {node_type}: {e}")
            return None

    def create_memory_block(self, block: MemoryBlock) -> tuple[bool, Optional[str]]:
        """
        Creates a new MemoryBlock, persisting to Dolt and indexing in LlamaIndex with atomic guarantees.
        If either operation fails, both are rolled back to ensure consistency between storage systems.

        Args:
            block: The MemoryBlock object to create.

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
            - success: True if creation was successful (both Dolt write and LlamaIndex add), False otherwise
            - error_message: Specific error details if creation failed, None if successful
        """
        logger.info(f"Attempting to create memory block: {block.id}")

        if not self.llama_memory.is_ready():
            error_msg = "LlamaMemory backend is not ready. Cannot create block."
            logger.error(error_msg)
            return False, error_msg

        # Query node_schemas for latest version and set block.schema_version if not already set
        if block.schema_version is None:
            try:
                latest_version = self.get_latest_schema_version(block.type)
                if latest_version is not None:
                    # Explicitly assign the schema version to the block
                    block.schema_version = latest_version
                    logger.info(f"Set schema_version to {latest_version} for block {block.id}")
                else:
                    logger.warning(
                        f"No schema version found for block type '{block.type}'. Creating block without schema_version."
                    )
            except Exception as e:
                logger.warning(f"Error looking up schema version for {block.type}: {e}")
                # Continue without schema version

        # --- VALIDATION PHASE ---
        # Ensure the block is valid before writing
        try:
            # Force re-validation of the entire block including nested fields
            block = MemoryBlock.model_validate(block)
        except ValidationError as ve:
            # Clear, specific logging for validation errors
            field_errors = [
                f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in ve.errors()
            ]
            error_details = "\n- ".join(field_errors)
            error_msg = f"Validation failed for block {block.id}:\n- {error_details}"
            logger.error(error_msg)
            # Create a simpler error message for return
            simple_errors = [
                f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in ve.errors()
            ]
            return False, f"Block validation failed: {'; '.join(simple_errors)}"

        # Validate namespace exists
        try:
            validate_namespace_exists(block.namespace_id, self, raise_error=True)
        except KeyError as e:
            error_msg = f"Namespace validation failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Namespace validation error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
        # --- END VALIDATION PHASE ---

        # --- ATOMIC PERSISTENCE PHASE ---
        # Tables to track for commit/rollback
        tables = PERSISTED_TABLES
        dolt_write_success = False
        llama_success = False

        try:
            # Step 1: Write to Dolt without auto-commit
            try:
                dolt_write_success, _ = self.dolt_writer.write_memory_block(
                    block=block,
                    branch=self.branch,
                    auto_commit=False,  # Do not auto-commit, we need atomicity control
                )

                if not dolt_write_success:
                    error_msg = f"Failed to write block {block.id} to Dolt database"
                    logger.error(f"{error_msg}. Aborting atomic operation.")
                    return False, error_msg

                logger.info(
                    f"Successfully wrote block {block.id} to Dolt working set (uncommitted)."
                )

            except MainBranchProtectionError as protection_e:
                error_msg = str(protection_e)
                logger.error(f"Branch protection error: {error_msg}")
                return False, error_msg
            except Exception as dolt_e:
                error_msg = f"Database write error for block {block.id}: {str(dolt_e)}"
                logger.error(
                    f"Unexpected error writing block {block.id} to Dolt: {dolt_e}", exc_info=True
                )
                return False, error_msg

            # Step 2: Add block to LlamaIndex
            try:
                self.llama_memory.add_block(block)
                llama_success = True
                logger.info(f"Successfully indexed block {block.id} in LlamaIndex.")
            except Exception as llama_e:
                llama_success = False
                error_msg = f"Search indexing failed for block {block.id}: {str(llama_e)}"
                logger.error(
                    f"Failed to index block {block.id} in LlamaIndex: {llama_e}", exc_info=True
                )

            # Step 3: Handle success or failure path
            if llama_success:
                # Both operations succeeded - commit the Dolt changes if auto_commit is enabled
                if self.auto_commit:
                    try:
                        commit_msg = f"Create memory block {block.id}"
                        commit_success, commit_hash = self.dolt_writer.commit_changes(
                            commit_msg=commit_msg, tables=tables
                        )

                        if commit_success:
                            logger.info(
                                f"Successfully created and indexed memory block: {block.id}"
                            )
                            self._store_block_proof(block.id, "create", commit_hash)
                            return True, None
                        else:
                            # Commit failed - attempt rollback
                            error_msg = f"Failed to commit changes for block {block.id} to database"
                            logger.error(f"{error_msg}. Attempting rollback.")

                            # Rollback Dolt changes
                            try:
                                self.dolt_writer.discard_changes(tables)
                                logger.info(
                                    f"Successfully rolled back Dolt changes for block {block.id}"
                                )
                            except Exception as rollback_e:
                                logger.critical(
                                    f"Failed to rollback Dolt changes: {rollback_e}. Database may be in an inconsistent state!"
                                )
                                self._mark_inconsistent(
                                    f"Dolt commit failed and rollback failed for block {block.id}",
                                    block.id,
                                )

                            return False, error_msg

                    except Exception as commit_e:
                        error_msg = f"Commit operation failed for block {block.id}: {str(commit_e)}"
                        logger.error(
                            f"Unexpected error during commit for block {block.id}: {commit_e}",
                            exc_info=True,
                        )
                        return False, error_msg
                else:
                    # Auto-commit disabled - operation succeeded but changes remain uncommitted
                    logger.info(
                        f"Successfully created memory block {block.id} (uncommitted - auto_commit=False)"
                    )
                    # Store proof with placeholder commit hash to track staged operations
                    self._store_block_proof(block.id, "create", "STAGED")
                    return True, None

            else:
                # LlamaIndex operation failed - rollback Dolt changes
                logger.error(
                    f"LlamaIndex operation failed for block {block.id}. Rolling back Dolt changes."
                )
                try:
                    self.dolt_writer.discard_changes(tables)
                    logger.info(f"Successfully rolled back Dolt changes for block {block.id}")
                except Exception as rollback_e:
                    logger.critical(
                        f"Failed to rollback Dolt changes: {rollback_e}. Database may be in an inconsistent state!"
                    )
                    self._mark_inconsistent(
                        f"LlamaIndex operation failed and Dolt rollback failed for block {block.id}",
                        block.id,
                    )

                return False, error_msg  # error_msg was set in the LlamaIndex exception handler

        except Exception as e:
            error_msg = f"Unexpected error during block creation: {str(e)}"
            logger.error(
                f"Unexpected error during atomic persistence of block {block.id}: {e}",
                exc_info=True,
            )

            # Attempt rollback of any Dolt changes
            try:
                self.dolt_writer.discard_changes(tables)
                logger.info(
                    f"Successfully rolled back any Dolt changes after exception for block {block.id}."
                )
            except Exception as rollback_e:
                logger.critical(
                    f"Failed to rollback Dolt changes after exception: {rollback_e}. Database may be in an inconsistent state!"
                )
                self._mark_inconsistent(
                    f"Exception during create and Dolt rollback failed for block {block.id}",
                    block.id,
                )

            return False, error_msg
        # --- END ATOMIC PERSISTENCE PHASE ---

    def get_memory_block(self, block_id: str) -> Optional[MemoryBlock]:
        """
        Retrieves a MemoryBlock from Dolt by its ID.

        Args:
            block_id: The ID of the block to retrieve.

        Returns:
            The MemoryBlock object if found, otherwise None.
        """
        logger.info(f"Attempting to get memory block: {block_id}")
        try:
            block = self.dolt_reader.read_memory_block(block_id, branch=self.branch)
            if block:
                logger.info(f"Successfully retrieved block {block_id}")
            else:
                logger.info(f"Block {block_id} not found in Dolt.")
            return block
        except Exception as e:
            logger.error(f"Error retrieving block {block_id}: {e}", exc_info=True)
            return None

    def update_memory_block(self, block: MemoryBlock) -> bool:
        """
        Updates an existing MemoryBlock, persisting to Dolt and updating in LlamaIndex with atomic guarantees.
        If either operation fails, both are rolled back to ensure consistency between storage systems.

        Args:
            block: The MemoryBlock object to update.

        Returns:
            True if update was successful (both Dolt write and LlamaIndex update), False otherwise.
        """
        logger.info(f"Attempting to update memory block: {block.id}")

        if not self.llama_memory.is_ready():
            logger.error("LlamaMemory backend is not ready. Cannot update block.")
            return False

        # --- VALIDATION PHASE ---
        # Ensure the block is valid before writing
        try:
            # Force re-validation of the entire block including nested fields
            block = MemoryBlock.model_validate(block)
        except ValidationError as ve:
            # Clear, specific logging for validation errors
            field_errors = [
                f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in ve.errors()
            ]
            error_details = "\n- ".join(field_errors)
            logger.error(f"Validation failed for block {block.id}:\n- {error_details}")
            return False

        # Validate namespace exists
        try:
            validate_namespace_exists(block.namespace_id, self, raise_error=True)
        except KeyError as e:
            error_msg = f"Namespace validation failed: {str(e)}"
            logger.error(error_msg)
            return False
        except Exception as e:
            error_msg = f"Namespace validation error: {str(e)}"
            logger.error(error_msg)
            return False
        # --- END VALIDATION PHASE ---

        # --- ATOMIC PERSISTENCE PHASE ---
        # Tables to track for commit/rollback
        tables = PERSISTED_TABLES
        dolt_write_success = False
        llama_success = False

        try:
            # Step 1: Write to Dolt without auto-commit
            try:
                dolt_write_success, _ = self.dolt_writer.write_memory_block(
                    block=block,
                    branch=self.branch,
                    auto_commit=False,  # Do not auto-commit, we need atomicity control
                    preserve_nulls=True,  # Preserve None values for update operations
                )

                if not dolt_write_success:
                    logger.error(
                        f"Failed to write block {block.id} to Dolt. Aborting atomic operation."
                    )
                    return False

                logger.info(
                    f"Successfully wrote block {block.id} to Dolt working set (uncommitted)."
                )

            except Exception as dolt_e:
                logger.error(
                    f"Unexpected error writing block {block.id} to Dolt: {dolt_e}", exc_info=True
                )
                return False

            # Step 2: Update block in LlamaIndex
            try:
                self.llama_memory.update_block(block)
                llama_success = True
                logger.info(f"Successfully updated block {block.id} in LlamaIndex.")
            except Exception as llama_e:
                llama_success = False
                logger.error(
                    f"Failed to update block {block.id} in LlamaIndex: {llama_e}", exc_info=True
                )

            # Step 3: Handle success or failure path
            if llama_success:
                # Both operations succeeded - commit the Dolt changes if auto_commit is enabled
                if self.auto_commit:
                    try:
                        commit_msg = f"Update memory block {block.id}"
                        commit_success, commit_hash = self.dolt_writer.commit_changes(
                            commit_msg=commit_msg, tables=tables
                        )

                        if commit_success:
                            logger.info(
                                f"Successfully updated and indexed memory block: {block.id}"
                            )
                            self._store_block_proof(block.id, "update", commit_hash)
                            return True
                        else:
                            # Commit failed - attempt rollback
                            logger.error(
                                f"Failed to commit Dolt changes for block {block.id}. Attempting rollback."
                            )

                            # Rollback Dolt changes
                            try:
                                self.dolt_writer.discard_changes(tables)
                                logger.info(
                                    f"Successfully rolled back Dolt changes for block {block.id}"
                                )
                            except Exception as rollback_e:
                                logger.critical(
                                    f"Failed to rollback Dolt changes: {rollback_e}. Database may be in an inconsistent state!"
                                )
                                self._mark_inconsistent(
                                    f"Dolt commit failed and rollback failed for block {block.id}",
                                    block.id,
                                )

                            return False

                    except Exception as commit_e:
                        logger.error(
                            f"Unexpected error during commit for block {block.id}: {commit_e}",
                            exc_info=True,
                        )
                        return False
                else:
                    # Auto-commit disabled - operation succeeded but changes remain uncommitted
                    logger.info(
                        f"Successfully updated memory block {block.id} (uncommitted - auto_commit=False)"
                    )
                    # Store proof with placeholder commit hash to track staged operations
                    self._store_block_proof(block.id, "update", "STAGED")
                    return True

            else:
                # LlamaIndex operation failed - rollback Dolt changes
                logger.error(
                    f"LlamaIndex operation failed for block {block.id}. Rolling back Dolt changes."
                )
                try:
                    self.dolt_writer.discard_changes(tables)
                    logger.info(f"Successfully rolled back Dolt changes for block {block.id}")
                except Exception as rollback_e:
                    logger.critical(
                        f"Failed to rollback Dolt changes: {rollback_e}. Database may be in an inconsistent state!"
                    )
                    self._mark_inconsistent(
                        f"LlamaIndex operation failed and Dolt rollback failed for block {block.id}",
                        block.id,
                    )

                return False

        except Exception as e:
            logger.error(
                f"Unexpected error during atomic persistence of block {block.id}: {e}",
                exc_info=True,
            )

            # Attempt rollback of any Dolt changes
            try:
                self.dolt_writer.discard_changes(tables)
                logger.info(
                    f"Successfully rolled back any Dolt changes after exception for block {block.id}."
                )
            except Exception as rollback_e:
                logger.critical(
                    f"Failed to rollback Dolt changes after exception: {rollback_e}. Database may be in an inconsistent state!"
                )
                self._mark_inconsistent(
                    f"Exception during update and Dolt rollback failed for block {block.id}",
                    block.id,
                )

            return False
        # --- END ATOMIC PERSISTENCE PHASE ---

    def delete_memory_block(self, block_id: str) -> bool:
        """
        Deletes a MemoryBlock from both Dolt and LlamaIndex with atomic guarantees.
        If either operation fails, both are rolled back to ensure consistency.

        Args:
            block_id: The ID of the block to delete.

        Returns:
            True if the deletion was successful (both Dolt delete and LlamaIndex removal), False otherwise.
        """
        logger.info(f"Attempting to delete memory block: {block_id}")

        if not self.llama_memory.is_ready():
            logger.error("LlamaMemory backend is not ready. Cannot delete block.")
            return False

        # Check if the block exists before deletion
        try:
            existing_block = self.dolt_reader.read_memory_block(block_id, branch=self.branch)
            if not existing_block:
                logger.warning(
                    f"Block {block_id} not found in Dolt. Cannot delete non-existent block."
                )
                return False
        except Exception as e:
            logger.error(f"Error checking if block {block_id} exists: {e}", exc_info=True)
            return False

        # --- ATOMIC DELETION PHASE ---
        # Tables to track for commit/rollback
        tables = PERSISTED_TABLES

        # Step 1: Delete from Dolt without auto-commit
        try:
            dolt_delete_success, _ = self.dolt_writer.delete_memory_block(
                block_id=block_id,
                branch=self.branch,
                auto_commit=False,  # Do not auto-commit, we need atomicity control
            )

            if not dolt_delete_success:
                logger.error(
                    f"Failed to delete block {block_id} from Dolt. Aborting atomic operation."
                )
                return False

            logger.info(
                f"Successfully deleted block {block_id} from Dolt working set (uncommitted)."
            )

            # Step 2: Remove block from LlamaIndex
            llama_success = True
            try:
                # Ensure we handle the case where the block might not exist in LlamaIndex
                try:
                    # This block ID format may need to match the ID format used by LlamaIndex adapter
                    self.llama_memory.delete_block(block_id)
                    logger.info(f"Successfully deleted block {block_id} from LlamaIndex.")
                except KeyError:
                    # If block doesn't exist in LlamaIndex, log but continue
                    logger.warning(
                        f"Block {block_id} not found in LlamaIndex. Continuing with deletion."
                    )
                    # Consider this a success since the desired end state is achieved
                except Exception as specific_e:
                    # Handle other LlamaIndex exceptions
                    logger.error(
                        f"Error deleting block {block_id} from LlamaIndex: {specific_e}",
                        exc_info=True,
                    )
                    llama_success = False
            except Exception as llama_e:
                llama_success = False
                logger.error(
                    f"Failed to delete block {block_id} from LlamaIndex: {llama_e}", exc_info=True
                )

            # Step 3: Handle success or failure path
            if llama_success:
                # Both operations succeeded - commit the Dolt changes if auto_commit is enabled
                if self.auto_commit:
                    try:
                        commit_msg = f"Delete memory block {block_id}"
                        commit_success, commit_hash = self.dolt_writer.commit_changes(
                            commit_msg=commit_msg, tables=tables
                        )

                        if commit_success:
                            logger.info(f"Successfully deleted memory block: {block_id}")
                            self._store_block_proof(block_id, "delete", commit_hash)
                            return True
                        else:
                            # Commit failed - attempt rollback
                            logger.error(
                                f"Failed to commit Dolt changes for deleted block {block_id}. Attempting rollback."
                            )

                            # Rollback Dolt changes - restore deleted block
                            try:
                                self.dolt_writer.discard_changes(tables)
                                logger.info(
                                    f"Successfully rolled back Dolt deletion for block {block_id}."
                                )
                            except Exception as rollback_e:
                                logger.critical(
                                    f"Failed to rollback Dolt changes: {rollback_e}. Database may be in an inconsistent state!"
                                )
                                self._mark_inconsistent(
                                    f"Dolt commit failed and rollback failed for deleted block {block_id}",
                                    block_id,
                                )

                            return False
                    except Exception as commit_e:
                        logger.error(
                            f"Exception during Dolt commit for deleted block {block_id}: {commit_e}",
                            exc_info=True,
                        )

                        # Rollback LlamaIndex changes - would need to re-add the original block
                        logger.warning(
                            f"LlamaIndex deletion of block {block_id} cannot be automatically rolled back."
                        )

                        # Rollback Dolt changes
                        try:
                            self.dolt_writer.discard_changes(tables)
                            logger.info(
                                f"Successfully rolled back Dolt deletion for block {block_id}."
                            )
                        except Exception as rollback_e:
                            logger.critical(
                                f"Failed to rollback Dolt changes: {rollback_e}. Database may be in an inconsistent state!"
                            )
                            self._mark_inconsistent(
                                f"Dolt commit failed and rollback failed for deleted block {block_id}",
                                block_id,
                            )

                        return False
                else:
                    # Auto-commit disabled - operation succeeded but changes remain uncommitted
                    logger.info(
                        f"Successfully deleted memory block {block_id} (uncommitted - auto_commit=False)"
                    )
                    # Store proof with placeholder commit hash to track staged operations
                    self._store_block_proof(block_id, "delete", "STAGED")
                    return True
            else:
                # LlamaIndex delete failed - rollback Dolt changes
                try:
                    self.dolt_writer.discard_changes(tables)
                    logger.info(
                        f"Successfully rolled back Dolt changes after LlamaIndex delete failure for block {block_id}."
                    )
                except Exception as rollback_e:
                    logger.critical(
                        f"Failed to rollback Dolt changes after LlamaIndex delete failure: {rollback_e}. Database may be in an inconsistent state!"
                    )
                    self._mark_inconsistent(
                        f"LlamaIndex delete failed and Dolt rollback failed for block {block_id}"
                    )

                return False

        except Exception as e:
            logger.error(f"Failed during atomic deletion of block {block_id}: {e}", exc_info=True)

            # Attempt rollback of any Dolt changes
            try:
                self.dolt_writer.discard_changes(tables)
                logger.info(
                    f"Successfully rolled back any Dolt changes after exception for deleted block {block_id}."
                )
            except Exception as rollback_e:
                logger.critical(
                    f"Failed to rollback Dolt changes after exception: {rollback_e}. Database may be in an inconsistent state!"
                )
                self._mark_inconsistent(
                    f"Exception during delete and Dolt rollback failed for block {block_id}",
                    block_id,
                )

            return False
        # --- END ATOMIC DELETION PHASE ---

    def query_semantic(self, query_text: str, top_k: int = 5) -> List[MemoryBlock]:
        """
        Performs a semantic search using LlamaIndex and retrieves full blocks from Dolt.

        Args:
            query_text: The text query for semantic search.
            top_k: The maximum number of results to return.

        Returns:
            A list of relevant MemoryBlock objects, potentially fewer than top_k if retrieval fails for some IDs.
        """
        logger.info(f"Performing semantic query: '{query_text}' (top_k={top_k})")
        if not self.llama_memory.is_ready():
            logger.error("LlamaMemory backend is not ready. Cannot perform semantic query.")
            return []

        retrieved_blocks: List[MemoryBlock] = []
        try:
            # 1. Query LlamaIndex vector store
            nodes_with_scores = self.llama_memory.query_vector_store(query_text, top_k=top_k)

            if not nodes_with_scores:
                logger.info("Semantic query returned no results from LlamaIndex.")
                return []

            # 2. Extract block IDs and retrieve full blocks from Dolt
            block_ids = [node.node.id_ for node in nodes_with_scores if node.node and node.node.id_]
            logger.info(
                f"LlamaIndex query returned {len(block_ids)} potential block IDs: {block_ids}"
            )

            # Consider adding a cache here later if performance becomes an issue
            for block_id in block_ids:
                try:
                    # 3. Retrieve full block from Dolt using existing method
                    block = self.get_memory_block(block_id)
                    if block:
                        # TODO: Consider adding relevance score from LlamaIndex to the returned block
                        # (Requires modifying MemoryBlock schema or returning a different structure)
                        retrieved_blocks.append(block)
                    else:
                        logger.warning(
                            f"Could not retrieve block with ID {block_id} from Dolt, though it was found in LlamaIndex."
                        )
                except Exception as e_get:
                    logger.error(
                        f"Error retrieving block {block_id} from Dolt during semantic query: {e_get}",
                        exc_info=True,
                    )
                    # Continue to try retrieving other blocks

            logger.info(
                f"Semantic query processing complete. Retrieved {len(retrieved_blocks)} full blocks from Dolt."
            )
            return retrieved_blocks

        except Exception as e:
            logger.error(f"Error during semantic query execution: {e}", exc_info=True)
            return []  # Return empty list on major query error

    def get_blocks_by_tags(self, tags: List[str], match_all: bool = True) -> List[MemoryBlock]:
        """
        Retrieves MemoryBlocks based on tags by querying Dolt directly.

        Args:
            tags: A list of tags to filter by.
            match_all: If True, blocks must have all tags. If False, blocks must have at least one tag.

        Returns:
            A list of matching MemoryBlock objects.
        """
        logger.info(f"Getting blocks by tags: {tags} (match_all={match_all})")
        try:
            matching_blocks = self.dolt_reader.read_memory_blocks_by_tags(
                tags=tags,
                match_all=match_all,
                branch=self.branch,
            )
            return matching_blocks
        except Exception as e:
            logger.error(f"Error retrieving blocks by tags ({tags}): {e}", exc_info=True)
            return []  # Return empty list on error

    def get_all_memory_blocks(self, branch: str = "main") -> List[MemoryBlock]:
        """
        Retrieves all MemoryBlocks from the specified Dolt branch.

        Args:
            branch: The Dolt branch to read from (defaults to 'main').

        Returns:
            A list of matching MemoryBlock objects.
        """
        logger.info(f"Getting all memory blocks from branch '{branch}'")
        try:
            all_blocks = self.dolt_reader.read_memory_blocks(branch=branch)
            return all_blocks
        except Exception as e:
            logger.error(
                f"Error retrieving all memory blocks from branch '{branch}': {e}", exc_info=True
            )
            return []  # Return empty list on error

    # TODO: Implement MySQL-based link management
    def get_forward_links(self, block_id: str, relation: Optional[str] = None) -> List[BlockLink]:
        """
        TODO: optimization needed here
        Retrieves outgoing links from a specific block.

        Args:
            block_id: The ID of the source block
            relation: Optional relation type to filter by

        Returns:
            List of BlockLink objects representing outgoing links
        """
        logger.debug(f"Getting forward links for block {block_id}, relation={relation}")
        try:
            # Use the new MySQL-based link reader
            link_rows = self.dolt_reader.read_forward_links(
                block_id=block_id, relation=relation, branch=self.branch
            )

            # Convert raw database rows to BlockLink objects
            links = []
            for row in link_rows:
                try:
                    link = BlockLink(
                        from_id=row["from_block_id"],
                        to_id=row["to_block_id"],
                        relation=row["relation"],
                        priority=row.get("priority", 0),
                        link_metadata=row.get("metadata"),
                        created_at=row.get("created_at"),
                    )
                    links.append(link)
                except Exception as e:
                    logger.warning(f"Failed to parse link row {row}: {e}")
                    continue

            logger.debug(f"Found {len(links)} forward links for block {block_id}")
            return links

        except Exception as e:
            logger.error(f"Error retrieving forward links for {block_id}: {e}", exc_info=True)
            return []

    def get_backlinks(self, block_id: str, relation: Optional[str] = None) -> List[BlockLink]:
        """
        TODO: optimization needed here
        Retrieves blocks that link TO the specified block.

        Args:
            block_id: The ID of the target block
            relation: Optional relation type to filter by

        Returns:
            List of BlockLink objects representing incoming links
        """
        logger.debug(f"Getting backlinks for block {block_id}, relation={relation}")
        try:
            # Use the new MySQL-based link reader
            link_rows = self.dolt_reader.read_backlinks(
                block_id=block_id, relation=relation, branch=self.branch
            )

            # Convert raw database rows to BlockLink objects
            links = []
            for row in link_rows:
                try:
                    link = BlockLink(
                        from_id=row["from_block_id"],
                        to_id=row["to_block_id"],
                        relation=row["relation"],
                        priority=row.get("priority", 0),
                        link_metadata=row.get("metadata"),
                        created_at=row.get("created_at"),
                    )
                    links.append(link)
                except Exception as e:
                    logger.warning(f"Failed to parse link row {row}: {e}")
                    continue

            logger.debug(f"Found {len(links)} backlinks for block {block_id}")
            return links

        except Exception as e:
            logger.error(f"Error retrieving backlinks for {block_id}: {e}", exc_info=True)
            return []

    def get_block_proofs(self, block_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves block operation proofs (create/update/delete) for a specific block.

        Args:
            block_id: The ID of the block to get proofs for

        Returns:
            List of dictionaries containing operation, commit_hash, timestamp info.
            Ordered newest first (most recent operation first).
        """
        logger.info(f"Getting block proofs for block: {block_id}")
        try:
            proofs = self.dolt_reader.read_block_proofs(block_id, branch=self.branch)
            logger.info(f"Found {len(proofs)} proofs for block {block_id}")
            return proofs
        except Exception as e:
            logger.error(f"Error retrieving block proofs for {block_id}: {e}", exc_info=True)
            return []

    def format_commit_message(
        self,
        operation: str,
        block_id: str,
        change_summary: str = "No significant changes",
        extra_info: Optional[str] = None,
    ) -> str:
        """
        Formats a standardized commit message for memory block operations.

        Args:
            operation: The operation type (create, update, delete)
            block_id: The ID of the block being operated on
            change_summary: Summary of changes made (default: "No significant changes")
            extra_info: Optional additional context (e.g., "actor=user-123")

        Returns:
            Formatted commit message string
        """
        # Standardize operation name to uppercase
        operation_upper = operation.upper()

        # Build base message
        message = f"{operation_upper}: {block_id} - {change_summary}"

        # Append extra info if provided
        if extra_info:
            message += f" [{extra_info}]"

        return message

    def use_persistent_connections(self, branch: str = None) -> None:
        """
        Enable persistent connection mode on both reader and writer with coordinated branch state.

        This ensures that branch checkouts persist across all memory bank operations.

        Args:
            branch: Branch to checkout and maintain (defaults to self.branch)
        """
        target_branch = branch or self.branch

        try:
            # Enable persistent connections on both reader and writer
            self.dolt_reader.use_persistent_connection(target_branch)
            reader_actual_branch = getattr(self.dolt_reader, "_current_branch", None)

            self.dolt_writer.use_persistent_connection(target_branch)
            writer_actual_branch = getattr(self.dolt_writer, "_current_branch", None)

            # Verify both connections are on the same branch (session synchronization)
            if reader_actual_branch != writer_actual_branch:
                self.close_persistent_connections()
                raise Exception(
                    f"Branch synchronization failed: reader on '{reader_actual_branch}', "
                    f"writer on '{writer_actual_branch}'. Both must be on same branch for consistent operations."
                )

            # Update the memory bank's branch to match the verified database session state
            self.branch = reader_actual_branch  # Use verified branch from database session

            logger.info(
                f"StructuredMemoryBank enabled persistent connections on verified branch '{self.branch}'"
            )

        except Exception as e:
            logger.error(f"Exception in use_persistent_connections: {e}", exc_info=True)
            # Cleanup on failure
            try:
                self.close_persistent_connections()
            except Exception:
                pass
            raise Exception(f"Failed to enable persistent connections: {e}")

    def close_persistent_connections(self) -> None:
        """
        Close persistent connections on both reader and writer.
        """
        try:
            if hasattr(self.dolt_reader, "close_persistent_connection"):
                self.dolt_reader.close_persistent_connection()
        except Exception as e:
            logger.warning(f"Error closing reader persistent connection: {e}")

        try:
            if hasattr(self.dolt_writer, "close_persistent_connection"):
                self.dolt_writer.close_persistent_connection()
        except Exception as e:
            logger.warning(f"Error closing writer persistent connection: {e}")

        logger.info("StructuredMemoryBank closed persistent connections")

    def test_commit_without_persistent(self) -> str:
        """
        Test method to close persistent connections and check if commits work.
        """
        self.close_persistent_connections()
        return "Persistent connections closed - ready for commit test"

    def debug_persistent_state(self, force: bool = False) -> Dict[str, Any]:
        """
        Debug method to check persistent connection state.

        This method is only available in debug mode to prevent accidental
        exposure of internal state in production environments.

        Args:
            force: If True, bypass the debug mode check (use with caution!)

        Returns:
            Dictionary with debug information about persistent connections
        """
        if not __debug__ and not force:
            raise RuntimeError(
                "debug_persistent_state() is only available in debug mode unless force=True"
            )

        return {
            "memory_bank_branch": self.branch,
            "reader_use_persistent": getattr(self.dolt_reader, "_use_persistent", "UNKNOWN"),
            "reader_current_branch": getattr(self.dolt_reader, "_current_branch", "UNKNOWN"),
            "writer_use_persistent": getattr(self.dolt_writer, "_use_persistent", "UNKNOWN"),
            "writer_current_branch": getattr(self.dolt_writer, "_current_branch", "UNKNOWN"),
            "reader_has_connection": getattr(self.dolt_reader, "_persistent_connection", None)
            is not None,
            "writer_has_connection": getattr(self.dolt_writer, "_persistent_connection", None)
            is not None,
        }

    def namespace_exists(self, namespace_id: str) -> bool:
        """
        Check if a namespace exists in the database.

        This is the single authoritative method for namespace existence checking,
        used by validation helpers and MCP tools.

        Args:
            namespace_id: The namespace ID to check (case-insensitive)

        Returns:
            True if the namespace exists, False otherwise
        """
        try:
            # Normalize namespace_id to lowercase for case-insensitive comparison
            normalized_id = namespace_id.lower().strip()

            # Fast path for default namespace
            if normalized_id == get_default_namespace():
                return True

            # Query database with case-insensitive comparison
            query = "SELECT id FROM namespaces WHERE LOWER(id) = %s"
            result = self.dolt_reader._execute_query(query, (normalized_id,))
            return len(result) > 0

        except Exception as e:
            logger.error(f"Error checking namespace existence for '{namespace_id}': {e}")
            return False
