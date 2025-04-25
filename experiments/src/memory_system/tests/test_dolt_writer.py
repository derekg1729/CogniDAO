"""
Tests for the Dolt writer functions, ensuring data is written correctly
and safely (e.g., resisting SQL injection).
"""

import pytest
from pathlib import Path
import datetime

# Target functions
from experiments.src.memory_system.dolt_writer import write_memory_block_to_dolt

# Schema
from experiments.src.memory_system.schemas.memory_block import MemoryBlock

# Helper for initializing test Dolt DB
from experiments.src.memory_system.initialize_dolt import initialize_dolt_db

# Helper for reading back data
from experiments.src.memory_system.dolt_reader import read_memory_block

# --- Fixtures ---

@pytest.fixture(scope="module")
def test_dolt_db_path(tmp_path_factory) -> Path:
    """Creates a temporary directory for a test Dolt database."""
    db_path = tmp_path_factory.mktemp("test_dolt_writer_db")
    assert initialize_dolt_db(str(db_path)), "Failed to initialize test Dolt DB"
    return db_path

@pytest.fixture
def sample_block_for_write() -> MemoryBlock:
    """Provides a basic MemoryBlock for write tests."""
    return MemoryBlock(
        id="write-test-001",
        type="knowledge",
        text="This is a basic write test.",
        tags=["write", "test"],
        metadata={"runner": "pytest"},
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now()
    )

# --- Test Class ---

class TestDoltWriter:

    def test_basic_write_and_read(self, test_dolt_db_path: Path, sample_block_for_write: MemoryBlock):
        """Tests writing a block and reading it back."""
        db_path_str = str(test_dolt_db_path)
        block = sample_block_for_write

        # Write the block
        success, commit_hash = write_memory_block_to_dolt(block, db_path_str, auto_commit=True)
        assert success, "Failed to write the block"
        assert commit_hash is not None, "Failed to get commit hash"

        # Read the block back
        read_back_block = read_memory_block(db_path_str, block.id)
        assert read_back_block is not None, f"Failed to read back block {block.id}"

        # Compare essential fields (handle potential microsecond differences in time)
        assert read_back_block.id == block.id
        assert read_back_block.type == block.type
        assert read_back_block.text == block.text
        assert read_back_block.tags == block.tags
        assert read_back_block.metadata == block.metadata
        # Timestamps might have slight variations, compare reasonably
        assert abs((read_back_block.created_at - block.created_at).total_seconds()) < 1
        # For updated_at, verify it's a datetime and reasonably close to now, 
        # as the DB might update it on write.
        assert isinstance(read_back_block.updated_at, datetime.datetime)
        assert abs((read_back_block.updated_at - datetime.datetime.now()).total_seconds()) < 5 # Allow 5 sec diff

    def test_sql_injection_attempt(self, test_dolt_db_path: Path):
        """
        Tests that input containing SQL-like syntax is written as a literal string
        and does not execute unintended SQL commands, thanks to parameterized queries.
        """
        db_path_str = str(test_dolt_db_path)
        malicious_text = "Malicious text'; DROP TABLE memory_blocks; --"
        injection_block_id = "injection-test-001"

        block = MemoryBlock(
            id=injection_block_id,
            type="knowledge",
            text=malicious_text,
            tags=["security", "injection"],
            metadata={"attempt": "drop table"},
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now()
        )

        # Write the block with potentially malicious text
        success, commit_hash = write_memory_block_to_dolt(block, db_path_str, auto_commit=True)
        assert success, "Failed to write the block with malicious text (parameterized query should handle this)"
        assert commit_hash is not None

        # Read the block back
        read_back_block = read_memory_block(db_path_str, injection_block_id)
        assert read_back_block is not None, f"Failed to read back block {injection_block_id}"

        # Verify the malicious text was stored literally
        assert read_back_block.text == malicious_text, "The malicious text was not stored literally."

        # --- Crucial Check: Verify the table still exists --- 
        # Try reading a different block (or the same one again) to ensure DROP TABLE didn't execute
        try:
            block_check = read_memory_block(db_path_str, injection_block_id)
            assert block_check is not None, "Table seems to be dropped or inaccessible after injection attempt."
        except Exception as e:
            pytest.fail(f"Reading from table failed after injection attempt, suggesting DROP TABLE might have executed. Error: {e}") 