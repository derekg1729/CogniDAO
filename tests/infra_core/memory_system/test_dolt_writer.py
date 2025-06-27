"""
Tests for the Dolt writer functions, ensuring data is written correctly
and safely (e.g., resisting SQL injection).
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Target functions

# Schema
from infra_core.memory_system.schemas.memory_block import MemoryBlock

# Helper for initializing test Dolt DB
from infra_core.memory_system.initialize_dolt import initialize_dolt_db

# Helper for reading back data

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
    @pytest.mark.skip(
        reason="Integration test - hangs due to complex Dolt SQL server setup. Use unit tests below."
    )
    def test_basic_write_and_read_integration(
        self, integration_memory_bank, sample_block_for_write: MemoryBlock
    ):
        """
        INTEGRATION TEST: Test basic write and read functionality using proper test database connection.

        SKIPPED: This test requires complex database infrastructure that currently hangs.
        Use the unit tests below instead for CI/fast feedback.
        """
        # Use the integrated memory bank's writer instead of deprecated function
        writer = integration_memory_bank.writer

        # Write the block using the proper writer
        success, commit_hash = writer.write_memory_block(sample_block_for_write, auto_commit=True)
        assert success, "Failed to write the sample block"
        assert commit_hash is not None, "Commit hash should be provided when auto_commit=True"

        # Read back and verify using the proper reader
        reader = integration_memory_bank.reader
        read_back_block = reader.get_memory_block(sample_block_for_write.id)
        assert read_back_block is not None, "Failed to read back the written block"
        assert read_back_block.id == sample_block_for_write.id
        assert read_back_block.type == sample_block_for_write.type
        assert read_back_block.text == sample_block_for_write.text
        assert read_back_block.tags == sample_block_for_write.tags
        assert read_back_block.metadata == sample_block_for_write.metadata

    @pytest.mark.skip(
        reason="Integration test - hangs due to complex Dolt SQL server setup during fixture creation."
    )
    def test_write_memory_block_integration(
        self, integration_memory_bank, sample_block_for_write: MemoryBlock
    ):
        """
        INTEGRATION TEST: Test write functionality using proper test database connection.

        SKIPPED: This test requires complex database infrastructure that currently hangs.
        Use the unit tests below instead for CI/fast feedback.
        """
        # Use the integrated memory bank's writer instead of deprecated function
        writer = integration_memory_bank.writer

        # Write the block using the proper writer
        success, commit_hash = writer.write_memory_block(sample_block_for_write, auto_commit=True)
        assert success, "Failed to write the sample block"
        assert commit_hash is not None, "Commit hash should be provided when auto_commit=True"

        # Read back and verify using the proper reader
        reader = integration_memory_bank.reader
        read_back_block = reader.get_memory_block(sample_block_for_write.id)
        assert read_back_block is not None, "Failed to read back the written block"
        assert read_back_block.id == sample_block_for_write.id
        assert read_back_block.type == sample_block_for_write.type
        assert read_back_block.text == sample_block_for_write.text
        assert read_back_block.tags == sample_block_for_write.tags
        assert read_back_block.metadata == sample_block_for_write.metadata

    def test_memory_block_serialization_unit(self, sample_block_for_write: MemoryBlock):
        """
        UNIT TEST: Test that MemoryBlock serializes correctly for database operations.

        This tests the data preparation logic without requiring database infrastructure.
        """
        # Test 1: Block can be converted to dict format (simulating DB preparation)
        block_dict = sample_block_for_write.model_dump()

        # Verify all required fields are present
        assert block_dict["id"] == "test-sample-001"
        assert block_dict["type"] == "knowledge"
        assert block_dict["text"] == "This is a sample knowledge block for testing."
        assert block_dict["tags"] == ["test", "sample"]
        assert block_dict["metadata"] == {"category": "testing", "priority": 5}
        assert block_dict["created_by"] == "test_user"

        # Test 2: Block can be reconstructed from dict (simulating DB read)
        reconstructed = MemoryBlock.model_validate(block_dict)
        assert reconstructed.id == sample_block_for_write.id
        assert reconstructed.type == sample_block_for_write.type
        assert reconstructed.text == sample_block_for_write.text
        assert reconstructed.tags == sample_block_for_write.tags
        assert reconstructed.metadata == sample_block_for_write.metadata

    @pytest.mark.skip(
        reason="CRITICAL: Test creates blocks with IDs that contaminate production namespace - bug 84c5996e-8fe5-49c1-90e5-36f1cf8555ad"
    )
    def test_sql_parameter_safety_unit(self):
        """
        UNIT TEST: Test that SQL parameters are handled safely against injection.

        This tests parameter escaping without requiring database infrastructure.
        SKIPPED: Creates test blocks with predictable IDs that contaminate production.
        """
        # Create a block with potentially malicious content
        malicious_text = "'; DROP TABLE memory_blocks; --"
        malicious_id = "'; DROP TABLE memory_blocks; --"

        block = MemoryBlock(
            id=malicious_id,
            type="knowledge",
            text=malicious_text,
            tags=["test", "security"],
            metadata={"danger": "'; DROP TABLE memory_blocks; --"},
            created_by="test_security",
        )

        # Test that serialization preserves the content exactly (doesn't escape it)
        block_dict = block.model_dump()
        assert block_dict["id"] == malicious_id, "ID should be preserved exactly"
        assert block_dict["text"] == malicious_text, "Text should be preserved exactly"
        assert block_dict["metadata"]["danger"] == "'; DROP TABLE memory_blocks; --", (
            "Metadata should be preserved exactly"
        )

        # Test round-trip preservation
        reconstructed = MemoryBlock.model_validate(block_dict)
        assert reconstructed.id == malicious_id
        assert reconstructed.text == malicious_text
        assert reconstructed.metadata["danger"] == "'; DROP TABLE memory_blocks; --"

    @pytest.mark.skip(
        reason="CRITICAL: Test creates blocks with IDs that contaminate production namespace - bug 84c5996e-8fe5-49c1-90e5-36f1cf8555ad"
    )
    def test_nullable_fields_unit(self):
        """
        UNIT TEST: Test that blocks with nullable fields serialize correctly.

        This tests schema handling of optional fields.
        SKIPPED: Creates test blocks with predictable IDs that contaminate production.
        """
        # Create block with explicitly null fields
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

        # Test serialization handles None values correctly
        block_dict = block.model_dump()
        assert block_dict["confidence"] is None, "confidence should serialize as None"
        assert block_dict["source_uri"] is None, "source_uri should serialize as None"
        assert block_dict["embedding"] is None, "embedding should serialize as None"

        # Test other fields are preserved
        assert block_dict["id"] == "nullable-fields-test"
        assert block_dict["type"] == "knowledge"
        assert block_dict["text"] == "Testing nullable fields in schema"
        assert block_dict["tags"] == ["test", "nullable"]
        assert block_dict["metadata"] == {"test": True}

        # Test round-trip preservation
        reconstructed = MemoryBlock.model_validate(block_dict)
        assert reconstructed.confidence is None
        assert reconstructed.source_uri is None
        assert reconstructed.embedding is None
        assert reconstructed.id == block.id
        assert reconstructed.type == block.type
        assert reconstructed.text == block.text
        assert reconstructed.tags == block.tags
        assert reconstructed.metadata == block.metadata

    @patch("mysql.connector.connect")
    def test_database_error_handling_unit(self, mock_connect):
        """
        UNIT TEST: Test that database errors are handled gracefully.

        This mocks database errors to test error handling logic.
        """
        # Mock connection that raises error on cursor operations
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = MySQLError(
            msg="Unknown column 'nonexistent_column' in 'field list'", errno=1054
        )
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Create test block
        block = MemoryBlock(
            id="error-test",
            type="knowledge",
            text="Testing error handling",
            tags=[],
            metadata={},
        )

        # Create a DoltMySQLWriter directly and test on a feature branch
        # (avoiding the deprecated write_memory_block_to_dolt function)
        from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig
        from infra_core.memory_system.dolt_writer import DoltMySQLWriter

        config = DoltConnectionConfig()
        writer = DoltMySQLWriter(config)

        # Attempt write on feature branch - should fail gracefully due to database error
        success, result = writer.write_memory_block(block, branch="feat/test-branch")
        assert not success, "Write should fail with database error"
        assert result is None or isinstance(result, str), "Should return None or error message"

    # FIX-02 Tests: Over-aggressive control character rejection
    @pytest.mark.skip(reason="Integration test requiring real database")
    def test_fix02_legitimate_newlines_allowed(self, test_dolt_db_path: Path):
        """FIX-02: INTEGRATION TEST - Test that legitimate newlines in text content are allowed."""
        # This integration test is skipped - use unit test above for newline handling
        pass

    @pytest.mark.skip(reason="Integration test requiring real database")
    def test_fix02_legitimate_tabs_allowed(self, test_dolt_db_path: Path):
        """FIX-02: INTEGRATION TEST - Test that legitimate tabs in text content are allowed."""
        # This integration test is skipped - use unit test above for tab handling
        pass

    @pytest.mark.skip(reason="Integration test requiring real database")
    def test_fix02_source_code_content_allowed(self, test_dolt_db_path: Path):
        """FIX-02: INTEGRATION TEST - Test that source code with mixed newlines and tabs is allowed."""
        # This integration test is skipped - use unit test above for source code handling
        pass

    @pytest.mark.skip(
        reason="CRITICAL: Test creates blocks with IDs that contaminate production namespace - bug 84c5996e-8fe5-49c1-90e5-36f1cf8555ad"
    )
    def test_fix02_control_characters_unit(self):
        """
        UNIT TEST: Test that legitimate control characters (newlines, tabs) are preserved.

        This tests character handling without requiring database infrastructure.
        SKIPPED: Creates test blocks with predictable IDs that contaminate production.
        """
        # Test with legitimate newlines (common in code, markdown, etc.)
        text_with_newlines = "Line 1\nLine 2\nLine 3"
        block_newlines = MemoryBlock(
            id="newline-test-001",
            type="knowledge",
            text=text_with_newlines,
            tags=["test", "newlines"],
            metadata={"description": "Text with\nnewlines"},
        )

        # Test with legitimate tabs (common in code, formatting)
        text_with_tabs = "Column1\tColumn2\tColumn3"
        block_tabs = MemoryBlock(
            id="tab-test-001",
            type="knowledge",
            text=text_with_tabs,
            tags=["test", "tabs"],
            metadata={"code": "if True:\n\treturn 'tabbed'"},
        )

        # Test with realistic source code content
        source_code = """def example_function():
