"""
Tests for the auto_commit feature in StructuredMemoryBank.

This module tests that:
1. auto_commit=True (default) preserves existing behavior
2. auto_commit=False prevents commits while operations succeed
3. Both modes work correctly for create/update/delete operations
"""

import pytest
from unittest.mock import patch, MagicMock

from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.schemas.memory_block import MemoryBlock, ConfidenceScore
from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

# Mock data paths
MOCK_CHROMA_PATH = "/mock/chroma/path"
MOCK_COLLECTION = "mock_collection"


@pytest.fixture
def mock_llama_memory():
    """Create a mock LlamaMemory instance."""
    with patch("infra_core.memory_system.structured_memory_bank.LlamaMemory") as mock_llama:
        mock_instance = mock_llama.return_value
        mock_instance.is_ready.return_value = True
        mock_instance.add_block.return_value = None  # No return value
        mock_instance.update_block.return_value = None  # No return value
        mock_instance.delete_block.return_value = None  # No return value
        mock_instance.chroma_path = MOCK_CHROMA_PATH
        yield mock_instance


@pytest.fixture
def mock_dolt_writer():
    """Mock the DoltMySQLWriter for unit tests."""
    with patch(
        "infra_core.memory_system.structured_memory_bank.DoltMySQLWriter"
    ) as mock_writer_class:
        # Create a mock writer instance
        mock_writer = MagicMock()
        mock_writer.write_memory_block.return_value = (True, "mock_commit_hash")
        mock_writer.delete_memory_block.return_value = (True, "mock_delete_hash")
        mock_writer.commit_changes.return_value = (True, "mock_commit_hash")
        mock_writer.discard_changes.return_value = None

        # Make the class constructor return our mock instance
        mock_writer_class.return_value = mock_writer
        yield mock_writer


@pytest.fixture
def mock_dolt_reader():
    """Mock the DoltMySQLReader for unit tests."""
    with patch(
        "infra_core.memory_system.structured_memory_bank.DoltMySQLReader"
    ) as mock_reader_class:
        # Create a mock reader instance
        mock_reader = MagicMock()
        mock_reader.read_memory_block.return_value = None  # Default to no block found
        mock_reader.read_latest_schema_version.return_value = None  # No schema found
        mock_reader.read_block_proofs.return_value = []

        # Make the class constructor return our mock instance
        mock_reader_class.return_value = mock_reader
        yield mock_reader


@pytest.fixture
def mock_config():
    """Create a mock connection config."""
    return DoltConnectionConfig(
        host="localhost", port=3306, user="root", password="", database="test_db"
    )


@pytest.fixture
def sample_memory_block():
    """Provides a sample MemoryBlock for testing."""
    return MemoryBlock(
        id="test-auto-commit-block",
        type="knowledge",
        text="This is a test memory block for auto-commit testing.",
        tags=["test", "auto-commit"],
        metadata={"source": "pytest"},
        confidence=ConfidenceScore(human=0.9),
    )


