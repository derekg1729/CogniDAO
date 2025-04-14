"""
Tests for the CogniAgent base class.
"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, call
from typing import Dict, Any

from infra_core.cogni_agents.base import CogniAgent
from infra_core.memory.memory_bank import CogniMemoryBank # Needed for type hinting and patching targets

# Dummy concrete agent implementation for testing
class DummyAgent(CogniAgent):
    def act(self, prepared_input: Dict[str, Any]) -> Dict[str, Any]:
        return {"result": "dummy action performed"}

# Fixtures
@pytest.fixture
def temp_dir():
    """Create a temporary directory for test artifacts, acting as project_root override."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def agent_root(temp_dir):
    """Create a dedicated agent root directory within the temp directory."""
    root = temp_dir / "agent_output"
    root.mkdir()
    return root

@pytest.fixture
def memory_bank_root(temp_dir):
    """Create a dedicated memory bank root directory within the temp directory."""
    root = temp_dir / "memory_banks"
    root.mkdir()
    return root

@pytest.fixture
def spirit_file(temp_dir):
    """Create a dummy spirit file."""
    file_path = temp_dir / "dummy_spirit.md"
    file_path.write_text("# Dummy Spirit Guide\nBe helpful.")
    return file_path

@pytest.fixture
def core_files(temp_dir):
    """Create dummy core document files within the temp_dir (project_root_override)."""
    files = {}
    core_docs = ["CHARTER.md", "MANIFESTO.md", "LICENSE.md", "README.md"]
    for fname in core_docs:
        # Place directly in temp_dir, matching structure expected by agent fallback
        fpath = temp_dir / fname 
        fpath.write_text(f"# {fname}\nContent for {fname}")
        files[fname] = fpath
    
    # Core spirit guide (place relative to temp_dir)
    core_spirit_dir = temp_dir / "infra_core/cogni_spirit/spirits"
    core_spirit_dir.mkdir(parents=True, exist_ok=True)
    core_spirit_path = core_spirit_dir / "cogni-core-spirit.md"
    core_spirit_path.write_text("# Core Spirit\nAct wisely.")
    files["core_spirit"] = core_spirit_path
    
    # Also create a custom guide (place relative to temp_dir)
    custom_guide_path = core_spirit_dir / "custom-guide.md"
    custom_guide_path.write_text("# Custom Guide\nBe specific.")
    files["custom-guide"] = custom_guide_path

    return files

# --- Test Cases ---

def test_agent_initialization(agent_root, spirit_file, memory_bank_root, temp_dir):
    """Test that the agent initializes correctly with CogniMemoryBank."""
    agent = DummyAgent(
        name="test_dummy", 
        spirit_path=spirit_file, 
        agent_root=agent_root,
        memory_bank_root_override=memory_bank_root,
        project_root_override=temp_dir # Pass temp_dir as project root
    )
    
    assert agent.name == "test_dummy"
    assert agent.spirit_path == spirit_file
    assert agent.agent_root == agent_root
    assert agent.project_root == temp_dir # Check project_root override was set
    assert isinstance(agent.memory, CogniMemoryBank)
    assert agent.memory.memory_bank_root == memory_bank_root
    assert agent.memory.project_name == "cogni_agents"
    # The session_id should be the agent name
    expected_session_path = memory_bank_root / "cogni_agents" / "test_dummy"
    # assert agent.memory.session_path == expected_session_path # Removed: session_path is not a public attribute
    # Check if the session directory was created by CogniMemoryBank init
    assert expected_session_path.exists()
    assert expected_session_path.is_dir()
    
    # Basic check that spirit and core context were attempted to be loaded (more detail in specific tests)
    assert agent.spirit is not None
    assert agent.core_context is not None

# Add more tests for load_spirit, load_core_context, get_guide_for_task, record_action below
# Use patching for memory methods as needed. 

@patch.object(CogniMemoryBank, 'write_context')
@patch.object(CogniMemoryBank, '_read_file')
def test_load_spirit_from_memory(mock_read, mock_write, agent_root, spirit_file, memory_bank_root, temp_dir):
    """Test loading spirit guide when it exists in memory bank (during init)."""
    # Simulate spirit IS in memory during init
    def init_read_side_effect(*args, **kwargs):
        filename = args[0]
        if filename == spirit_file.name:
            return "Spirit from memory"
        return None # Other files not found in memory during init for this test
    mock_read.side_effect = init_read_side_effect

    agent = DummyAgent(
        name="test_load_spirit_mem", 
        spirit_path=spirit_file, 
        agent_root=agent_root,
        memory_bank_root_override=memory_bank_root,
        project_root_override=temp_dir
    )
    
    # Check state AFTER init
    assert agent.spirit == "Spirit from memory"
    # Check calls made DURING init
    mock_read.assert_any_call(spirit_file.name) # Check that the read attempt happened
    mock_write.assert_not_called() # Should not write if read from memory

