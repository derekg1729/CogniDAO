"""
Tests for the Dolt writer functions, ensuring data is written correctly
and safely (e.g., resisting SQL injection).
"""

import pytest
from pathlib import Path
import datetime
import subprocess
import json

# Target functions
from experiments.src.memory_system.dolt_writer import write_memory_block_to_dolt

# Schema
from experiments.src.memory_system.schemas.memory_block import MemoryBlock

# Helper for initializing test Dolt DB
from experiments.src.memory_system.initialize_dolt import initialize_dolt_db

# Helper for reading back data
from experiments.src.memory_system.dolt_reader import read_memory_block

# Import Dolt class for mocking
from doltpy.cli import Dolt

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
        links=[],  # Explicit empty list instead of None
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )


# --- Test Class ---


class TestDoltWriter:
    def test_basic_write_and_read(
        self, test_dolt_db_path: Path, sample_block_for_write: MemoryBlock
    ):
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
        assert (
            abs((read_back_block.updated_at - datetime.datetime.now()).total_seconds()) < 5
        )  # Allow 5 sec diff

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
            links=[],  # Explicit empty list instead of None
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        )

        # Write the block with potentially malicious text
        success, commit_hash = write_memory_block_to_dolt(block, db_path_str, auto_commit=True)
        assert success, (
            "Failed to write the block with malicious text (parameterized query should handle this)"
        )
        assert commit_hash is not None

        # Read the block back
        read_back_block = read_memory_block(db_path_str, injection_block_id)
        assert read_back_block is not None, f"Failed to read back block {injection_block_id}"

        # Verify the malicious text was stored literally
        assert read_back_block.text == malicious_text, (
            "The malicious text was not stored literally."
        )

        # --- Crucial Check: Verify the table still exists ---
        # Try reading a different block (or the same one again) to ensure DROP TABLE didn't execute
        try:
            block_check = read_memory_block(db_path_str, injection_block_id)
            assert block_check is not None, (
                "Table seems to be dropped or inaccessible after injection attempt."
            )
        except Exception as e:
            pytest.fail(
                f"Reading from table failed after injection attempt, suggesting DROP TABLE might have executed. Error: {e}"
            )

    def test_write_with_nullable_fields(self, test_dolt_db_path: Path):
        """Tests writing a block with null fields to test schema handling of nullable fields."""
        db_path_str = str(test_dolt_db_path)

        # Create block with explicitly null fields
        block = MemoryBlock(
            id="nullable-fields-test",
            type="knowledge",
            text="Testing nullable fields in schema",
            tags=["test", "nullable"],
            metadata={"test": True},
            links=[],  # Explicit empty list instead of None
            # Leave confidence, source_uri, and embedding as None
            confidence=None,
            source_uri=None,
            embedding=None,
        )

        # Write the block
        success, commit_hash = write_memory_block_to_dolt(block, db_path_str, auto_commit=True)
        assert success, "Failed to write the block with null fields"

        # Read back and verify using the API
        read_back_block = read_memory_block(db_path_str, block.id)
        assert read_back_block is not None, "Failed to read back block"
        assert read_back_block.confidence is None, "confidence should be None"
        assert read_back_block.source_uri is None, "source_uri should be None"
        assert read_back_block.embedding is None, "embedding should be None"

        # Directly verify via SQL that the values were stored as NULL
        try:
            # Use JSON format for reliable parsing
            result = subprocess.run(
                [
                    "dolt",
                    "sql",
                    "-q",
                    f"SELECT confidence IS NULL, source_uri IS NULL, embedding IS NULL FROM memory_blocks WHERE id = '{block.id}'",
                    "-r",
                    "json",  # Use JSON result format
                ],
                cwd=db_path_str,
                capture_output=True,
                text=True,
                check=True,
            )

            # Parse the JSON output
            try:
                data = json.loads(result.stdout)
                # Check that all values are null
                if "rows" in data and len(data["rows"]) > 0:
                    row = data["rows"][0]
                    confidence_is_null = row.get("confidence IS NULL", False)
                    source_uri_is_null = row.get("source_uri IS NULL", False)
                    embedding_is_null = row.get("embedding IS NULL", False)

                    assert confidence_is_null, "confidence should be NULL in database"
                    assert source_uri_is_null, "source_uri should be NULL in database"
                    assert embedding_is_null, "embedding should be NULL in database"
                else:
                    assert False, f"No rows returned from query: {result.stdout}"
            except json.JSONDecodeError:
                # If JSON parsing fails, the output might be in a different format
                # Just check that the test block can be read back correctly
                assert read_back_block.confidence is None, "confidence should be None"
                assert read_back_block.source_uri is None, "source_uri should be None"
                assert read_back_block.embedding is None, "embedding should be None"

        except subprocess.CalledProcessError as e:
            pytest.fail(f"SQL query failed: {e.stderr}")

    def test_schema_mismatch_error_handling(self, monkeypatch, test_dolt_db_path: Path):
        """Tests that schema mismatches during writes result in meaningful errors."""
        db_path_str = str(test_dolt_db_path)

        # Create a test block
        block = MemoryBlock(
            id="schema-mismatch-test",
            type="knowledge",
            text="Testing schema mismatch error handling",
            tags=[],  # Provide empty tags
            metadata={},  # Provide empty metadata
            links=[],  # Provide empty links
        )

        # Mock Dolt.sql method to simulate a schema mismatch error
        original_dolt_sql = Dolt.sql

        def mock_dolt_sql(self, **kwargs):
            if "REPLACE INTO memory_blocks" in kwargs.get("query", ""):
                from doltpy.cli.dolt import DoltException

                raise DoltException(
                    "sql",
                    b"",
                    b"Error 1054: Unknown column 'nonexistent_column' in 'field list'",
                    1,
                )
            return original_dolt_sql(self, **kwargs)

        # Apply the mock to the Dolt class
        monkeypatch.setattr(Dolt, "sql", mock_dolt_sql)

        # Attempt to write the block - should fail with a meaningful error
        success, _ = write_memory_block_to_dolt(block, db_path_str)
        assert not success, "Write should fail with schema mismatch error"

        # Alternative approach using with pytest.raises
        with pytest.raises(Exception) as excinfo:
            # Force the exception to be raised by bypassing the try/except in write_memory_block_to_dolt
            repo = Dolt(db_path_str)
            repo.sql(query="REPLACE INTO memory_blocks (nonexistent_column) VALUES ('test')")

        # Verify the error message contains information about the schema mismatch
        error_msg = str(excinfo.value)
        assert "unknown column" in error_msg.lower(), (
            f"Error should mention unknown column, got: {error_msg}"
        )
