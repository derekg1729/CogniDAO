"""
Tests for the Dolt to LlamaIndex synchronization script.

This module contains both unit tests (with mocks) and integration tests for
the sync_dolt_to_llamaindex script.
"""

import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path
import logging
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, call
import importlib

# Configure logging for tests
logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Add project root to path for imports
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent.parent.parent  # Navigate up to project root
sys.path.insert(0, str(project_root))

# Skip tests if doltpy not available (optional dependency)
# try:
#     from doltpy.cli import Dolt
#     DOLTPY_AVAILABLE = True
# except ImportError:
#     DOLTPY_AVAILABLE = False
DOLTPY_AVAILABLE = importlib.util.find_spec("doltpy") is not None

# Local imports
from infra_core.memory_system.schemas.memory_block import MemoryBlock, BlockLink, ConfidenceScore  # noqa: E402
from infra_core.memory_system.scripts.sync_dolt_to_llamaindex import sync_dolt_to_llamaindex  # noqa: E402


def create_test_blocks():
    """Create sample memory blocks for testing."""
    blocks = []

    # Block 1: Basic block with tags
    blocks.append(
        MemoryBlock(
            id="test-block-1",
            type="doc",
            schema_version=1,
            text="This is a test document for syncing. It contains important information about the system.",
            tags=["test", "documentation", "sync"],
            metadata={"title": "Test Document 1", "importance": "high"},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            created_by="test_system",
        )
    )

    # Block 2: Block with links to Block 1
    blocks.append(
        MemoryBlock(
            id="test-block-2",
            type="knowledge",
            schema_version=1,
            text="This block links to the documentation. The document explains key concepts.",
            tags=["knowledge", "references"],
            metadata={"title": "Knowledge Block 2", "source": "internal"},
            links=[BlockLink(to_id="test-block-1", relation="related_to")],
            confidence=ConfidenceScore(ai=0.8, human=0.9),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            created_by="test_system",
        )
    )

    # Block 3: Another block with links to both previous blocks
    blocks.append(
        MemoryBlock(
            id="test-block-3",
            type="task",
            schema_version=1,
            text="Implement the synchronization system and verify it works with all block types.",
            tags=["task", "implementation"],
            metadata={"title": "Task: Implement Sync", "status": "in_progress", "priority": "high"},
            links=[
                BlockLink(to_id="test-block-1", relation="depends_on"),
                BlockLink(to_id="test-block-2", relation="related_to"),
            ],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            created_by="test_system",
        )
    )

    return blocks


