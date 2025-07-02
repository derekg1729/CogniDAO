"""
LinkManager for the memory system.

This module provides centralized management of block links with validation,
referential integrity enforcement, cycle detection, and efficient querying.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any, Iterator, Union, get_args

from .schemas.common import BlockLink, RelationType
from .relation_registry import CANONICAL_DEPENDENCY_RELATION


class LinkErrorType(Enum):
    """
    Enum of error types for link operations.

    Used to categorize different failure modes with appropriate HTTP status codes.
    """

    VALIDATION_ERROR = "validation_error"
    CYCLE_DETECTED = "cycle_detected"
    CONCURRENCY_CONFLICT = "concurrency_conflict"
    ORPHAN_BLOCK = "orphan_block"

    @property
    def http_status(self) -> int:
        """Map error type to HTTP status code."""
        status_map = {
            LinkErrorType.VALIDATION_ERROR: 400,
            LinkErrorType.CYCLE_DETECTED: 409,
            LinkErrorType.CONCURRENCY_CONFLICT: 409,
            LinkErrorType.ORPHAN_BLOCK: 404,
        }
        return status_map[self]  # pragma: no cover


class LinkError(Exception):
    """
    Exception raised for link operation errors.

    Attributes:
        error_type: Type of error from LinkErrorType enum
        message: Detailed error message
    """

    def __init__(self, error_type: LinkErrorType, message: str = ""):
        self.error_type = error_type
        self.message = message or str(error_type.value)
        super().__init__(self.message)

    @property
    def http_status(self) -> int:
        """Get the HTTP status code for this error."""
        return self.error_type.http_status


class Direction(Enum):
    """
    Direction for link traversal.

    Used in queries to specify whether to follow links in the outbound direction
    (from block to its linked blocks), inbound (blocks linking to this block),
    or both directions.
    """

    OUTBOUND = "outbound"
    INBOUND = "inbound"
    BOTH = "both"

    @classmethod
    def from_string(cls, value: str) -> "Direction":
        """
        Convert string to Direction enum.

        Args:
            value: String value to convert ("outbound", "inbound", or "both")

        Returns:
            Direction enum value

        Raises:
            ValueError: If value is not a valid direction string
        """
        try:
            return cls(value.lower())
        except ValueError:
            valid_values = [d.value for d in cls]
            raise ValueError(f"Invalid direction: {value}. Must be one of {valid_values}")


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
        """Initialize the index with empty graph structures."""
        import collections

        # Outbound adjacency lists (from_id -> set of (to_id, relation) tuples)
        self._outbound = collections.defaultdict(set)

        # Inbound adjacency lists (to_id -> set of (from_id, relation) tuples)
        self._inbound = collections.defaultdict(set)

        # Track in-degree counts by relation type (relation -> {block_id -> count})
        # This is a performance optimization for ready_tasks
        self._in_degree = collections.defaultdict(lambda: collections.defaultdict(int))

    def add_link(self, from_id: str, to_id: str, relation: RelationType) -> None:
        """
        Add a link to the index.

        Args:
            from_id: Source block ID
            to_id: Target block ID
            relation: Relation type
        """
        # Get the relation as a string for consistent indexing
        relation_str = relation if isinstance(relation, str) else relation

        # Add to outbound adjacency list
        self._outbound[from_id].add((to_id, relation_str))

        # Add to inbound adjacency list
        self._inbound[to_id].add((from_id, relation_str))

        # Increment in-degree count for this relation type
        self._in_degree[relation_str][to_id] += 1

    def remove_link(self, from_id: str, to_id: str, relation: RelationType) -> None:
        """
        Remove a link from the index.

        Args:
            from_id: Source block ID
            to_id: Target block ID
            relation: Relation type
        """
        # Get the relation as a string for consistent indexing
        relation_str = relation if isinstance(relation, str) else relation

        # Remove from outbound adjacency list if exists
        if from_id in self._outbound and (to_id, relation_str) in self._outbound[from_id]:
            self._outbound[from_id].remove((to_id, relation_str))
            # Clean up empty sets
            if not self._outbound[from_id]:
                del self._outbound[from_id]

        # Remove from inbound adjacency list if exists
        if to_id in self._inbound and (from_id, relation_str) in self._inbound[to_id]:
            self._inbound[to_id].remove((from_id, relation_str))
            # Clean up empty sets
            if not self._inbound[to_id]:
                del self._inbound[to_id]

            # Decrement in-degree count
            self._in_degree[relation_str][to_id] -= 1
            # Clean up zero counts
            if self._in_degree[relation_str][to_id] == 0:
                del self._in_degree[relation_str][to_id]
            if not self._in_degree[relation_str]:
                del self._in_degree[relation_str]

    def get_ready_tasks(
        self, relation: Union[str, RelationType] = CANONICAL_DEPENDENCY_RELATION
    ) -> List[str]:
        """
        Get IDs of blocks that have zero inbound links of the specified relation.

        Args:
            relation: Relation type to check (default: CANONICAL_DEPENDENCY_RELATION)
                     Can be a string literal or a RelationType value

        Returns:
            List of block IDs with no inbound dependencies
        """
        # Get the relation as a string for consistent indexing
        relation_str = relation if isinstance(relation, str) else relation

        # All block IDs that appear in outbound links with this relation
        all_blocks = set()
        for from_id, links in self._outbound.items():
            all_blocks.add(from_id)
            for to_id, rel in links:
                if rel == relation_str:
                    all_blocks.add(to_id)

        # Return blocks with zero in-degree for this relation
        # By checking which blocks in all_blocks don't appear in the in_degree map
        return [
            block_id
            for block_id in all_blocks
            if block_id not in self._in_degree.get(relation_str, {})
        ]

    def has_path(self, start_id: str, end_id: str, relation: Union[str, RelationType]) -> bool:
        """
        Check if there is a path from start_id to end_id following links of the specified relation.

        Args:
            start_id: Starting block ID
            end_id: Target block ID
            relation: Relation type to follow

        Returns:
            True if a path exists, False otherwise
        """
        # Get the relation as a string for consistent indexing
        relation_str = relation if isinstance(relation, str) else relation

        # This method is called both for checking general paths and for cycle detection
        # For cycle detection, start_id and end_id are the same
        is_cycle_check = start_id == end_id

        # Use breadth-first search to find a path
        visited = set()
        queue = [start_id]

        while queue:
            current = queue.pop(0)

            # For cycle detection, we need to check if we've returned to the start
            # But we should skip the initial node for this check
            if current == end_id and (
                not is_cycle_check or current != start_id or len(visited) > 0
            ):
                return True

            if current in visited:
                continue

            visited.add(current)

            # Add all neighbors with matching relation type
            if current in self._outbound:
                for neighbor, rel in self._outbound[current]:
                    if rel == relation_str and neighbor not in visited:
                        queue.append(neighbor)

        return False

    def get_connected_blocks(
        self,
        block_id: str,
        relation: Union[str, RelationType],
        direction: Direction = Direction.OUTBOUND,
        depth: int = 1,
    ) -> Set[str]:
        """
        Get all blocks connected to the given block within specified depth.

        Args:
            block_id: Starting block ID
            relation: Relation type to follow
            direction: Direction to traverse (OUTBOUND, INBOUND, or BOTH)
            depth: Maximum traversal depth

        Returns:
            Set of connected block IDs (excluding the starting block)
        """
        # Get the relation as a string for consistent indexing
        relation_str = relation if isinstance(relation, str) else relation

        # Keep track of visited blocks and their depth
        visited = {block_id: 0}
        result = set()

        # Use BFS to explore the graph within depth limit
        queue = [(block_id, 0)]  # (node, depth)

        while queue:
            current, current_depth = queue.pop(0)

            # Skip if we've reached max depth
            if current_depth >= depth:
                continue

            # Process outbound links
            if direction in (Direction.OUTBOUND, Direction.BOTH) and current in self._outbound:
                for neighbor, rel in self._outbound[current]:
                    if rel == relation_str and (
                        neighbor not in visited or visited[neighbor] > current_depth + 1
                    ):
                        visited[neighbor] = current_depth + 1
                        result.add(neighbor)
                        if current_depth + 1 < depth:
                            queue.append((neighbor, current_depth + 1))

            # Process inbound links
            if direction in (Direction.INBOUND, Direction.BOTH) and current in self._inbound:
                for neighbor, rel in self._inbound[current]:
                    if rel == relation_str and (
                        neighbor not in visited or visited[neighbor] > current_depth + 1
                    ):
                        visited[neighbor] = current_depth + 1
                        result.add(neighbor)
                        if current_depth + 1 < depth:
                            queue.append((neighbor, current_depth + 1))

        return result


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
        """
        Set starting cursor for pagination.

        Args:
            cursor: Pagination cursor, which can be:
                   - A simple offset integer (e.g., "100")
                   - An opaque token from a previous query's next_cursor

        Raises:
            ValueError: If cursor is not a valid format
        """
        # Validate the cursor format
        if cursor:
            # For the simple implementation, we expect an integer offset
            try:
                offset = int(cursor)
                if offset < 0:
                    raise ValueError("Cursor offset must be non-negative")
            except ValueError:
                # If it's not a simple integer, check if it's a valid opaque token
                # For now, we'll just consider any string valid and let the
                # implementation handle it
                pass

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
        """
        # Start with the base query
        sql = "SELECT * FROM block_links WHERE "
        params = []

        # Get direction from filters or default to "outbound"
        direction = self._filters.get("direction", Direction.OUTBOUND.value)

        # Add the basic direction condition
        if direction == Direction.OUTBOUND.value:
            sql += "from_id = ?"
            params.append(block_id)
        elif direction == Direction.INBOUND.value:
            sql += "to_id = ?"
            params.append(block_id)
        else:  # BOTH
            sql += "(from_id = ? OR to_id = ?)"
            params.extend([block_id, block_id])

        # Add relation filter if specified
        if "relation" in self._filters:
            sql += " AND relation = ?"
            params.append(self._filters["relation"])

        # Add limit
        sql += f" LIMIT {self._limit}"

        # Add cursor if specified (simple offset-based pagination)
        if self._cursor:
            try:
                offset = int(self._cursor)
                sql += f" OFFSET {offset}"
            except ValueError:
                # Invalid cursor, just ignore it
                pass

        # For SQL with ? parameters, return both the SQL and the params
        # This is commented out for now, but would be useful in a real implementation
        # sql_with_params = {
        #     "sql": sql,
        #     "params": params
        # }

        # For this example, we'll return a formatted SQL string with params inserted
        # In a real implementation, you'd return the parameterized query
        formatted_sql = sql
        for param in params:
            formatted_sql = formatted_sql.replace("?", f"'{param}'", 1)

        return formatted_sql


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
            Topologically sorted list of block IDs in dependency order
            (e.g., for is_blocked_by, if A is_blocked_by B, then B comes before A)

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

    @abstractmethod
    def get_all_links(self, query: Optional[LinkQuery] = None) -> LinkQueryResult:
        """
        Get all links in the system.

        Args:
            query: Optional query parameters for filtering

        Returns:
            LinkQueryResult containing all matching links

        Raises:
            RuntimeError: If operation fails due to database error
        """
        pass


