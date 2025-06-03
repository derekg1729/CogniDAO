"""
Shared pytest fixtures for memory system tests.

This conftest.py provides a comprehensive testing setup that:
1. Creates a temporary Dolt repository
2. Initializes it with proper schema
3. Starts a real dolt sql-server on a free port
4. Provides DoltConnectionConfig pointing to that server
5. Creates temporary ChromaDB storage
6. Provides StructuredMemoryBank instances using the new MySQL-only constructor

This is the DRY approach - all tests can use these fixtures instead of
creating their own test setup.
"""

import pytest
import tempfile
import subprocess
import time
import socket
import shutil
from typing import Generator
from pathlib import Path

from infra_core.memory_system.initialize_dolt import initialize_dolt_db
from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.schemas.memory_block import MemoryBlock
from infra_core.memory_system.schemas.common import ConfidenceScore


def find_free_port() -> int:
    """Find a free port for the test dolt sql-server, avoiding common database ports."""
    # Start from port 9000 to avoid common database ports (3306, 5432, etc.)
    for port in range(9000, 65535):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", port))
                s.listen(1)
                return port
        except OSError:
            continue  # Port is in use, try next one

    # Fallback to original method if no port found in range
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


@pytest.fixture(scope="session")
def temp_dolt_repo() -> Generator[str, None, None]:
    """Create a temporary Dolt repository with proper schema."""
    # Create temporary directory
    temp_dir = tempfile.mkdtemp(prefix="test_dolt_")

    try:
        # Initialize Dolt repo and create tables
        success = initialize_dolt_db(temp_dir)
        assert success, f"Failed to initialize Dolt database in {temp_dir}"

        # Commit the initial schema so it's visible to sql-server
        subprocess.run(
            ["dolt", "add", "."],
            cwd=temp_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["dolt", "commit", "-m", "Initial schema for test database"],
            cwd=temp_dir,
            check=True,
            capture_output=True,
            text=True,
        )

        yield temp_dir

    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def dolt_sql_server(temp_dolt_repo: str) -> Generator[tuple[str, int], None, None]:
    """Start a dolt sql-server on the temp repo and return (host, port)."""
    # Find a free port
    port = find_free_port()
    host = "localhost"

    # Database name is the same as the directory name in Dolt
    database_name = Path(temp_dolt_repo).name

    # Start dolt sql-server
    process = subprocess.Popen(
        ["dolt", "sql-server", f"--host={host}", f"--port={port}", "--no-auto-commit"],
        cwd=temp_dolt_repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Wait for server to start up
    max_retries = 5
    for retry in range(max_retries):
        try:
            # Try to connect
            import mysql.connector

            conn = mysql.connector.connect(
                host=host,
                port=port,
                user="root",
                password="",
                database=database_name,  # Use correct database name
                connection_timeout=2,
            )
            conn.close()
            break  # Connection successful
        except Exception as e:
            if retry == max_retries - 1:  # Last retry, capture error details
                # Get stderr/stdout from the process
                stdout, stderr = process.communicate()
                print(f"Dolt SQL server failed to start. Port: {port}, Database: {database_name}")
                print(f"Process stdout: {stdout}")
                print(f"Process stderr: {stderr}")
                print(f"Process return code: {process.returncode}")
                print(f"Connection error: {e}")
            time.sleep(0.5)
    else:
        # Server didn't start in time
        process.terminate()
        process.wait()
        raise RuntimeError(f"Dolt SQL server failed to start on port {port}")

    try:
        yield (host, port)
    finally:
        # Cleanup: terminate the server
        process.terminate()
        process.wait()


@pytest.fixture(scope="session")
def dolt_connection_config(
    dolt_sql_server: tuple[str, int], temp_dolt_repo: str
) -> DoltConnectionConfig:
    """Provide DoltConnectionConfig pointing to the test server."""
    host, port = dolt_sql_server
    # Database name is the same as the directory name in Dolt
    database_name = Path(temp_dolt_repo).name
    return DoltConnectionConfig(
        host=host,
        port=port,
        user="root",
        password="",
        database=database_name,
    )


@pytest.fixture(scope="session")
def temp_chroma_path() -> Generator[str, None, None]:
    """Temporary ChromaDB storage path for testing."""
    with tempfile.TemporaryDirectory(prefix="test_chroma_") as temp_dir:
        yield temp_dir


@pytest.fixture(scope="function")
def integration_memory_bank(
    dolt_connection_config: DoltConnectionConfig, temp_chroma_path: str
) -> StructuredMemoryBank:
    """Create a StructuredMemoryBank instance using the test setup."""
    return StructuredMemoryBank(
        chroma_path=temp_chroma_path,
        chroma_collection="test_collection",
        dolt_connection_config=dolt_connection_config,
        branch="main",
    )


@pytest.fixture(scope="function")
def temp_memory_bank(
    dolt_connection_config: DoltConnectionConfig, temp_chroma_path: str
) -> StructuredMemoryBank:
    """Create a StructuredMemoryBank instance using the test setup (backward compatibility alias)."""
    return StructuredMemoryBank(
        chroma_path=temp_chroma_path,
        chroma_collection="test_collection",
        dolt_connection_config=dolt_connection_config,
        branch="main",
    )


@pytest.fixture
def sample_memory_block() -> MemoryBlock:
    """Provide a sample MemoryBlock for testing."""
    return MemoryBlock(
        id="test-block-001",
        type="knowledge",
        text="This is a test memory block.",
        tags=["test", "fixture"],
        metadata={"source": "pytest"},
        confidence=ConfidenceScore(human=0.9),
    )


@pytest.fixture
def sample_memory_block_with_links() -> MemoryBlock:
    """Provide a sample MemoryBlock with links for testing."""
    return MemoryBlock(
        id="test-block-with-links-001",
        type="task",
        text="This is a test memory block with links.",
        tags=["test", "fixture", "links"],
        metadata={"source": "pytest", "priority": "high"},
        confidence=ConfidenceScore(human=0.9, ai=0.8),
    )