@patch.object(CogniMemoryBank, 'write_context')
@patch.object(CogniMemoryBank, '_read_file')
def test_load_spirit_from_file_fallback(mock_read, mock_write, agent_root, spirit_file, memory_bank_root, temp_dir):
    """Test loading spirit guide fallback to file system and writing to memory (during init)."""
    mock_read.return_value = None # Simulate spirit NOT in memory during init
    expected_spirit_content = spirit_file.read_text() # Content from dummy file
    
    agent = DummyAgent(
        name="test_load_spirit_file", 
        spirit_path=spirit_file, 
        agent_root=agent_root,
        memory_bank_root_override=memory_bank_root,
        project_root_override=temp_dir
    )
    
    # Check state AFTER init
    assert agent.spirit == expected_spirit_content
    # Check calls made DURING init
    mock_read.assert_any_call(spirit_file.name) # Spirit read attempt
    mock_write.assert_any_call(spirit_file.name, expected_spirit_content) # Spirit writeback

@patch.object(CogniMemoryBank, 'write_context')
@patch.object(CogniMemoryBank, '_read_file')
def test_load_spirit_not_found(mock_read, mock_write, agent_root, temp_dir, memory_bank_root):
    """Test loading spirit when it's not in memory or file system (during init)."""
    mock_read.return_value = None
    non_existent_spirit = temp_dir / "not_real_spirit.md" # Does not exist
    
    agent = DummyAgent(
        name="test_load_spirit_none", 
        spirit_path=non_existent_spirit, 
        agent_root=agent_root,
        memory_bank_root_override=memory_bank_root,
        project_root_override=temp_dir
    )
    
    # Check state AFTER init
    assert agent.spirit == "⚠️ Spirit guide not found."
    # Check calls made DURING init
    mock_read.assert_any_call(non_existent_spirit.name) # Read attempt
    # Assert write was NOT called for the spirit
    write_calls = mock_write.call_args_list
    # Check if the file actually exists before trying to read it for the call check
    spirit_content_for_check = non_existent_spirit.read_text() if non_existent_spirit.exists() else ""
    spirit_write_call = call(non_existent_spirit.name, spirit_content_for_check)
    # Check if a call matching the spirit write pattern exists. It shouldn't.
    found_spirit_write = any(cargs == spirit_write_call[0] and ckwargs == spirit_write_call[1] for cargs, ckwargs in write_calls)
    assert not found_spirit_write, "write_context should not have been called for a non-existent spirit file"

# Helper function for mocking multiple reads in load_core_context
# Updated to reference core_files fixture for fallback content
def multi_read_side_effect_core(core_files):
    def side_effect(*args, **kwargs):
        filename = args[0]
        if filename == "CHARTER.md":
            return "Charter from memory"
        if filename == "MANIFESTO.md":
            return None # Fallback
        if filename == "LICENSE.md":
            return "License from memory"
        if filename == "README.md":
            return None # Fallback
        if filename == "core_spirit.md":
            return "Core Spirit from memory"
        # Handle spirit file read during init as well if needed by test context
        # For simplicity, assume spirit is handled by separate tests or found in memory here
        # If spirit needs fallback in this test too, add: if filename == spirit_file.name: return None
        return None
    return side_effect

