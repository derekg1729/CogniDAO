"""
Tests for the Dolt database initialization functionality.

This module tests the initialization process of Dolt databases, including:
- Directory creation and validation
- Dolt repository initialization
- Table creation (memory_blocks and node_schemas)
- Error handling
- Command line interface
"""

import logging
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from infra_core.memory_system.initialize_dolt import (
    initialize_dolt_db,
    parse_args,
)

# Configure logging for tests
logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Fixtures ---


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for testing."""
    return tmp_path / "test_dolt_db"


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run for testing command execution."""
    with patch("subprocess.run") as mock:
        yield mock


# --- Tests ---


def test_directory_creation(temp_dir):
    """Test that directory is created if it doesn't exist."""
    # Directory shouldn't exist initially
    assert not temp_dir.exists()

    # Initialize Dolt DB
    result = initialize_dolt_db(str(temp_dir))

    # Directory should exist now
    assert temp_dir.exists()
    assert temp_dir.is_dir()
    assert result is True


def test_existing_directory(temp_dir):
    """Test handling of existing directory."""
    # Create directory first
    temp_dir.mkdir()

    # Initialize Dolt DB
    result = initialize_dolt_db(str(temp_dir))

    # Directory should still exist
    assert temp_dir.exists()
    assert temp_dir.is_dir()
    assert result is True


def test_existing_file(temp_dir):
    """Test handling of path that exists but is a file."""
    # Create a file instead of directory
    temp_dir.write_text("test")

    # Initialize Dolt DB should fail
    result = initialize_dolt_db(str(temp_dir))
    assert result is False


def test_dolt_init(temp_dir, mock_subprocess):
    """Test Dolt repository initialization."""
    # Configure mock to simulate successful Dolt init
    mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")

    # Initialize Dolt DB
    result = initialize_dolt_db(str(temp_dir))

    # Check that dolt init was called
    mock_subprocess.assert_any_call(
        ["dolt", "init"], cwd=str(temp_dir), check=True, capture_output=True, text=True
    )
    assert result is True


def test_table_creation(temp_dir, mock_subprocess):
    """Test creation of memory_blocks and node_schemas tables."""
    # Configure mock to simulate successful table creation
    mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")

    # Initialize Dolt DB
    with patch("infra_core.memory_system.initialize_dolt.run_command") as mock_run_command:
        mock_run_command.return_value = True
        result = initialize_dolt_db(str(temp_dir))

    # Get the actual SQL command that was called
    sql_calls = [
        call
        for call in mock_run_command.call_args_list
        if len(call[0]) >= 1 and call[0][0][0] == "dolt" and call[0][0][1] == "sql"
    ]
    assert len(sql_calls) == 1, "Expected exactly one SQL command call"

    # Check that the SQL file was used
    assert "--file" in sql_calls[0][0][0], "SQL file was not used to create tables"
    assert "create_tables.sql" in sql_calls[0][0][0], "SQL file was not used to create tables"
    assert result is True


def test_command_not_found(temp_dir, mock_subprocess):
    """Test handling of missing Dolt CLI."""
    # Configure mock to simulate command not found
    mock_subprocess.side_effect = FileNotFoundError("dolt: command not found")

    # Initialize Dolt DB should fail
    result = initialize_dolt_db(str(temp_dir))
    assert result is False


def test_command_failure(temp_dir, mock_subprocess):
    """Test handling of Dolt command failure."""
    # Configure mock to simulate command failure
    mock_subprocess.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=["dolt", "init"], output="", stderr="Error: Dolt init failed"
    )

    # Initialize Dolt DB should fail
    result = initialize_dolt_db(str(temp_dir))
    assert result is False


def test_parse_args():
    """Test command line argument parsing."""
    # Test with a path argument
    with patch("sys.argv", ["script.py", "/test/path"]):
        args = parse_args()
        assert args.db_path == "/test/path"


def test_script_execution_success(temp_dir, mock_subprocess):
    """Test script execution with successful initialization."""
    # Configure mock to simulate successful initialization
    mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")

    # Mock sys.exit to prevent actual exit
    with patch("sys.exit") as mock_exit:
        with patch("sys.argv", ["script.py", str(temp_dir)]):
            # Run the script's main code
            args = parse_args()
            if initialize_dolt_db(args.db_path):
                sys.exit(0)
            else:
                sys.exit(1)

            # Check that sys.exit(0) was called
            mock_exit.assert_called_once_with(0)


def test_script_execution_failure(temp_dir, mock_subprocess):
    """Test script execution with failed initialization."""
    # Configure mock to simulate initialization failure
    mock_subprocess.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=["dolt", "init"], output="", stderr="Error: Dolt init failed"
    )

    # Mock sys.exit to prevent actual exit
    with patch("sys.exit") as mock_exit:
        with patch("sys.argv", ["script.py", str(temp_dir)]):
            # Run the script's main code
            args = parse_args()
            if initialize_dolt_db(args.db_path):
                sys.exit(0)
            else:
                sys.exit(1)

            # Check that sys.exit(1) was called
            mock_exit.assert_called_once_with(1)
