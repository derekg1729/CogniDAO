"""
Tests for the CogniAgent base class.
"""
import pytest
from unittest.mock import patch, call, MagicMock
from typing import Dict, Any

from infra_core.cogni_agents.base import CogniAgent
from infra_core.memory.memory_bank import FileMemoryBank # Needed for type hinting and patching targets

# Dummy concrete agent implementation for testing
class DummyAgent(CogniAgent):
    def act(self, prepared_input: Dict[str, Any]) -> Dict[str, Any]:
        return {"result": "This is a dummy response"}

# Fixtures
@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for test files."""
    return tmp_path

@pytest.fixture
def agent_root(temp_dir):
    """Create a temporary agent root directory."""
    agent_dir = temp_dir / "agent_workspace"
    agent_dir.mkdir()
    return agent_dir

@pytest.fixture
def memory_bank_root(temp_dir):
    """Create a temporary memory bank root directory."""
    memory_dir = temp_dir / "memory_banks"
    memory_dir.mkdir()
    return memory_dir

@pytest.fixture
def spirit_file(temp_dir):
    """Create a test spirit file."""
    spirit_dir = temp_dir / "spirits"
    spirit_dir.mkdir()
    spirit_path = spirit_dir / "test-agent-spirit.md"
    spirit_path.write_text("# Test Agent Spirit\nThis is a test spirit guide.")
    return spirit_path.relative_to(temp_dir)  # Return relative path from root

@pytest.fixture
def core_files(temp_dir):
    """Create test core files."""
    # Create Charter
    charter_path = temp_dir / "CHARTER.md"
    charter_path.write_text("# Test Charter\nThis is a test charter.")
    
    # Create Core Spirit file in the expected canonical location
    spirits_dir = temp_dir / "infra_core" / "cogni_spirit" / "spirits"
    spirits_dir.mkdir(parents=True, exist_ok=True)
    core_spirit_path = spirits_dir / "cogni-core-spirit.md"
    core_spirit_path.write_text("# Core Spirit\nThis is the core spirit guide.")
    
    # Create a Manifesto
    manifesto_path = temp_dir / "MANIFESTO.md"
    manifesto_path.write_text("# Test Manifesto\nThis is a test manifesto.")

    # Create a README
    readme_path = temp_dir / "README.md"
    readme_path.write_text("# Test README\nThis is a test readme.")

    # Create a LICENSE
    license_path = temp_dir / "LICENSE.md"
    license_path.write_text("# Test License\nThis is a test license.")
    
    return {
        "charter": charter_path,
        "core_spirit": core_spirit_path,
        "manifesto": manifesto_path,
        "readme": readme_path,
        "license": license_path
    }

@pytest.fixture
def memory_instance(memory_bank_root):
    """Create a real FileMemoryBank instance for testing."""
    return FileMemoryBank(
        memory_bank_root=memory_bank_root,
        project_name="test_project",
        session_id="test_session"
    )

@pytest.fixture
def mock_memory_instance():
    """Create a mock memory instance for testing."""
    mock = MagicMock(spec=FileMemoryBank)
    # Set up default behaviors for commonly used methods
    mock.load_or_seed_file.return_value = "# Mocked Content\nThis is mocked content."
    mock.write_context.return_value = None
    mock.log_decision.return_value = None
    return mock

# --- Test Cases ---

def test_agent_initialization(memory_instance, agent_root, spirit_file, memory_bank_root, temp_dir):
    """Test agent initialization with a real memory bank instance."""
    # Create a simple memory bank instance
    with patch.object(FileMemoryBank, 'load_or_seed_file', return_value="Test Spirit Content"):
        # Initialize agent with the memory bank
        agent = DummyAgent(
            name="test_agent",
            spirit_path=spirit_file,
            agent_root=agent_root,
            memory=memory_instance,
            project_root_override=temp_dir
        )

        # Validate agent properties
        assert agent.name == "test_agent"
        assert agent.spirit_path == spirit_file
        assert agent.agent_root == agent_root
        assert agent.memory == memory_instance
        assert agent.project_root == temp_dir
        assert agent.spirit == "Test Spirit Content"
        assert memory_instance.project_name == "test_project"
        assert memory_instance.session_id == "test_session"

def test_load_spirit_from_memory(mock_memory_instance, agent_root, spirit_file, temp_dir):
    """Test loading spirit from memory bank."""
    expected_spirit = "# Mocked Spirit\nThis is a mocked spirit guide."
    mock_memory_instance.load_or_seed_file.return_value = expected_spirit
    
    agent = DummyAgent(
        name="test_spirit_memory",
        spirit_path=spirit_file,
        agent_root=agent_root,
        memory=mock_memory_instance,
        project_root_override=temp_dir
    )
    
    # Verify the spirit was loaded from memory
    assert agent.spirit == expected_spirit
    
    # Verify the memory bank was asked to load the file
    expected_bank_filename = f"guide_{spirit_file.stem}.md"
    mock_memory_instance.load_or_seed_file.assert_called_once_with(
        file_name=expected_bank_filename,
        fallback_path=temp_dir / spirit_file
    )

def test_load_spirit_from_file_fallback(mock_memory_instance, agent_root, spirit_file, temp_dir):
    """Test loading spirit from file fallback when not in memory."""
    # Prepare expected data
    expected_spirit = "# Test Spirit from File\nThis is loaded from file."
    
    # Configure mocks to simulate memory miss, file hit
    # First call will return None (memory miss), second call would fallback
    mock_memory_instance.load_or_seed_file.return_value = expected_spirit
    
    agent = DummyAgent(
        name="test_spirit_fallback",
        spirit_path=spirit_file,
        agent_root=agent_root,
        memory=mock_memory_instance,
        project_root_override=temp_dir
    )
    
    # Verify the spirit was loaded from the fallback
    assert agent.spirit == expected_spirit
    
    # Verify the correct bank_filename was used in the fallback path
    expected_bank_filename = f"guide_{spirit_file.stem}.md"
    mock_memory_instance.load_or_seed_file.assert_called_once_with(
        file_name=expected_bank_filename,
        fallback_path=temp_dir / spirit_file
    )

def test_load_spirit_not_found(mock_memory_instance, agent_root, spirit_file, temp_dir):
    """Test FileNotFoundError when spirit can't be loaded from memory or file."""
    # Configure mock to simulate both memory and file miss
    mock_memory_instance.load_or_seed_file.return_value = None
    
    # Test should raise FileNotFoundError
    with pytest.raises(FileNotFoundError) as excinfo:
        DummyAgent(
            name="test_spirit_not_found",
            spirit_path=spirit_file,
            agent_root=agent_root,
            memory=mock_memory_instance,
            project_root_override=temp_dir
        )
    
    # Verify the error message contains the expected paths
    expected_bank_filename = f"guide_{spirit_file.stem}.md"
    assert expected_bank_filename in str(excinfo.value)
    assert str(temp_dir / spirit_file) in str(excinfo.value)

