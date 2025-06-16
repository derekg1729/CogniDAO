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

        # Mock get_all_memory_blocks to return both blocks
        bank.get_all_memory_blocks.return_value = [legacy_block, user_block]

        # Mock query_semantic to return both blocks
        bank.query_semantic.return_value = [legacy_block, user_block]

        # Mock create_memory_block to succeed
        bank.create_memory_block.return_value = (True, None)
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
        """Test that namespace filtering provides proper isolation."""
        # Test that legacy namespace only sees legacy blocks
        legacy_input = GetMemoryBlockInput(type_filter="doc", namespace_id="legacy")
        legacy_result = get_memory_block_core(legacy_input, mock_memory_bank)

        # Test that user namespace only sees user blocks
        user_input = GetMemoryBlockInput(type_filter="doc", namespace_id="user-123")
        user_result = get_memory_block_core(user_input, mock_memory_bank)

        # Verify isolation
        assert legacy_result.success is True
        assert user_result.success is True
        assert len(legacy_result.blocks) == 1
        assert len(user_result.blocks) == 1
        assert legacy_result.blocks[0].namespace_id == "legacy"
        assert user_result.blocks[0].namespace_id == "user-123"

        # Verify no cross-contamination
        legacy_ids = {block.id for block in legacy_result.blocks}
        user_ids = {block.id for block in user_result.blocks}
        assert legacy_ids.isdisjoint(user_ids)
