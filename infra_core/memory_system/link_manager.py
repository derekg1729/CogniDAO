"""
LinkManager for the memory system.

This module provides centralized management of block links with validation,
referential integrity enforcement, cycle detection, and efficient querying.
"""

from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple, Any, Iterator, Union, get_args

from .schemas.common import BlockLink, RelationType


class LinkError(Enum):
    """Error types that can be raised during link operations."""

    VALIDATION_ERROR = auto()  # Covers invalid parameters, missing blocks, etc.
    CYCLE_DETECTED = auto()
    CONCURRENCY_CONFLICT = auto()
    ORPHAN_BLOCK = auto()  # For operations that would create orphaned blocks/links

    @property
    def code(self) -> str:
        """Return a string code for API responses."""
        return f"LINK_{self.name}"

    @property
    def http_status(self) -> int:
        """Return appropriate HTTP status code for this error."""
        status_map = {
            LinkError.VALIDATION_ERROR: 400,  # Bad Request
            LinkError.CYCLE_DETECTED: 400,  # Bad Request
            LinkError.CONCURRENCY_CONFLICT: 409,  # Conflict
            LinkError.ORPHAN_BLOCK: 400,  # Bad Request
        }
        # All possible enum values are covered above
        return status_map[self]  # pragma: no cover


class Direction(Enum):
    """Direction for link traversal operations."""

    OUTBOUND = "outbound"
    INBOUND = "inbound"
    BOTH = "both"

    @classmethod
    def from_string(cls, value: str) -> "Direction":
        """Convert string to Direction enum value."""
        try:
            return cls(value.lower())
        except ValueError:
            valid_values = [d.value for d in cls]
            raise ValueError(f"Direction must be one of {valid_values}")


class LinkQueryResult:
    """Result of a link query operation."""

    def __init__(self, links: List[BlockLink], next_cursor: Optional[str] = None):
        self.links = links
        self.next_cursor = next_cursor

    def __len__(self) -> int:
        return len(self.links)

    def __iter__(self) -> Iterator[BlockLink]:
        return iter(self.links)


class LinkIndex:
    """
    In-memory index for link operations with incremental in_degree tracking.

    Optimizes graph traversal and ready_tasks queries for performance.
    """

    def __init__(self):
        # Implementation details will be added in a future PR
        pass

    def add_link(self, from_id: str, to_id: str, relation: RelationType) -> None:
        """
        Add a link to the index.

        Args:
            from_id: Source block ID
            to_id: Target block ID
            relation: Relation type
        """
        # TODO(core-v0.1.0): Implement index tracking (TASK-LINKS-123)
        raise NotImplementedError("LinkIndex.add_link not yet implemented")

    def remove_link(self, from_id: str, to_id: str, relation: RelationType) -> None:
        """
        Remove a link from the index.

        Args:
            from_id: Source block ID
            to_id: Target block ID
            relation: Relation type
        """
        # TODO(core-v0.1.0): Implement index tracking (TASK-LINKS-123)
        raise NotImplementedError("LinkIndex.remove_link not yet implemented")

    def get_ready_tasks(self, relation: Union[str, RelationType] = "is_blocked_by") -> List[str]:
        """
        Get IDs of blocks that have zero inbound links of the specified relation.

        Args:
            relation: Relation type to check (default: "is_blocked_by")
                     Can be a string literal or a RelationType value

        Returns:
            List of block IDs with no inbound dependencies
        """
        # TODO(core-v0.1.0): Implement efficient ready tasks query (TASK-LINKS-123)
        raise NotImplementedError("LinkIndex.get_ready_tasks not yet implemented")


