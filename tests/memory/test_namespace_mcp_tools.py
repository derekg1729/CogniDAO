"""
Tests for namespace functionality in MCP tools.

This test suite validates that all MCP tools properly support namespace operations
and maintain proper isolation between namespaces.
"""

import pytest
import uuid
from unittest.mock import MagicMock, patch
from datetime import datetime

from infra_core.memory_system.tools.agent_facing.create_memory_block_agent_tool import (
    CreateMemoryBlockAgentInput,
    create_memory_block_agent,
)
from infra_core.memory_system.tools.memory_core.get_memory_block_core import (
    GetMemoryBlockInput,
    get_memory_block_core,
)
from infra_core.memory_system.tools.memory_core.query_memory_blocks_tool import (
    QueryMemoryBlocksInput,
    query_memory_blocks_core,
)
from infra_core.memory_system.tools.memory_core.create_memory_block_tool import (
    CreateMemoryBlockInput,
)
from infra_core.memory_system.schemas.memory_block import MemoryBlock


class TestNamespaceMCPTools:
    """Test namespace functionality in MCP tools."""

    @pytest.fixture
    def mock_memory_bank(self):
        """Create a mock StructuredMemoryBank with namespace-aware data."""
        bank = MagicMock()

        # Mock blocks in different namespaces
        legacy_block = MemoryBlock(
            id="legacy-block-1",
            type="doc",
            text="Legacy namespace content",
            namespace_id="legacy",
            tags=["test"],
            metadata={"source": "legacy"},
        )

        user_block = MemoryBlock(
            id="user-block-1",
            type="doc",
            text="User namespace content",
            namespace_id="user-123",
            tags=["test"],
            metadata={"source": "user"},
        )

        # Track all blocks (initial + dynamically created) - use a list that can be modified
        bank._all_blocks = [legacy_block, user_block]

        # Mock create_memory_block to return proper result object and track created blocks
        def mock_create_memory_block(block):
            # Create a new block and add it to our tracked blocks
            # Note: the block parameter is already a MemoryBlock object
            bank._all_blocks.append(block)

            # Return tuple as expected by create_memory_block_tool: (success, error_message)
            return (True, None)

        bank.create_memory_block.side_effect = mock_create_memory_block

        # Mock get_all_memory_blocks to return current state of all tracked blocks
        def mock_get_all_memory_blocks(branch=None):
            return bank._all_blocks.copy()  # Return a copy to avoid modification issues

        bank.get_all_memory_blocks.side_effect = mock_get_all_memory_blocks

        # Mock query_semantic to return current state of all tracked blocks
        def mock_query_semantic(query_text, top_k=None):
            return bank._all_blocks.copy()

        bank.query_semantic.side_effect = mock_query_semantic

        bank.dolt_writer.active_branch = "feat/namespaces"

        # Mock the _execute_query method to return proper branch info
        bank.dolt_writer._execute_query.return_value = [{"branch": "feat/namespaces"}]

        return bank

    def test_create_memory_block_agent_default_namespace(self, mock_memory_bank):
        """Test that CreateMemoryBlockAgent defaults to 'legacy' namespace."""
        input_data = CreateMemoryBlockAgentInput(type="doc", content="Test content")

        # Generate a proper UUID for the test
        test_uuid = str(uuid.uuid4())

        with patch(
            "infra_core.memory_system.tools.agent_facing.create_memory_block_agent_tool.create_memory_block"
        ) as mock_create:
            mock_create.return_value = MagicMock(
                success=True,
                id=test_uuid,
                active_branch="feat/namespaces",
                timestamp=datetime.now(),
                error=None,
            )

            result = create_memory_block_agent(input_data, mock_memory_bank)

            # Verify the core create_memory_block was called with legacy namespace
            mock_create.assert_called_once()
            core_input = mock_create.call_args[0][0]
            assert core_input.namespace_id == "legacy"
            assert result.success is True

    def test_create_memory_block_agent_custom_namespace(self, mock_memory_bank):
        """Test that CreateMemoryBlockAgent accepts custom namespace."""
        input_data = CreateMemoryBlockAgentInput(
            type="doc", content="Test content", namespace_id="user-123"
        )

        # Generate a proper UUID for the test
        test_uuid = str(uuid.uuid4())

        with patch(
            "infra_core.memory_system.tools.agent_facing.create_memory_block_agent_tool.create_memory_block"
        ) as mock_create:
            mock_create.return_value = MagicMock(
                success=True,
                id=test_uuid,
                active_branch="feat/namespaces",
                timestamp=datetime.now(),
                error=None,
            )

            result = create_memory_block_agent(input_data, mock_memory_bank)

            # Verify the core create_memory_block was called with custom namespace
            mock_create.assert_called_once()
            core_input = mock_create.call_args[0][0]
            assert core_input.namespace_id == "user-123"
            assert result.success is True

    def test_get_memory_block_namespace_filter(self, mock_memory_bank):
        """Test that GetMemoryBlock can filter by namespace."""
        input_data = GetMemoryBlockInput(type_filter="doc", namespace_id="legacy")

        result = get_memory_block_core(input_data, mock_memory_bank)

        assert result.success is True
        assert len(result.blocks) == 1
        assert result.blocks[0].namespace_id == "legacy"
        assert result.blocks[0].id == "legacy-block-1"

    def test_get_memory_block_different_namespace_filter(self, mock_memory_bank):
        """Test that GetMemoryBlock filters correctly for different namespace."""
        input_data = GetMemoryBlockInput(type_filter="doc", namespace_id="user-123")

        result = get_memory_block_core(input_data, mock_memory_bank)

        assert result.success is True
        assert len(result.blocks) == 1
        assert result.blocks[0].namespace_id == "user-123"
        assert result.blocks[0].id == "user-block-1"

    def test_get_memory_block_no_namespace_filter(self, mock_memory_bank):
        """Test that GetMemoryBlock returns all blocks when no namespace filter."""
        input_data = GetMemoryBlockInput(type_filter="doc")

        result = get_memory_block_core(input_data, mock_memory_bank)

        assert result.success is True
        assert len(result.blocks) == 2
        namespace_ids = {block.namespace_id for block in result.blocks}
        assert namespace_ids == {"legacy", "user-123"}

    def test_query_memory_blocks_namespace_filter(self, mock_memory_bank):
        """Test that QueryMemoryBlocks can filter by namespace."""
        input_data = QueryMemoryBlocksInput(query_text="test content", namespace_id="legacy")

        result = query_memory_blocks_core(input_data, mock_memory_bank)

        assert result.success is True
        assert len(result.blocks) == 1
        assert result.blocks[0].namespace_id == "legacy"

    def test_query_memory_blocks_different_namespace_filter(self, mock_memory_bank):
        """Test that QueryMemoryBlocks filters correctly for different namespace."""
        input_data = QueryMemoryBlocksInput(query_text="test content", namespace_id="user-123")

        result = query_memory_blocks_core(input_data, mock_memory_bank)

        assert result.success is True
        assert len(result.blocks) == 1
        assert result.blocks[0].namespace_id == "user-123"

    def test_query_memory_blocks_no_namespace_filter(self, mock_memory_bank):
        """Test that QueryMemoryBlocks returns all blocks when no namespace filter."""
        input_data = QueryMemoryBlocksInput(query_text="test content")

        result = query_memory_blocks_core(input_data, mock_memory_bank)

        assert result.success is True
        assert len(result.blocks) == 2
        namespace_ids = {block.namespace_id for block in result.blocks}
        assert namespace_ids == {"legacy", "user-123"}

    def test_namespace_isolation_validation(self, mock_memory_bank):
        """Test that different namespaces properly isolate data"""
        # This validates the complete namespace isolation workflow
        from infra_core.memory_system.tools.memory_core.create_memory_block_tool import (
            create_memory_block,
        )

        # 1. Create block in default namespace using MCP tool
        result_legacy = create_memory_block(
            CreateMemoryBlockInput(
                type="knowledge",
                text="Legacy knowledge content",
                namespace_id="legacy",
                metadata={"title": "Legacy Knowledge Block"},
            ),
            mock_memory_bank,
        )
        assert result_legacy.success, f"Failed to create legacy block: {result_legacy.error}"

        # 2. Create block in custom namespace using MCP tool
        result_custom = create_memory_block(
            CreateMemoryBlockInput(
                type="knowledge",
                text="Custom knowledge content",
                namespace_id="custom-tenant",
                metadata={"title": "Custom Knowledge Block"},
            ),
            mock_memory_bank,
        )
        assert result_custom.success, f"Failed to create custom block: {result_custom.error}"

        # 3. Verify namespace filtering works correctly
        legacy_blocks = get_memory_block_core(
            GetMemoryBlockInput(type_filter="knowledge", namespace_id="legacy"), mock_memory_bank
        )
        assert legacy_blocks.success, "Failed to query legacy namespace"
        assert len([b for b in legacy_blocks.blocks if b.id == result_legacy.id]) == 1, (
            "Legacy block not found in legacy namespace"
        )
        assert len([b for b in legacy_blocks.blocks if b.id == result_custom.id]) == 0, (
            "Custom block incorrectly found in legacy namespace"
        )

        custom_blocks = get_memory_block_core(
            GetMemoryBlockInput(type_filter="knowledge", namespace_id="custom-tenant"),
            mock_memory_bank,
        )
        assert custom_blocks.success, "Failed to query custom namespace"
        assert len([b for b in custom_blocks.blocks if b.id == result_custom.id]) == 1, (
            "Custom block not found in custom namespace"
        )
        assert len([b for b in custom_blocks.blocks if b.id == result_legacy.id]) == 0, (
            "Legacy block incorrectly found in custom namespace"
        )

    def test_create_work_item_agent_default_namespace(self, mock_memory_bank):
        """Test CreateWorkItem with default namespace"""
        from infra_core.memory_system.tools.agent_facing.create_work_item_tool import (
            create_work_item,
            CreateWorkItemInput,
        )

        # Create work item without specifying namespace_id (should default to 'legacy')
        result = create_work_item(
            CreateWorkItemInput(
                type="task",
                title="Test Task",
                description="Test task description",
                acceptance_criteria=["Criteria 1", "Criteria 2"],
            ),
            mock_memory_bank,
        )

        assert result.success, f"CreateWorkItem failed: {result.error}"
        assert result.id is not None, "Work item ID should not be None"

        # Verify the work item was created in legacy namespace
        retrieved = get_memory_block_core(
            GetMemoryBlockInput(block_ids=[result.id]), mock_memory_bank
        )
        assert retrieved.success, "Failed to retrieve created work item"
        assert len(retrieved.blocks) == 1, "Should retrieve exactly one work item"
        assert retrieved.blocks[0].namespace_id == "legacy", (
            f"Expected 'legacy' namespace, got '{retrieved.blocks[0].namespace_id}'"
        )

    def test_create_work_item_agent_custom_namespace(self, mock_memory_bank):
        """Test CreateWorkItem with custom namespace"""
        from infra_core.memory_system.tools.agent_facing.create_work_item_tool import (
            create_work_item,
            CreateWorkItemInput,
        )

        # Create work item with custom namespace
        result = create_work_item(
            CreateWorkItemInput(
                type="epic",
                title="Test Epic",
                description="Test epic description",
                acceptance_criteria=["Epic criteria"],
                namespace_id="custom-workspace",
                owner="test-owner",
            ),
            mock_memory_bank,
        )

        assert result.success, f"CreateWorkItem failed: {result.error}"
        assert result.id is not None, "Work item ID should not be None"

        # Verify the work item was created in custom namespace
        retrieved = get_memory_block_core(
            GetMemoryBlockInput(block_ids=[result.id]), mock_memory_bank
        )
        assert retrieved.success, "Failed to retrieve created work item"
        assert len(retrieved.blocks) == 1, "Should retrieve exactly one work item"
        assert retrieved.blocks[0].namespace_id == "custom-workspace", (
            f"Expected 'custom-workspace' namespace, got '{retrieved.blocks[0].namespace_id}'"
        )

    def test_create_work_item_namespace_isolation(self, mock_memory_bank):
        """Test that work items in different namespaces are properly isolated"""
        from infra_core.memory_system.tools.agent_facing.create_work_item_tool import (
            create_work_item,
            CreateWorkItemInput,
        )

        # Create work item in default namespace
        result_legacy = create_work_item(
            CreateWorkItemInput(
                type="task",
                title="Legacy Task",
                description="Task in legacy namespace",
                acceptance_criteria=["Done"],
            ),
            mock_memory_bank,
        )
        assert result_legacy.success, f"Failed to create legacy work item: {result_legacy.error}"

        # Create work item in custom namespace
        result_custom = create_work_item(
            CreateWorkItemInput(
                type="task",
                title="Custom Task",
                description="Task in custom namespace",
                acceptance_criteria=["Done"],
                namespace_id="custom-project",
            ),
            mock_memory_bank,
        )
        assert result_custom.success, f"Failed to create custom work item: {result_custom.error}"

        # Verify namespace isolation - legacy namespace should only see legacy work item
        legacy_blocks = get_memory_block_core(
            GetMemoryBlockInput(type_filter="task", namespace_id="legacy"), mock_memory_bank
        )
        assert legacy_blocks.success, "Failed to query legacy namespace"
        legacy_ids = [b.id for b in legacy_blocks.blocks]
        assert result_legacy.id in legacy_ids, "Legacy work item not found in legacy namespace"
        assert result_custom.id not in legacy_ids, (
            "Custom work item incorrectly found in legacy namespace"
        )

        # Verify namespace isolation - custom namespace should only see custom work item
        custom_blocks = get_memory_block_core(
            GetMemoryBlockInput(type_filter="task", namespace_id="custom-project"), mock_memory_bank
        )
        assert custom_blocks.success, "Failed to query custom namespace"
        custom_ids = [b.id for b in custom_blocks.blocks]
        assert result_custom.id in custom_ids, "Custom work item not found in custom namespace"
        assert result_legacy.id not in custom_ids, (
            "Legacy work item incorrectly found in custom namespace"
        )