class TestStructuredMemoryBankAutoCommit:
    """Test class for auto_commit functionality."""

    def test_auto_commit_true_create_block(
        self,
        mock_llama_memory,
        mock_dolt_writer,
        mock_dolt_reader,
        mock_config,
        sample_memory_block,
    ):
        """Test that auto_commit=True calls commit_changes during create operation."""
        # Create memory bank with auto_commit=True (default)
        bank = StructuredMemoryBank(
            chroma_path=MOCK_CHROMA_PATH,
            chroma_collection=MOCK_COLLECTION,
            dolt_connection_config=mock_config,
            branch="main",
            auto_commit=True,  # Explicit for clarity
        )

        # Verify the auto_commit setting
        assert bank.auto_commit is True

        # Execute create operation
        result = bank.create_memory_block(sample_memory_block)

        # Verify operation succeeded
        assert result is True

        # Verify that commit_changes was called
        mock_dolt_writer.commit_changes.assert_called_once()

        # Verify all expected operations were called
        mock_dolt_writer.write_memory_block.assert_called_once()
        mock_llama_memory.add_block.assert_called_once_with(sample_memory_block)

    def test_auto_commit_false_create_block(
        self,
        mock_llama_memory,
        mock_dolt_writer,
        mock_dolt_reader,
        mock_config,
        sample_memory_block,
    ):
        """Test that auto_commit=False does NOT call commit_changes during create operation."""
        # Create memory bank with auto_commit=False
        bank = StructuredMemoryBank(
            chroma_path=MOCK_CHROMA_PATH,
            chroma_collection=MOCK_COLLECTION,
            dolt_connection_config=mock_config,
            branch="main",
            auto_commit=False,  # Key test parameter
        )

        # Verify the auto_commit setting
        assert bank.auto_commit is False

        # Execute create operation
        result = bank.create_memory_block(sample_memory_block)

        # Verify operation succeeded
        assert result is True

        # Verify that commit_changes was NOT called
        mock_dolt_writer.commit_changes.assert_not_called()

        # Verify other operations were still called
        mock_dolt_writer.write_memory_block.assert_called_once()
        mock_llama_memory.add_block.assert_called_once_with(sample_memory_block)

    def test_auto_commit_true_update_block(
        self,
        mock_llama_memory,
        mock_dolt_writer,
        mock_dolt_reader,
        mock_config,
        sample_memory_block,
    ):
        """Test that auto_commit=True calls commit_changes during update operation."""
        # Create memory bank with auto_commit=True
        bank = StructuredMemoryBank(
            chroma_path=MOCK_CHROMA_PATH,
            chroma_collection=MOCK_COLLECTION,
            dolt_connection_config=mock_config,
            branch="main",
            auto_commit=True,
        )

        # Execute update operation
        result = bank.update_memory_block(sample_memory_block)

        # Verify operation succeeded
        assert result is True

        # Verify that commit_changes was called
        mock_dolt_writer.commit_changes.assert_called_once()

        # Verify all expected operations were called
        mock_dolt_writer.write_memory_block.assert_called_once()
        mock_llama_memory.update_block.assert_called_once_with(sample_memory_block)

    def test_auto_commit_false_update_block(
        self,
        mock_llama_memory,
        mock_dolt_writer,
        mock_dolt_reader,
        mock_config,
        sample_memory_block,
    ):
        """Test that auto_commit=False does NOT call commit_changes during update operation."""
        # Create memory bank with auto_commit=False
        bank = StructuredMemoryBank(
            chroma_path=MOCK_CHROMA_PATH,
            chroma_collection=MOCK_COLLECTION,
            dolt_connection_config=mock_config,
            branch="main",
            auto_commit=False,
        )

        # Execute update operation
        result = bank.update_memory_block(sample_memory_block)

        # Verify operation succeeded
        assert result is True

        # Verify that commit_changes was NOT called
        mock_dolt_writer.commit_changes.assert_not_called()

        # Verify other operations were still called
        mock_dolt_writer.write_memory_block.assert_called_once()
        mock_llama_memory.update_block.assert_called_once_with(sample_memory_block)

    def test_auto_commit_true_delete_block(
        self,
        mock_llama_memory,
        mock_dolt_writer,
        mock_dolt_reader,
        mock_config,
        sample_memory_block,
    ):
        """Test that auto_commit=True calls commit_changes during delete operation."""
        # Mock that the block exists
        mock_dolt_reader.read_memory_block.return_value = sample_memory_block

        # Create memory bank with auto_commit=True
        bank = StructuredMemoryBank(
            chroma_path=MOCK_CHROMA_PATH,
            chroma_collection=MOCK_COLLECTION,
            dolt_connection_config=mock_config,
            branch="main",
            auto_commit=True,
        )

        # Execute delete operation
        result = bank.delete_memory_block(sample_memory_block.id)

        # Verify operation succeeded
        assert result is True

        # Verify that commit_changes was called
        mock_dolt_writer.commit_changes.assert_called_once()

        # Verify all expected operations were called
        mock_dolt_writer.delete_memory_block.assert_called_once()
        mock_llama_memory.delete_block.assert_called_once_with(sample_memory_block.id)

    def test_auto_commit_false_delete_block(
        self,
        mock_llama_memory,
        mock_dolt_writer,
        mock_dolt_reader,
        mock_config,
        sample_memory_block,
    ):
        """Test that auto_commit=False does NOT call commit_changes during delete operation."""
        # Mock that the block exists
        mock_dolt_reader.read_memory_block.return_value = sample_memory_block

        # Create memory bank with auto_commit=False
        bank = StructuredMemoryBank(
            chroma_path=MOCK_CHROMA_PATH,
            chroma_collection=MOCK_COLLECTION,
            dolt_connection_config=mock_config,
            branch="main",
            auto_commit=False,
        )

        # Execute delete operation
        result = bank.delete_memory_block(sample_memory_block.id)

        # Verify operation succeeded
        assert result is True

        # Verify that commit_changes was NOT called
        mock_dolt_writer.commit_changes.assert_not_called()

        # Verify other operations were still called
        mock_dolt_writer.delete_memory_block.assert_called_once()
        mock_llama_memory.delete_block.assert_called_once_with(sample_memory_block.id)

    def test_auto_commit_default_is_false(
        self, mock_llama_memory, mock_dolt_writer, mock_dolt_reader, mock_config
    ):
        """Test that auto_commit defaults to False when not specified."""
        # Create memory bank without specifying auto_commit
        bank = StructuredMemoryBank(
            chroma_path=MOCK_CHROMA_PATH,
            chroma_collection=MOCK_COLLECTION,
            dolt_connection_config=mock_config,
            branch="main",
            # auto_commit not specified - should default to False
        )

        # Verify the default value
        assert bank.auto_commit is False

    def test_auto_commit_backward_compatibility(
        self,
        mock_llama_memory,
        mock_dolt_writer,
        mock_dolt_reader,
        mock_config,
        sample_memory_block,
    ):
        """Test that existing code without auto_commit parameter continues to work."""
        # Create memory bank using old-style constructor (without auto_commit parameter)
        bank = StructuredMemoryBank(
            chroma_path=MOCK_CHROMA_PATH,
            chroma_collection=MOCK_COLLECTION,
            dolt_connection_config=mock_config,
            # branch and auto_commit are optional parameters
        )

        # Verify backward compatibility: now defaults to False
        assert bank.auto_commit is False
        assert bank.branch == "main"  # Should also use default branch

        # Verify operations work but don't auto-commit
        result = bank.create_memory_block(sample_memory_block)
        assert result is True
        mock_dolt_writer.commit_changes.assert_not_called()
