import sys
import os
import unittest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
from datetime import datetime

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from infra_core.cogni_agents.base import CogniAgent


# Mock datetime for testing
class MockDateTime:
    """Mock datetime.utcnow() to return a fixed timestamp"""
    
    @classmethod
    def utcnow(cls):
        """Return a fixed datetime for testing"""
        return datetime(2023, 1, 1, 12, 0, 0)


class TestCogniAgent(unittest.TestCase):
    """Tests for the CogniAgent base class"""
    
    class ConcreteAgent(CogniAgent):
        """Concrete implementation of CogniAgent for testing abstract methods"""
        
        def act(self, prepared_input):
            """Implement abstract method for testing"""
            return {"result": "test_result", "input": prepared_input}
    
    def setUp(self):
        """Set up test environment before each test"""
        # Create mock paths
        self.spirit_path = MagicMock(spec=Path)
        self.spirit_path.exists.return_value = True
        self.spirit_path.read_text.return_value = "Test spirit guide content"
        
        self.agent_root = MagicMock(spec=Path)
        
        # Create test agent
        self.agent = self.ConcreteAgent(
            name="test-agent",
            spirit_path=self.spirit_path,
            agent_root=self.agent_root
        )
    
    def test_initialization(self):
        """Test agent initialization"""
        self.assertEqual(self.agent.name, "test-agent")
        self.assertEqual(self.agent.spirit_path, self.spirit_path)
        self.assertEqual(self.agent.agent_root, self.agent_root)
        self.assertEqual(self.agent.spirit, "Test spirit guide content")
        self.assertIsNone(self.agent.core_context)
    
    def test_load_spirit_exists(self):
        """Test loading spirit guide when file exists"""
        self.spirit_path.read_text.return_value = "Updated spirit content"
        self.agent.load_spirit()
        self.assertEqual(self.agent.spirit, "Updated spirit content")
    
    def test_load_spirit_not_exists(self):
        """Test loading spirit guide when file doesn't exist"""
        self.spirit_path.exists.return_value = False
        self.agent.load_spirit()
        self.assertEqual(self.agent.spirit, "⚠️ Spirit guide not found.")
    
    def test_load_core_context(self):
        """Test loading core context"""
        self.agent.load_core_context()
        self.assertIsNone(self.agent.core_context)
    
    def test_prepare_input(self):
        """Test prepare_input returns empty dict by default"""
        result = self.agent.prepare_input()
        self.assertEqual(result, {})
    
    def test_act(self):
        """Test concrete implementation of act"""
        test_input = {"test": "data"}
        result = self.agent.act(test_input)
        self.assertEqual(result["result"], "test_result")
        self.assertEqual(result["input"], test_input)
    
    @patch('pathlib.Path.write_text')
    @patch('infra_core.cogni_agents.base.datetime', MockDateTime)
    def test_record_action(self, mock_write_text):
        """Test recording action output"""
        # Set up the expected formatted timestamp
        expected_timestamp = "2023-01-01T12-00-00"
        
        # Create output dir path
        output_dir = MagicMock(spec=Path)
        output_path = MagicMock(spec=Path)
        self.agent_root.__truediv__.return_value = output_dir
        output_dir.__truediv__.return_value = output_path
        output_path.parent = output_dir
        
        # Test data
        test_output = {"key": "value"}
        
        # Call method
        result_path = self.agent.record_action(test_output, subdir="test_dir")
        
        # Verify directory was created
        output_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        
        # Verify correct markdown formatting
        expected_markdown = (
            "# CogniAgent Output — test-agent\n"
            "\n"
            "**Generated**: 2023-01-01T12:00:00\n"
            "\n"
            "## key\n"
            "value\n"
            "\n"
            "---\n"
            "> Agent: test-agent\n"
            "> Timestamp: 2023-01-01 12:00:00 UTC"
        )
        
        # Verify write_text was called with expected content
        output_path.write_text.assert_called_once()
        call_args = output_path.write_text.call_args[0][0]
        self.assertEqual(call_args, expected_markdown)
        
        # Verify correct path was returned
        self.assertEqual(result_path, output_path)
    
    @patch('infra_core.cogni_agents.base.datetime', MockDateTime)
    def test_format_output_markdown(self):
        """Test markdown formatting with nested data"""
        # Test with mixed simple and nested data
        test_data = {
            "simple_key": "simple_value",
            "nested_key": {
                "sub_key1": "sub_value1",
                "sub_key2": "sub_value2"
            }
        }
        
        # Format the output
        result = self.agent.format_output_markdown(test_data)
        
        # Check for key elements in the output
        self.assertIn("# CogniAgent Output — test-agent", result)
        self.assertIn("**Generated**: 2023-01-01T12:00:00", result)
        self.assertIn("## simple_key", result)
        self.assertIn("simple_value", result)
        self.assertIn("## nested_key", result)
        self.assertIn("**sub_key1**:", result)
        self.assertIn("sub_value1", result)
        self.assertIn("**sub_key2**:", result)
        self.assertIn("sub_value2", result)
        self.assertIn("> Agent: test-agent", result)
        self.assertIn("> Timestamp: 2023-01-01 12:00:00 UTC", result)


if __name__ == "__main__":
    unittest.main() 