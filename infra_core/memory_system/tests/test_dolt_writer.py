"""
Tests for the Dolt writer functions, ensuring data is written correctly
and safely (e.g., resisting SQL injection).
"""

import pytest
from pathlib import Path
import datetime
from unittest.mock import MagicMock

# Target functions
from infra_core.memory_system.dolt_writer import write_memory_block_to_dolt

# Schema
from infra_core.memory_system.schemas.memory_block import MemoryBlock

# Helper for initializing test Dolt DB
from infra_core.memory_system.initialize_dolt import initialize_dolt_db

# Helper for reading back data
from infra_core.memory_system.dolt_reader import read_memory_block, read_memory_blocks

# Import Dolt class for mocking
from mysql.connector import Error as MySQLError  # Import MySQL error

# --- Fixtures ---


@pytest.fixture(scope="module")
def test_dolt_db_path(tmp_path_factory) -> Path:
    """Creates a temporary Dolt database for testing."""
    tmp_path = tmp_path_factory.mktemp("test_dolt_writer_db")
    test_db_path = tmp_path
    initialize_dolt_db(str(test_db_path))
    return test_db_path


@pytest.fixture
def sample_block_for_write() -> MemoryBlock:
    """Provides a sample MemoryBlock for write tests."""
    return MemoryBlock(
        id="test-sample-001",
        type="knowledge",
        text="This is a sample knowledge block for testing.",
        tags=["test", "sample"],
        metadata={"category": "testing", "priority": 5},
        # Removed links field as it no longer exists in MemoryBlock
        created_by="test_user",
    )


# --- Test Class ---


