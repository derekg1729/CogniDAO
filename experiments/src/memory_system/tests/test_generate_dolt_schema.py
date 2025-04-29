"""
Tests for the Dolt schema generation script.
"""

from pathlib import Path
import pytest
from unittest.mock import patch, mock_open

from experiments.scripts.generate_dolt_schema import (
    generate_schema_file as generate_schema_sql,
    main,
)


class TestGenerateDoltSchema:
    """Tests for the Dolt schema generation functionality."""

    @pytest.fixture
    def mock_file(self):
        """Create a mock file for testing file operations."""
        with patch("builtins.open", mock_open()) as mock_file:
            yield mock_file

    @pytest.fixture
    def mock_mkdir(self):
        """Create a mock for Path.mkdir."""
        with patch("pathlib.Path.mkdir") as mock:
            yield mock

    def test_generate_schema_sql_success(self, mock_file, mock_mkdir):
        """Test successful schema generation."""
        # Set up test
        output_path = Path("/fake/path/schema.sql")

        # Call the function
        generate_schema_sql(output_path)

        # Check results
        mock_mkdir.assert_called_with(parents=True, exist_ok=True)
        mock_file.assert_called_once_with(output_path, "w")

        # Get the written content
        handle = mock_file()
        written_content = handle.write.call_args[0][0]

        # Check key elements in the generated SQL
        assert "CREATE TABLE IF NOT EXISTS memory_blocks" in written_content
        assert "CREATE TABLE IF NOT EXISTS block_links" in written_content
        assert "CREATE INDEX idx_memory_blocks_type_state_visibility" in written_content
        assert "CREATE INDEX idx_block_links_to_id" in written_content

        # Check specific fields and constraints
        assert "id VARCHAR(255) PRIMARY KEY" in written_content
        assert "type VARCHAR(50) NOT NULL" in written_content
        assert "text LONGTEXT NOT NULL" in written_content
        assert "CONSTRAINT chk_valid_state" in written_content
        assert "CONSTRAINT chk_valid_visibility" in written_content
        assert "CONSTRAINT chk_block_version_positive" in written_content

    def test_main_success(self, mock_file, mock_mkdir):
        """Test the main function with successful schema generation."""
        # Call main
        main()

        # Verify file operations
        mock_mkdir.assert_called_with(parents=True, exist_ok=True)
        mock_file.assert_called_once()
