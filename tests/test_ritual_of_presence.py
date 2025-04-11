import pytest
from unittest.mock import MagicMock
import os
import sys
import importlib.util

# Add the parent directory to the path so we can import the module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock the core documents function
mock_get_core_documents = MagicMock(return_value={
    "context": {
        "role": "system",
        "content": "Test context"
    },
    "metadata": {
        "core_docs": {"charter": "Test charter content", "manifesto": "Test manifesto content"},
        "total_sections": 2,
        "total_core_docs_length": 200,
        "total_context_length": 220
    }
})

# Mock the OpenAI functions
mock_initialize_openai = MagicMock()
mock_create_completion = MagicMock(return_value={"choices": [{"message": {"content": "Test thought content"}}]})
mock_extract_content = MagicMock(return_value="Test thought content")

# Mock needed modules before importing ritual_of_presence
sys.modules['cogni_spirit'] = MagicMock()
sys.modules['cogni_spirit.context'] = MagicMock()
sys.modules['cogni_spirit.context'].get_core_documents = mock_get_core_documents

# Also mock the openai_handler module
sys.modules['openai_handler'] = MagicMock()
sys.modules['openai_handler'].initialize_openai_client = mock_initialize_openai
sys.modules['openai_handler'].create_completion = mock_create_completion
sys.modules['openai_handler'].extract_content = mock_extract_content

# Now import the module to test (must be after mocking)  # noqa: E402
spec = importlib.util.spec_from_file_location(
    "ritual_of_presence",
    os.path.join(os.path.dirname(__file__), "../infra_core/flows/rituals/ritual_of_presence.py")
)
ritual_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ritual_module)

# Import specific functions from the module
write_thought_file = ritual_module.write_thought_file
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

def test_write_thought_file(temp_thoughts_dir):
    """Test that thought files are written correctly"""
    test_content = "This is a test thought"
    timestamp, filepath = write_thought_file(test_content)
    
    # Verify file exists and contains the correct content
    assert os.path.exists(filepath)
    with open(filepath, "r") as f:
        content = f.read()
    
    assert "tags:: #thought" in content
    assert test_content in content
    assert timestamp in filepath

def test_create_thought(temp_thoughts_dir):
    """Test the create_thought task"""
    # Reset mock call counts
    mock_get_core_documents.reset_mock()
    mock_create_completion.reset_mock()
    mock_extract_content.reset_mock()
    
    timestamp, filepath, content = create_thought()
    
    # Verify the function calls
    assert mock_get_core_documents.call_count >= 1
    assert mock_create_completion.call_count >= 1
    assert mock_extract_content.call_count >= 1
    
    # Verify outputs
    assert isinstance(timestamp, str)
    assert os.path.exists(filepath)
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