class InMemoryLinkManager(LinkManager):
    """
    In-memory implementation of LinkManager for testing and prototyping.

    Uses a LinkIndex for fast graph operations and keeps all links in memory.
    Not suitable for production use with large numbers of links.
    """

    def __init__(self):
        """Initialize the manager with empty storage."""
        from datetime import datetime
        import uuid

        # The index for fast graph operations
        self._index = LinkIndex()

        # Storage for link metadata keyed by (from_id, to_id, relation)
        self._links = {}

        # For UUID validation
        self._uuid_module = uuid

        # For timestamp creation
        self._datetime = datetime

    def _validate_uuid(self, *ids: str) -> None:
        """Validate that all provided IDs are valid UUIDs."""
        for id_str in ids:
            try:
                self._uuid_module.UUID(id_str)
            except ValueError:
                raise ValueError(f"Invalid UUID format: {id_str}")

    def _validate_relation(self, relation: Union[str, RelationType]) -> str:
        """Validate the relation type and return it as a string."""
        # Get valid relation types
        valid_relations = get_args(RelationType)

        # Check if it's a valid relation
        relation_str = relation if isinstance(relation, str) else relation
        if relation_str not in valid_relations:
            raise ValueError(
                f"Invalid relation type: {relation_str}. Must be one of {valid_relations}"
            )

        return relation_str

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
            LinkError: For specific error conditions
        """
        # Validate IDs
        self._validate_uuid(from_id, to_id)

        # Validate relation
        relation_str = self._validate_relation(relation)

        # Validate priority
        if priority < 0:
            raise ValueError("Priority must be non-negative")

        # Detect self-links (direct cycles)
        if from_id == to_id:
            raise LinkError(
                LinkErrorType.CYCLE_DETECTED, f"Self-referential link not allowed: {from_id}"
            )

        # Check for existing link
        link_key = (from_id, to_id, relation_str)
        if link_key in self._links:
            raise LinkError(
                LinkErrorType.VALIDATION_ERROR,
                f"Link already exists: {from_id} -> {to_id} ({relation_str})",
            )

        # Check for cycles before adding
        # Temporarily add the link to the index
        self._index.add_link(from_id, to_id, relation_str)

        # Check for cycles - if found, remove the link and raise error
        if self.has_cycle(to_id, relation_str):
            self._index.remove_link(from_id, to_id, relation_str)
            raise LinkError(
                LinkErrorType.CYCLE_DETECTED,
                f"Creating link would introduce a cycle: {from_id} -> {to_id} ({relation_str})",
            )

        # No cycle detected, create the link
        now = self._datetime.now()
        link = BlockLink(
            from_id=from_id,
            to_id=to_id,
            relation=relation_str,
            priority=priority,
            link_metadata=link_metadata,
            created_by=created_by,
            created_at=now,
        )

        # Store the link
        self._links[link_key] = link

        return link

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
        """
        # Validate IDs
        self._validate_uuid(from_id, to_id)

        # Validate relation
        relation_str = self._validate_relation(relation)

        # Check if link exists
        link_key = (from_id, to_id, relation_str)
        if link_key not in self._links:
            return False

        # Remove from index
        self._index.remove_link(from_id, to_id, relation_str)

        # Remove from storage
        del self._links[link_key]

        return True

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
        # Validate ID
        self._validate_uuid(block_id)

        # Default query if none provided
        if query is None:
            query = LinkQuery()

        query_dict = query.to_dict()
        relation = query_dict.get("relation")
        depth = query_dict.get("depth", 1)
        direction = Direction.from_string(query_dict.get("direction", "outbound"))
        limit = query_dict.get("limit", 100)
        # Cursor is currently not used in this implementation
        # cursor = query_dict.get("cursor")

        results = []

        # For depth=1, just get direct links
        if depth == 1:
            # Find all outbound links from this block
            for link_key, link in self._links.items():
                from_id, to_id, rel = link_key
                if from_id == block_id and (relation is None or rel == relation):
                    results.append(link)
        else:
            # For depth > 1, use the index to find connected blocks
            connected = self._index.get_connected_blocks(
                block_id=block_id,
                relation=relation if relation else "*",  # '*' means any relation
                direction=direction,
                depth=depth,
            )

            # Collect all links between the connected blocks
            for link_key, link in self._links.items():
                from_id, to_id, rel = link_key
                if (from_id == block_id or from_id in connected) and (
                    to_id == block_id or to_id in connected
                ):
                    if relation is None or rel == relation:
                        results.append(link)

        # Apply limit
        if len(results) > limit:
            # TODO: Implement proper pagination with cursor
            results = results[:limit]
            next_cursor = str(limit)  # Simple cursor implementation
        else:
            next_cursor = None

        return LinkQueryResult(links=results, next_cursor=next_cursor)

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
        # Validate ID
        self._validate_uuid(block_id)

        # Default query if none provided
        if query is None:
            query = LinkQuery()

        query_dict = query.to_dict()
        relation = query_dict.get("relation")
        depth = query_dict.get("depth", 1)
        direction = Direction.from_string(query_dict.get("direction", "inbound"))
        limit = query_dict.get("limit", 100)
        # Cursor is currently not used in this implementation
        # cursor = query_dict.get("cursor")

        results = []

        # For depth=1, just get direct links
        if depth == 1:
            # Find all inbound links to this block
            for link_key, link in self._links.items():
                from_id, to_id, rel = link_key
                if to_id == block_id and (relation is None or rel == relation):
                    results.append(link)
        else:
            # For depth > 1, use the index to find connected blocks
            connected = self._index.get_connected_blocks(
                block_id=block_id,
                relation=relation if relation else "*",  # '*' means any relation
                direction=direction,
                depth=depth,
            )

            # Collect all links between the connected blocks
            for link_key, link in self._links.items():
                from_id, to_id, rel = link_key
                if (from_id == block_id or from_id in connected) and (
                    to_id == block_id or to_id in connected
                ):
                    if relation is None or rel == relation:
                        results.append(link)

        # Apply limit
        if len(results) > limit:
            # TODO: Implement proper pagination with cursor
            results = results[:limit]
            next_cursor = str(limit)  # Simple cursor implementation
        else:
            next_cursor = None

        return LinkQueryResult(links=results, next_cursor=next_cursor)

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
        # Validate ID
        self._validate_uuid(start_id)

        # Validate relation
        relation_str = self._validate_relation(relation)

        # Use DFS for cycle detection
        if visited is None:
            visited = set()

        # If we've seen this node already, we have a cycle
        if start_id in visited:
            return True

        # Mark as visited
        visited.add(start_id)

        # Check all outbound links from this node
        if start_id in self._index._outbound:
            for to_id, rel in self._index._outbound[start_id]:
                if rel == relation_str:
                    # Recurse to check neighbors
                    if self.has_cycle(to_id, relation_str, visited.copy()):
                        return True

        return False

    def topo_sort(self, block_ids: List[str], relation: RelationType) -> List[str]:
        """
        Perform topological sort on a subset of blocks.

        Args:
            block_ids: List of block IDs to sort
            relation: Relation type to use for sorting

        Returns:
            Topologically sorted list of block IDs in dependency order
            (e.g., for is_blocked_by, if A is_blocked_by B, then B comes before A)

        Raises:
            ValueError: If a cycle is detected
        """
        # Validate IDs
        for block_id in block_ids:
            self._validate_uuid(block_id)

        # Validate relation
        relation_str = self._validate_relation(relation)

        # First check for cycles using our has_cycle method
        # Create a temporary set of node IDs to check
        nodes_in_subset = set(block_ids)
        for block_id in block_ids:
            # Use a temporary visited set for each starting node
            visited = set()
            if self._check_cycle_in_subset(block_id, relation_str, nodes_in_subset, visited):
                raise ValueError("Cycle detected in graph, cannot perform topological sort")

        # Build a subgraph with only the specified blocks
        import collections

        graph = collections.defaultdict(set)
        in_degree = collections.defaultdict(int)

        # For "is_blocked_by" semantics:
        # If A is_blocked_by B, then A depends on B (B must come before A)
        # So we add an edge from B -> A in our dependency graph
        for (from_id, to_id, rel), _ in self._links.items():
            if rel != relation_str:
                continue

            if from_id in block_ids and to_id in block_ids:
                # Reverse the edge for dependency graph:
                # If from_id is_blocked_by to_id, then to_id should come before from_id
                # So in the graph, we add to_id -> from_id (target -> source)
                graph[to_id].add(from_id)
                in_degree[from_id] += 1

        # Make sure all nodes are in the graph
        for block_id in block_ids:
            if block_id not in graph:
                graph[block_id] = set()

        # Kahn's algorithm for topological sort
        result = []
        queue = [node for node in block_ids if in_degree.get(node, 0) == 0]

        # Process the queue
        while queue:
            current = queue.pop(0)
            result.append(current)

            # Reduce in-degree of neighbors
            for neighbor in graph.get(current, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # If we couldn't process all nodes, there must be a cycle
        if len(result) != len(block_ids):
            raise ValueError("Cycle detected in graph, cannot perform topological sort")

        return result

    def _check_cycle_in_subset(
        self, node: str, relation: str, nodes_in_subset: Set[str], visited: Set[str]
    ) -> bool:
        """
        Helper method to check for cycles in a subset of nodes.

        Args:
            node: Current node to check
            relation: Relation type to follow
            nodes_in_subset: Set of nodes to consider
            visited: Set of already visited nodes in this traversal

        Returns:
            True if a cycle is detected, False otherwise
        """
        if node in visited:
            return True

        visited.add(node)

        # Check all outbound edges from this node that are in our subset
        for (from_id, to_id, rel), _ in self._links.items():
            if from_id == node and rel == relation and to_id in nodes_in_subset:
                if self._check_cycle_in_subset(to_id, relation, nodes_in_subset, visited.copy()):
                    return True

        return False

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
        # Validate all links first
        for from_id, to_id, relation, _ in links:
            self._validate_uuid(from_id, to_id)
            self._validate_relation(relation)

        # Check for cycles
        # First add all links to a temporary index
        temp_index = LinkIndex()
        for from_id, to_id, relation, _ in links:
            relation_str = relation if isinstance(relation, str) else relation
            temp_index.add_link(from_id, to_id, relation_str)

        # Check for cycles in each relation type
        for relation_type in set(rel for _, _, rel, _ in links):
            relation_str = relation_type if isinstance(relation_type, str) else relation_type
            for from_id, _, _, _ in links:
                if temp_index.has_path(from_id, from_id, relation_str):
                    raise LinkError(
                        LinkErrorType.CYCLE_DETECTED,
                        f"Creating links would introduce a cycle with relation: {relation_str}",
                    )

        # No cycles, proceed with the upsert
        results = []
        for from_id, to_id, relation, metadata in links:
            try:
                link = self.create_link(
                    from_id=from_id, to_id=to_id, relation=relation, link_metadata=metadata
                )
                results.append(link)
            except LinkError as e:
                if e.error_type == LinkErrorType.VALIDATION_ERROR:
                    # Link already exists, update it
                    link_key = (from_id, to_id, relation if isinstance(relation, str) else relation)
                    link = self._links[link_key]
                    if metadata is not None:
                        link.link_metadata = metadata
                    results.append(link)
                else:
                    # Propagate other errors
                    raise

        return results

    def delete_links_for_block(self, block_id: str) -> int:
        """
        Delete all links involving a block (as source or target).

        Args:
            block_id: ID of the block being deleted

        Returns:
            Number of links deleted
        """
        # Validate ID
        self._validate_uuid(block_id)

        # Find all links involving this block
        links_to_delete = []
        for link_key in self._links.keys():
            from_id, to_id, _ = link_key
            if from_id == block_id or to_id == block_id:
                links_to_delete.append(link_key)

        # Delete the links
        for link_key in links_to_delete:
            from_id, to_id, relation = link_key
            self._index.remove_link(from_id, to_id, relation)
            del self._links[link_key]

        return len(links_to_delete)

    def get_all_links(self, query: Optional[LinkQuery] = None) -> LinkQueryResult:
        """
        Get all links in the system.

        Args:
            query: Optional query parameters for filtering

        Returns:
            LinkQueryResult containing all matching links
        """
        # Default query if none provided
        if query is None:
            query = LinkQuery()

        query_dict = query.to_dict()
        relation = query_dict.get("relation")
        limit = query_dict.get("limit", 100)
        # cursor = query_dict.get("cursor")  # TODO: Implement pagination

        results = []

        # Get all links and apply filtering
        for link_key, link in self._links.items():
            from_id, to_id, rel = link_key
            # Apply relation filter if specified
            if relation is None or rel == relation:
                results.append(link)

        # Apply limit
        if len(results) > limit:
            # TODO: Implement proper pagination with cursor
            results = results[:limit]
            next_cursor = str(limit)  # Simple cursor implementation
        else:
            next_cursor = None

        return LinkQueryResult(links=results, next_cursor=next_cursor)