class LinkQuery:
    """
    Fluent builder for link queries.

    Allows flexible querying with relation, depth, and direction filters.
    """

    def __init__(self):
        self._filters = {}
        self._limit = 100
        self._cursor = None

    def relation(self, relation_type: Union[str, RelationType]) -> "LinkQuery":
        """
        Filter links by relation type.

        Args:
            relation_type: A relation type string or RelationType value

        Raises:
            ValueError: If relation_type is not a valid relation type
        """

        # Get the list of valid relation string literals
        valid_relation_strings = get_args(RelationType)

        # Convert string to validated value
        if isinstance(relation_type, str):
            if relation_type not in valid_relation_strings:
                raise ValueError(
                    f"Invalid relation type: {relation_type}. Must be one of {valid_relation_strings}"
                )
            # Store the validated string literal
            self._filters["relation"] = relation_type
        else:
            # It should already be a valid RelationType literal
            if relation_type not in valid_relation_strings:
                raise ValueError(
                    f"Invalid relation type: {relation_type}. Must be one of {valid_relation_strings}"
                )
            # Store the string value for consistency in serialization
            self._filters["relation"] = relation_type

        return self

    def depth(self, depth: int) -> "LinkQuery":
        """
        Limit traversal depth for recursive queries.

        Args:
            depth: Maximum traversal depth (1 = direct links only)
        """
        if depth <= 0:
            raise ValueError("Depth must be a positive integer")
        self._filters["depth"] = depth
        return self

    def direction(self, direction: Direction) -> "LinkQuery":
        """
        Set traversal direction.

        Args:
            direction: Direction enum value (Direction.OUTBOUND, Direction.INBOUND, or Direction.BOTH)
                      Do not use string values directly - use the Direction enum.

        Raises:
            ValueError: If direction is not a valid Direction enum value

        Examples:
            # Correct usage:
            query.direction(Direction.OUTBOUND)

            # Not supported:
            query.direction("outbound")  # Use Direction.OUTBOUND instead
        """
        if not isinstance(direction, Direction):
            raise ValueError(
                f"direction must be a Direction enum value (Direction.OUTBOUND, Direction.INBOUND, or Direction.BOTH), got {type(direction)}"
            )
        self._filters["direction"] = direction.value  # Store the string value for serialization
        return self

    def limit(self, limit: int) -> "LinkQuery":
        """Set maximum number of results to return."""
        if limit <= 0:
            raise ValueError("Limit must be a positive integer")
        self._limit = limit
        return self

    def cursor(self, cursor: str) -> "LinkQuery":
        """Set starting cursor for pagination."""
        # TODO(core-v0.1.0): Implement cursor validation (TASK-LINKS-124)
        self._cursor = cursor
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Convert query to dictionary representation."""
        result = self._filters.copy()
        result["limit"] = self._limit
        if self._cursor:
            result["cursor"] = self._cursor
        return result

    def __str__(self) -> str:
        """String representation of the query for debugging."""
        parts = []
        for k, v in self._filters.items():
            parts.append(f"{k}={v}")
        if self._limit != 100:
            parts.append(f"limit={self._limit}")
        if self._cursor:
            parts.append(f"cursor={self._cursor}")
        return f"LinkQuery({', '.join(parts)})"

    def to_sql(self, block_id: str) -> str:
        """
        Convert the query to SQL.

        Args:
            block_id: ID of the block to query from/to

        Returns:
            SQL string for execution

        Not yet implemented - will be added in future PR.
        """
        # TODO(core-v0.1.0): Implement SQL generation (TASK-LINKS-125)
        raise NotImplementedError("SQL generation not yet implemented")


class LinkManager(ABC):
    """
    Abstract base class for link management operations.

    Provides a standard interface for creating, deleting, and querying links
    between memory blocks, with validation and cycle detection.
    """

    @abstractmethod
    def create_link(
        self,
        from_id: str,
        to_id: str,
        relation: RelationType,
        priority: int = 0,
        link_metadata: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None,
    ) -> BlockLink:
        """
        Create a new link between two blocks.

        Args:
            from_id: Source block ID
            to_id: Target block ID
            relation: Type of relationship
            priority: Priority value (higher = more important)
            link_metadata: Additional metadata about the link
            created_by: ID of the agent/user creating the link

        Returns:
            The created BlockLink

        Raises:
            ValueError: If validation fails
            RuntimeError: If operation fails due to database error
            LinkError: For specific error conditions:
                - VALIDATION_ERROR: Invalid parameters or block doesn't exist
                - CYCLE_DETECTED: Creating this link would introduce a cycle
                - CONCURRENCY_CONFLICT: Conflict with parallel operation
        """
        pass

    @abstractmethod
    def delete_link(self, from_id: str, to_id: str, relation: RelationType) -> bool:
        """
        Delete a link between two blocks.

        Args:
            from_id: Source block ID
            to_id: Target block ID
            relation: Type of relationship

        Returns:
            True if link was deleted, False if link didn't exist

        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If operation fails due to database error
        """
        pass

    @abstractmethod
    def links_from(self, block_id: str, query: Optional[LinkQuery] = None) -> LinkQueryResult:
        """
        Get links originating from a block.

        Args:
            block_id: ID of the source block
            query: Optional query parameters

        Returns:
            LinkQueryResult containing matching links

        Raises:
            ValueError: If block_id is invalid
        """
        pass

    @abstractmethod
    def links_to(self, block_id: str, query: Optional[LinkQuery] = None) -> LinkQueryResult:
        """
        Get links pointing to a block.

        Args:
            block_id: ID of the target block
            query: Optional query parameters

        Returns:
            LinkQueryResult containing matching links

        Raises:
            ValueError: If block_id is invalid
        """
        pass

    @abstractmethod
    def has_cycle(
        self, start_id: str, relation: RelationType, visited: Optional[Set[str]] = None
    ) -> bool:
        """
        Check if adding a link would create a cycle in the graph.

        Args:
            start_id: Starting block ID for cycle detection
            relation: Relation type to check for cycles
            visited: Set of already visited nodes (for recursive calls)

        Returns:
            True if a cycle is detected, False otherwise
        """
        pass

    @abstractmethod
    def topo_sort(self, block_ids: List[str], relation: RelationType) -> List[str]:
        """
        Perform topological sort on a subset of blocks.

        Args:
            block_ids: List of block IDs to sort
            relation: Relation type to use for sorting

        Returns:
            Topologically sorted list of block IDs

        Raises:
            ValueError: If a cycle is detected
        """
        pass

    @abstractmethod
    def bulk_upsert(
        self, links: List[Tuple[str, str, RelationType, Optional[Dict[str, Any]]]]
    ) -> List[BlockLink]:
        """
        Create or update multiple links in a single operation.

        Args:
            links: List of (from_id, to_id, relation, metadata) tuples

        Returns:
            List of created/updated BlockLinks

        Raises:
            ValueError: If validation fails for any link
            RuntimeError: If operation fails due to database error
        """
        pass

    @abstractmethod
    def delete_links_for_block(self, block_id: str) -> int:
        """
        Delete all links involving a block (as source or target).

        Used to maintain referential integrity when deleting blocks.

        Args:
            block_id: ID of the block being deleted

        Returns:
            Number of links deleted

        Raises:
            RuntimeError: If operation fails due to database error
        """
        pass