@patch.object(CogniMemoryBank, 'write_context')
@patch.object(CogniMemoryBank, '_read_file')
def test_load_core_context_mixed(mock_read, mock_write, agent_root, spirit_file, memory_bank_root, core_files, temp_dir):
    """Test loading core context with mixed memory/file sources (during init)."""
    # Expected fallback content from dummy files created by core_files fixture
    manifesto_content = core_files["MANIFESTO.md"].read_text()
    readme_content = core_files["README.md"].read_text()
    
    # Simulate spirit found in memory, core files mixed
    def init_read_side_effect(*args, **kwargs):
        filename = args[0]
        if filename == spirit_file.name:
            return "Spirit from memory during core test"
        if filename == "CHARTER.md":
            return "Charter from memory"
        if filename == "MANIFESTO.md":
            return None # Fallback
        if filename == "LICENSE.md":
            return "License from memory"
        if filename == "README.md":
            return None # Fallback
        if filename == "core_spirit.md":
            return "Core Spirit from memory"
        return None
    mock_read.side_effect = init_read_side_effect

    agent = DummyAgent(
        name="test_load_core", 
        spirit_path=spirit_file, 
        agent_root=agent_root,
        memory_bank_root_override=memory_bank_root,
        project_root_override=temp_dir # Crucial for fallback paths
    )
    
    # Check calls made DURING init
    # Reads:
    expected_read_calls = [
        call(spirit_file.name),
        call("CHARTER.md"), 
        call("MANIFESTO.md"),
        call("LICENSE.md"),
        call("README.md"),
        call("core_spirit.md")
    ]
    mock_read.assert_has_calls(expected_read_calls, any_order=True)
    
    # Writes (only fallbacks during init):
    expected_write_calls = [
        call("MANIFESTO.md", manifesto_content), # Core fallback from dummy file
        call("README.md", readme_content)       # Core fallback from dummy file
    ]
    mock_write.assert_has_calls(expected_write_calls, any_order=True) 
    assert mock_write.call_count == 2 # Only the 2 core fallbacks should be written

    # Check final context content (state after init)
    assert "## CHARTER.md\n\nCharter from memory" in agent.core_context["context"]["content"]
    assert f"## MANIFESTO.md\n\n{manifesto_content}" in agent.core_context["context"]["content"]
    assert "## LICENSE.md\n\nLicense from memory" in agent.core_context["context"]["content"]
    assert f"## README.md\n\n{readme_content}" in agent.core_context["context"]["content"]
    assert "## cogni-core-spirit\n\nCore Spirit from memory" in agent.core_context["context"]["content"]

    # Check metadata
    assert agent.core_context["metadata"]["CHARTER.md"]["length"] == len("Charter from memory")
    assert agent.core_context["metadata"]["MANIFESTO.md"]["length"] == len(manifesto_content)
    assert agent.core_context["metadata"]["LICENSE.md"]["length"] == len("License from memory")
    assert agent.core_context["metadata"]["README.md"]["length"] == len(readme_content)
    assert agent.core_context["metadata"]["core_spirit"]["length"] == len("Core Spirit from memory")

@patch.object(CogniMemoryBank, 'write_context')
@patch.object(CogniMemoryBank, '_read_file')
def test_get_guide_for_task_default(mock_read, mock_write, agent_root, spirit_file, memory_bank_root, core_files, temp_dir):
    """Test get_guide_for_task uses core spirit by default, checking memory/file."""
    # Let init run normally (mocks will capture calls)
    agent = DummyAgent(
        name="test_get_guide_default", 
        spirit_path=spirit_file, 
        agent_root=agent_root,
        memory_bank_root_override=memory_bank_root,
        project_root_override=temp_dir # Use temp dir for fallbacks
    )
    
    # Reset mocks AFTER init is done, before calling the target method
    mock_read.reset_mock()
    mock_write.reset_mock()

    # Set up mocks specifically for the get_guide_for_task call
    mock_read.return_value = None # Simulate guide not in memory for THIS call
    # Get content from the DUMMY core spirit file created by fixture
    core_spirit_content = core_files["core_spirit"].read_text() 
    expected_memory_filename = "guide_cogni-core-spirit.md"
    
    guide_context = agent.get_guide_for_task("some_task")

    # Assert calls made ONLY during get_guide_for_task
    mock_read.assert_called_once_with(expected_memory_filename)
    mock_write.assert_called_once_with(expected_memory_filename, core_spirit_content)
    
    assert guide_context["role"] == "system"
    assert "# Cogni Spirit Context for: some_task" in guide_context["content"]
    # Check content matches the DUMMY file
    assert f"## cogni-core-spirit\n\n{core_spirit_content}" in guide_context["content"]


