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
    
    # Freeze time slightly for predictable filenames/timestamps if needed (optional)
    # from freezegun import freeze_time
    # with freeze_time("2023-10-27 10:00:00 UTC"):
    output_path = agent.record_action(action_output, subdir="test_sessions", prefix="rec_")

    # 1. Check file system path (should still be calculated correctly)
    assert output_path.parent == agent_root / "test_sessions"
    assert output_path.name.startswith("rec_")
    assert output_path.name.endswith(".md")
    # assert output_path.exists() # REMOVED - File is no longer created

    # 2. Check Memory Bank Writes
    # Check write_context call
    mock_write_context.assert_called_once()
    args_wc, kwargs_wc = mock_write_context.call_args
    assert args_wc[0].startswith("action_") # Check memory filename format
    assert args_wc[0].endswith(".md")
    assert "# CogniAgent Output — test_record" in args_wc[1] # Check formatted content
    assert "## step\n1" in args_wc[1]
    assert "## details" in args_wc[1]
    assert "**info**:" in args_wc[1]

    # Check log_decision call
    mock_log_decision.assert_called_once()
    args_ld, kwargs_ld = mock_log_decision.call_args
    decision_log = args_ld[0]
    assert decision_log["agent"] == "test_record"
    assert decision_log["action_filename"] == args_wc[0] # Ensure it matches write_context filename
    assert decision_log["output_path"] == str(output_path) # Ensure it logged the calculated external path

    # 3. Check return value
    assert isinstance(output_path, Path) 

@patch.object(CogniMemoryBank, 'load_or_seed_file') # Patch the correct method
def test_load_core_context_reads_from_core_bank(mock_load_seed_file, agent_root, spirit_file, mock_memory_instance, temp_dir):
    """Verify load_core_context reads files from the 'core/main' bank."""
    # The mock_load_seed_file is now patched at the class level

    # Set up the side effect for the mocked method
    def core_load_seed_effect(file_name, fallback_path=None):
        if file_name == "CHARTER.md": 
            return "Test Charter Content"
        if file_name == "MANIFESTO.md": 
            return "Test Manifesto Content"
        if file_name == "guide_cogni-core-spirit.md": 
            return "Test Core Spirit Content"
        return None # Simulate LICENSE and README missing
    mock_load_seed_file.side_effect = core_load_seed_effect

    # Initialize agent, patching the other load method called during init
    with patch.object(DummyAgent, 'load_spirit'):
        agent = DummyAgent(
            name="test_core_load", spirit_path=spirit_file,
            agent_root=agent_root, memory=mock_memory_instance,
            project_root_override=temp_dir
        )
        # Manually call the method under test
        agent.load_core_context()

    # Assertions
    # Check that load_or_seed_file was called for expected files
    expected_core_calls = [
        call(file_name="CHARTER.md", fallback_path=temp_dir / "CHARTER.md"),
        call(file_name="MANIFESTO.md", fallback_path=temp_dir / "MANIFESTO.md"),
        call(file_name="LICENSE.md", fallback_path=temp_dir / "LICENSE.md"),
        call(file_name="README.md", fallback_path=temp_dir / "README.md"),
        call(file_name="guide_cogni-core-spirit.md", fallback_path=temp_dir / "infra_core/cogni_spirit/spirits/cogni-core-spirit.md")
    ]
    # Verify calls made to the mock
    mock_load_seed_file.assert_has_calls(expected_core_calls, any_order=True)

    # Verify the content loaded into the agent
    assert "Test Charter Content" in agent.core_context['context']['content']
    assert "Test Manifesto Content" in agent.core_context['context']['content']
    assert "Test Core Spirit Content" in agent.core_context['context']['content']
    assert "LICENSE.md" not in agent.core_context['context']['content'] # Should not be present

@patch.object(CogniMemoryBank, 'load_or_seed_file') # Patch the correct method
def test_load_spirit_reads_from_core_bank(mock_load_seed_file, agent_root, spirit_file, mock_memory_instance, temp_dir):
    """Verify load_spirit (called during init) reads the correct guide from the 'core/main' bank."""
    expected_guide_filename = f"guide_{spirit_file.stem}.md"
    expected_spirit_content = "Test Dummy Spirit Content from Core"
    expected_fallback_path = temp_dir / spirit_file # Resolve spirit_file against temp_dir

    # Simulate load_or_seed_file returning the content
    mock_load_seed_file.return_value = expected_spirit_content

    # Initialize agent, patching the other load method called during init
    # load_spirit will be called automatically by __init__
    with patch.object(DummyAgent, 'load_core_context'):
        agent = DummyAgent(
            name="test_spirit_load", spirit_path=spirit_file,
            agent_root=agent_root, memory=mock_memory_instance,
            project_root_override=temp_dir
        )

    # Assertions check the state *after* init
    # Check load_or_seed_file was called correctly during init
    mock_load_seed_file.assert_called_once_with(
        file_name=expected_guide_filename,
        fallback_path=expected_fallback_path
    )
    # Check the loaded spirit content
    assert agent.spirit == expected_spirit_content

@patch.object(CogniMemoryBank, 'load_or_seed_file') # Patch the correct method
def test_load_spirit_not_found_in_core_bank(mock_load_seed_file, agent_root, spirit_file, mock_memory_instance, temp_dir):
    """Verify load_spirit (called during init) handles guide missing from core bank."""
    expected_guide_filename = f"guide_{spirit_file.stem}.md"
    expected_fallback_path = temp_dir / spirit_file # Resolve spirit_file against temp_dir

    # Simulate load_or_seed_file returning None (not found in bank or fallback)
    mock_load_seed_file.return_value = None

    # Initialize agent, load_spirit called by init
    with patch.object(DummyAgent, 'load_core_context'):
        agent = DummyAgent(
            name="test_spirit_missing", spirit_path=spirit_file,
            agent_root=agent_root, memory=mock_memory_instance,
            project_root_override=temp_dir
        )

    # Assertions check state after init
    # Check load_or_seed_file was called correctly during init
    mock_load_seed_file.assert_called_once_with(
        file_name=expected_guide_filename,
        fallback_path=expected_fallback_path
    )
    # Check the loaded spirit content (should be the warning)
    assert agent.spirit == "⚠️ Spirit guide not found." 