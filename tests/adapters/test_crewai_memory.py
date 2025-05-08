"""
Tests for the CogniMemoryStorage class.

These tests verify that:
1. The class correctly implements CrewAI's ExternalMemory interface
2. Thoughts are properly saved and retrieved
3. Error handling works as expected
"""

from datetime import datetime

from cogni_adapters.crewai.memory import CogniMemoryStorage
from infra_core.memory_system.schemas.memory_block import MemoryBlock


def test_initialization(memory_bank):
    """Test that CogniMemoryStorage initializes correctly."""
    storage = CogniMemoryStorage(memory_bank)
    assert storage.memory_bank == memory_bank


def test_save_thought(memory_bank):
    """Test saving a thought."""
    # Setup
    storage = CogniMemoryStorage(memory_bank)
    thought = "Test thought content"
    metadata = {"source": "test"}

    # Mock successful save
    memory_bank.create_memory_block.return_value = True

    # Execute
    success = storage.save(thought, metadata)

    # Verify
    assert success is True
    memory_bank.create_memory_block.assert_called_once()
    saved_block = memory_bank.create_memory_block.call_args[0][0]
    assert isinstance(saved_block, MemoryBlock)
    assert saved_block.text == thought
    assert saved_block.metadata == metadata
    assert saved_block.type == "knowledge"
    assert "crewai" in saved_block.tags
    assert "thought" in saved_block.tags


def test_save_thought_failure(memory_bank):
    """Test handling of save failure."""
    # Setup
    storage = CogniMemoryStorage(memory_bank)
    thought = "Test thought content"

    # Mock failed save
    memory_bank.create_memory_block.return_value = False

    # Execute
    success = storage.save(thought)

    # Verify
    assert success is False
    memory_bank.create_memory_block.assert_called_once()


def test_search_thoughts(memory_bank):
    """Test searching for thoughts."""
    # Setup
    storage = CogniMemoryStorage(memory_bank)
    query = "test query"

    # Mock search results
    mock_blocks = [
        MemoryBlock(
            id="test1",
            type="knowledge",
            text="First test thought",
            tags=["crewai", "thought"],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ),
        MemoryBlock(
            id="test2",
            type="knowledge",
            text="Second test thought",
            tags=["crewai", "thought"],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ),
    ]
    memory_bank.query_semantic.return_value = mock_blocks

    # Execute
    results = storage.search(query, top_k=2)

    # Verify
    assert len(results) == 2
    assert results[0] == "First test thought"
    assert results[1] == "Second test thought"
    memory_bank.query_semantic.assert_called_once_with(query, top_k=2)


def test_search_no_results(memory_bank):
    """Test search when no results are found."""
    # Setup
    storage = CogniMemoryStorage(memory_bank)
    query = "nonexistent query"

    # Mock empty results
    memory_bank.query_semantic.return_value = []

    # Execute
    results = storage.search(query)

    # Verify
    assert len(results) == 0
    memory_bank.query_semantic.assert_called_once()


def test_reset_not_implemented(memory_bank):
    """Test that reset is not yet implemented."""
    # Setup
    storage = CogniMemoryStorage(memory_bank)

    # Execute
    success = storage.reset()

    # Verify
    assert success is False
    # No calls to memory_bank methods since reset is not implemented
