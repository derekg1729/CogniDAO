"""
Tests for the Dolt schema generation script.
"""

import os
import pytest
from unittest.mock import patch, mock_open

from experiments.scripts.generate_dolt_schema import generate_schema_sql, main


class TestGenerateDoltSchema:
    """Tests for the Dolt schema generation functionality."""

    @pytest.fixture
    def mock_file(self):
        """Create a mock file for testing file operations."""
        with patch("builtins.open", mock_open()) as mock_file:
            yield mock_file

    @pytest.fixture
    def mock_makedirs(self):
        """Create a mock for os.makedirs."""
        with patch("os.makedirs") as mock:
            yield mock

    def test_generate_schema_sql_success(self, mock_file, mock_makedirs):
        """Test successful schema generation."""
        # Set up test
        output_path = "/fake/path/schema.sql"

        # Call the function
        result = generate_schema_sql(output_path)

        # Check results
        assert result is True
        mock_makedirs.assert_called_once_with(os.path.dirname(output_path), exist_ok=True)
        mock_file.assert_called_once_with(output_path, "w")

        # Get the written content
        handle = mock_file()
        written_content = handle.write.call_args[0][0]

        # Check key elements in the generated SQL
        assert "CREATE TABLE memory_blocks" in written_content
        assert "CREATE TABLE block_links" in written_content
        assert "CREATE TABLE node_schemas" in written_content
        assert "CREATE TABLE block_proofs" in written_content

        # Check specific fields
        assert "id VARCHAR(255) PRIMARY KEY" in written_content
        assert "type TEXT NOT NULL" in written_content
        assert "text TEXT NOT NULL" in written_content
        assert "json_schema JSON NOT NULL" in written_content

    def test_generate_schema_sql_failure(self, mock_file, mock_makedirs):
        """Test schema generation failure."""
        # Make the file operation fail
        mock_file.side_effect = IOError("Test error")

        # Call the function
        result = generate_schema_sql("/fake/path/schema.sql")

        # Check result
        assert result is False

    def test_main_success(self, mock_file, mock_makedirs):
        """Test the main function with successful schema generation."""
        # Set up test
        with (
            patch("os.path.dirname") as mock_dirname,
            patch("os.path.abspath") as mock_abspath,
            patch("os.path.join") as mock_join,
        ):
            # Mock path operations
            mock_dirname.return_value = "/fake/script/dir"
            mock_abspath.return_value = "/fake/script/dir/generate_dolt_schema.py"
            mock_join.return_value = "/fake/script/dir/../dolt_data/schema.sql"

            # Call main
            main()

            # Verify path operations
            mock_dirname.assert_called()
            mock_abspath.assert_called()
            mock_join.assert_called()

            # Verify file operations
            mock_file.assert_called_once()

    def test_main_failure(self, mock_file, mock_makedirs):
        """Test the main function with failed schema generation."""
        # Make the file operation fail
        mock_file.side_effect = IOError("Test error")

        # Call main
        main()
        # Verify file operations were attempted
        mock_makedirs.assert_called_once()
        mock_file.assert_called_once()
