"""
Tests for the GetMemoryLinks core tool.
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime

from infra_core.memory_system.tools.memory_core.get_memory_links_core import (
    GetMemoryLinksInput,
    get_memory_links_core,
)
from infra_core.memory_system.schemas.common import BlockLink
from infra_core.memory_system.link_manager import LinkQueryResult
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank


@pytest.fixture
def mock_memory_bank():
    """Create a mock StructuredMemoryBank."""
    bank = MagicMock(spec=StructuredMemoryBank)
    mock_link_manager = MagicMock()
    bank.link_manager = mock_link_manager
    return bank


@pytest.fixture
def sample_input():
    """Create a sample input for testing."""
    return GetMemoryLinksInput(relation_filter="depends_on", limit=10)


@pytest.fixture
def sample_block_link():
    """Create a sample BlockLink for testing."""
    return BlockLink(
        from_id="test-block-123",
        to_id="test-block-456",
        relation="depends_on",
        priority=1,
        link_metadata={"test": "data"},
        created_at=datetime.now(),
    )


class TestGetMemoryLinksCore:
    """Test suite for the core get_memory_links function."""

    def test_get_memory_links_success(self, mock_memory_bank, sample_input, sample_block_link):
        """Test successful memory links retrieval."""
        # Configure mock to return the sample link
        mock_result = LinkQueryResult(links=[sample_block_link], next_cursor=None)
        mock_memory_bank.link_manager.get_all_links.return_value = mock_result

        # Call the function
        result = get_memory_links_core(sample_input, mock_memory_bank)

        # Verify success
        assert result.success is True
        assert len(result.links) == 1
        assert result.links[0] == sample_block_link
        assert result.error is None
        assert result.next_cursor is None

        # Verify the mock was called correctly
        mock_memory_bank.link_manager.get_all_links.assert_called_once()
        call_args = mock_memory_bank.link_manager.get_all_links.call_args[1]
        assert "query" in call_args

    def test_get_memory_links_no_filters(self, mock_memory_bank, sample_block_link):
        """Test retrieval with no filters (all links)."""
        # Configure mock to return the sample link
        mock_result = LinkQueryResult(links=[sample_block_link], next_cursor=None)
        mock_memory_bank.link_manager.get_all_links.return_value = mock_result

        # Test input with no filters
        input_data = GetMemoryLinksInput()
        result = get_memory_links_core(input_data, mock_memory_bank)

        # Verify success
        assert result.success is True
        assert len(result.links) == 1
        assert result.links[0] == sample_block_link
        assert result.error is None

        # Verify the mock was called correctly
        mock_memory_bank.link_manager.get_all_links.assert_called_once()

    def test_get_memory_links_with_cursor(self, mock_memory_bank, sample_block_link):
        """Test retrieval with pagination cursor."""
        # Configure mock to return the sample link with next cursor
        mock_result = LinkQueryResult(links=[sample_block_link], next_cursor="next_page_123")
        mock_memory_bank.link_manager.get_all_links.return_value = mock_result

        # Test input with cursor
        input_data = GetMemoryLinksInput(cursor="page_123", limit=5)
        result = get_memory_links_core(input_data, mock_memory_bank)

        # Verify success
        assert result.success is True
        assert len(result.links) == 1
        assert result.links[0] == sample_block_link
        assert result.next_cursor == "next_page_123"
        assert result.error is None

        # Verify the mock was called correctly
        mock_memory_bank.link_manager.get_all_links.assert_called_once()

    def test_get_memory_links_empty_result(self, mock_memory_bank):
        """Test successful retrieval with no links found."""
        # Configure mock to return empty result
        mock_result = LinkQueryResult(links=[], next_cursor=None)
        mock_memory_bank.link_manager.get_all_links.return_value = mock_result

        # Test input with a valid but uncommon relation type
        input_data = GetMemoryLinksInput(relation_filter="mentions")  # Valid relation that won't exist
        result = get_memory_links_core(input_data, mock_memory_bank)

        # Verify success with empty result
        assert result.success is True
        assert len(result.links) == 0
        assert result.error is None
        assert result.next_cursor is None

    def test_get_memory_links_no_link_manager(self):
        """Test handling when memory bank has no link_manager."""
        # Create a mock memory bank without link_manager
        mock_memory_bank = MagicMock()
        del mock_memory_bank.link_manager  # Remove the attribute

        input_data = GetMemoryLinksInput()
        result = get_memory_links_core(input_data, mock_memory_bank)

        # Verify failure
        assert result.success is False
        assert "does not have a link_manager" in result.error
        assert len(result.links) == 0

    def test_get_memory_links_exception_handling(self, mock_memory_bank):
        """Test exception handling in link retrieval."""
        # Configure mock to raise an exception
        mock_memory_bank.link_manager.get_all_links.side_effect = Exception("Database error")

        input_data = GetMemoryLinksInput()
        result = get_memory_links_core(input_data, mock_memory_bank)

        # Verify error handling
        assert result.success is False
        assert "Database error" in result.error
        assert len(result.links) == 0

    def test_get_memory_links_relation_filter(self, mock_memory_bank, sample_block_link):
        """Test retrieval with specific relation filter."""
        # Configure mock to return the sample link
        mock_result = LinkQueryResult(links=[sample_block_link], next_cursor=None)
        mock_memory_bank.link_manager.get_all_links.return_value = mock_result

        # Test input with relation filter
        input_data = GetMemoryLinksInput(relation_filter="subtask_of")
        result = get_memory_links_core(input_data, mock_memory_bank)

        # Verify success
        assert result.success is True
        assert len(result.links) == 1
        assert result.links[0] == sample_block_link

        # Verify the mock was called with relation filter
        mock_memory_bank.link_manager.get_all_links.assert_called_once()

    def test_get_memory_links_limit_validation(self, mock_memory_bank):
        """Test limit parameter validation."""
        # Test valid limit
        input_data = GetMemoryLinksInput(limit=500)
        assert input_data.limit == 500

        # Test minimum limit validation
        with pytest.raises(ValueError):
            GetMemoryLinksInput(limit=0)

        # Test maximum limit validation
        with pytest.raises(ValueError):
            GetMemoryLinksInput(limit=1001)

    def test_get_memory_links_multiple_filters(self, mock_memory_bank, sample_block_link):
        """Test retrieval with multiple filters applied."""
        # Configure mock to return the sample link
        mock_result = LinkQueryResult(links=[sample_block_link], next_cursor="next_123")
        mock_memory_bank.link_manager.get_all_links.return_value = mock_result

        # Test input with multiple filters
        input_data = GetMemoryLinksInput(
            relation_filter="depends_on", limit=25, cursor="current_123"
        )
        result = get_memory_links_core(input_data, mock_memory_bank)

        # Verify success
        assert result.success is True
        assert len(result.links) == 1
        assert result.links[0] == sample_block_link
        assert result.next_cursor == "next_123"

        # Verify the mock was called
        mock_memory_bank.link_manager.get_all_links.assert_called_once()
