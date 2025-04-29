import pytest
from memory_system.schemas.memory_block import MemoryBlock


def test_memory_block_state_field():
    """Test that the state field accepts valid values and rejects invalid ones."""
    # Test valid state values
    block = MemoryBlock(type="knowledge", text="Test content", state="draft")
    assert block.state == "draft"

    block.state = "published"
    assert block.state == "published"

    block.state = "archived"
    assert block.state == "archived"

    # Test invalid state value
    with pytest.raises(ValueError):
        MemoryBlock(type="knowledge", text="Test content", state="invalid_state")


def test_memory_block_state_optional():
    """Test that state field is optional and defaults to None."""
    block = MemoryBlock(type="knowledge", text="Test content")
    assert block.state is None


def test_memory_block_state_transition():
    """Test that state transitions are properly tracked in updated_at."""
    block = MemoryBlock(type="knowledge", text="Test content", state="draft")
    initial_updated_at = block.updated_at

    # Change state and verify updated_at changed
    block.state = "published"
    assert block.updated_at > initial_updated_at