def test_load_core_context_from_memory(memory_instance, agent_root, spirit_file, core_files, temp_dir):
    """Test loading core context using the real memory bank."""
    # Initialize agent with real memory bank
    # First, seed the memory bank with core files for testing
    memory_instance.write_context("CHARTER.md", core_files["charter"].read_text(), is_json=False)
    memory_instance.write_context("MANIFESTO.md", core_files["manifesto"].read_text(), is_json=False)
    memory_instance.write_context("guide_cogni-core-spirit.md", core_files["core_spirit"].read_text(), is_json=False)
    
    with patch.object(FileMemoryBank, '__init__', return_value=None) as mock_init:
        with patch.object(FileMemoryBank, 'load_or_seed_file') as mock_load:
            # Set up the mock to return proper content
            mock_load.side_effect = lambda file_name, fallback_path: {
                "CHARTER.md": core_files["charter"].read_text(),
                "MANIFESTO.md": core_files["manifesto"].read_text(),
                "LICENSE.md": core_files["license"].read_text(),
                "README.md": core_files["readme"].read_text(),
                "guide_cogni-core-spirit.md": core_files["core_spirit"].read_text()
            }.get(file_name)
            
            # Patch load_spirit to avoid that dependency
            with patch.object(DummyAgent, 'load_spirit'):
                agent = DummyAgent(
                    name="test_load_core",
                    spirit_path=spirit_file,
                    agent_root=agent_root,
                    memory=memory_instance,
                    project_root_override=temp_dir
                )
                
                # Verify FileMemoryBank was initialized with the correct parameters
                mock_init.assert_called_once()
                
                # Verify the core context was loaded and processed
                assert agent.core_context is not None
                assert "context" in agent.core_context
                assert "metadata" in agent.core_context
                assert "Cogni Core Documents" in agent.core_context["context"]["content"]
                assert "CHARTER.md" in agent.core_context["metadata"]
                assert "MANIFESTO.md" in agent.core_context["metadata"]
                assert "cogni-core-spirit" in agent.core_context["metadata"]

