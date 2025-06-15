"""
SQL-based LinkManager implementation for production use with Dolt.

This module provides a SQL-backed LinkManager that persists links to the block_links table
and includes hooks for maintaining parent/child hierarchy columns when 'contains' relations change.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Any, Union, get_args
import json

from .link_manager import LinkManager, LinkError, LinkErrorType, LinkQuery, LinkQueryResult
from .schemas.common import BlockLink, RelationType
from .dolt_mysql_base import DoltMySQLBase, DoltConnectionConfig

# Setup logging
logger = logging.getLogger(__name__)


class SQLLinkManager(LinkManager, DoltMySQLBase):
    """
    SQL-backed implementation of LinkManager using Dolt database via MySQL connector.

    Provides production-ready link management with persistent storage and hooks
    for maintaining parent/child hierarchy columns.
    """

    def __init__(self, config: DoltConnectionConfig):
        """
        Initialize the SQL LinkManager.

        Args:
            config: DoltConnectionConfig for MySQL connection
        """
        # Initialize both parent classes
        LinkManager.__init__(self)
        DoltMySQLBase.__init__(self, config)

        # For validation
        self._uuid_module = uuid
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

    def _parse_datetime(self, dt_value: Any) -> Optional[datetime]:
        """Parse datetime value that could be string, datetime, or None."""
        if dt_value is None:
            return None
        elif isinstance(dt_value, datetime):
            return dt_value
        elif isinstance(dt_value, str):
            return datetime.fromisoformat(dt_value)
        else:
            logger.warning(f"Unexpected datetime type: {type(dt_value)}, value: {dt_value}")
            return None

    def _parse_json_metadata(self, metadata_value: Any) -> Optional[Dict[str, Any]]:
        """Parse JSON metadata value that could be string, dict, or None."""
        if metadata_value is None:
            return None
        elif isinstance(metadata_value, dict):
            return metadata_value
        elif isinstance(metadata_value, str):
            try:
                return json.loads(metadata_value)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse JSON metadata: {metadata_value}, error: {e}")
                return None
        else:
            logger.warning(
                f"Unexpected metadata type: {type(metadata_value)}, value: {metadata_value}"
            )
            return None

    def _sync_parent_child_columns(
        self, from_id: str, to_id: str, relation: str, operation: str
    ) -> None:
        """
        Hook to sync parent_id and has_children columns when 'contains' relations change.

        Args:
            from_id: Source block ID (parent when relation='contains')
            to_id: Target block ID (child when relation='contains')
            relation: The relation type
            operation: 'create' or 'delete'
        """
        if relation != "contains":
            return  # Only process 'contains' relations

        try:
            if operation == "create":
                # Set parent_id on child and has_children=TRUE on parent
                self._set_parent_relationship(child_id=to_id, parent_id=from_id)
            elif operation == "delete":
                # Clear parent_id on child and potentially set has_children=FALSE on parent
                self._clear_parent_relationship(child_id=to_id, parent_id=from_id)

        except Exception as e:
            logger.error(
                f"Failed to sync parent/child columns for {operation} {from_id}->{to_id}: {e}"
            )
            # Don't fail the link operation for sync errors, just log them

    def _set_parent_relationship(self, child_id: str, parent_id: str) -> None:
        """Set parent_id on child block and has_children=TRUE on parent block."""
        # Update child's parent_id
        child_update_query = """
        UPDATE memory_blocks 
        SET parent_id = %s
        WHERE id = %s
        """
        self._execute_update(child_update_query, (parent_id, child_id))

        # Update parent's has_children flag
        parent_update_query = """
        UPDATE memory_blocks 
        SET has_children = %s
        WHERE id = %s
        """
        self._execute_update(parent_update_query, (1, parent_id))

        logger.info(f"Set parent relationship: {child_id} -> {parent_id}")

    def _clear_parent_relationship(self, child_id: str, parent_id: str) -> None:
        """Clear parent_id on child block and update has_children on parent if no other children."""
        # Clear child's parent_id
        child_update_query = """
        UPDATE memory_blocks 
        SET parent_id = NULL
        WHERE id = %s
        """
        self._execute_update(child_update_query, (child_id,))

        # Check if parent has any other children via 'contains' links
        check_children_query = """
        SELECT COUNT(*) as child_count 
        FROM block_links 
        WHERE from_id = %s AND relation = %s
        """
        result = self._execute_query(check_children_query, (parent_id, "contains"))

        child_count = 0
        if result and len(result) > 0:
            child_count = result[0]["child_count"]

        # Update parent's has_children flag based on remaining children
        parent_update_query = """
        UPDATE memory_blocks 
        SET has_children = %s
        WHERE id = %s
        """
        self._execute_update(parent_update_query, (1 if child_count > 0 else 0, parent_id))

        logger.info(
            f"Cleared parent relationship: {child_id} -> {parent_id} (parent has {child_count} remaining children)"
        )

    def upsert_link(
        self,
        from_id: str,
        to_id: str,
        relation: RelationType,
        priority: int = 0,
        link_metadata: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None,
    ) -> BlockLink:
        """
        Create or update a single link with parent/child synchronization.

        This is the main method with hooks for 'contains' relation processing.

        Args:
            from_id: Source block ID
            to_id: Target block ID
            relation: Type of relationship
            priority: Priority value (higher = more important)
            link_metadata: Additional metadata about the link
            created_by: ID of the agent/user creating the link

        Returns:
            The created/updated BlockLink

        Raises:
            ValueError: If validation fails
            LinkError: For specific error conditions
        """
        # Branch protection: prevent link writes to main branch
        self._check_main_branch_protection("upsert_link")

        # Validate inputs
        self._validate_uuid(from_id, to_id)
        relation_str = self._validate_relation(relation)

        if priority < 0:
            raise ValueError("Priority must be non-negative")

        if from_id == to_id:
            raise LinkError(
                LinkErrorType.CYCLE_DETECTED, f"Self-referential link not allowed: {from_id}"
            )

        # Check if link already exists
        check_query = """
        SELECT COUNT(*) as link_count
        FROM block_links 
        WHERE from_id = %s 
        AND to_id = %s 
        AND relation = %s
        """
        result = self._execute_query(check_query, (from_id, to_id, relation_str))

        link_exists = False
        if result and len(result) > 0:
            link_exists = result[0]["link_count"] > 0

        # Prepare timestamp and metadata
        now = self._datetime.now()
        timestamp_str = now.isoformat(sep=" ", timespec="seconds")

        # Properly handle JSON metadata
        if link_metadata is None:
            metadata_json = None  # Pass None for NULL in parameterized query
        else:
            metadata_json = json.dumps(link_metadata)

        created_by_value = None if created_by is None else created_by

        if link_exists:
            # Update existing link
            update_query = """
            UPDATE block_links SET
                priority = %s,
                link_metadata = %s,
                created_by = %s
            WHERE from_id = %s 
            AND to_id = %s 
            AND relation = %s
            """
            self._execute_update(
                update_query,
                (priority, metadata_json, created_by_value, from_id, to_id, relation_str),
            )
            operation = "update"
        else:
            # Insert new link
            insert_query = """
            INSERT INTO block_links (from_id, to_id, relation, priority, link_metadata, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            self._execute_update(
                insert_query,
                (
                    from_id,
                    to_id,
                    relation_str,
                    priority,
                    metadata_json,
                    created_by_value,
                    timestamp_str,
                ),
            )
            operation = "create"

        # Call hook for parent/child synchronization
        self._sync_parent_child_columns(from_id, to_id, relation_str, operation)

        # Return the BlockLink object
        return BlockLink(
            from_id=from_id,
            to_id=to_id,
            relation=relation_str,
            priority=priority,
            link_metadata=link_metadata,
            created_by=created_by,
            created_at=now,
        )

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

        This method delegates to upsert_link which includes the parent/child hooks.
        """
        return self.upsert_link(from_id, to_id, relation, priority, link_metadata, created_by)

    def delete_link(self, from_id: str, to_id: str, relation: RelationType) -> bool:
        """
        Delete a link between two blocks.

        Args:
            from_id: Source block ID
            to_id: Target block ID
            relation: Type of relationship

        Returns:
            True if link was deleted, False if link didn't exist
        """
        # Branch protection: prevent link deletions on main branch
        self._check_main_branch_protection("delete_link")

        # Validate inputs
        self._validate_uuid(from_id, to_id)
        relation_str = self._validate_relation(relation)

        # Check if link exists
        check_query = """
        SELECT COUNT(*) as link_count
        FROM block_links 
        WHERE from_id = %s 
        AND to_id = %s 
        AND relation = %s
        """
        result = self._execute_query(check_query, (from_id, to_id, relation_str))

        link_exists = False
        if result and len(result) > 0:
            link_exists = result[0]["link_count"] > 0

        if not link_exists:
            return False

        # Delete the link
        delete_query = """
        DELETE FROM block_links 
        WHERE from_id = %s 
        AND to_id = %s 
        AND relation = %s
        """
        self._execute_update(delete_query, (from_id, to_id, relation_str))

        # Call hook for parent/child synchronization
        self._sync_parent_child_columns(from_id, to_id, relation_str, "delete")

        return True

    def links_from(self, block_id: str, query: Optional[LinkQuery] = None) -> LinkQueryResult:
        """
        Get links originating from a block.

        Args:
            block_id: ID of the source block
            query: Optional query parameters

        Returns:
            LinkQueryResult containing matching links
        """
        # Validate ID
        self._validate_uuid(block_id)

        # Default query if none provided
        if query is None:
            query = LinkQuery()

        query_dict = query.to_dict()
        relation = query_dict.get("relation")
        limit = query_dict.get("limit", 100)

        # Build SQL query
        where_clauses = ["from_id = %s"]
        params = [block_id]

        if relation:
            where_clauses.append("relation = %s")
            params.append(relation)

        sql_query = f"""
        SELECT to_id, relation, priority, link_metadata, created_by, created_at
        FROM block_links 
        WHERE {" AND ".join(where_clauses)}
        ORDER BY priority DESC, created_at DESC
        LIMIT %s
        """

        params.append(limit)

        result = self._execute_query(sql_query, params)

        links = []
        if result and len(result) > 0:
            for row in result:
                # For links FROM this block
                link = BlockLink(
                    from_id=block_id,
                    to_id=row["to_id"],
                    relation=row["relation"],
                    priority=row.get("priority", 0),
                    link_metadata=self._parse_json_metadata(row.get("link_metadata")),
                    created_by=row.get("created_by"),
                    created_at=self._parse_datetime(row.get("created_at")),
                )
                links.append(link)

        # TODO: Implement pagination with cursor
        return LinkQueryResult(links=links, next_cursor=None)

    def links_to(self, block_id: str, query: Optional[LinkQuery] = None) -> LinkQueryResult:
        """
        Get links pointing to a block.

        Args:
            block_id: ID of the target block
            query: Optional query parameters

        Returns:
            LinkQueryResult containing matching links
        """
        # Validate ID
        self._validate_uuid(block_id)

        # Default query if none provided
        if query is None:
            query = LinkQuery()

        query_dict = query.to_dict()
        relation = query_dict.get("relation")
        limit = query_dict.get("limit", 100)

        # Build SQL query
        where_clauses = ["to_id = %s"]
        params = [block_id]

        if relation:
            where_clauses.append("relation = %s")
            params.append(relation)

        sql_query = f"""
        SELECT from_id, to_id, relation, priority, link_metadata, created_by, created_at
        FROM block_links 
        WHERE {" AND ".join(where_clauses)}
        ORDER BY priority DESC, created_at DESC
        LIMIT %s
        """

        params.append(limit)

        result = self._execute_query(sql_query, params)

        links = []
        if result and len(result) > 0:
            for row in result:
                # For links pointing TO this block, the from_id is what we get from DB
                link = BlockLink(
                    from_id=row["from_id"],
                    to_id=row["to_id"],  # This should be the block_id we queried for
                    relation=row["relation"],
                    priority=row.get("priority", 0),
                    link_metadata=self._parse_json_metadata(row.get("link_metadata")),
                    created_by=row.get("created_by"),
                    created_at=self._parse_datetime(row.get("created_at")),
                )
                links.append(link)

        # TODO: Implement pagination with cursor
        return LinkQueryResult(links=links, next_cursor=None)

    def has_cycle(
        self, start_id: str, relation: RelationType, visited: Optional[Set[str]] = None
    ) -> bool:
        """
        Check if there's a cycle starting from the given block for the specified relation.

        This is a simplified implementation for now. For production, consider more sophisticated
        cycle detection algorithms.
        """
        # For now, return False to allow link creation
        # TODO: Implement proper cycle detection with SQL queries
        return False

    def topo_sort(self, block_ids: List[str], relation: RelationType) -> List[str]:
        """
        Perform topological sort on the given blocks for the specified relation.

        This is a placeholder implementation.
        """
        # For now, return blocks in original order
        # TODO: Implement proper topological sort with SQL queries
        return block_ids

    def bulk_upsert(
        self, links: List[Tuple[str, str, RelationType, Optional[Dict[str, Any]]]]
    ) -> List[BlockLink]:
        """
        Create or update multiple links in a single operation.

        Args:
            links: List of (from_id, to_id, relation, metadata) tuples

        Returns:
            List of created/updated BlockLinks
        """
        # Branch protection: prevent bulk link operations on main branch
        self._check_main_branch_protection("bulk_upsert")

        results = []
        for from_id, to_id, relation, metadata in links:
            link = self.upsert_link(
                from_id=from_id, to_id=to_id, relation=relation, link_metadata=metadata
            )
            results.append(link)
        return results

    def delete_links_for_block(self, block_id: str) -> int:
        """
        Delete all links involving a block (as source or target).

        Args:
            block_id: ID of the block being deleted

        Returns:
            Number of links deleted
        """
        # Branch protection: prevent link deletions on main branch
        self._check_main_branch_protection("delete_links_for_block")

        # Validate ID
        self._validate_uuid(block_id)

        # Get all links involving this block for hook processing
        get_links_query = """
        SELECT from_id, to_id, relation
        FROM block_links 
        WHERE from_id = %s OR to_id = %s
        """
        result = self._execute_query(get_links_query, (block_id, block_id))

        links_to_process = []
        if result and len(result) > 0:
            links_to_process = result

        # Process hooks for each link before deletion
        for link_row in links_to_process:
            if link_row["relation"] == "contains":
                if link_row["from_id"] == block_id:
                    # This block was a parent, clear parent relationship
                    self._clear_parent_relationship(link_row["to_id"], block_id)
                elif link_row["to_id"] == block_id:
                    # This block was a child, clear parent relationship
                    self._clear_parent_relationship(block_id, link_row["from_id"])

        # Delete all links involving this block
        delete_query = """
        DELETE FROM block_links 
        WHERE from_id = %s OR to_id = %s
        """
        self._execute_update(delete_query, (block_id, block_id))

        return len(links_to_process)

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

        # Build SQL query
        where_clauses = []
        params = []

        if relation:
            where_clauses.append("relation = %s")
            params.append(relation)

        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        sql_query = f"""
        SELECT from_id, to_id, relation, priority, link_metadata, created_by, created_at
        FROM block_links 
        {where_clause}
        ORDER BY priority DESC, created_at DESC
        LIMIT %s
        """

        params.append(limit)

        result = self._execute_query(sql_query, params)

        links = []
        if result and len(result) > 0:
            for row in result:
                link = BlockLink(
                    from_id=row["from_id"],
                    to_id=row["to_id"],
                    relation=row["relation"],
                    priority=row.get("priority", 0),
                    link_metadata=self._parse_json_metadata(row.get("link_metadata")),
                    created_by=row.get("created_by"),
                    created_at=self._parse_datetime(row.get("created_at")),
                )
                links.append(link)

        # TODO: Implement pagination with cursor
        return LinkQueryResult(links=links, next_cursor=None)
