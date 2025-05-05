# experiments/tests/test_memory_block_schema.py
import pytest
from datetime import datetime
import sys
from pathlib import Path

# Add the project root to the Python path
# This allows importing the schema module directly
project_root = Path(
    __file__
).parent.parent.parent  # Adjust based on actual file location relative to project root
sys.path.insert(0, str(project_root))

# Import the models AFTER adding the path
try:
    from infra_core.memory_system.schemas.memory_block import (
        MemoryBlock,
        BlockLink,
        ConfidenceScore,
    )
except ImportError as e:
    pytest.fail(f"Failed to import MemoryBlock schemas. Check sys.path and file location: {e}")


def test_memory_block_instantiation():
    """Tests basic instantiation of the MemoryBlock schema with all fields."""
    block_id = "test-id-123"
    link_to_id = "linked-id-456"

    try:
        block = MemoryBlock(
            id=block_id,
            type="knowledge",
            text="This is a test memory block.",
            tags=["test", "pydantic"],
            metadata={"source": "test_script", "version": 1.0},
            links=[BlockLink(to_id=link_to_id, relation="related_to")],
            source_file="test_file.md",
            source_uri="logseq://graph/page/block-id",
            confidence=ConfidenceScore(human=0.9, ai=0.75),
            created_by="test_runner",
            # created_at and updated_at have defaults
            # embedding is optional
        )

        # Assertions to verify fields were set correctly
        assert block.id == block_id
        assert block.type == "knowledge"
        assert block.text == "This is a test memory block."
        assert block.tags == ["test", "pydantic"]
        assert block.metadata == {"source": "test_script", "version": 1.0}
        assert len(block.links) == 1
        assert block.links[0].to_id == link_to_id
        assert block.links[0].relation == "related_to"
        assert block.source_file == "test_file.md"
        assert block.source_uri == "logseq://graph/page/block-id"
        assert block.confidence.human == 0.9
        assert block.confidence.ai == 0.75
        assert block.created_by == "test_runner"
        assert isinstance(block.created_at, datetime)
        assert isinstance(block.updated_at, datetime)
        assert block.embedding is None

    except Exception as e:
        pytest.fail(f"MemoryBlock instantiation failed: {e}")


def test_memory_block_defaults():
    """Tests instantiation with minimal required fields and checks defaults."""
    try:
        block = MemoryBlock(
            id="minimal-id",
            type="task",
            text="Minimal block.",
            # All other fields should use defaults or be None
        )

        assert block.id == "minimal-id"
        assert block.type == "task"
        assert block.text == "Minimal block."
        assert block.tags == []
        assert block.metadata == {}
        assert block.links == []
        assert block.source_file is None
        assert block.source_uri is None
        assert block.confidence is None
        assert block.created_by is None
        assert isinstance(block.created_at, datetime)
        assert isinstance(block.updated_at, datetime)
        assert block.embedding is None

    except Exception as e:
        pytest.fail(f"Minimal MemoryBlock instantiation failed: {e}")
