import json
from pathlib import Path
from datetime import datetime, timezone  # Import timezone for UTC
import pytest

# Updated imports
from legacy_logseq.memory.memory_bank import FileMemoryBank, CogniLangchainMemoryAdapter
# Assuming adapter is also moved or will be moved to legacy_logseq.memory.adapters
# For now, let's try importing from the expected future location
# If this fails later, we know we need to move the adapter file too.
# from legacy_logseq.memory.adapters.langchain_adapter import CogniLangchainMemoryAdapter
# --> Commenting out Adapter import for now as its location is unconfirmed and tests might not need it directly.
# --> If tests *do* need it, we'll need to locate and move that file first.

# Imports for LangChain messages used in tests
from langchain_core.messages import HumanMessage, AIMessage

# --- Fixtures ---


@pytest.fixture
def temp_memory_bank_root(tmp_path: Path) -> Path:
    """Create a temporary root directory for memory banks."""
    # tmp_path is automatically provided by pytest and cleaned up
    test_root = tmp_path / "_memory_banks_pytest"
    test_root.mkdir(exist_ok=True)  # Use exist_ok=True for safety
    return test_root


@pytest.fixture
def test_project_name() -> str:
    """Return a consistent project name for tests."""
    return "test_project_pytest"


@pytest.fixture
def test_session_id() -> str:
    """Generate a unique session ID for a test run."""
    # Use timezone-aware datetime for UTC
    return "pytest_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")


@pytest.fixture
def core_memory_bank(
    temp_memory_bank_root: Path, test_project_name: str, test_session_id: str
) -> FileMemoryBank:
    """Fixture to create a clean FileMemoryBank instance for testing core logic."""
    bank = FileMemoryBank(
        memory_bank_root=temp_memory_bank_root,
        project_name=test_project_name,
        session_id=test_session_id,
    )
    # Ensure clean state before test by clearing if it somehow exists
    bank.clear_session()
    yield bank
    # Cleanup is implicitly handled by tmp_path fixture removing the root


@pytest.fixture
def adapter_memory_bank(
    temp_memory_bank_root: Path, test_project_name: str, test_session_id: str
) -> FileMemoryBank:
    """Fixture to create a clean FileMemoryBank instance specifically for adapter tests."""
    # Create a distinct session ID for adapter tests
    adapter_session_id = test_session_id + "_adapter"
    bank = FileMemoryBank(
        memory_bank_root=temp_memory_bank_root,
        project_name=test_project_name,
        session_id=adapter_session_id,
    )
    bank.clear_session()  # Ensure clean state
    yield bank


@pytest.fixture
def memory_adapter(adapter_memory_bank: FileMemoryBank) -> CogniLangchainMemoryAdapter:
    """Fixture to create a CogniLangchainMemoryAdapter wrapping a clean memory bank."""
    adapter = CogniLangchainMemoryAdapter(memory_bank=adapter_memory_bank)
    # Clearing is done via the adapter_memory_bank fixture setup
    return adapter


# --- Test Functions ---

# == FileMemoryBank Core Tests ==


def test_memory_bank_initialization(
    core_memory_bank: FileMemoryBank,
    temp_memory_bank_root: Path,
    test_project_name: str,
    test_session_id: str,
):
    """Test basic initialization and path generation."""
    assert core_memory_bank.memory_bank_root == temp_memory_bank_root
    assert core_memory_bank.project_name == test_project_name
    # Check if the generated session_id starts with the prefix we added
    assert core_memory_bank.session_id.startswith("pytest_")
    expected_session_path = temp_memory_bank_root / test_project_name / core_memory_bank.session_id
    assert core_memory_bank._get_session_path() == expected_session_path
    # Ensure path doesn't exist initially (clear_session was called in fixture)
    assert not expected_session_path.exists()


def test_memory_bank_ensure_session_path(core_memory_bank: FileMemoryBank):
    """Test that the session path is created when needed."""
    session_path = core_memory_bank._get_session_path()
    assert not session_path.exists()
    core_memory_bank._ensure_session_path_exists()
    assert session_path.exists()
    assert session_path.is_dir()


