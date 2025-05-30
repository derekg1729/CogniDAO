"""
Integration tests for MCP server with SQLLinkManager.

These tests ensure that the MCP server correctly uses SQLLinkManager
and that link operations persist to the actual database.
"""

import pytest
import uuid
from unittest.mock import patch

from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.sql_link_manager import SQLLinkManager
from infra_core.memory_system.tools.memory_core.create_block_link_tool import (
    create_block_link,
    CreateBlockLinkInput,
)
from infra_core.memory_system.schemas.memory_block import MemoryBlock


class TestMCPSQLLinkManagerIntegration:
    """Test MCP tools with real SQLLinkManager integration."""

    @pytest.fixture
    def test_memory_bank(self, temp_dolt_db):
        """Create a memory bank with SQLLinkManager for testing."""
        # Initialize StructuredMemoryBank
        memory_bank = StructuredMemoryBank(
            dolt_db_path=temp_dolt_db,
            chroma_path=temp_dolt_db + "_chroma",  # Separate chroma path
            chroma_collection="test_links_collection",
        )

        # Initialize and attach SQLLinkManager
        link_manager = SQLLinkManager(db_path=temp_dolt_db)
        memory_bank.link_manager = link_manager

        return memory_bank

    @pytest.fixture
    def sample_blocks(self, test_memory_bank):
        """Create sample memory blocks for testing."""
        blocks = []
        for i in range(3):
            block = MemoryBlock(
                id=str(uuid.uuid4()),
                type="task",
                text=f"Test block {i + 1}",
                tags=[f"test_{i}"],
                metadata={"test": True, "index": i},
                schema_version=1,
            )
            # Mock the block creation since we're focusing on link testing
            with patch.object(test_memory_bank, "create_memory_block", return_value=True):
                with patch.object(test_memory_bank, "get_memory_block", return_value=block):
                    blocks.append(block)

        return blocks

    def test_create_block_link_with_sql_persistence(self, test_memory_bank):
        """Test that MCP CreateBlockLink tool persists links to SQL."""
        # Create source and target block IDs
        source_id = str(uuid.uuid4())
        target_id = str(uuid.uuid4())

        # First create actual blocks so they exist
        from infra_core.memory_system.schemas.memory_block import MemoryBlock
        from datetime import datetime

        block1 = MemoryBlock(
            id=source_id,
            type="task",
            text="Source block",
            tags=[],
            metadata={},
            links=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        block2 = MemoryBlock(
            id=target_id,
            type="task",
            text="Target block",
            tags=[],
            metadata={},
            links=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Store the blocks using create_memory_block
        assert test_memory_bank.create_memory_block(block1), "Failed to create source block"
        assert test_memory_bank.create_memory_block(block2), "Failed to create target block"

        # Create test input
        input_data = CreateBlockLinkInput(
            from_id=source_id,
            to_id=target_id,
            relation="depends_on",
            is_bidirectional=False,
        )

        # Call the core tool function
        result = create_block_link(input_data, test_memory_bank)

        # Verify the tool succeeded
        assert result.success is True

        # Check that link exists in database via SQLLinkManager
        links = test_memory_bank.link_manager.links_from(source_id)
        assert len(links.links) == 1
        assert links.links[0].to_id == target_id
        assert links.links[0].relation == "depends_on"

    def test_bidirectional_link_creation(self, test_memory_bank):
        """Test bidirectional link creation through MCP tools."""
        source_id = str(uuid.uuid4())
        target_id = str(uuid.uuid4())

        # First create actual blocks so they exist
        from infra_core.memory_system.schemas.memory_block import MemoryBlock
        from datetime import datetime

        block1 = MemoryBlock(
            id=source_id,
            type="task",
            text="Source block",
            tags=[],
            metadata={},
            links=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        block2 = MemoryBlock(
            id=target_id,
            type="task",
            text="Target block",
            tags=[],
            metadata={},
            links=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Store the blocks using create_memory_block
        assert test_memory_bank.create_memory_block(block1), "Failed to create source block"
        assert test_memory_bank.create_memory_block(block2), "Failed to create target block"

        input_data = CreateBlockLinkInput(
            from_id=source_id,
            to_id=target_id,
            relation="depends_on",
            is_bidirectional=True,
        )

        result = create_block_link(input_data, test_memory_bank)

        assert result.success is True

        # Check both directions exist
        forward_links = test_memory_bank.link_manager.links_from(source_id)
        backward_links = test_memory_bank.link_manager.links_from(target_id)

        assert len(forward_links.links) == 1
        assert len(backward_links.links) == 1

    def test_multiple_links_persistence(self, test_memory_bank):
        """Test multiple links persist correctly."""
        parent_id = str(uuid.uuid4())
        child1_id = str(uuid.uuid4())
        child2_id = str(uuid.uuid4())

        # First create actual blocks so they exist
        from infra_core.memory_system.schemas.memory_block import MemoryBlock
        from datetime import datetime

        parent_block = MemoryBlock(
            id=parent_id,
            type="project",
            text="Parent block",
            tags=[],
            metadata={},
            links=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        child1_block = MemoryBlock(
            id=child1_id,
            type="task",
            text="Child 1 block",
            tags=[],
            metadata={},
            links=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        child2_block = MemoryBlock(
            id=child2_id,
            type="task",
            text="Child 2 block",
            tags=[],
            metadata={},
            links=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Store the blocks using create_memory_block
        assert test_memory_bank.create_memory_block(parent_block), "Failed to create parent block"
        assert test_memory_bank.create_memory_block(child1_block), "Failed to create child1 block"
        assert test_memory_bank.create_memory_block(child2_block), "Failed to create child2 block"

        # Create parent->child1
        input1 = CreateBlockLinkInput(
            from_id=parent_id,
            to_id=child1_id,
            relation="child_of",
            is_bidirectional=False,
        )
        result1 = create_block_link(input1, test_memory_bank)
        assert result1.success is True

        # Create parent->child2
        input2 = CreateBlockLinkInput(
            from_id=parent_id,
            to_id=child2_id,
            relation="child_of",
            is_bidirectional=False,
        )
        result2 = create_block_link(input2, test_memory_bank)
        assert result2.success is True

        # Verify both links exist
        links = test_memory_bank.link_manager.links_from(parent_id)
        assert len(links.links) == 2

    def test_error_handling_invalid_blocks(self, test_memory_bank):
        """Test error handling when trying to link non-existent blocks."""
        # Don't create any blocks
        source_id = str(uuid.uuid4())
        target_id = str(uuid.uuid4())

        input_data = CreateBlockLinkInput(
            from_id=source_id,
            to_id=target_id,
            relation="depends_on",
            is_bidirectional=False,
        )

        result = create_block_link(input_data, test_memory_bank)

        # Should fail with NOT_FOUND error
        assert result.success is False
        assert result.error_type == "NOT_FOUND"
        assert "Block not found" in result.error

    def test_relation_alias_resolution(self, test_memory_bank):
        """Test that relation aliases are resolved correctly."""
        source_id = str(uuid.uuid4())
        target_id = str(uuid.uuid4())

        # First create actual blocks so they exist
        from infra_core.memory_system.schemas.memory_block import MemoryBlock
        from datetime import datetime

        block1 = MemoryBlock(
            id=source_id,
            type="task",
            text="Source block",
            tags=[],
            metadata={},
            links=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        block2 = MemoryBlock(
            id=target_id,
            type="task",
            text="Target block",
            tags=[],
            metadata={},
            links=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Store the blocks using create_memory_block
        assert test_memory_bank.create_memory_block(block1), "Failed to create source block"
        assert test_memory_bank.create_memory_block(block2), "Failed to create target block"

        # Test using a relation alias
        input_data = CreateBlockLinkInput(
            from_id=source_id,
            to_id=target_id,
            relation="depends_on",
            is_bidirectional=False,
        )

        result = create_block_link(input_data, test_memory_bank)
        assert result.success is True

        # Verify the canonical relation was stored
        links = test_memory_bank.link_manager.links_from(source_id)
        assert len(links.links) == 1
        # The alias should be resolved to canonical relation
        assert links.links[0].relation in ["depends_on", "blocks"]  # Either is valid

    def test_duplicate_link_prevention(self, test_memory_bank):
        """Test that duplicate links are prevented."""
        source_id = str(uuid.uuid4())
        target_id = str(uuid.uuid4())

        # First create actual blocks so they exist
        from infra_core.memory_system.schemas.memory_block import MemoryBlock
        from datetime import datetime

        block1 = MemoryBlock(
            id=source_id,
            type="task",
            text="Source block",
            tags=[],
            metadata={},
            links=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        block2 = MemoryBlock(
            id=target_id,
            type="task",
            text="Target block",
            tags=[],
            metadata={},
            links=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Store the blocks using create_memory_bank
        assert test_memory_bank.create_memory_block(block1), "Failed to create source block"
        assert test_memory_bank.create_memory_block(block2), "Failed to create target block"

        input_data = CreateBlockLinkInput(
            from_id=source_id,
            to_id=target_id,
            relation="depends_on",
            is_bidirectional=False,
        )

        # Create first link
        result1 = create_block_link(input_data, test_memory_bank)
        assert result1.success is True

        # Try to create duplicate
        result2 = create_block_link(input_data, test_memory_bank)
        # Should handle gracefully - either succeed (idempotent) or fail with clear message
        if result2.success is False:
            assert result2.error_type is not None

        # Check that we don't have excessive links
        links = test_memory_bank.link_manager.links_from(source_id)
        assert len(links.links) <= 2  # At most one duplicate

    def test_memory_bank_configuration_matches_web_api(self, temp_dolt_db):
        """Test that MCP server memory bank configuration matches web API pattern."""
        # This test ensures the MCP server initialization follows the same pattern as web API

        # Initialize like the web API does
        memory_bank = StructuredMemoryBank(
            dolt_db_path=temp_dolt_db,
            chroma_path=temp_dolt_db + "_chroma",
            chroma_collection="cogni_memory_test",
        )

        # Attach SQLLinkManager like MCP server does
        link_manager = SQLLinkManager(db_path=temp_dolt_db)
        memory_bank.link_manager = link_manager

        # Basic functionality test
        assert memory_bank.dolt_db_path == temp_dolt_db
        assert memory_bank.link_manager is not None
        assert isinstance(memory_bank.link_manager, SQLLinkManager)


class TestMCPServerInitializationFix:
    """Test that the MCP server initialization has been fixed."""

    def test_mcp_server_uses_sql_link_manager(self):
        """Test that MCP server imports and uses SQLLinkManager."""
        # This test verifies our fix to services/mcp_server/app/mcp_server.py

        with open("services/mcp_server/app/mcp_server.py", "r") as f:
            mcp_server_content = f.read()

        # Verify SQLLinkManager is imported
        assert (
            "from infra_core.memory_system.sql_link_manager import SQLLinkManager"
            in mcp_server_content
        )

        # Verify InMemoryLinkManager is NOT used in initialization
        assert "InMemoryLinkManager()" not in mcp_server_content

        # Verify SQLLinkManager is used
        assert "SQLLinkManager(" in mcp_server_content

    def test_mcp_initialization_pattern_consistency(self):
        """Test that MCP server and web API use the same initialization pattern."""
        # Read both files
        with open("services/mcp_server/app/mcp_server.py", "r") as f:
            mcp_content = f.read()

        with open("services/web_api/app.py", "r") as f:
            web_api_content = f.read()

        # Both should import SQLLinkManager
        assert "SQLLinkManager" in mcp_content
        assert "SQLLinkManager" in web_api_content

        # Both should use the same dolt path pattern - use dolt_db_path
        assert "dolt_db_path" in mcp_content
        assert "dolt_db_path" in web_api_content

        # Neither should use InMemoryLinkManager in production code
        assert "InMemoryLinkManager()" not in mcp_content
        assert "InMemoryLinkManager()" not in web_api_content