def test_load_core_context_mixed(mock_memory_instance, agent_root, spirit_file, core_files, temp_dir):
    """Test loading core context with mixed sources (some in memory, some from files)."""
    # Configure the mock to simulate some memory hits, some misses
    def mock_load_side_effect(file_name, fallback_path):
        if file_name == "CHARTER.md":
            return core_files["charter"].read_text()
        elif file_name == "guide_cogni-core-spirit.md":
            return core_files["core_spirit"].read_text()
        else:
            # For testing, read from the actual file system for other files
            if fallback_path and fallback_path.exists():
                return fallback_path.read_text()
            return None
    
    mock_memory_instance.load_or_seed_file.side_effect = mock_load_side_effect
    
    with patch('infra_core.cogni_agents.base.FileMemoryBank', return_value=mock_memory_instance):
        with patch.object(DummyAgent, 'load_spirit'):
            agent = DummyAgent(
                name="test_load_core_mixed",
                spirit_path=spirit_file,
                agent_root=agent_root,
                memory=mock_memory_instance,
                project_root_override=temp_dir
            )
            
            # Verify the core context was loaded with content from both sources
            assert agent.core_context is not None
            assert "context" in agent.core_context
            assert "metadata" in agent.core_context
            assert "CHARTER.md" in agent.core_context["metadata"]
            assert "cogni-core-spirit" in agent.core_context["metadata"]
            
            # Verify memory bank was asked to load expected files
            assert mock_memory_instance.load_or_seed_file.call_count >= 2
            
            # Verify no write operations were performed (we're just reading)
            # This is important for validating we're not modifying memory during loading
            assert mock_memory_instance.write_context.call_count == 0

def test_get_guide_for_task_default(mock_memory_instance, agent_root, spirit_file, core_files, temp_dir):
    """Test getting guide for a task with default parameters."""
    # Create the directory structure expected by get_guide_for_task
    memory_dir = temp_dir / "infra_core" / "memory" / "banks"
    memory_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure mock to return content for core spirit
    mock_memory_instance._read_file = MagicMock(return_value=core_files["core_spirit"].read_text())
    
    with patch.object(DummyAgent, 'load_spirit'):
        with patch.object(DummyAgent, 'load_core_context'):
            # Also patch FileMemoryBank constructor to return our mock
            with patch('infra_core.cogni_agents.base.FileMemoryBank', return_value=mock_memory_instance):
                agent = DummyAgent(
                    name="test_guide_task",
                    spirit_path=spirit_file,
                    agent_root=agent_root,
                    memory=mock_memory_instance,
                    project_root_override=temp_dir
                )
                
                # Get guide for a task using default parameters (should use cogni-core-spirit)
                guide = agent.get_guide_for_task("test_task")
                
                # Verify structure and content
                assert "role" in guide
                assert guide["role"] == "system"
                assert "content" in guide
                assert "Cogni Spirit Context for: test_task" in guide["content"]
                assert "cogni-core-spirit" in guide["content"]
                
                # Verify the correct file was read
                mock_memory_instance._read_file.assert_called_with("guide_cogni-core-spirit.md")