def test_memory_bank_history_read_write(core_memory_bank: FileMemoryBank):
    """Test writing and reading history dictionaries."""
    assert core_memory_bank.read_history_dicts() == []  # Should be empty initially

    history1 = [
        {"type": "human", "data": {"content": "Hello Bank!"}},
        {"type": "ai", "data": {"content": "Hello Core!"}},
    ]
    core_memory_bank.write_history_dicts(history1)
    assert core_memory_bank.read_history_dicts() == history1

    history2 = history1 + [
        {"type": "human", "data": {"content": "How does this work?"}},
        {"type": "ai", "data": {"content": "Via file I/O."}},
    ]
    core_memory_bank.write_history_dicts(history2)
    assert core_memory_bank.read_history_dicts() == history2

    # Test reading non-existent history (after clearing)
    core_memory_bank.clear_session()
    assert core_memory_bank.read_history_dicts() == []


def test_memory_bank_write_context_text(core_memory_bank: FileMemoryBank):
    """Test writing plain text context."""
    file_name = "thought.txt"
    content = "This is an intermediate thought."
    core_memory_bank.write_context(file_name, content, is_json=False)
    file_path = core_memory_bank._get_file_path(file_name)
    assert file_path.exists()
    assert file_path.read_text() == content
    assert core_memory_bank._read_file(file_name) == content


def test_memory_bank_write_context_json(core_memory_bank: FileMemoryBank):
    """Test writing JSON context."""
    file_name = "tool_output.json"
    content = {"tool": "calculator", "result": 42, "nested": {"works": True}}
    core_memory_bank.write_context(file_name, content, is_json=True)
    file_path = core_memory_bank._get_file_path(file_name)
    assert file_path.exists()
    loaded_content = json.loads(file_path.read_text())
    assert loaded_content == content
    read_content_str = core_memory_bank._read_file(file_name)
    assert read_content_str is not None  # Add check for None
    assert json.loads(read_content_str) == content


def test_memory_bank_log_decision(core_memory_bank: FileMemoryBank):
    """Test logging decisions to a JSONL file."""
    file_name = "decisions.jsonl"
    decision1 = {"action": "decision_1", "param": "a"}
    decision2 = {"action": "decision_2", "value": 123}

    core_memory_bank.log_decision(decision1)
    core_memory_bank.log_decision(decision2)

    file_path = core_memory_bank._get_file_path(file_name)
    assert file_path.exists()

    lines = file_path.read_text().strip().split("\n")
    assert len(lines) == 2

    log1 = json.loads(lines[0])
    log2 = json.loads(lines[1])

    assert log1["action"] == decision1["action"]
    assert log1["param"] == decision1["param"]
    assert "timestamp" in log1

    assert log2["action"] == decision2["action"]
    assert log2["value"] == decision2["value"]
    assert "timestamp" in log2
    assert log2["timestamp"] >= log1["timestamp"]  # Check order


def test_memory_bank_update_progress(core_memory_bank: FileMemoryBank):
    """Test updating the progress JSON file."""
    file_name = "progress.json"
    progress1 = {"status": "running", "step": 1}
    progress2 = {"status": "complete", "step": 2, "result": "ok"}

    core_memory_bank.update_progress(progress1)
    file_path = core_memory_bank._get_file_path(file_name)
    assert file_path.exists()
    assert json.loads(file_path.read_text()) == progress1

    core_memory_bank.update_progress(progress2)  # Should overwrite
    assert file_path.exists()
    assert json.loads(file_path.read_text()) == progress2


def test_memory_bank_clear_session(core_memory_bank: FileMemoryBank):
    """Test clearing the session directory."""
    # Write some files first
    core_memory_bank.write_context("test1.txt", "content1")
    core_memory_bank.log_decision({"action": "test"})
    session_path = core_memory_bank._get_session_path()
    # Ensure path exists before asserting it has contents
    core_memory_bank._ensure_session_path_exists()
    assert session_path.exists()
    # Ensure files were actually written before checking emptiness
    assert (session_path / "test1.txt").exists()
    assert (session_path / "decisions.jsonl").exists()

    core_memory_bank.clear_session()
    assert not session_path.exists()


