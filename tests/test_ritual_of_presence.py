import pytest
from unittest.mock import MagicMock
import os
import sys
import importlib.util

# Add the parent directory to the path so we can import the module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock the CogniMemoryClient
mock_memory_client = MagicMock()
mock_memory_client.get_page = MagicMock(return_value="Test content")
mock_memory_client.write_page = MagicMock()

# Mock the CoreCogniAgent
mock_core_cogni = MagicMock()
mock_core_cogni.prepare_input = MagicMock(return_value={"prompt": "Test prompt", "temperature": 0.8})
mock_core_cogni.act = MagicMock(return_value={
    "timestamp": "2023-01-01-01-01",
    "filepath": "/test/path/2023-01-01-01-01.md",
    "thought_content": "Test thought content",
    "formatted_content": "tags:: #thought\n\n# Thought 2023-01-01-01-01\n\nTest thought content\n\nTime: 2023-01-01T01:01:00"
})

# Mock initialization of CoreCogniAgent
mock_core_cogni_init = MagicMock(return_value=mock_core_cogni)

# Mock the modules
sys.modules['infra_core.cogni_agents.core_cogni'] = MagicMock()
sys.modules['infra_core.cogni_agents.core_cogni'].CoreCogniAgent = mock_core_cogni_init

# Now import the module to test (must be after mocking)
spec = importlib.util.spec_from_file_location(
    "ritual_of_presence",
    os.path.join(os.path.dirname(__file__), "../infra_core/flows/rituals/ritual_of_presence.py")
)
ritual_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ritual_module)

# Import specific functions from the module
create_thought = ritual_module.create_thought
ritual_of_presence_flow = ritual_module.ritual_of_presence_flow
THOUGHTS_DIR = ritual_module.THOUGHTS_DIR

@pytest.fixture
def temp_thoughts_dir(tmpdir):
    """Create a temporary directory for thoughts"""
    thoughts_dir = str(tmpdir.join("thoughts"))
    os.makedirs(thoughts_dir, exist_ok=True)
    
    # Store the original value
    original_dir = THOUGHTS_DIR
    
    # Patch the value at the module level
    ritual_module.THOUGHTS_DIR = thoughts_dir
    
    yield thoughts_dir
    
    # Restore the original value
    ritual_module.THOUGHTS_DIR = original_dir

def test_create_thought(temp_thoughts_dir):
    """Test the create_thought task"""
    # Reset mock call counts
    mock_core_cogni_init.reset_mock()
    mock_core_cogni.prepare_input.reset_mock()
    mock_core_cogni.act.reset_mock()
    
    timestamp, filepath, content = create_thought()
    
    # Verify the function calls
    assert mock_core_cogni_init.call_count >= 1
    assert mock_core_cogni.prepare_input.call_count >= 1
    assert mock_core_cogni.act.call_count >= 1
    
    # Verify outputs
    assert isinstance(timestamp, str)
    assert timestamp == "2023-01-01-01-01"
    assert filepath == "/test/path/2023-01-01-01-01.md"
    assert content == "Test thought content"

def test_ritual_of_presence_flow(temp_thoughts_dir, monkeypatch):
    """Test the ritual_of_presence_flow"""
    # Set up a mock for create_thought within the same module
    mock_timestamp = "2023-01-01-01-01"
    mock_filepath = os.path.join(temp_thoughts_dir, f"{mock_timestamp}.md")
    mock_content = "Test thought content"
    
    mock_create = MagicMock(return_value=(mock_timestamp, mock_filepath, mock_content))
    monkeypatch.setattr(ritual_module, "create_thought", mock_create)
    
    result = ritual_of_presence_flow()
    
    # Verify the task was called
    assert mock_create.call_count == 1
    
    # Verify the result contains the expected information
    assert "Thought created successfully" in result
    assert mock_filepath in result 