"""
Common fixtures for testing the Cogni Memory Architecture.
"""

import os
import tempfile
import shutil
import pytest
import sys
import uuid
from unittest.mock import MagicMock
import subprocess

# Ensure project root is in the Python path for test discovery from any location
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Configure pytest
pytest_plugins = []


# === General Testing Fixtures ===


@pytest.fixture
def sample_block_id():
    """Generate a valid UUID for testing."""
    return str(uuid.uuid4())


@pytest.fixture
def mock_memory_bank():
    """Create a mock memory bank for testing."""
    mock_bank = MagicMock()
    mock_bank.get_memory_block.return_value = None
    mock_bank.update_memory_block.return_value = True
    return mock_bank


# === Temporary Database Fixtures for MCP Server Tests ===


@pytest.fixture(scope="module")
def temp_dolt_db(tmp_path_factory):
    """Create a temporary Dolt database for MCP server testing."""
    from infra_core.memory_system.initialize_dolt import initialize_dolt_db

    db_path = tmp_path_factory.mktemp("test_mcp_dolt_db")
    assert initialize_dolt_db(str(db_path)), "Failed to initialize test Dolt DB"

    # CRITICAL FIX: Commit the table creation changes so they are visible to all operations
    try:
        subprocess.run(
            ["dolt", "add", "."],
            cwd=str(db_path),
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            ["dolt", "commit", "-m", "Initial table creation for test database"],
            cwd=str(db_path),
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise Exception(f"Failed to commit table creation in test database: {e}")

    return str(db_path)


@pytest.fixture(scope="module")
def temp_chroma_db(tmp_path_factory):
    """Create a temporary ChromaDB for MCP server testing."""
    chroma_path = tmp_path_factory.mktemp("test_mcp_chroma")
    return str(chroma_path)


# Note: temp_memory_bank fixture is now provided by infra_core/memory_system/tests/conftest.py
# which creates a proper Dolt SQL server setup instead of trying to connect to localhost:3306


# === MCP Server Testing Fixtures ===


@pytest.fixture
def sample_work_item_input():
    """Sample input for creating a work item."""
    return {
        "type": "task",
        "title": "Test Task",
        "description": "A test task for validation",
        "owner": "test_user",
        "acceptance_criteria": ["Criterion 1", "Criterion 2"],
    }


@pytest.fixture
def sample_memory_block_input(sample_block_id):
    """Sample input for updating a memory block."""
    return {
        "block_id": sample_block_id,
        "text": "Updated text content",
        "tags": ["test", "updated"],
        "change_note": "Test update",
    }


@pytest.fixture
def sample_work_item_update_input(sample_block_id):
    """Sample input for updating a work item."""
    return {
        "block_id": sample_block_id,
        "title": "Updated Task Title",
        "status": "in_progress",
        "change_note": "Updated task status",
    }


@pytest.fixture
def sample_work_item_data():
    """Sample data for creating a work item."""
    return {
        "type": "task",
        "title": "Integration Test Task",
        "description": "Testing the complete workflow",
        "owner": "test-user",
        "acceptance_criteria": ["Complete integration test"],
        "agent_id": "test-agent-001",
    }


@pytest.fixture
def sample_memory_block_data():
    """Sample data for creating a memory block."""
    return {
        "block_id": str(uuid.uuid4()),
        "text": "Original content",
        "tags": ["test"],
        "metadata": {"x_agent_id": "test-agent-001"},
        "agent_id": "test-agent-001",
    }


# === Legacy Logseq Testing Fixtures ===


@pytest.fixture
def sample_logseq_dir():
    """
    Create a temporary directory with sample Logseq markdown files.

    This fixture creates markdown files with various tagged and untagged blocks
    that can be used for testing the parser and indexer.
    """
    temp_dir = tempfile.mkdtemp()
    try:
        # Create test files
        with open(os.path.join(temp_dir, "test1.md"), "w") as f:
            f.write("- Test block with #thought tag\n")
            f.write("- Regular block without tags\n")
            f.write("- Another #thought with some context\n")

        with open(os.path.join(temp_dir, "test2.md"), "w") as f:
            f.write("- Test block with #broadcast tag\n")
            f.write("- Test block with #broadcast and #approved tags\n")
            f.write("- More content without tags\n")

        with open(os.path.join(temp_dir, "mixed.md"), "w") as f:
            f.write("- Multiple tags in one block #thought #broadcast\n")
            f.write("- Some complex formatting with *italic* and **bold** #approved\n")
            f.write("- Block with a [[Page Link]] #thought\n")
            f.write("- Regular content without any special formatting or tags\n")

        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)