# == CogniLangchainMemoryAdapter Tests ==


def test_adapter_initial_load(memory_adapter: CogniLangchainMemoryAdapter):
    """Test loading memory when the history file doesn't exist."""
    loaded_vars = memory_adapter.load_memory_variables({})
    assert loaded_vars == {"history": []}


def test_adapter_save_and_load(memory_adapter: CogniLangchainMemoryAdapter):
    """Test saving context and loading it back via the adapter."""
    # Interaction 1
    inputs1 = {"input": "Hello Adapter!"}
    outputs1 = {"output": "Hello Langchain!"}
    memory_adapter.save_context(inputs1, outputs1)

    # Load after 1 save
    loaded_vars1 = memory_adapter.load_memory_variables({})
    history1 = loaded_vars1.get("history", [])
    assert len(history1) == 2
    assert isinstance(history1[0], HumanMessage)
    assert history1[0].content == inputs1["input"]
    assert isinstance(history1[1], AIMessage)
    assert history1[1].content == outputs1["output"]

    # Interaction 2
    inputs2 = {"input": "How is the wrapping?"}
    outputs2 = {"output": "Seems functional."}
    memory_adapter.save_context(inputs2, outputs2)

    # Load after 2 saves
    loaded_vars2 = memory_adapter.load_memory_variables({})
    history2 = loaded_vars2.get("history", [])
    assert len(history2) == 4
    # Check previous messages are still there
    assert history2[0].content == inputs1["input"]
    assert history2[1].content == outputs1["output"]
    # Check new messages
    assert isinstance(history2[2], HumanMessage)
    assert history2[2].content == inputs2["input"]
    assert isinstance(history2[3], AIMessage)
    assert history2[3].content == outputs2["output"]


def test_adapter_clear(memory_adapter: CogniLangchainMemoryAdapter):
    """Test clearing memory via the adapter."""
    # Save something first to ensure the directory exists
    inputs1 = {"input": "Need to save something"}
    outputs1 = {"output": "OK"}
    memory_adapter.save_context(inputs1, outputs1)

    session_path = memory_adapter.memory_bank._get_session_path()
    assert session_path.exists()

    memory_adapter.clear()
    assert not session_path.exists()

    # Check loading after clear returns empty
    loaded_vars = memory_adapter.load_memory_variables({})
    assert loaded_vars == {"history": []}


# == Markdown Export Test ==


def test_markdown_export(memory_adapter: CogniLangchainMemoryAdapter):
    """Test the markdown export functionality."""
    # Use the adapter fixture which has a clean bank initially
    # Save some history using the adapter
    inputs1 = {"input": "First Input"}
    outputs1 = {"output": "First Response"}
    memory_adapter.save_context(inputs1, outputs1)
    inputs2 = {"input": "Second Input"}
    outputs2 = {"output": "Second Response"}
    memory_adapter.save_context(inputs2, outputs2)

    # Export using the underlying bank instance
    markdown_output = memory_adapter.memory_bank.export_history_markdown()

    # Basic checks
    assert "# Conversation History" in markdown_output
    assert "\n## Human\nFirst Input" in markdown_output
    assert "\n## Ai\nFirst Response" in markdown_output  # Corrected case
    assert "\n## Human\nSecond Input" in markdown_output
    assert "\n## Ai\nSecond Response" in markdown_output  # Corrected case
    assert markdown_output.count("\n## ") == 4  # Check for 4 message headers


def test_markdown_export_empty(core_memory_bank: FileMemoryBank):
    """Test markdown export when history is empty."""
    markdown_output = core_memory_bank.export_history_markdown()
    assert markdown_output == "# Conversation History\n\n*No history found.*"