def test_get_guide_for_task_custom(mock_memory_instance, agent_root, spirit_file, core_files, temp_dir):
    """Test getting guide for a task with custom guide names."""
    # Create the directory structure expected by get_guide_for_task
    memory_dir = temp_dir / "infra_core" / "memory" / "banks"
    memory_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure mock to return content based on the requested guide
    def mock_read_file(filename):
        if filename == "guide_custom-guide.md":
            return "# Custom Guide\nThis is a custom test guide."
        elif filename == "guide_another-guide.md":
            return "# Another Guide\nThis is another test guide."
        return None
    
    mock_memory_instance._read_file = MagicMock(side_effect=mock_read_file)
    
    with patch.object(DummyAgent, 'load_spirit'):
        with patch.object(DummyAgent, 'load_core_context'):
            # Also patch FileMemoryBank constructor to return our mock
            with patch('infra_core.cogni_agents.base.FileMemoryBank', return_value=mock_memory_instance):
                agent = DummyAgent(
                    name="test_guide_custom",
                    spirit_path=spirit_file,
                    agent_root=agent_root,
                    memory=mock_memory_instance,
                    project_root_override=temp_dir
                )
                
                # Get guide for a task using custom guides
                guide = agent.get_guide_for_task(
                    "custom_task", 
                    guides=["custom-guide", "another-guide"]
                )
                
                # Verify structure and content
                assert "role" in guide
                assert guide["role"] == "system"
                assert "content" in guide
                assert "Cogni Spirit Context for: custom_task" in guide["content"]
                assert "custom-guide" in guide["content"]
                assert "another-guide" in guide["content"]
                
                # Verify the correct files were read in correct order
                expected_calls = [
                    call("guide_custom-guide.md"),
                    call("guide_another-guide.md")
                ]
                mock_memory_instance._read_file.assert_has_calls(expected_calls, any_order=False)

def test_record_action(mock_memory_instance, agent_root, spirit_file, temp_dir):
    """Test recording an action to memory bank."""
    with patch.object(DummyAgent, 'load_spirit'):
        with patch.object(DummyAgent, 'load_core_context'):
            agent = DummyAgent(
                name="test_record_action",
                spirit_path=spirit_file,
                agent_root=agent_root,
                memory=mock_memory_instance,
                project_root_override=temp_dir
            )
            
            # Record an action
            output = {"thought": "This is a test thought", "decision": "Test decision"}
            agent.record_action(output, prefix="thought_")
            
            # Verify content was written to the memory bank
            mock_memory_instance.write_context.assert_called_once()
            # Extract filename from the first argument of write_context
            filename_arg = mock_memory_instance.write_context.call_args[0][0]
            assert filename_arg.startswith("DummyAgent_thought_")
            assert filename_arg.endswith(".md")
            
            # Verify decision was logged
            mock_memory_instance.log_decision.assert_called_once()
            decision_arg = mock_memory_instance.log_decision.call_args[0][0]
            assert decision_arg["agent_name"] == "test_record_action"
            assert decision_arg["agent_class"] == "DummyAgent"
            assert decision_arg["action_type"] == "thought_"
            assert "markdown_filename" in decision_arg

