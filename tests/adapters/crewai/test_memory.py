"""
Tests for the CrewAI memory adapter implementation.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock

from cogni_adapters.crewai.memory import CogniMemoryStorage
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.schemas.memory_block import MemoryBlock


@pytest.fixture
def mock_memory_bank():
    """Create a mock StructuredMemoryBank for testing."""
    return Mock(spec=StructuredMemoryBank)


@pytest.fixture
def memory_storage(mock_memory_bank):
    """Create a CogniMemoryStorage instance with a mock memory bank."""
    return CogniMemoryStorage(mock_memory_bank)


def test_memory_storage_save(memory_storage, mock_memory_bank):
    """Test saving a thought using CogniMemoryStorage."""
    # Setup
    thought = "Test thought"
    metadata = {"source": "test"}
    mock_memory_bank.create_memory_block.return_value = True

    # Execute
    result = memory_storage.save(thought, metadata)

    # Verify
    assert result is True
    mock_memory_bank.create_memory_block.assert_called_once()
    saved_block = mock_memory_bank.create_memory_block.call_args[0][0]
    assert isinstance(saved_block, MemoryBlock)
    assert saved_block.text == thought
    assert saved_block.type == "knowledge"
    assert "crewai" in saved_block.tags
    assert "thought" in saved_block.tags
    assert saved_block.metadata == metadata


def test_memory_storage_search(memory_storage, mock_memory_bank):
    """Test searching thoughts using CogniMemoryStorage."""
    # Setup
    query = "test query"
    mock_blocks = [
        MemoryBlock(
            id="test1",
            type="knowledge",
            text="Test result 1",
            tags=["crewai"],
            metadata={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ),
        MemoryBlock(
            id="test2",
            type="knowledge",
            text="Test result 2",
            tags=["crewai"],
            metadata={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ),
    ]
    mock_memory_bank.query_semantic.return_value = mock_blocks

    # Execute
    results = memory_storage.search(query, top_k=2)

    # Verify
    assert len(results) == 2
    assert results[0] == "Test result 1"
    assert results[1] == "Test result 2"
    mock_memory_bank.query_semantic.assert_called_once_with(query, top_k=2)


def test_memory_storage_reset(memory_storage):
    """Test reset functionality of CogniMemoryStorage."""
    # Execute
    result = memory_storage.reset()

    # Verify
    assert result is False  # Currently not implemented


def test_memory_storage_error_handling(memory_storage, mock_memory_bank):
    """Test error handling in CogniMemoryStorage."""
    # Setup
    mock_memory_bank.create_memory_block.side_effect = Exception("Test error")

    # Execute
    result = memory_storage.save("test thought")

    # Verify
    assert result is False
