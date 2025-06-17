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
# pytest_plugins = ["tests.infra_core.memory_system.conftest"]  # Temporarily commented during consolidation


# === General Testing Fixtures ===


@pytest.fixture
def sample_block_id():
    """Generate a valid UUID for testing."""
    return str(uuid.uuid4())


@pytest.fixture
def mock_memory_bank():
    """Create a properly configured mock StructuredMemoryBank for unit tests.

    This fixture provides a mock that includes:
    - dolt_writer.active_branch property set to "main"
    - Common method mocks with sensible defaults
    """
    from unittest.mock import MagicMock

    bank = MagicMock()

    # Configure common method returns
    bank.get_latest_schema_version.return_value = 1
    bank.create_memory_block.return_value = (True, None)
    bank.update_memory_block.return_value = True
    bank.get_memory_block.return_value = None

    # Add dolt_writer mock with active_branch property
    bank.dolt_writer = MagicMock()
    bank.dolt_writer.active_branch = "main"

    # Add dolt_reader mock for completeness
    bank.dolt_reader = MagicMock()
    bank.dolt_reader.active_branch = "main"

    return bank


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


# Shared MCP Server Mocking Fixtures (using proven working pattern)
@pytest.fixture(autouse=True)
def mock_mysql_connect_for_mcp_server(monkeypatch):
    """
    Replace mysql.connector.connect with a dummy connection for MCP server tests.
    This prevents sys.exit(1) during module import when tests run.
    Uses the proven working pattern from test_mcp_poc_dry.py.
    """
    dummy_conn = MagicMock()
    dummy_cursor = MagicMock()
    dummy_cursor.execute.return_value = None
    dummy_cursor.fetchone.return_value = (1,)
    dummy_conn.cursor.return_value = dummy_cursor

    # Patch the connect() call globally for all MCP server tests
    monkeypatch.setattr("mysql.connector.connect", lambda **kwargs: dummy_conn)
    yield


@pytest.fixture(autouse=True)
def mock_structured_memory_bank_for_mcp_server(monkeypatch):
    """
    Replace StructuredMemoryBank and SQLLinkManager with MagicMocks for MCP server tests.
    This ensures MCP tools work without real persistence layers during testing.
    Uses the proven working pattern from test_mcp_poc_dry.py with enhanced return values
    for Pydantic validation compatibility.
    """
    from infra_core.memory_system.link_manager import LinkManager

    dummy_bank = MagicMock()
    dummy_link_mgr = MagicMock()

    # Make isinstance(link_manager, LinkManager) return True for validation
    dummy_link_mgr.__class__ = LinkManager

    # Configure get_all_links to return properly structured data instead of MagicMock
    class MockLinkResult:
        def __init__(self):
            self.links = []  # Empty list instead of MagicMock
            self.next_cursor = None  # None instead of MagicMock (Pydantic expects str|None)

    dummy_link_mgr.get_all_links.return_value = MockLinkResult()

    # Configure the dummy_bank to have a link_manager attribute pointing to dummy_link_mgr
    dummy_bank.link_manager = dummy_link_mgr

    # Configure dummy_bank methods to return proper types for Pydantic validation
    dummy_bank.active_branch = "main"  # String instead of MagicMock
    dummy_bank.get_memory_blocks.return_value = []  # Empty list for work items

    # Configure writer mock to return proper string for active_branch
    dummy_writer = MagicMock()

    # Use PropertyMock to ensure active_branch always returns a string
    from unittest.mock import PropertyMock

    type(dummy_writer).active_branch = PropertyMock(return_value="main")

    dummy_writer.list_branches.return_value = ([], "main")  # (branches_list, current_branch)
    dummy_writer._execute_query.return_value = [
        {"branch": "main"}
    ]  # For SELECT active_branch() query
    dummy_bank.writer = dummy_writer
    dummy_bank.dolt_writer = dummy_writer  # Also set as dolt_writer

    # Patch the constructors globally for all MCP server tests
    monkeypatch.setattr(
        "infra_core.memory_system.structured_memory_bank.StructuredMemoryBank",
        lambda *args, **kwargs: dummy_bank,
    )
    monkeypatch.setattr(
        "infra_core.memory_system.sql_link_manager.SQLLinkManager",
        lambda *args, **kwargs: dummy_link_mgr,
    )
    yield


@pytest.fixture
def mcp_app():
    """
    Import and reload the MCP server so that mocks apply at module-load time.
    This uses the proven working pattern from test_mcp_poc_dry.py.
    Tests should use this fixture to get a properly mocked MCP server module.
    """
    import importlib
    import services.mcp_server.app.mcp_server as app_module

    return importlib.reload(app_module)


@pytest.fixture
def sample_work_item_input():
    """Sample input for creating a work item."""
    return {
        "type": "task",
        "title": "Test Task",
        "description": "A test task for validation",
        "owner": "test_user",
        "acceptance_criteria": ["Criterion 1", "Criterion 2"],
        "action_items": [],
        "expected_artifacts": [],
        "blocked_by": [],
        "tool_hints": [],
        "tags": [],
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
def sample_memory_block_update():
    """Sample memory block update data."""
    return {
        "text": "Updated text content",
        "tags": ["updated", "test"],
        "metadata": {"source": "test", "priority": "high"},
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
        "action_items": [],
        "expected_artifacts": [],
        "blocked_by": [],
        "tool_hints": [],
        "tags": [],
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
