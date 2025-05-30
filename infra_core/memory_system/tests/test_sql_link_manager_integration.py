"""
Integration test for SQLLinkManager with a temporary test database.
"""

import uuid
from infra_core.memory_system.sql_link_manager import SQLLinkManager
from infra_core.memory_system.schemas.memory_block import MemoryBlock
from infra_core.memory_system.dolt_writer import write_memory_block_to_dolt
from .test_utils import add_parent_child_columns_to_db


def test_sql_link_manager_with_temp_db(temp_dolt_db):
    """Test SQLLinkManager with a temporary test database."""
    # Add parent/child columns to the temp database
    add_parent_child_columns_to_db(temp_dolt_db)

    # Create SQLLinkManager with the temp database
    sql_link_manager = SQLLinkManager(temp_dolt_db)

    # Create test blocks
    parent_id = str(uuid.uuid4())
    child_id = str(uuid.uuid4())

    parent_block = MemoryBlock(
        id=parent_id,
        type="project",
        text="Integration test parent block",
        tags=["integration", "test", "parent"],
    )

    child_block = MemoryBlock(
        id=child_id,
        type="task",
        text="Integration test child block",
        tags=["integration", "test", "child"],
    )

    # Write blocks to database
    write_success_1, _ = write_memory_block_to_dolt(parent_block, temp_dolt_db, auto_commit=True)
    write_success_2, _ = write_memory_block_to_dolt(child_block, temp_dolt_db, auto_commit=True)

    assert write_success_1 and write_success_2, "Failed to write test blocks"

    # Create a contains relation using SQLLinkManager
    link = sql_link_manager.create_link(
        from_id=parent_id,
        to_id=child_id,
        relation="contains",
        priority=1,
        link_metadata={"test": "integration"},
        created_by="test_agent",
    )

    assert link.relation == "contains"
    assert link.priority == 1

    # Verify link exists in database via links_from API
    links_from_parent = sql_link_manager.links_from(parent_id)
    assert len(links_from_parent.links) == 1
    assert links_from_parent.links[0].to_id == child_id
    assert links_from_parent.links[0].relation == "contains"

    # F2: Verify backlinks API shows the relationship
    links_to_child = sql_link_manager.links_to(child_id)
    assert len(links_to_child.links) == 1
    assert links_to_child.links[0].to_id == parent_id  # Source becomes target in backlinks
    assert links_to_child.links[0].relation == "contains"

    # Verify parent/child columns were updated
    from doltpy.cli import Dolt

    repo = Dolt(temp_dolt_db)

    # Check child has parent_id set
    child_query = f"SELECT parent_id FROM memory_blocks WHERE id = '{child_id}'"
    child_result = repo.sql(query=child_query, result_format="json")
    assert child_result["rows"][0]["parent_id"] == parent_id

    # Check parent has has_children = TRUE
    parent_query = f"SELECT has_children FROM memory_blocks WHERE id = '{parent_id}'"
    parent_result = repo.sql(query=parent_query, result_format="json")
    assert parent_result["rows"][0]["has_children"] == 1

    # Test deletion
    deleted = sql_link_manager.delete_link(from_id=parent_id, to_id=child_id, relation="contains")

    assert deleted is True

    # F1: Verify link was actually removed from database via links_from API
    links_from_parent_after = sql_link_manager.links_from(parent_id)
    assert len(links_from_parent_after.links) == 0, "Expected 0 links from parent after deletion"

    # F2: Verify backlinks API shows no relationships after deletion
    links_to_child_after = sql_link_manager.links_to(child_id)
    assert len(links_to_child_after.links) == 0, "Expected 0 backlinks to child after deletion"

    # Verify parent/child columns were cleared
    child_result = repo.sql(query=child_query, result_format="json")
    assert child_result["rows"][0].get("parent_id") is None

    parent_result = repo.sql(query=parent_query, result_format="json")
    assert parent_result["rows"][0]["has_children"] == 0

    print("✅ SQLLinkManager integration test passed!")


if __name__ == "__main__":
    test_sql_link_manager_with_temp_db()
