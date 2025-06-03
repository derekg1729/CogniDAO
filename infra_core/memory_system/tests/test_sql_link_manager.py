"""
Tests for the SQLLinkManager implementation with parent/child hierarchy hooks.
"""

import pytest
import uuid

from infra_core.memory_system.sql_link_manager import SQLLinkManager
from infra_core.memory_system.schemas.memory_block import MemoryBlock
from infra_core.memory_system.dolt_writer import DoltMySQLWriter


@pytest.fixture
def sql_link_manager(dolt_connection_config):
    """Create a SQLLinkManager instance for testing."""
    return SQLLinkManager(dolt_connection_config)


@pytest.fixture
def sample_blocks(dolt_connection_config):
    """Create sample memory blocks for testing."""
    parent_block = MemoryBlock(
        id=str(uuid.uuid4()),
        type="project",
        text="Parent project block",
        tags=["test", "parent"],
    )

    child_block = MemoryBlock(
        id=str(uuid.uuid4()),
        type="task",
        text="Child task block",
        tags=["test", "child"],
    )

    # Write blocks to database using DoltMySQLWriter
    writer = DoltMySQLWriter(dolt_connection_config)
    writer.write_memory_block(parent_block, "main", auto_commit=True)
    writer.write_memory_block(child_block, "main", auto_commit=True)

    return parent_block, child_block


