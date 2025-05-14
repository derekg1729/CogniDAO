"""
Tests for the LinkQuery builder.
"""

import pytest
from infra_core.memory_system.link_manager import LinkQuery, Direction


def test_link_query_default_values():
    """Test that LinkQuery initializes with expected defaults."""
    query = LinkQuery()
    query_dict = query.to_dict()

    assert query_dict["limit"] == 100
    assert "cursor" not in query_dict
    assert len(query_dict) == 1  # Only limit is set by default


@pytest.mark.xfail(reason="Not yet implemented")
def test_link_query_relation_filter():
    """Test filtering by relation type."""
    query = LinkQuery().relation("related_to")
    query_dict = query.to_dict()

    assert query_dict["relation"] == "related_to"
    assert query_dict["limit"] == 100
    # Check internal structure directly to ensure proper implementation
    assert query._filters.get("relation") == "related_to"


@pytest.mark.xfail(reason="Not yet implemented")
def test_link_query_depth_filter():
    """Test filtering by traversal depth."""
    query = LinkQuery().depth(3)
    query_dict = query.to_dict()

    assert query_dict["depth"] == 3
    assert query_dict["limit"] == 100
    # Check internal structure directly to ensure proper implementation
    assert query._filters.get("depth") == 3


@pytest.mark.xfail(reason="Not yet implemented")
def test_link_query_direction_filter():
    """Test filtering by traversal direction."""
    query = LinkQuery().direction(Direction.INBOUND)
    query_dict = query.to_dict()

    assert query_dict["direction"] == Direction.INBOUND.value
    assert query_dict["limit"] == 100
    # Check internal structure directly to ensure proper implementation
    assert query._filters.get("direction") == Direction.INBOUND.value


@pytest.mark.xfail(reason="Not yet implemented")
def test_link_query_limit():
    """Test setting result limit."""
    query = LinkQuery().limit(50)
    query_dict = query.to_dict()

    assert query_dict["limit"] == 50
    # Check internal structure directly to ensure proper implementation
    assert query._limit == 50


@pytest.mark.xfail(reason="Not yet implemented")
def test_link_query_cursor():
    """Test setting pagination cursor."""
    query = LinkQuery().cursor("test-cursor-value")
    query_dict = query.to_dict()

    assert query_dict["cursor"] == "test-cursor-value"
    assert query_dict["limit"] == 100
    # Check internal structure directly to ensure proper implementation
    assert query._cursor == "test-cursor-value"


@pytest.mark.xfail(reason="Not yet implemented")
def test_link_query_chained_filters():
    """Test chaining multiple filters together."""
    query = (
        LinkQuery()
        .relation("is_blocked_by")
        .depth(2)
        .direction(Direction.OUTBOUND)
        .limit(25)
        .cursor("test-cursor-value")
    )
    query_dict = query.to_dict()

    assert query_dict["relation"] == "is_blocked_by"
    assert query_dict["depth"] == 2
    assert query_dict["direction"] == Direction.OUTBOUND.value
    assert query_dict["limit"] == 25
    assert query_dict["cursor"] == "test-cursor-value"

    # Test actual SQL generation which would be used in the real implementation
    # This will fail until we implement the SQL generation functionality
    sql = query.to_sql("test_block_id")
    assert "FROM block_links" in sql
    assert "WHERE from_id = 'test_block_id'" in sql
    assert "relation = 'is_blocked_by'" in sql
    assert "LIMIT 25" in sql


@pytest.mark.xfail(reason="Not yet implemented")
def test_link_query_string_representation():
    """Test string representation of query for debugging."""
    query = LinkQuery().relation("child_of").depth(1).limit(10)
    query_str = str(query)

    assert "LinkQuery" in query_str
    assert "relation=child_of" in query_str
    assert "depth=1" in query_str
    assert "limit=10" in query_str


@pytest.mark.xfail(reason="Not yet implemented")
def test_link_query_invalid_depth():
    """Test validation of depth parameter."""
    with pytest.raises(ValueError) as exc_info:
        LinkQuery().depth(0)
    assert "depth must be a positive integer" in str(exc_info.value).lower()


@pytest.mark.xfail(reason="Not yet implemented")
def test_link_query_invalid_direction():
    """Test validation of direction parameter."""
    with pytest.raises(ValueError) as exc_info:
        # Using an invalid Direction value should be caught by type checking,
        # so we test the runtime validation for non-Direction objects
        LinkQuery().direction("sideways")  # type: ignore
    assert "direction must be a Direction enum value" in str(exc_info.value).lower()


@pytest.mark.xfail(reason="Not yet implemented")
def test_link_query_invalid_limit():
    """Test validation of limit parameter."""
    with pytest.raises(ValueError) as exc_info:
        LinkQuery().limit(0)
    assert "limit must be a positive integer" in str(exc_info.value).lower()


@pytest.mark.xfail(reason="Not yet implemented")
def test_link_query_complex_filter_combinations():
    """Test various combinations of filters for complex queries."""
    # Test case 1: Outbound traversal with depth
    query1 = LinkQuery().relation("child_of").direction(Direction.OUTBOUND).depth(3)
    assert query1.to_dict()["relation"] == "child_of"
    assert query1.to_dict()["direction"] == Direction.OUTBOUND.value
    assert query1.to_dict()["depth"] == 3

    # Test case 2: Bidirectional traversal
    query2 = LinkQuery().relation("related_to").direction(Direction.BOTH)
    assert query2.to_dict()["relation"] == "related_to"
    assert query2.to_dict()["direction"] == Direction.BOTH.value

    # Test case 3: Inbound with custom limit
    query3 = LinkQuery().relation("parent_of").direction(Direction.INBOUND).limit(5)
    assert query3.to_dict()["relation"] == "parent_of"
    assert query3.to_dict()["direction"] == Direction.INBOUND.value
    assert query3.to_dict()["limit"] == 5

    # Test actual execution method, which should fail until implemented
    # This simulates what would be executed in the real LinkManager implementation
    sql3 = query3.to_sql("test_block_id")
    assert "SELECT * FROM block_links" in sql3
    assert "WHERE to_id = 'test_block_id'" in sql3  # Inbound direction
    assert "relation = 'parent_of'" in sql3
    assert "LIMIT 5" in sql3