class TestDoltWriter:
    def test_basic_write_and_read(
        self, test_dolt_db_path: Path, sample_block_for_write: MemoryBlock
    ):
        """Test basic write and read functionality."""
        db_path_str = str(test_dolt_db_path)

        # Write the block
        success, commit_hash = write_memory_block_to_dolt(
            sample_block_for_write, db_path_str, auto_commit=True
        )
        assert success, "Failed to write the sample block"
        assert commit_hash is not None, "Commit hash should be provided when auto_commit=True"

        # Read back and verify
        read_back_block = read_memory_block(db_path_str, sample_block_for_write.id)
        assert read_back_block is not None, "Failed to read back the written block"
        assert read_back_block.id == sample_block_for_write.id
        assert read_back_block.type == sample_block_for_write.type
        assert read_back_block.text == sample_block_for_write.text
        assert read_back_block.tags == sample_block_for_write.tags
        assert read_back_block.metadata == sample_block_for_write.metadata

    def test_sql_injection_attempt(self, test_dolt_db_path: Path):
        """Test that SQL injection attempts are properly handled via parameterized queries."""
        db_path_str = str(test_dolt_db_path)

        # Create a block with potentially malicious content
        malicious_text = "'; DROP TABLE memory_blocks; --"
        malicious_id = "'; DROP TABLE memory_blocks; --"

        block = MemoryBlock(
            id=malicious_id,
            type="knowledge",
            text=malicious_text,
            tags=["test", "security"],
            metadata={"danger": "'; DROP TABLE memory_blocks; --"},
            # Removed links field
            created_by="test_security",
        )

        # The write should succeed because parameterized queries handle this safely
        success, commit_hash = write_memory_block_to_dolt(block, db_path_str, auto_commit=True)
        assert success, "Failed to write block with special characters"

        # Verify the content was stored literally (not executed as SQL)
        read_back_block = read_memory_block(db_path_str, malicious_id)
        assert read_back_block is not None
        assert read_back_block.text == malicious_text
        assert read_back_block.metadata["danger"] == "'; DROP TABLE memory_blocks; --"

        # Verify the table still exists by listing all blocks
        all_blocks = read_memory_blocks(db_path_str)
        assert len(all_blocks) > 0, "Table should still exist and contain blocks"

    def test_write_with_nullable_fields(self, test_dolt_db_path: Path):
        """Tests writing a block with null fields to test schema handling of nullable fields."""
        db_path_str = str(test_dolt_db_path)

        # Create block with explicitly null fields - removed links field
        block = MemoryBlock(
            id="nullable-fields-test",
            type="knowledge",
            text="Testing nullable fields in schema",
            tags=["test", "nullable"],
            metadata={"test": True},
            # Leave confidence, source_uri, and embedding as None
            confidence=None,
            source_uri=None,
            embedding=None,
        )

        # Write the block
        success, commit_hash = write_memory_block_to_dolt(block, db_path_str, auto_commit=True)
        assert success, "Failed to write the block with null fields"

        # Read back and verify using the API - this is the primary verification
        read_back_block = read_memory_block(db_path_str, block.id)
        assert read_back_block is not None, "Failed to read back block"
        assert read_back_block.confidence is None, "confidence should be None"
        assert read_back_block.source_uri is None, "source_uri should be None"
        assert read_back_block.embedding is None, "embedding should be None"

        # Verify other fields were written correctly
        assert read_back_block.id == block.id
        assert read_back_block.type == block.type
        assert read_back_block.text == block.text
        assert read_back_block.tags == block.tags
        assert read_back_block.metadata == block.metadata

    def test_schema_mismatch_error_handling(self, monkeypatch, test_dolt_db_path: Path):
        """Tests that schema mismatches during writes result in meaningful errors."""
        db_path_str = str(test_dolt_db_path)

        # Create a test block - removed links field
        block = MemoryBlock(
            id="schema-mismatch-test",
            type="knowledge",
            text="Testing schema mismatch error handling",
            tags=[],  # Provide empty tags
            metadata={},  # Provide empty metadata
        )

        # Mock mysql.connector.connect to simulate a schema mismatch error
        original_connect = None
        try:
            import mysql.connector

            original_connect = mysql.connector.connect

            def mock_connect(*args, **kwargs):
                # Return a real connection for setup operations
                real_conn = original_connect(*args, **kwargs)
                mock_conn = MagicMock()
                mock_conn.rollback = real_conn.rollback
                mock_conn.close = real_conn.close

                # Mock cursor to raise error on REPLACE INTO
                mock_cursor = MagicMock()

                def mock_execute(query, params=None):
                    if query and "REPLACE INTO memory_blocks" in query:
                        raise MySQLError(
                            msg="Unknown column 'nonexistent_column' in 'field list'", errno=1054
                        )
                    return None

                mock_cursor.execute = mock_execute
                mock_conn.cursor.return_value = mock_cursor
                return mock_conn

            monkeypatch.setattr("mysql.connector.connect", mock_connect)

            # Attempt to write the block - should fail with a meaningful error
            success, _ = write_memory_block_to_dolt(block, db_path_str)
            assert not success, "Write should fail with schema mismatch error"

        finally:
            # Restore original function
            if original_connect:
                monkeypatch.setattr("mysql.connector.connect", original_connect)

    # FIX-02 Tests: Over-aggressive control character rejection
    def test_fix02_legitimate_newlines_allowed(self, test_dolt_db_path: Path):
        """FIX-02: Test that legitimate newlines in text content are allowed."""
        db_path_str = str(test_dolt_db_path)
        block_id = "newline-test-001"

        # Text with legitimate newlines (common in code, markdown, etc.)
        text_with_newlines = "Line 1\nLine 2\nLine 3"

        block = MemoryBlock(
            id=block_id,
            type="knowledge",
            text=text_with_newlines,
            tags=["test", "newlines"],
            metadata={"description": "Text with\nnewlines"},
            links=[],
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        )

        # This should not raise an exception
        success, commit_hash = write_memory_block_to_dolt(block, db_path_str, auto_commit=True)
        assert success, "Failed to write block with legitimate newlines"
        assert commit_hash is not None

        # Verify data was stored correctly
        read_back_block = read_memory_block(db_path_str, block_id)
        assert read_back_block is not None
        assert read_back_block.text == text_with_newlines
        assert read_back_block.metadata["description"] == "Text with\nnewlines"

    def test_fix02_legitimate_tabs_allowed(self, test_dolt_db_path: Path):
        """FIX-02: Test that legitimate tabs in text content are allowed."""
        db_path_str = str(test_dolt_db_path)
        block_id = "tab-test-001"

        # Text with legitimate tabs (common in code, formatting)
        text_with_tabs = "Column1\tColumn2\tColumn3"

        block = MemoryBlock(
            id=block_id,
            type="knowledge",
            text=text_with_tabs,
            tags=["test", "tabs"],
            metadata={"code": "if True:\n\treturn 'tabbed'"},
            links=[],
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        )

        # This should not raise an exception
        success, commit_hash = write_memory_block_to_dolt(block, db_path_str, auto_commit=True)
        assert success, "Failed to write block with legitimate tabs"
        assert commit_hash is not None

        # Verify data was stored correctly
        read_back_block = read_memory_block(db_path_str, block_id)
        assert read_back_block is not None
        assert read_back_block.text == text_with_tabs
        assert read_back_block.metadata["code"] == "if True:\n\treturn 'tabbed'"

    def test_fix02_source_code_content_allowed(self, test_dolt_db_path: Path):
        """FIX-02: Test that source code with mixed newlines and tabs is allowed."""
        db_path_str = str(test_dolt_db_path)
        block_id = "source-code-test-001"

        # Realistic source code content
        source_code = """def example_function():
\tif True:
\t\treturn "Hello\nWorld"
\telse:
\t\treturn None"""

        block = MemoryBlock(
            id=block_id,
            type="knowledge",
            text=source_code,
            tags=["source", "code"],
            metadata={
                "language": "python",
                "file_path": "/path/to/file.py",
                "content": source_code,
            },
            links=[],
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        )

        # This should not raise an exception
        success, commit_hash = write_memory_block_to_dolt(block, db_path_str, auto_commit=True)
        assert success, "Failed to write block with source code content"
        assert commit_hash is not None

        # Verify data was stored correctly
        read_back_block = read_memory_block(db_path_str, block_id)
        assert read_back_block is not None
        assert read_back_block.text == source_code
        assert read_back_block.metadata["content"] == source_code
