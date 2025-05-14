"""
LinkManager for the memory system.

This module provides centralized management of block links with validation,
referential integrity enforcement, cycle detection, and efficient querying.
"""

from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple, Any, Iterator

from .schemas.common import BlockLink, RelationType


class LinkError(Enum):
    """Error types that can be raised during link operations."""

    VALIDATION_ERROR = auto()
    CYCLE_DETECTED = auto()
    CONCURRENCY_CONFLICT = auto()
    ORPHAN_BLOCK = auto()

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
        return status_map.get(self, 500)  # Default to 500 Internal Server Error


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


class LinkQuery:
    """
    Fluent builder for link queries.

    Allows flexible querying with relation, depth, and direction filters.
    """

    def __init__(self):
        self._filters = {}
        self._limit = 100
        self._cursor = None

    def relation(self, relation_type: RelationType) -> "LinkQuery":
        """Filter links by relation type."""
        # Implementation should check if relation_type is valid
        return self

    def depth(self, depth: int) -> "LinkQuery":
        """
        Limit traversal depth for recursive queries.

        Args:
            depth: Maximum traversal depth (1 = direct links only)
        """
        # Removed validation to make tests fail
        return self

    def direction(self, direction: str) -> "LinkQuery":
        """
        Set traversal direction.

        Args:
            direction: One of 'outbound', 'inbound', or 'both'
        """
        # Removed validation to make tests fail
        return self

    def limit(self, limit: int) -> "LinkQuery":
        """Set maximum number of results to return."""
        # Removed validation to make tests fail
        return self

    def cursor(self, cursor: str) -> "LinkQuery":
        """Set starting cursor for pagination."""
        # Stub implementation
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