class TestSQLLinkManager:
    """Tests for SQLLinkManager functionality."""

    def test_initialization(self, sql_link_manager):
        """Test that SQLLinkManager initializes correctly."""
        # SQLLinkManager should be properly initialized with DoltConnectionConfig
        assert sql_link_manager is not None
        # Test database connection works
        result = sql_link_manager._execute_query("SELECT 1 as test", ())
        assert result[0]["test"] == 1

    def test_create_link_basic(self, sql_link_manager, sample_blocks):
        """Test basic link creation without hooks."""
        parent_block, child_block = sample_blocks

        # Create a non-contains relation (no hook should trigger)
        link = sql_link_manager.create_link(
            from_id=parent_block.id, to_id=child_block.id, relation="depends_on", priority=5
        )

        assert link.to_id == child_block.id
        assert link.relation == "depends_on"
        assert link.priority == 5

        # Verify link exists in database
        links_from = sql_link_manager.links_from(parent_block.id)
        assert len(links_from.links) == 1
        assert links_from.links[0].to_id == child_block.id

    def test_contains_relation_hook_create(self, sql_link_manager, sample_blocks):
        """Test that creating a 'contains' relation triggers parent/child column updates."""
        parent_block, child_block = sample_blocks

        # Create a 'contains' relation
        link = sql_link_manager.create_link(
            from_id=parent_block.id, to_id=child_block.id, relation="contains", priority=1
        )

        assert link.relation == "contains"

        # Verify parent/child columns were updated using MySQL queries
        # Check child's parent_id was set
        child_query = "SELECT parent_id FROM memory_blocks WHERE id = %s"
        child_result = sql_link_manager._execute_query(child_query, (child_block.id,))
        assert child_result[0]["parent_id"] == parent_block.id

        # Check parent's has_children was set to TRUE
        parent_query = "SELECT has_children FROM memory_blocks WHERE id = %s"
        parent_result = sql_link_manager._execute_query(parent_query, (parent_block.id,))
        assert parent_result[0]["has_children"] == 1  # TRUE in SQL

    def test_contains_relation_hook_delete(self, sql_link_manager, sample_blocks):
        """Test that deleting a 'contains' relation triggers parent/child column cleanup."""
        parent_block, child_block = sample_blocks

        # First create a 'contains' relation
        sql_link_manager.create_link(
            from_id=parent_block.id, to_id=child_block.id, relation="contains"
        )

        # Delete the 'contains' relation
        deleted = sql_link_manager.delete_link(
            from_id=parent_block.id, to_id=child_block.id, relation="contains"
        )

        assert deleted is True

        # Verify parent/child columns were cleared using MySQL queries
        # Check child's parent_id was cleared (should be NULL)
        child_query = "SELECT parent_id FROM memory_blocks WHERE id = %s"
        child_result = sql_link_manager._execute_query(child_query, (child_block.id,))
        assert child_result[0]["parent_id"] is None

        # Check parent's has_children was set to FALSE
        parent_query = "SELECT has_children FROM memory_blocks WHERE id = %s"
        parent_result = sql_link_manager._execute_query(parent_query, (parent_block.id,))
        assert parent_result[0]["has_children"] == 0  # FALSE in SQL

    def test_multiple_children_handling(self, sql_link_manager, dolt_connection_config):
        """Test that has_children flag is handled correctly with multiple children."""
        # Create parent and two children
        parent_id = str(uuid.uuid4())
        child1_id = str(uuid.uuid4())
        child2_id = str(uuid.uuid4())

        parent_block = MemoryBlock(id=parent_id, type="project", text="Parent", tags=["test"])
        child1_block = MemoryBlock(id=child1_id, type="task", text="Child 1", tags=["test"])
        child2_block = MemoryBlock(id=child2_id, type="task", text="Child 2", tags=["test"])

        # Write blocks to database using DoltMySQLWriter
        writer = DoltMySQLWriter(dolt_connection_config)
        for block in [parent_block, child1_block, child2_block]:
            writer.write_memory_block(block, "main", auto_commit=True)

        # Create contains relations to both children
        sql_link_manager.create_link(parent_id, child1_id, "contains")
        sql_link_manager.create_link(parent_id, child2_id, "contains")

        # Verify parent has_children is TRUE
        parent_query = "SELECT has_children FROM memory_blocks WHERE id = %s"
        parent_result = sql_link_manager._execute_query(parent_query, (parent_id,))
        assert parent_result[0]["has_children"] == 1

        # Delete one child relationship
        sql_link_manager.delete_link(parent_id, child1_id, "contains")

        # Parent should still have has_children = TRUE (still has child2)
        parent_result = sql_link_manager._execute_query(parent_query, (parent_id,))
        assert parent_result[0]["has_children"] == 1

        # Delete the last child relationship
        sql_link_manager.delete_link(parent_id, child2_id, "contains")

        # Now parent should have has_children = FALSE
        parent_result = sql_link_manager._execute_query(parent_query, (parent_id,))
        assert parent_result[0]["has_children"] == 0

    def test_upsert_link_functionality(self, sql_link_manager, sample_blocks):
        """Test the upsert_link method that handles both create and update."""
        parent_block, child_block = sample_blocks

        # First upsert (should create)
        link1 = sql_link_manager.upsert_link(
            from_id=parent_block.id,
            to_id=child_block.id,
            relation="contains",
            priority=1,
            link_metadata={"initial": True},
        )

        assert link1.priority == 1

        # Second upsert (should update)
        link2 = sql_link_manager.upsert_link(
            from_id=parent_block.id,
            to_id=child_block.id,
            relation="contains",
            priority=5,
            link_metadata={"updated": True},
        )

        assert link2.priority == 5

        # Verify only one link exists
        links = sql_link_manager.links_from(parent_block.id)
        assert len(links.links) == 1
        assert links.links[0].priority == 5

    def test_bulk_upsert_with_hooks(self, sql_link_manager, dolt_connection_config):
        """Test bulk_upsert with contains relations triggering hooks."""
        # Create test blocks
        parent_id = str(uuid.uuid4())
        child1_id = str(uuid.uuid4())
        child2_id = str(uuid.uuid4())

        for block_id, block_type in [
            (parent_id, "project"),
            (child1_id, "task"),
            (child2_id, "task"),
        ]:
            block = MemoryBlock(
                id=block_id, type=block_type, text=f"Block {block_id}", tags=["test"]
            )
            writer = DoltMySQLWriter(dolt_connection_config)
            writer.write_memory_block(block, "main", auto_commit=True)

        # Bulk upsert with contains relations
        links_data = [
            (parent_id, child1_id, "contains", {"bulk": True}),
            (parent_id, child2_id, "contains", {"bulk": True}),
        ]

        result_links = sql_link_manager.bulk_upsert(links_data)
        assert len(result_links) == 2

        # Verify hooks were triggered for both
        # Check both children have parent_id set
        for child_id in [child1_id, child2_id]:
            child_query = "SELECT parent_id FROM memory_blocks WHERE id = %s"
            child_result = sql_link_manager._execute_query(child_query, (child_id,))
            assert child_result[0]["parent_id"] == parent_id

    def test_delete_links_for_block_with_hooks(self, sql_link_manager, dolt_connection_config):
        """Test delete_links_for_block properly handles parent/child cleanup."""
        # Create parent and child blocks
        parent_id = str(uuid.uuid4())
        child_id = str(uuid.uuid4())

        for block_id, block_type in [(parent_id, "project"), (child_id, "task")]:
            block = MemoryBlock(
                id=block_id, type=block_type, text=f"Block {block_id}", tags=["test"]
            )
            writer = DoltMySQLWriter(dolt_connection_config)
            writer.write_memory_block(block, "main", auto_commit=True)

        # Create contains relation
        sql_link_manager.create_link(parent_id, child_id, "contains")

        # Delete all links for the parent block
        deleted_count = sql_link_manager.delete_links_for_block(parent_id)
        assert deleted_count == 1

        # Verify child's parent_id was cleared (should be NULL)
        child_query = "SELECT parent_id FROM memory_blocks WHERE id = %s"
        child_result = sql_link_manager._execute_query(child_query, (child_id,))
        assert child_result[0]["parent_id"] is None

    def test_non_contains_relations_no_hooks(self, sql_link_manager, sample_blocks):
        """Test that non-contains relations don't trigger parent/child hooks."""
        parent_block, child_block = sample_blocks

        # Create a non-contains relation
        sql_link_manager.create_link(
            from_id=parent_block.id, to_id=child_block.id, relation="depends_on"
        )

        # Verify parent/child columns remain unchanged
        # Check child's parent_id remains NULL (should be NULL)
        child_query = "SELECT parent_id FROM memory_blocks WHERE id = %s"
        child_result = sql_link_manager._execute_query(child_query, (child_block.id,))
        assert child_result[0]["parent_id"] is None

        # Check parent's has_children remains FALSE
        parent_query = "SELECT has_children FROM memory_blocks WHERE id = %s"
        parent_result = sql_link_manager._execute_query(parent_query, (parent_block.id,))
        assert parent_result[0]["has_children"] == 0

    def test_links_to_query(self, sql_link_manager, sample_blocks):
        """Test the links_to method for finding backlinks."""
        parent_block, child_block = sample_blocks

        # Create a link
        sql_link_manager.create_link(
            from_id=parent_block.id, to_id=child_block.id, relation="contains"
        )

        # Query backlinks
        backlinks = sql_link_manager.links_to(child_block.id)
        assert len(backlinks.links) == 1
        assert (
            backlinks.links[0].from_id == parent_block.id
        )  # Source block that links TO our target
        assert backlinks.links[0].to_id == child_block.id  # Target block we queried for
        assert backlinks.links[0].relation == "contains"

    def test_validation_errors(self, sql_link_manager):
        """Test that validation errors are properly raised."""
        # Test invalid UUID
        with pytest.raises(ValueError, match="Invalid UUID format"):
            sql_link_manager.create_link("invalid-uuid", "another-invalid", "contains")

        # Test invalid relation
        valid_uuid = str(uuid.uuid4())
        with pytest.raises(ValueError, match="Invalid relation type"):
            sql_link_manager.create_link(valid_uuid, valid_uuid, "invalid_relation")

        # Test negative priority
        with pytest.raises(ValueError, match="Priority must be non-negative"):
            sql_link_manager.create_link(valid_uuid, valid_uuid, "contains", priority=-1)

    @pytest.mark.skip("Cycle detection not yet implemented")
    def test_cycle_detection(self, sql_link_manager, sample_blocks):
        """Test cycle detection (placeholder for future implementation)."""
        # This test will be implemented when cycle detection is added to SQLLinkManager
        pass
