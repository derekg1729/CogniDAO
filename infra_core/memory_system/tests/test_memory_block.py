import pytest
from infra_core.memory_system.schemas.memory_block import MemoryBlock


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


def test_memory_block_visibility_field():
    """Test that the visibility field accepts valid values and rejects invalid ones."""
    # Test valid visibility values
    block = MemoryBlock(type="knowledge", text="Test content", visibility="internal")
    assert block.visibility == "internal"

    block.visibility = "public"
    assert block.visibility == "public"

    block.visibility = "restricted"
    assert block.visibility == "restricted"

    # Test invalid visibility value
    with pytest.raises(ValueError):
        MemoryBlock(type="knowledge", text="Test content", visibility="invalid_visibility")


def test_memory_block_visibility_optional():
    """Test that visibility field is optional and defaults to None."""
    block = MemoryBlock(type="knowledge", text="Test content")
    assert block.visibility is None


def test_memory_block_visibility_transition():
    """Test that visibility transitions are properly tracked in updated_at."""
    block = MemoryBlock(type="knowledge", text="Test content", visibility="internal")
    initial_updated_at = block.updated_at

    # Change visibility and verify updated_at changed
    block.visibility = "public"
    assert block.updated_at > initial_updated_at


def test_memory_block_version():
    """Test that block_version accepts integers and is optional."""
    # Test valid version values
    block = MemoryBlock(type="knowledge", text="Test content", block_version=1)
    assert block.block_version == 1

    block.block_version = 2
    assert block.block_version == 2

    # Test that version must be an integer
    with pytest.raises(ValueError):
        MemoryBlock(type="knowledge", text="Test content", block_version="not_an_int")

    # Test that version must be positive
    with pytest.raises(ValueError):
        MemoryBlock(type="knowledge", text="Test content", block_version=-1)


def test_memory_block_version_optional():
    """Test that block_version is optional and defaults to None."""
    block = MemoryBlock(type="knowledge", text="Test content")
    assert block.block_version is None


def test_memory_block_version_transition():
    """Test that version changes are properly tracked in updated_at."""
    block = MemoryBlock(type="knowledge", text="Test content", block_version=1)
    initial_updated_at = block.updated_at

    # Change version and verify updated_at changed
    block.block_version = 2
    assert block.updated_at > initial_updated_at


def test_memory_block_embedding_validation():
    """Test that embedding field validates vector size."""
    # Test valid embedding
    valid_embedding = [0.1] * 384  # Standard size for many embedding models
    block = MemoryBlock(type="knowledge", text="Test content", embedding=valid_embedding)
    assert block.embedding == valid_embedding

    # Test invalid embedding size
    with pytest.raises(ValueError):
        MemoryBlock(
            type="knowledge",
            text="Test content",
            embedding=[0.1] * 100,  # Wrong size
        )

    # Test invalid embedding type
    with pytest.raises(ValueError):
        MemoryBlock(
            type="knowledge", text="Test content", embedding=["not", "a", "float", "vector"]
        )


def test_memory_block_tags_validation():
    """Test that tags list enforces max_items constraint."""
    # Test valid number of tags
    valid_tags = [f"tag_{i}" for i in range(20)]
    block = MemoryBlock(type="knowledge", text="Test content", tags=valid_tags)
    assert block.tags == valid_tags

    # Test too many tags
    too_many_tags = [f"tag_{i}" for i in range(21)]
    with pytest.raises(ValueError):
        MemoryBlock(type="knowledge", text="Test content", tags=too_many_tags)
