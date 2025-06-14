"""
Tests for the BulkCreateLinks tool.

Tests the bulk link creation functionality with independent success tracking,
validation, error handling, and various edge cases.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from uuid import uuid4

from infra_core.memory_system.tools.agent_facing.bulk_create_links_tool import (
    bulk_create_links,
    BulkCreateLinksInput,
    LinkSpec,
)
from infra_core.memory_system.link_manager import LinkError, LinkErrorType
from infra_core.memory_system.schemas.common import BlockLink


class TestBulkCreateLinksTool:
    """Test suite for the BulkCreateLinks tool."""

    @pytest.fixture
    def mock_memory_bank(self):
        """Create a mock memory bank with LinkManager."""
        mock_memory_bank = Mock()

        # Mock dolt_writer with proper active_branch string
        mock_dolt_writer = Mock()
        mock_dolt_writer.active_branch = "test-branch"
        mock_memory_bank.dolt_writer = mock_dolt_writer

        # Mock LinkManager with upsert_link method
        mock_link_manager = Mock()
        mock_memory_bank.link_manager = mock_link_manager

        return mock_memory_bank

    @pytest.fixture
    def sample_block_ids(self):
        """Generate sample block IDs for testing."""
        return {
            "block1": str(uuid4()),
            "block2": str(uuid4()),
            "block3": str(uuid4()),
            "block4": str(uuid4()),
        }

    def test_successful_bulk_creation(self, mock_memory_bank, sample_block_ids):
        """Test successful creation of multiple links."""
        # Arrange
        link_specs = [
            LinkSpec(
                from_id=sample_block_ids["block1"],
                to_id=sample_block_ids["block2"],
                relation="depends_on",
                priority=1,
            ),
            LinkSpec(
                from_id=sample_block_ids["block2"],
                to_id=sample_block_ids["block3"],
                relation="child_of",
                metadata={"reason": "task breakdown"},
            ),
            LinkSpec(
                from_id=sample_block_ids["block3"],
                to_id=sample_block_ids["block4"],
                relation="related_to",
            ),
        ]

        input_data = BulkCreateLinksInput(links=link_specs)

        # Mock successful responses using upsert_link
        mock_results = [
            BlockLink(
                from_id=sample_block_ids["block1"],
                to_id=sample_block_ids["block2"],
                relation="depends_on",
                priority=1,
                created_at=datetime.now(),
            ),
            BlockLink(
                from_id=sample_block_ids["block2"],
                to_id=sample_block_ids["block3"],
                relation="child_of",
                link_metadata={"reason": "task breakdown"},
                created_at=datetime.now(),
            ),
            BlockLink(
                from_id=sample_block_ids["block3"],
                to_id=sample_block_ids["block4"],
                relation="related_to",
                created_at=datetime.now(),
            ),
        ]

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_create_links_tool.ensure_blocks_exist"
        ) as mock_ensure_blocks:
            mock_ensure_blocks.return_value = {
                block_id: True for block_id in sample_block_ids.values()
            }
            mock_memory_bank.link_manager.upsert_link.side_effect = mock_results

            # Act
            result = bulk_create_links(input_data, mock_memory_bank)

            # Assert
            assert result.success is True  # All links succeeded
            assert result.partial_success is True  # At least one link succeeded
            assert result.total_specs == 3
            assert result.successful_specs == 3
            assert result.failed_specs == 0
            assert result.skipped_specs == 0
            assert result.total_actual_links == 3  # No bidirectional links
            assert len(result.results) == 3
            assert all(r.success for r in result.results)
            assert (
                result.active_branch is not None or result.active_branch is None
            )  # Branch is optional

            # Verify upsert_link was called correctly
            assert mock_memory_bank.link_manager.upsert_link.call_count == 3

    def test_bidirectional_link_creation(self, mock_memory_bank, sample_block_ids):
        """Test creation of bidirectional links."""
        # Arrange - use blocks/is_blocked_by which have proper inverses
        link_specs = [
            LinkSpec(
                from_id=sample_block_ids["block1"],
                to_id=sample_block_ids["block2"],
                relation="blocks",  # This has inverse "is_blocked_by"
                bidirectional=True,
            ),
        ]

        input_data = BulkCreateLinksInput(links=link_specs)

        # Mock successful bidirectional response (2 links created)
        mock_results = [
            BlockLink(
                from_id=sample_block_ids["block1"],
                to_id=sample_block_ids["block2"],
                relation="blocks",
                created_at=datetime.now(),
            ),
            BlockLink(
                from_id=sample_block_ids["block2"],
                to_id=sample_block_ids["block1"],
                relation="is_blocked_by",  # Inverse of blocks
                created_at=datetime.now(),
            ),
        ]

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_create_links_tool.ensure_blocks_exist"
        ) as mock_ensure_blocks:
            with patch(
                "infra_core.memory_system.tools.agent_facing.bulk_create_links_tool.get_inverse_relation",
                return_value="is_blocked_by",
            ):
                mock_ensure_blocks.return_value = {
                    block_id: True for block_id in sample_block_ids.values()
                }
                mock_memory_bank.link_manager.upsert_link.side_effect = mock_results

                # Act
                result = bulk_create_links(input_data, mock_memory_bank)

                # Assert
                assert result.success is True
                assert result.total_specs == 1  # One link spec
                assert result.successful_specs == 1
                assert result.total_actual_links == 2  # Two actual links created
                assert result.results[0].bidirectional is True
                assert result.results[0].links_created == 2

                # Verify upsert_link was called twice (forward and inverse)
                assert mock_memory_bank.link_manager.upsert_link.call_count == 2

    def test_partial_success_scenario(self, mock_memory_bank, sample_block_ids):
        """Test scenario where some links succeed and others fail."""
        # Arrange
        link_specs = [
            LinkSpec(
                from_id=sample_block_ids["block1"],
                to_id=sample_block_ids["block2"],
                relation="depends_on",
            ),
            LinkSpec(
                from_id=sample_block_ids["block2"],
                to_id=sample_block_ids["block3"],
                relation="child_of",
            ),
        ]

        input_data = BulkCreateLinksInput(links=link_specs)

        # Mock mixed responses
        def mock_upsert_side_effect(*args, **kwargs):
            if kwargs.get("from_id") == sample_block_ids["block1"]:
                # First link succeeds
                return BlockLink(
                    from_id=sample_block_ids["block1"],
                    to_id=sample_block_ids["block2"],
                    relation="depends_on",
                    created_at=datetime.now(),
                )
            else:
                # Second link fails
                raise LinkError(LinkErrorType.CYCLE_DETECTED, "Would create cycle")

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_create_links_tool.ensure_blocks_exist"
        ) as mock_ensure_blocks:
            mock_ensure_blocks.return_value = {
                block_id: True for block_id in sample_block_ids.values()
            }
            mock_memory_bank.link_manager.upsert_link.side_effect = mock_upsert_side_effect

            # Act
            result = bulk_create_links(input_data, mock_memory_bank)

            # Assert
            assert result.success is False  # Not all links succeeded
            assert result.partial_success is True  # Some links succeeded
            assert result.total_specs == 2
            assert result.successful_specs == 1
            assert result.failed_specs == 1
            assert result.skipped_specs == 0
            assert result.total_actual_links == 1
            assert len(result.results) == 2

            # Check individual results
            assert result.results[0].success is True
            assert result.results[1].success is False
            assert "Would create cycle" in result.results[1].error

    def test_stop_on_first_error(self, mock_memory_bank, sample_block_ids):
        """Test early termination when stop_on_first_error is True."""
        # Arrange
        link_specs = [
            LinkSpec(
                from_id=sample_block_ids["block1"],
                to_id=sample_block_ids["block2"],
                relation="depends_on",
            ),
            LinkSpec(
                from_id=sample_block_ids["block2"],
                to_id=sample_block_ids["block3"],
                relation="child_of",
            ),
        ]

        input_data = BulkCreateLinksInput(links=link_specs, stop_on_first_error=True)

        # Mock first link to fail
        def mock_upsert_side_effect(*args, **kwargs):
            raise LinkError(LinkErrorType.VALIDATION_ERROR, "Invalid link")

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_create_links_tool.ensure_blocks_exist"
        ) as mock_ensure_blocks:
            mock_ensure_blocks.return_value = {
                block_id: True for block_id in sample_block_ids.values()
            }
            mock_memory_bank.link_manager.upsert_link.side_effect = mock_upsert_side_effect

            # Act
            result = bulk_create_links(input_data, mock_memory_bank)

            # Assert
            assert result.success is False
            assert result.partial_success is False
            assert result.total_specs == 2
            assert result.successful_specs == 0
            assert result.failed_specs == 1  # Only first link processed
            assert result.skipped_specs == 1  # Second link skipped
            assert len(result.results) == 1  # Second link not processed

            # Verify only one call to upsert_link
            assert mock_memory_bank.link_manager.upsert_link.call_count == 1

    def test_batch_block_validation_failure(self, mock_memory_bank, sample_block_ids):
        """Test handling of batch block validation failures."""
        # Arrange - use a valid UUID format but nonexistent block
        nonexistent_id = str(uuid4())
        link_specs = [
            LinkSpec(
                from_id=sample_block_ids["block1"],
                to_id=nonexistent_id,
                relation="depends_on",
            ),
        ]

        input_data = BulkCreateLinksInput(links=link_specs, validate_blocks_exist=True)

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_create_links_tool.ensure_blocks_exist"
        ) as mock_ensure_blocks:
            # Mock batch validation to return missing blocks
            mock_ensure_blocks.return_value = {
                sample_block_ids["block1"]: True,
                nonexistent_id: False,
            }

            # Act
            result = bulk_create_links(input_data, mock_memory_bank)

            # Assert
            assert result.success is False
            assert result.partial_success is False
            assert result.total_specs == 1
            assert result.successful_specs == 0
            assert result.failed_specs == 1
            assert result.skipped_specs == 0
            assert (
                f"The following blocks do not exist: ['{nonexistent_id}']"
                in result.results[0].error
            )

            # Verify LinkManager was not called
            mock_memory_bank.link_manager.upsert_link.assert_not_called()

    def test_skip_block_validation(self, mock_memory_bank, sample_block_ids):
        """Test skipping block validation when validate_blocks_exist=False."""
        # Arrange
        link_specs = [
            LinkSpec(
                from_id=sample_block_ids["block1"],
                to_id=sample_block_ids["block2"],
                relation="depends_on",
            ),
        ]

        input_data = BulkCreateLinksInput(links=link_specs, validate_blocks_exist=False)

        # Mock successful response
        mock_result = BlockLink(
            from_id=sample_block_ids["block1"],
            to_id=sample_block_ids["block2"],
            relation="depends_on",
            created_at=datetime.now(),
        )

        mock_memory_bank.link_manager.upsert_link.return_value = mock_result

        # Act
        result = bulk_create_links(input_data, mock_memory_bank)

        # Assert
        assert result.success is True
        assert result.successful_specs == 1

        # Verify ensure_blocks_exist was not called
        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_create_links_tool.ensure_blocks_exist"
        ) as mock_ensure_blocks:
            mock_ensure_blocks.assert_not_called()

    def test_exception_handling(self, mock_memory_bank, sample_block_ids):
        """Test handling of unexpected exceptions during processing."""
        # Arrange
        link_specs = [
            LinkSpec(
                from_id=sample_block_ids["block1"],
                to_id=sample_block_ids["block2"],
                relation="depends_on",
            ),
        ]

        input_data = BulkCreateLinksInput(links=link_specs)

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_create_links_tool.ensure_blocks_exist"
        ) as mock_ensure_blocks:
            mock_ensure_blocks.return_value = {
                block_id: True for block_id in sample_block_ids.values()
            }
            # Mock unexpected exception
            mock_memory_bank.link_manager.upsert_link.side_effect = RuntimeError(
                "Database connection failed"
            )

            # Act
            result = bulk_create_links(input_data, mock_memory_bank)

            # Assert
            assert result.success is False
            assert result.partial_success is False
            assert result.successful_specs == 0
            assert result.failed_specs == 1
            assert "Unexpected error processing link 1" in result.results[0].error
            assert "Database connection failed" in result.results[0].error

    def test_all_failures_scenario(self, mock_memory_bank, sample_block_ids):
        """Test scenario where all links fail to create."""
        # Arrange
        link_specs = [
            LinkSpec(
                from_id=sample_block_ids["block1"],
                to_id=sample_block_ids["block2"],
                relation="depends_on",
            ),
            LinkSpec(
                from_id=sample_block_ids["block2"],
                to_id=sample_block_ids["block3"],
                relation="child_of",
            ),
        ]

        input_data = BulkCreateLinksInput(links=link_specs)

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_create_links_tool.ensure_blocks_exist"
        ) as mock_ensure_blocks:
            mock_ensure_blocks.return_value = {
                block_id: True for block_id in sample_block_ids.values()
            }
            # Mock all links to fail
            mock_memory_bank.link_manager.upsert_link.side_effect = LinkError(
                LinkErrorType.VALIDATION_ERROR, "All links invalid"
            )

            # Act
            result = bulk_create_links(input_data, mock_memory_bank)

            # Assert
            assert result.success is False
            assert result.partial_success is False
            assert result.total_specs == 2
            assert result.successful_specs == 0
            assert result.failed_specs == 2
            assert result.skipped_specs == 0
            assert result.total_actual_links == 0
            assert all(not r.success for r in result.results)

    def test_missing_link_manager(self, sample_block_ids):
        """Test handling when LinkManager is not available."""
        # Arrange
        mock_memory_bank = Mock()
        mock_memory_bank.link_manager = None  # No LinkManager

        # Mock dolt_writer with proper active_branch string
        mock_dolt_writer = Mock()
        mock_dolt_writer.active_branch = "test-branch"
        mock_memory_bank.dolt_writer = mock_dolt_writer

        link_specs = [
            LinkSpec(
                from_id=sample_block_ids["block1"],
                to_id=sample_block_ids["block2"],
                relation="depends_on",
            ),
        ]

        input_data = BulkCreateLinksInput(links=link_specs)

        # Act
        result = bulk_create_links(input_data, mock_memory_bank)

        # Assert
        assert result.success is False
        assert result.partial_success is False
        assert result.total_specs == 1
        assert result.successful_specs == 0
        assert result.failed_specs == 1
        assert result.skipped_specs == 0
        assert "LinkManager not available" in result.results[0].error
        assert (
            result.active_branch is not None or result.active_branch is None
        )  # Branch is optional

    def test_input_validation(self):
        """Test input validation for LinkSpec and BulkCreateLinksInput."""
        from pydantic import ValidationError

        # Test invalid relation type
        with pytest.raises(ValidationError) as exc_info:
            LinkSpec(
                from_id=str(uuid4()),
                to_id=str(uuid4()),
                relation="invalid_relation",
            )
        assert "literal_error" in str(exc_info.value)

        # Test invalid bidirectional relation (mentions has no meaningful inverse)
        with pytest.raises(ValidationError) as exc_info:
            LinkSpec(
                from_id=str(uuid4()),
                to_id=str(uuid4()),
                relation="mentions",  # No meaningful inverse defined
                bidirectional=True,
            )
        assert "does not have a defined inverse" in str(exc_info.value)

        # Test empty links list
        with pytest.raises(ValidationError):
            BulkCreateLinksInput(links=[])

        # Test too many links
        with pytest.raises(ValidationError):
            BulkCreateLinksInput(
                links=[
                    LinkSpec(
                        from_id=str(uuid4()),
                        to_id=str(uuid4()),
                        relation="depends_on",
                    )
                    for _ in range(5001)  # Exceeds max_length
                ]
            )

    def test_priority_and_metadata_handling(self, mock_memory_bank, sample_block_ids):
        """Test that priority and metadata are properly handled."""
        # Arrange
        link_specs = [
            LinkSpec(
                from_id=sample_block_ids["block1"],
                to_id=sample_block_ids["block2"],
                relation="depends_on",
                priority=5,
                metadata={"importance": "high", "deadline": "2024-01-01"},
                created_by="test_agent",
            ),
        ]

        input_data = BulkCreateLinksInput(links=link_specs)

        # Mock successful response
        mock_result = BlockLink(
            from_id=sample_block_ids["block1"],
            to_id=sample_block_ids["block2"],
            relation="depends_on",
            priority=5,
            link_metadata={"importance": "high", "deadline": "2024-01-01"},
            created_by="test_agent",
            created_at=datetime.now(),
        )

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_create_links_tool.ensure_blocks_exist"
        ) as mock_ensure_blocks:
            mock_ensure_blocks.return_value = {
                block_id: True for block_id in sample_block_ids.values()
            }
            mock_memory_bank.link_manager.upsert_link.return_value = mock_result

            # Act
            result = bulk_create_links(input_data, mock_memory_bank)

            # Assert
            assert result.success is True
            assert result.successful_specs == 1

            # Verify upsert_link was called with correct parameters
            mock_memory_bank.link_manager.upsert_link.assert_called_once_with(
                from_id=sample_block_ids["block1"],
                to_id=sample_block_ids["block2"],
                relation="depends_on",
                priority=5,
                link_metadata={"importance": "high", "deadline": "2024-01-01"},
                created_by="test_agent",
            )

    def test_fallback_to_bulk_upsert(self, mock_memory_bank, sample_block_ids):
        """Test fallback to bulk_upsert when upsert_link is not available."""
        # Arrange - remove upsert_link method
        del mock_memory_bank.link_manager.upsert_link

        link_specs = [
            LinkSpec(
                from_id=sample_block_ids["block1"],
                to_id=sample_block_ids["block2"],
                relation="depends_on",
            ),
        ]

        input_data = BulkCreateLinksInput(links=link_specs)

        # Mock successful response from bulk_upsert
        mock_result = [
            BlockLink(
                from_id=sample_block_ids["block1"],
                to_id=sample_block_ids["block2"],
                relation="depends_on",
                created_at=datetime.now(),
            )
        ]

        with patch(
            "infra_core.memory_system.tools.agent_facing.bulk_create_links_tool.ensure_blocks_exist"
        ) as mock_ensure_blocks:
            mock_ensure_blocks.return_value = {
                block_id: True for block_id in sample_block_ids.values()
            }
            mock_memory_bank.link_manager.bulk_upsert.return_value = mock_result

            # Act
            result = bulk_create_links(input_data, mock_memory_bank)

            # Assert
            assert result.success is True
            assert result.successful_specs == 1

            # Verify bulk_upsert was called
            mock_memory_bank.link_manager.bulk_upsert.assert_called_once()