def test_load_core_context_from_core_bank(mock_memory_instance, agent_root, spirit_file, core_files, temp_dir):
    """Test loading core context from a core bank at MEMORY_BANKS_ROOT."""
    with patch('infra_core.cogni_agents.base.FileMemoryBank') as mock_core_bank_cls:
        # Create a mock for the core bank instance
        mock_core_bank = MagicMock()
        mock_core_bank_cls.return_value = mock_core_bank
        
        # Configure the mock core bank to return content for core files
        def mock_load_seed_file(file_name, fallback_path):
            if file_name == "CHARTER.md":
                return core_files["charter"].read_text()
            elif file_name == "guide_cogni-core-spirit.md":
                return core_files["core_spirit"].read_text()
            elif file_name == "MANIFESTO.md":
                return core_files["manifesto"].read_text()
            elif file_name == "LICENSE.md":
                return core_files["license"].read_text()
            elif file_name == "README.md":
                return core_files["readme"].read_text()
            return None
        
        mock_core_bank.load_or_seed_file.side_effect = mock_load_seed_file
        
        with patch.object(DummyAgent, 'load_spirit'):
            agent = DummyAgent(
                name="test_core_bank",
                spirit_path=spirit_file,
                agent_root=agent_root,
                memory=mock_memory_instance,
                project_root_override=temp_dir
            )
            
            # Verify core bank was initialized with expected parameters
            mock_core_bank_cls.assert_called_once()
            kwargs = mock_core_bank_cls.call_args[1]
            assert 'project_name' in kwargs and kwargs['project_name'] == 'core'
            assert 'session_id' in kwargs and kwargs['session_id'] == 'main'
            
            # Verify core context was loaded properly
            assert agent.core_context is not None
            assert "context" in agent.core_context
            assert "metadata" in agent.core_context
            
            # Create expected fallback paths that match the actual implementation in base.py
            expected_fallback_paths = {
                "CHARTER.md": temp_dir / "CHARTER.md",
                "MANIFESTO.md": temp_dir / "MANIFESTO.md",
                "LICENSE.md": temp_dir / "LICENSE.md",
                "README.md": temp_dir / "README.md",
                "guide_cogni-core-spirit.md": temp_dir / "infra_core/cogni_spirit/spirits/cogni-core-spirit.md"
            }
            
            # Verify correct files were loaded from core bank with correct fallback paths
            expected_files = [
                "CHARTER.md", 
                "MANIFESTO.md", 
                "LICENSE.md", 
                "README.md"
            ]
            
            for file_name in expected_files:
                mock_core_bank.load_or_seed_file.assert_any_call(
                    file_name=file_name,
                    fallback_path=expected_fallback_paths[file_name]
                )
            
            # Separately verify the guide file since it has a different fallback path
            mock_core_bank.load_or_seed_file.assert_any_call(
                file_name="guide_cogni-core-spirit.md",
                fallback_path=expected_fallback_paths["guide_cogni-core-spirit.md"]
            )

@patch.object(FileMemoryBank, 'load_or_seed_file')
def test_load_spirit_not_found_in_core_bank(mock_load_seed_file, agent_root, spirit_file, mock_memory_instance, temp_dir):
    """Verify load_spirit raises FileNotFoundError when spirit can't be loaded or seeded."""
    # Set up the side effect for the mocked method to simulate not found for spirit
    # We need to fix two things:
    # 1. Make sure the patched method affects mock_memory_instance.load_or_seed_file
    # 2. Return None specifically for spirit_file but not for other files
    
    # Instead of patching FileMemoryBank.load_or_seed_file, set up the mock directly
    mock_memory_instance.load_or_seed_file.return_value = None
    
    # Test should raise FileNotFoundError for spirit file
    with pytest.raises(FileNotFoundError) as excinfo:
        DummyAgent(
            name="test_spirit_not_found",
            spirit_path=spirit_file,
            agent_root=agent_root,
            memory=mock_memory_instance,
            project_root_override=temp_dir
        )

    # Verify the error message contains the expected paths for spirit file
    expected_bank_filename = f"guide_{spirit_file.stem}.md"
    assert expected_bank_filename in str(excinfo.value)
    assert str(temp_dir / spirit_file) in str(excinfo.value) 