@pytest.fixture
def sample_memory_blocks():
    """
    Create sample memory block data for testing.

    This fixture provides a list of dictionaries that mimic the structure
    of MemoryBlock objects, without requiring the actual implementation.
    These can be used to test storage and client components.
    """
    return [
        {
            "id": "test-block-1",
            "text": "Test block with #thought tag",
            "tags": ["#thought"],
            "source_file": "test1.md",
            "embedding": [0.1] * 1536,  # Mock embedding vector
        },
        {
            "id": "test-block-2",
            "text": "Test block with #broadcast tag",
            "tags": ["#broadcast"],
            "source_file": "test2.md",
            "embedding": [0.2] * 1536,
        },
        {
            "id": "test-block-3",
            "text": "Test block with #broadcast and #approved tags",
            "tags": ["#broadcast", "#approved"],
            "source_file": "test2.md",
            "embedding": [0.3] * 1536,
        },
        {
            "id": "test-block-4",
            "text": "Multiple tags in one block #thought #broadcast",
            "tags": ["#thought", "#broadcast"],
            "source_file": "mixed.md",
            "embedding": [0.4] * 1536,
        },
    ]


@pytest.fixture
def test_storage_dirs():
    """
    Create temporary directories for testing storage components.

    This fixture creates directories for ChromaDB and Archive storage,
    and cleans them up after the tests.
    """
    chroma_dir = tempfile.mkdtemp()
    archive_dir = tempfile.mkdtemp()
    try:
        # Create archive subdirectories
        os.makedirs(os.path.join(archive_dir, "blocks"))
        os.makedirs(os.path.join(archive_dir, "index"))

        yield {"chroma": chroma_dir, "archive": archive_dir}
    finally:
        shutil.rmtree(chroma_dir)
        shutil.rmtree(archive_dir)


@pytest.fixture(scope="function")
def temp_memory_bank():
    """Create a StructuredMemoryBank using the working pattern from memory system tests."""
    from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
    import tempfile

    # Create temporary paths
    with tempfile.TemporaryDirectory(prefix="test_dolt_") as temp_dolt_dir:
        with tempfile.TemporaryDirectory(prefix="test_chroma_") as temp_chroma_dir:
            # Import and run the setup from memory system conftest
            from infra_core.memory_system.initialize_dolt import initialize_dolt_db
            from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig
            from infra_core.memory_system.dolt_schema_manager import register_all_metadata_schemas
            import subprocess
            import socket
            from pathlib import Path

            # Initialize Dolt repo
            success = initialize_dolt_db(temp_dolt_dir)
            assert success, f"Failed to initialize Dolt database in {temp_dolt_dir}"

            # CRITICAL: Register all metadata schemas
            registration = register_all_metadata_schemas(db_path=temp_dolt_dir)
            assert all(registration.values()), f"Schema registration failed: {registration}"

            # Commit the initial schema
            subprocess.run(
                ["dolt", "add", "."],
                cwd=temp_dolt_dir,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["dolt", "commit", "-m", "Initial schema for test database"],
                cwd=temp_dolt_dir,
                check=True,
                capture_output=True,
                text=True,
            )

            # Find free port and start dolt sql-server
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", 0))
                s.listen(1)
                port = s.getsockname()[1]

            host = "localhost"
            database_name = Path(temp_dolt_dir).name

            # Start dolt sql-server
            process = subprocess.Popen(
                ["dolt", "sql-server", f"--host={host}", f"--port={port}", "--no-auto-commit"],
                cwd=temp_dolt_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Wait for server to start
            import time

            for retry in range(5):
                try:
                    import mysql.connector

                    conn = mysql.connector.connect(
                        host=host,
                        port=port,
                        user="root",
                        password="",
                        database=database_name,
                        connection_timeout=2,
                    )
                    conn.close()
                    break
                except Exception:
                    if retry == 4:
                        process.terminate()
                        process.wait()
                        raise RuntimeError(f"Dolt SQL server failed to start on port {port}")
                    time.sleep(0.5)

            try:
                # Create connection config
                dolt_config = DoltConnectionConfig(
                    host=host,
                    port=port,
                    user="root",
                    password="",
                    database=database_name,
                )

                # Create StructuredMemoryBank
                bank = StructuredMemoryBank(
                    chroma_path=temp_chroma_dir,
                    chroma_collection="test_collection",
                    dolt_connection_config=dolt_config,
                    branch="main",
                )

                yield bank

            finally:
                # Cleanup: terminate the server
                process.terminate()
                process.wait()
