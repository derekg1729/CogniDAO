"""
Project Management Executable Links Helper.

This module provides a thin layer on top of LinkManager that adds specialized
methods for handling executable blocks (tasks, projects, epics) and their
relationships.
"""

from typing import Dict, List, Optional, Any, cast

from .link_manager import LinkManager, LinkQuery, BlockLink, InMemoryLinkManager
from .relation_registry import PMRelationType, CoreRelationType


class ExecutableLinkManager:
    """
    Helper class for managing links between executable blocks.

    Provides specialized methods for handling relationships between tasks,
    projects, epics, and other executable blocks, building on top of the
    generic LinkManager implementation.
    """

    def __init__(self, link_manager: LinkManager):
        """
        Initialize with a LinkManager instance.

        Args:
            link_manager: The underlying LinkManager to use for operations
        """
        self._link_manager = link_manager

    # Blocker relationship methods
    def add_blocker(
        self,
        task_id: str,
        blocker_id: str,
        priority: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None,
    ) -> BlockLink:
        """
        Mark a task as blocked by another task.

        Args:
            task_id: ID of the task being blocked
            blocker_id: ID of the blocking task
            priority: Priority of the blocker (higher = more important)
            metadata: Additional metadata about the relationship
            created_by: ID of the agent/user creating the link

        Returns:
            The created BlockLink

        Raises:
            LinkError: If validation fails or the operation would create a cycle
        """
        return self._link_manager.create_link(
            from_id=blocker_id,
            to_id=task_id,
            relation=PMRelationType.BLOCKS.value,
            priority=priority,
            link_metadata=metadata,
            created_by=created_by,
        )

    def remove_blocker(self, task_id: str, blocker_id: str) -> bool:
        """
        Remove a blocker from a task.

        Args:
            task_id: ID of the task being unblocked
            blocker_id: ID of the blocking task to remove

        Returns:
            True if the blocker was removed, False if it didn't exist
        """
        return self._link_manager.delete_link(
            from_id=blocker_id,
            to_id=task_id,
            relation=PMRelationType.BLOCKS.value,
        )

    def get_blockers(self, task_id: str) -> List[BlockLink]:
        """
        Get all tasks that are blocking the given task.

        Args:
            task_id: ID of the task to get blockers for

        Returns:
            List of BlockLinks representing the blockers
        """
        # We need to find all blocks -> task_id relationships
        query = LinkQuery().relation(PMRelationType.BLOCKS.value)
        result = self._link_manager.links_to(task_id, query)
        return result.links

    def get_blocker_ids(self, task_id: str) -> List[str]:
        """
        Get IDs of all tasks that are blocking the given task.

        Args:
            task_id: ID of the task to get blockers for

        Returns:
            List of IDs of blocking tasks
        """
        # For InMemoryLinkManager, we can access internal structures
        if isinstance(self._link_manager, InMemoryLinkManager):
            in_memory_lm = cast(InMemoryLinkManager, self._link_manager)
            blocker_ids = []

            # Find all links where to_id == task_id and relation == BLOCKS
            for (from_id, to_id, rel), _ in in_memory_lm._links.items():
                if to_id == task_id and rel == PMRelationType.BLOCKS.value:
                    blocker_ids.append(from_id)

            return blocker_ids
        else:
            # Generic implementation for other LinkManager implementations
            # Get BlockLinks and try to determine source IDs from metadata, if possible
            # This is less optimal, as BlockLink doesn't expose from_id directly
            return []

    def get_blocking(self, task_id: str) -> List[BlockLink]:
        """
        Get all tasks that are blocked by the given task.

        Args:
            task_id: ID of the task to get blocked tasks for

        Returns:
            List of BlockLinks representing the blocked tasks
        """
        query = LinkQuery().relation(PMRelationType.BLOCKS.value)
        result = self._link_manager.links_from(task_id, query)
        return result.links

    def get_ready_tasks(self, task_ids: Optional[List[str]] = None) -> List[str]:
        """
        Get IDs of tasks that have no blockers.

        Args:
            task_ids: Optional list of task IDs to check.
                     If None, all tasks in the system are checked.

        Returns:
            List of task IDs with no blockers
        """
        # If we're using the in-memory implementation, we can use the optimized method
        if hasattr(self._link_manager, "_index"):
            return self._link_manager._index.get_ready_tasks(PMRelationType.BLOCKS.value)

        # Otherwise, we need to query each task
        if task_ids is None:
            # For testing purposes, collect all unique IDs from the link manager
            all_ids = set()

            # If using InMemoryLinkManager, access its internal structure
            if isinstance(self._link_manager, InMemoryLinkManager):
                in_memory_lm = cast(InMemoryLinkManager, self._link_manager)

                # Collect all unique block IDs
                for from_id, to_id, _ in in_memory_lm._links.keys():
                    all_ids.add(from_id)
                    all_ids.add(to_id)
            else:
                # Generic implementation for other LinkManager types
                # Get all tasks by querying for any relation
                blocks_query = LinkQuery()
                all_blocks = self._link_manager.query_links(blocks_query)

                for link in all_blocks.links:
                    all_ids.add(link.to_id)

            task_ids = list(all_ids)

        # Check each task for blockers
        ready_tasks = []
        for task_id in task_ids:
            blockers = self.get_blocker_ids(task_id)
            if not blockers:
                ready_tasks.append(task_id)

        return ready_tasks

    # Parent-child relationship methods
    def set_parent(
        self,
        child_id: str,
        parent_id: str,
        update_metadata: bool = True,
        created_by: Optional[str] = None,
    ) -> BlockLink:
        """
        Set a parent-child relationship between two blocks.

        Args:
            child_id: ID of the child block
            parent_id: ID of the parent block
            update_metadata: Whether to update the x_parent_block_id in the child's metadata
            created_by: ID of the agent/user creating the link

        Returns:
            The created BlockLink

        Raises:
            LinkError: If validation fails or the operation would create a cycle
        """
        link = self._link_manager.create_link(
            from_id=child_id,
            to_id=parent_id,
            relation=CoreRelationType.CHILD_OF.value,
            created_by=created_by,
        )

        if update_metadata:
            # TODO: Update the child block's metadata to set x_parent_block_id
            # This would require interfacing with the block store
            pass

        return link

    def remove_parent(self, child_id: str, parent_id: str, update_metadata: bool = True) -> bool:
        """
        Remove a parent-child relationship.

        Args:
            child_id: ID of the child block
            parent_id: ID of the parent block
            update_metadata: Whether to update the x_parent_block_id in the child's metadata

        Returns:
            True if the relationship was removed, False if it didn't exist
        """
        result = self._link_manager.delete_link(
            from_id=child_id,
            to_id=parent_id,
            relation=CoreRelationType.CHILD_OF.value,
        )

        if result and update_metadata:
            # TODO: Update the child block's metadata to clear x_parent_block_id
            # This would require interfacing with the block store
            pass

        return result

    def get_parent(self, child_id: str) -> Optional[str]:
        """
        Get the parent of a block.

        Args:
            child_id: ID of the child block

        Returns:
            ID of the parent block, or None if no parent exists
        """
        query = LinkQuery().relation(CoreRelationType.CHILD_OF.value)
        result = self._link_manager.links_from(child_id, query)

        if not result.links:
            return None

        # A block should have at most one parent
        if len(result.links) > 1:
            # Log a warning, but return the first parent found
            # TODO: Add proper logging
            print(f"Warning: Block {child_id} has multiple parents")

        return result.links[0].to_id

    def get_children(self, parent_id: str) -> List[str]:
        """
        Get all children of a block.

        Args:
            parent_id: ID of the parent block

        Returns:
            List of child block IDs
        """
        # For InMemoryLinkManager, access internal data structure
        if isinstance(self._link_manager, InMemoryLinkManager):
            in_memory_lm = cast(InMemoryLinkManager, self._link_manager)
            child_ids = []

            # Find all links where to_id == parent_id and relation == CHILD_OF
            for (from_id, to_id, rel), _ in in_memory_lm._links.items():
                if to_id == parent_id and rel == CoreRelationType.CHILD_OF.value:
                    child_ids.append(from_id)

            return child_ids
        else:
            # Generic implementation for other LinkManager implementations
            # Might need to use a join in SQL-based implementations
            return []

    # Epic relationship methods
    def add_to_epic(
        self,
        task_id: str,
        epic_id: str,
        created_by: Optional[str] = None,
    ) -> BlockLink:
        """
        Add a task to an epic.

        Args:
            task_id: ID of the task to add
            epic_id: ID of the epic
            created_by: ID of the agent/user creating the link

        Returns:
            The created BlockLink
        """
        return self._link_manager.create_link(
            from_id=task_id,
            to_id=epic_id,
            relation=PMRelationType.BELONGS_TO_EPIC.value,
            created_by=created_by,
        )

    def remove_from_epic(self, task_id: str, epic_id: str) -> bool:
        """
        Remove a task from an epic.

        Args:
            task_id: ID of the task to remove
            epic_id: ID of the epic

        Returns:
            True if the task was removed, False if it wasn't in the epic
        """
        return self._link_manager.delete_link(
            from_id=task_id,
            to_id=epic_id,
            relation=PMRelationType.BELONGS_TO_EPIC.value,
        )

    def get_epic(self, task_id: str) -> Optional[str]:
        """
        Get the epic that a task belongs to.

        Args:
            task_id: ID of the task

        Returns:
            ID of the epic, or None if the task doesn't belong to an epic
        """
        query = LinkQuery().relation(PMRelationType.BELONGS_TO_EPIC.value)
        result = self._link_manager.links_from(task_id, query)

        if not result.links:
            return None

        # A task should belong to at most one epic
        if len(result.links) > 1:
            # Log a warning, but return the first epic found
            # TODO: Add proper logging
            print(f"Warning: Task {task_id} belongs to multiple epics")

        return result.links[0].to_id

    def get_epic_tasks(self, epic_id: str) -> List[str]:
        """
        Get all tasks that belong to an epic.

        Args:
            epic_id: ID of the epic

        Returns:
            List of task IDs
        """
        # For InMemoryLinkManager, access internal data structure
        if isinstance(self._link_manager, InMemoryLinkManager):
            in_memory_lm = cast(InMemoryLinkManager, self._link_manager)
            task_ids = []

            # Find all links where to_id == epic_id and relation == BELONGS_TO_EPIC
            for (from_id, to_id, rel), _ in in_memory_lm._links.items():
                if to_id == epic_id and rel == PMRelationType.BELONGS_TO_EPIC.value:
                    task_ids.append(from_id)

            return task_ids
        else:
            # Generic implementation for other LinkManager implementations
            # Might need to use a join in SQL-based implementations
            return []

    # Dependency resolution methods
    def get_task_sequence(self, task_ids: List[str]) -> List[str]:
        """
        Get a topologically sorted list of tasks based on dependencies.

        Args:
            task_ids: List of task IDs to sort

        Returns:
            List of task IDs in dependency order (tasks with no dependencies first)

        Raises:
            ValueError: If a dependency cycle is detected
        """
        # Use the BLOCKS relation for dependency sorting
        return self._link_manager.topo_sort(task_ids, PMRelationType.BLOCKS.value)

    def sync_parent_reference(self, block_id: str, block_store=None) -> bool:
        """
        Synchronize the x_parent_block_id field in a block's metadata with its child_of link.

        Args:
            block_id: ID of the block to update
            block_store: Optional block store to use for the update.
                         If None, this is a no-op.

        Returns:
            True if the metadata was updated, False otherwise
        """
        if block_store is None:
            return False

        # Get parent ID and update metadata when block store is available
        # Currently a stub for future implementation
        # parent_id = self.get_parent(block_id)

        # TODO: Update the block's metadata
        # block = block_store.get_block(block_id)
        # if block and block.metadata:
        #     block.metadata.x_parent_block_id = parent_id
        #     block_store.update_block(block)
        #     return True

        return False