@patch.object(CogniMemoryBank, 'write_context')
@patch.object(CogniMemoryBank, '_read_file')
def test_get_guide_for_task_custom(mock_read, mock_write, agent_root, spirit_file, memory_bank_root, core_files, temp_dir):
    """Test get_guide_for_task with custom guides, checking memory/file."""
    
    # Let init run normally
    agent = DummyAgent(
        name="test_get_guide_custom", 
        spirit_path=spirit_file, 
        agent_root=agent_root,
        memory_bank_root_override=memory_bank_root,
        project_root_override=temp_dir # Use temp dir for fallbacks
    )

    # Reset mocks AFTER init
    mock_read.reset_mock()
    mock_write.reset_mock()

    # Setup mocks for the get_guide_for_task call
    custom_guide_content = core_files["custom-guide"].read_text() # Dummy content
    core_spirit_content = "Core Spirit from memory" # Simulate this one IS in memory
    def custom_guide_read_side_effect(*args, **kwargs):
        filename = args[0]
        if filename == "guide_cogni-core-spirit.md":
            return core_spirit_content 
        elif filename == "guide_custom-guide.md":
            return None # Simulate custom guide needs file fallback
        return None
    mock_read.side_effect = custom_guide_read_side_effect

    guide_context = agent.get_guide_for_task("another_task", guides=["cogni-core-spirit", "custom-guide"])

    # Check calls made ONLY during get_guide_for_task
    expected_read_calls = [
        call("guide_cogni-core-spirit.md"),
        call("guide_custom-guide.md")
    ]
    mock_read.assert_has_calls(expected_read_calls)
    
    # Only custom guide should have been written during this call (from dummy file)
    mock_write.assert_called_once_with("guide_custom-guide.md", custom_guide_content)
    
    assert guide_context["role"] == "system"
    assert "# Cogni Spirit Context for: another_task" in guide_context["content"]
    assert f"## cogni-core-spirit\n\n{core_spirit_content}" in guide_context["content"]
    # Check content matches the DUMMY file for the fallback
    assert f"## custom-guide\n\n{custom_guide_content}" in guide_context["content"]

@patch.object(CogniMemoryBank, 'log_decision')
@patch.object(CogniMemoryBank, 'write_context')
def test_record_action(mock_write_context, mock_log_decision, agent_root, spirit_file, memory_bank_root, temp_dir):
    """Test recording agent action to file and memory bank."""
    # Let init run normally
    agent = DummyAgent(
        name="test_record", 
        spirit_path=spirit_file, 
        agent_root=agent_root,
        memory_bank_root_override=memory_bank_root,
        project_root_override=temp_dir
    )
    
    # Reset mocks AFTER init to isolate calls during record_action
    mock_write_context.reset_mock()
    mock_log_decision.reset_mock()

    action_output = {"step": 1, "decision": "proceed", "details": {"info": "abc", "value": 123}}
    
    # with freeze_time("2023-10-27 10:00:00 UTC"):
    # Note: record_action now returns None
    result = agent.record_action(action_output, subdir="test_sessions", prefix="rec_")

    # 1. Check return value
    assert result is None, "record_action should now return None"

    # --- Assertions based on the NEW behavior of record_action ---

    # 2. Check Memory Bank write_context call (saves MD file)
    mock_write_context.assert_called_once()
    args_wc, kwargs_wc = mock_write_context.call_args
    
    markdown_filename = args_wc[0]
    markdown_content = args_wc[1]
    
    # Check filename format (uses class name, prefix, timestamp, .md extension)
    assert markdown_filename.startswith("DummyAgent_rec_") 
    assert markdown_filename.endswith(".md")
    
    # Check content is the formatted Markdown
    assert "# CogniAgent Output — test_record" in markdown_content 
    assert "## step\n1" in markdown_content
    assert "## details" in markdown_content
    assert "**info**:" in markdown_content
    
    # Check is_json=False was passed
    assert kwargs_wc.get('is_json') is False

    # 3. Check Memory Bank log_decision call
    mock_log_decision.assert_called_once()
    args_ld, kwargs_ld = mock_log_decision.call_args
    decision_log = args_ld[0]
    
    # Check logged metadata
    assert decision_log.get("agent_name") == "test_record"
    assert decision_log.get("agent_class") == "DummyAgent"
    assert decision_log.get("action_type") == "rec_"
    
    # Check pointer to the saved Markdown file
    assert decision_log.get("markdown_filename") == markdown_filename 
    
    # Ensure old fields are not present
    assert "action_filename" not in decision_log # Renamed to markdown_filename
    assert "output_path" not in decision_log # External path is no longer relevant here

    # 4. External file system checks are REMOVED
    # No need to check output_path.parent or output_path.exists() 