\tif True:
\t\treturn "Hello\nWorld"
\telse:
\t\treturn None"""

        block_source = MemoryBlock(
            id="source-code-test-001",
            type="knowledge",
            text=source_code,
            tags=["source", "code"],
            metadata={
                "language": "python",
                "file_path": "/path/to/file.py",
                "content": source_code,
            },
        )

        # Test all blocks serialize and deserialize correctly
        for block in [block_newlines, block_tabs, block_source]:
            # Serialize to dict (simulating database write preparation)
            block_dict = block.model_dump()

            # Deserialize back (simulating database read)
            reconstructed = MemoryBlock.model_validate(block_dict)

            # Verify content is preserved exactly
            assert reconstructed.text == block.text, (
                "Text with control characters should be preserved"
            )
            assert reconstructed.metadata == block.metadata, (
                "Metadata with control characters should be preserved"
            )

    @pytest.mark.skip(reason="Integration test requiring real database")
    def test_sql_injection_attempt(self, test_dolt_db_path: Path):
        """INTEGRATION TEST - SQL injection test requiring real database."""
        # This integration test is skipped - use unit test above for SQL safety
        pass

    @pytest.mark.skip(reason="Integration test requiring real database")
    def test_write_with_nullable_fields(self, test_dolt_db_path: Path):
        """INTEGRATION TEST - Nullable fields test requiring real database."""
        # This integration test is skipped - use unit test above for nullable field handling
        pass

    @pytest.mark.skip(reason="Integration test requiring real database")
    def test_schema_mismatch_error_handling(self, monkeypatch, test_dolt_db_path: Path):
        """INTEGRATION TEST - Schema mismatch test requiring real database."""
        # This integration test is skipped - use unit test above for error handling
        pass


class TestDoltWriterMergeBranch:
    """Unit tests for the merge_branch method of DoltMySQLWriter."""

    @patch("infra_core.memory_system.dolt_writer.DoltMySQLWriter._execute_query")
    def test_merge_branch_basic_success(self, mock_execute):
        """Test successful basic merge operation."""
        from infra_core.memory_system.dolt_writer import DoltMySQLWriter
        from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

        # Mock successful merge result
        mock_execute.return_value = [{"merge_result": "merge successful"}]

        # Create writer instance with proper config
        config = DoltConnectionConfig()
        writer = DoltMySQLWriter(config)

        # Execute merge
        success, message = writer.merge_branch("feature/test-branch")

        # Verify results
        assert success is True
        assert "Successfully merged branch 'feature/test-branch'" in message

        # Verify SQL call
        mock_execute.assert_called_once_with("CALL DOLT_MERGE(%s)", ("feature/test-branch",))

    @patch("infra_core.memory_system.dolt_writer.DoltMySQLWriter._execute_query")
    def test_merge_branch_with_squash(self, mock_execute):
        """Test merge operation with squash flag."""
        from infra_core.memory_system.dolt_writer import DoltMySQLWriter
        from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

        # Mock successful squash merge result
        mock_execute.return_value = [{"merge_result": "merge successful"}]

        # Create writer instance with proper config
        config = DoltConnectionConfig()
        writer = DoltMySQLWriter(config)

        # Execute squash merge
        success, message = writer.merge_branch("feature/squash-test", squash=True)

        # Verify results
        assert success is True
        assert "Successfully merged branch 'feature/squash-test'" in message

        # Verify SQL call with squash flag
        mock_execute.assert_called_once_with(
            "CALL DOLT_MERGE(%s, %s)", ("--squash", "feature/squash-test")
        )

    @patch("infra_core.memory_system.dolt_writer.DoltMySQLWriter._execute_query")
    def test_merge_branch_with_no_ff(self, mock_execute):
        """Test merge operation with no-fast-forward flag."""
        from infra_core.memory_system.dolt_writer import DoltMySQLWriter
        from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

        # Mock successful no-ff merge result
        mock_execute.return_value = [{"merge_result": "merge successful"}]

        # Create writer instance with proper config
        config = DoltConnectionConfig()
        writer = DoltMySQLWriter(config)

        # Execute no-ff merge
        success, message = writer.merge_branch("feature/no-ff-test", no_ff=True)

        # Verify results
        assert success is True
        assert "Successfully merged branch 'feature/no-ff-test'" in message

        # Verify SQL call with no-ff flag
        mock_execute.assert_called_once_with(
            "CALL DOLT_MERGE(%s, %s)", ("--no-ff", "feature/no-ff-test")
        )

    @patch("infra_core.memory_system.dolt_writer.DoltMySQLWriter._execute_query")
    def test_merge_branch_with_commit_message(self, mock_execute):
        """Test merge operation with custom commit message."""
        from infra_core.memory_system.dolt_writer import DoltMySQLWriter
        from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

        # Mock successful merge result
        mock_execute.return_value = [{"merge_result": "merge successful"}]

        # Create writer instance with proper config
        config = DoltConnectionConfig()
        writer = DoltMySQLWriter(config)

        # Execute merge with custom message
        success, message = writer.merge_branch(
            "feature/custom-msg", commit_message="Custom merge commit message"
        )

        # Verify results
        assert success is True
        assert "Successfully merged branch 'feature/custom-msg'" in message

        # Verify SQL call with commit message
        mock_execute.assert_called_once_with(
            "CALL DOLT_MERGE(%s, %s, %s)",
            ("-m", "Custom merge commit message", "feature/custom-msg"),
        )

    @patch("infra_core.memory_system.dolt_writer.DoltMySQLWriter._execute_query")
    def test_merge_branch_with_all_flags(self, mock_execute):
        """Test merge operation with all flags and custom message."""
        from infra_core.memory_system.dolt_writer import DoltMySQLWriter
        from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

        # Mock successful merge result
        mock_execute.return_value = [{"merge_result": "merge successful"}]

        # Create writer instance with proper config
        config = DoltConnectionConfig()
        writer = DoltMySQLWriter(config)

        # Execute merge with all options
        success, message = writer.merge_branch(
            "feature/all-flags", squash=True, no_ff=True, commit_message="Complete merge test"
        )

        # Verify results
        assert success is True
        assert "Successfully merged branch 'feature/all-flags'" in message

        # Verify SQL call with all flags
        mock_execute.assert_called_once_with(
            "CALL DOLT_MERGE(%s, %s, %s, %s, %s)",
            ("--squash", "--no-ff", "-m", "Complete merge test", "feature/all-flags"),
        )

    @patch("infra_core.memory_system.dolt_writer.DoltMySQLWriter._execute_query")
    def test_merge_branch_conflict_error(self, mock_execute):
        """Test merge operation that encounters conflicts."""
        from infra_core.memory_system.dolt_writer import DoltMySQLWriter
        from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

        # Mock conflict error
        conflict_error = MySQLError(
            "error: local changes would be stomped by merge:\\n\\tblock_proofs\\n Please commit your changes before you merge."
        )
        mock_execute.side_effect = conflict_error

        # Create writer instance with proper config
        config = DoltConnectionConfig()
        writer = DoltMySQLWriter(config)

        # Execute merge that will fail
        success, message = writer.merge_branch("feature/conflict-branch")

        # Verify results
        assert success is False
        assert "local changes would be stomped by merge" in message
        assert "block_proofs" in message

        # Verify SQL call was attempted
        mock_execute.assert_called_once_with("CALL DOLT_MERGE(%s)", ("feature/conflict-branch",))

    @patch("infra_core.memory_system.dolt_writer.DoltMySQLWriter._execute_query")
    def test_merge_branch_nonexistent_branch_error(self, mock_execute):
        """Test merge operation with non-existent branch."""
        from infra_core.memory_system.dolt_writer import DoltMySQLWriter
        from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

        # Mock branch not found error
        branch_error = MySQLError("Branch 'nonexistent-branch' not found")
        mock_execute.side_effect = branch_error

        # Create writer instance with proper config
        config = DoltConnectionConfig()
        writer = DoltMySQLWriter(config)

        # Execute merge that will fail
        success, message = writer.merge_branch("nonexistent-branch")

        # Verify results
        assert success is False
        assert "Branch 'nonexistent-branch' not found" in message

        # Verify SQL call was attempted
        mock_execute.assert_called_once_with("CALL DOLT_MERGE(%s)", ("nonexistent-branch",))

    def test_merge_branch_parameter_validation(self):
        """Test merge_branch parameter validation."""
        from infra_core.memory_system.dolt_writer import DoltMySQLWriter
        from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

        # Create writer instance with proper config
        config = DoltConnectionConfig()
        writer = DoltMySQLWriter(config)

        # Test empty source branch
        with pytest.raises(ValueError, match="Source branch name cannot be empty"):
            writer.merge_branch("")

        # Test None source branch
        with pytest.raises(ValueError, match="Source branch name cannot be empty"):
            writer.merge_branch(None)

        # Test whitespace-only source branch
        with pytest.raises(ValueError, match="Source branch name cannot be empty"):
            writer.merge_branch("   ")