# Module-level patching to avoid real implementations from being called
@patch("infra_core.memory_system.scripts.sync_dolt_to_llamaindex.read_memory_blocks")
@patch("infra_core.memory_system.scripts.sync_dolt_to_llamaindex.LlamaMemory")
class TestSyncDoltToLlamaIndexUnit(unittest.TestCase):
    """
    Unit tests for the sync_dolt_to_llamaindex script.
    These tests use mocks to isolate testing from external dependencies.
    """

    def setUp(self):
        """Set up test environment with temporary directory for LlamaIndex storage."""
        self.temp_dir = tempfile.mkdtemp()
        self.llama_dir = os.path.join(self.temp_dir, "llama_storage")
        self.dolt_dir = "/fake/dolt/path"  # Mock path, not used with real Dolt
        self.test_blocks = create_test_blocks()

    def tearDown(self):
        """Clean up temporary directories."""
        shutil.rmtree(self.temp_dir)

    def test_successful_sync(self, mock_llama_memory_class, mock_read_blocks):
        """Test successful synchronization with all valid blocks."""
        # Setup mocks
        mock_read_blocks.return_value = self.test_blocks

        mock_memory = MagicMock()
        mock_memory.is_ready.return_value = True
        mock_llama_memory_class.return_value = mock_memory

        # Call the sync function
        result = sync_dolt_to_llamaindex(
            dolt_db_path=self.dolt_dir, llama_storage_path=self.llama_dir
        )

        # Verify success
        self.assertTrue(result, "Sync should report success")

        # Verify that read_memory_blocks was called correctly
        mock_read_blocks.assert_called_once_with(self.dolt_dir, branch="main")

        # Verify that LlamaMemory was initialized correctly
        mock_llama_memory_class.assert_called_once_with(chroma_path=self.llama_dir)

        # Verify that each block was added to the memory
        self.assertEqual(
            mock_memory.add_block.call_count,
            3,
            "Should call add_block for each of the 3 test blocks",
        )

        # Verify the blocks were added in the right order
        for i, block in enumerate(self.test_blocks):
            args, _ = mock_memory.add_block.call_args_list[i]
            self.assertEqual(
                args[0].id, block.id, f"Block at position {i} should have ID {block.id}"
            )

    def test_empty_dolt_db(self, mock_llama_memory_class, mock_read_blocks):
        """Test sync with an empty Dolt database (no blocks)."""
        # Setup mocks
        mock_read_blocks.return_value = []

        mock_memory = MagicMock()
        mock_memory.is_ready.return_value = True
        mock_llama_memory_class.return_value = mock_memory

        # Call the sync function
        result = sync_dolt_to_llamaindex(
            dolt_db_path=self.dolt_dir, llama_storage_path=self.llama_dir
        )

        # Verify success (even with empty DB)
        self.assertTrue(result, "Sync should report success with empty DB")

        # Verify that add_block was never called (no blocks to add)
        mock_memory.add_block.assert_not_called()

    def test_llama_memory_not_ready(self, mock_llama_memory_class, mock_read_blocks):
        """Test handling of LlamaMemory initialization failure."""
        # Setup mock - LlamaMemory.is_ready() returns False
        mock_memory = MagicMock()
        mock_memory.is_ready.return_value = False
        mock_llama_memory_class.return_value = mock_memory

        # Call the sync function
        result = sync_dolt_to_llamaindex(
            dolt_db_path=self.dolt_dir, llama_storage_path=self.llama_dir
        )

        # Verify the function returns False when LlamaMemory is not ready
        self.assertFalse(result, "Sync should report failure if LlamaMemory not ready")

        # Verify that read_memory_blocks was not called (short-circuit)
        mock_read_blocks.assert_not_called()

    def test_block_indexing_error(self, mock_llama_memory_class, mock_read_blocks):
        """Test handling of errors during block indexing."""
        # Setup mocks
        mock_read_blocks.return_value = self.test_blocks

        # Create a mock LlamaMemory instance that throws an exception on the second add_block call
        mock_memory = MagicMock()
        mock_memory.is_ready.return_value = True
        mock_memory.add_block.side_effect = [None, Exception("Test indexing error"), None]
        mock_llama_memory_class.return_value = mock_memory

        # Call the sync function
        result = sync_dolt_to_llamaindex(
            dolt_db_path=self.dolt_dir, llama_storage_path=self.llama_dir
        )

        # Verify failure
        self.assertFalse(result, "Sync should report failure if any block fails during indexing")

        # Verify all blocks were attempted
        expected_calls = [call(block) for block in self.test_blocks]
        mock_memory.add_block.assert_has_calls(expected_calls, any_order=False)

        # Verify mocks were called the expected number of times
        self.assertEqual(
            mock_memory.add_block.call_count, 3, "Should try to add all blocks even after error"
        )


@unittest.skipIf(not DOLTPY_AVAILABLE, "doltpy not installed, skipping integration tests")
class TestSyncDoltToLlamaIndexIntegration(unittest.TestCase):
    """
    Integration tests for the Dolt to LlamaIndex sync process.
    These tests use actual Dolt databases and LlamaIndex storage.

    Note: These tests are currently skipped as they require more complex setup.
    When implementing integration tests, ensure proper cleanup between runs.
    """

    @unittest.skip("Integration tests require more complex setup")
    def test_end_to_end(self):
        """
        Basic test showing how an end-to-end integration test would work.
        This is a placeholder and should be implemented when integration testing is needed.
        """
        # This would set up a real Dolt database and perform an actual sync
        pass


if __name__ == "__main__":
    unittest.main()
