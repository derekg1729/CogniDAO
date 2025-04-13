import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from infra_core.cogni_agents.git_cogni.git_cogni import GitCogniAgent


class TestGitCogniAgent(unittest.TestCase):
    """Tests for the GitCogniAgent implementation"""
    
    def setUp(self):
        """Set up test environment before each test"""
        # Mock the Path object and its methods
        with patch('pathlib.Path') as mock_path_class:
            # Configure the mock path to behave like expected
            mock_spirit_path = MagicMock()
            mock_spirit_path.exists.return_value = True
            mock_spirit_path.read_text.return_value = "Git Cogni spirit guide content"
            
            # Make path division return a fixed string path
            mock_spirit_path.__truediv__.return_value = mock_spirit_path
            
            mock_path_class.return_value = mock_spirit_path
            mock_path_class.side_effect = lambda p: mock_spirit_path
            
            # Set up agent root
            self.agent_root = MagicMock(spec=Path)
            # Ensure truediv returns a controlled value
            self.agent_root.__truediv__.return_value = mock_spirit_path
            
            # Create the test agent
            self.agent = GitCogniAgent(agent_root=self.agent_root)
            
            # Create memory client mock
            self.mock_memory_client = MagicMock()
            
            # Configure get_page method for different paths
            self.mock_memory_client.get_page.side_effect = lambda path: {
                "CHARTER.md": "Charter content",
                "MANIFESTO.md": "Manifesto content",
                "LICENSE.md": "License content",
                "README.md": "README content",
                "infra_core/cogni_spirit/spirits/cogni-core-spirit.md": "Core spirit content",
                "infra_core/cogni_spirit/spirits/git-cogni.md": "Git Cogni spirit guide content"
            }.get(path, "")
            
            # Use a lambda for write_page to completely avoid filesystem operations
            self.mock_memory_client.write_page = lambda filepath, content, append=False: "/fake/path/output.md"
            
            # Replace the agent's memory client with our mock
            self.agent.memory_client = self.mock_memory_client
            
            # Mock the record_action method to return a fixed path
            self.original_record_action = self.agent.record_action
            self.agent.record_action = MagicMock(return_value="/fake/path/output.md")
            
            # Store the mock for verification
            self.mock_path_class = mock_path_class
            
    def tearDown(self):
        """Clean up after each test"""
        # Reset mocks to avoid any leakage between tests
        if hasattr(self, 'mock_memory_client'):
            self.mock_memory_client.reset_mock()
        
        # Restore original record_action method if it was replaced
        if hasattr(self, 'original_record_action') and hasattr(self, 'agent'):
            self.agent.record_action = self.original_record_action
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.initialize_openai_client')
    def test_initialize_client(self, mock_init_client):
        """Test OpenAI client initialization"""
        # Set up mock
        mock_client = MagicMock()
        mock_init_client.return_value = mock_client
        
        # Test first call
        self.assertIsNone(self.agent.openai_client)
        self.agent._initialize_client()
        mock_init_client.assert_called_once()
        self.assertEqual(self.agent.openai_client, mock_client)
        
        # Test second call (should not initialize again)
        mock_init_client.reset_mock()
        self.agent._initialize_client()
        mock_init_client.assert_not_called()
    
    def test_load_core_context(self):
        """Test loading core context documents with memory client"""
        # Call the method
        self.agent.load_core_context()
        
        # Verify memory client calls
        self.mock_memory_client.get_page.assert_any_call("CHARTER.md")
        self.mock_memory_client.get_page.assert_any_call("MANIFESTO.md")
        self.mock_memory_client.get_page.assert_any_call("LICENSE.md")
        self.mock_memory_client.get_page.assert_any_call("README.md")
        self.mock_memory_client.get_page.assert_any_call("infra_core/cogni_spirit/spirits/cogni-core-spirit.md")
        
        # Verify that core_context was populated
        self.assertIsNotNone(self.agent.core_context)
        self.assertIn("context", self.agent.core_context)
        self.assertIn("metadata", self.agent.core_context)
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.get_pr_commits')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.get_pr_branches')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.parse_pr_url')
    def test_prepare_input(self, mock_parse, mock_branches, mock_commits):
        """Test prepare_input method with successful PR data retrieval"""
        # Set up mocks
        mock_pr_info = {"owner": "test-owner", "repo": "test-repo", "number": 123, "success": True}
        mock_parse.return_value = mock_pr_info
        
        mock_branch_info = {"source_branch": "feature", "target_branch": "main", "success": True}
        mock_branches.return_value = mock_branch_info
        
        mock_commit_info = {"commits": [{"sha": "abcd1234"}], "success": True}
        mock_commits.return_value = mock_commit_info
        
        # Test the method
        result = self.agent.prepare_input("https://github.com/test-owner/test-repo/pull/123")
        
        # Verify calls
        mock_parse.assert_called_once_with("https://github.com/test-owner/test-repo/pull/123")
        mock_branches.assert_called_once_with(mock_pr_info)
        mock_commits.assert_called_once_with(mock_pr_info)
        
        # Verify result
        self.assertEqual(result["pr_url"], "https://github.com/test-owner/test-repo/pull/123")
        self.assertEqual(result["pr_info"], mock_pr_info)
        self.assertEqual(result["branches"], mock_branch_info)
        self.assertEqual(result["commits"], mock_commit_info)
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.initialize_openai_client')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.review_pr')
    def test_act(self, mock_review, mock_init_client):
        """Test act method with PR review flow"""
        # Set up mocks
        mock_client = MagicMock()
        mock_init_client.return_value = mock_client
        
        mock_review_results = {
            "verdict": "APPROVE",
            "summary": "Good PR",
            "commit_reviews": [{"sha": "abc123", "feedback": "Looks good"}]
        }
        mock_review.return_value = mock_review_results
        
        # Create test input data
        test_input = {
            "pr_url": "https://github.com/test-owner/test-repo/pull/123",
            "pr_info": {"owner": "test-owner", "repo": "test-repo", "number": 123, "success": True},
            "pr_data": {"test": "data"}
        }
        
        # Set up core context
        self.agent.core_context = {"charter": "Charter content"}
        
        # Call the method
        result = self.agent.act(test_input)
        
        # Verify client initialization
        mock_init_client.assert_called_once()
        
        # Verify memory client call to get guide
        self.mock_memory_client.get_page.assert_any_call("infra_core/cogni_spirit/spirits/git-cogni.md")
        
        # Verify review call
        mock_review.assert_called_once()
        
        # Verify result
        self.assertEqual(result["pr_url"], test_input["pr_url"])
        self.assertEqual(result["task_description"], "Reviewing PR #123 in test-owner/test-repo")
        self.assertEqual(result["verdict"], "APPROVE")
        self.assertEqual(result["summary"], "Good PR")
        self.assertEqual(result["commit_reviews"], [{"sha": "abc123", "feedback": "Looks good"}])
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.prepare_input')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.act')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.load_core_context')
    def test_review_and_save_success(self, mock_load, mock_act, mock_prepare):
        """Test the review_and_save method with successful flow"""
        # Set up mocks
        mock_load.return_value = None
        
        input_data = {
            "pr_url": "https://github.com/test-owner/test-repo/pull/123",
            "pr_info": {"success": True, "owner": "test-owner", "repo": "test-repo", "number": 123},
            "branches": {"success": True},
            "commits": {
                "success": True,
                "commits": [{"sha": "abcd1234", "message": "Test commit"}]
            },
            "pr_data": {
                "metadata": {
                    "commit_count": 1
                }
            }
        }
        mock_prepare.return_value = input_data
        
        results = {
            "verdict": "APPROVE",
            "summary": "Good PR",
            "timestamp": "2023-01-01T12:00:00",
            "pr_info": {"owner": "test-owner", "repo": "test-repo", "number": 123},
            "final_verdict": "APPROVE",
            "verdict_decision": "APPROVE"
        }
        mock_act.return_value = results
        
        # Call the method
        result = self.agent.review_and_save("https://github.com/test-owner/test-repo/pull/123")
        
        # Verify calls
        mock_load.assert_called_once()
        mock_prepare.assert_called_once_with("https://github.com/test-owner/test-repo/pull/123")
        mock_act.assert_called_once_with(input_data)
        
        # Verify that record_action was called
        self.agent.record_action.assert_called_once()
        
        # Verify result
        self.assertEqual(result["review_file"], "/fake/path/output.md")
        self.assertEqual(result["verdict"], results["verdict"])
        self.assertEqual(result["summary"], results["summary"])
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.prepare_input')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.load_core_context')
    def test_review_and_save_pr_parse_error(self, mock_load, mock_prepare):
        """Test the review_and_save method with PR parsing error"""
        # Set up mock with failed PR info
        input_data = {
            "pr_url": "https://github.com/test-owner/test-repo/pull/123",
            "pr_info": {"success": False, "error": "Invalid URL format"},
            "branches": {},
            "commits": {},
            "pr_data": {}
        }
        mock_prepare.return_value = input_data
        
        # Call the method
        result = self.agent.review_and_save("invalid-url")
        
        # Verify that record_action was called
        self.agent.record_action.assert_called_once()
        
        # Verify error result was returned
        self.assertEqual(result["error"], "Failed to parse PR URL: Invalid URL format")
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.prepare_input')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.load_core_context')
    def test_review_and_save_branch_error(self, mock_load, mock_prepare):
        """Test the review_and_save method with branch retrieval error"""
        # Set up mock with failed branch info
        input_data = {
            "pr_url": "https://github.com/test-owner/test-repo/pull/123",
            "pr_info": {"success": True, "owner": "test-owner", "repo": "test-repo", "number": 123},
            "branches": {"success": False, "error": "API error"},
            "commits": {},
            "pr_data": {}
        }
        mock_prepare.return_value = input_data
        
        # Call the method
        result = self.agent.review_and_save("https://github.com/test-owner/test-repo/pull/123")
        
        # Verify that record_action was called
        self.agent.record_action.assert_called_once()
        
        # Verify error result was returned
        self.assertEqual(result["error"], "Failed to get branch info: API error")
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.prepare_input')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.load_core_context')
    def test_review_and_save_commit_error(self, mock_load, mock_prepare):
        """Test the review_and_save method with commit retrieval error"""
        # Set up mock with failed commit info
        input_data = {
            "pr_url": "https://github.com/test-owner/test-repo/pull/123",
            "pr_info": {"success": True, "owner": "test-owner", "repo": "test-repo", "number": 123},
            "branches": {"success": True},
            "commits": {"success": False, "error": "API error"},
            "pr_data": {}
        }
        mock_prepare.return_value = input_data
        
        # Call the method
        result = self.agent.review_and_save("https://github.com/test-owner/test-repo/pull/123")
        
        # Verify that record_action was called
        self.agent.record_action.assert_called_once()
        
        # Verify error result was returned
        self.assertEqual(result["error"], "Failed to get commit info: API error")
    
    def test_cleanup_files(self):
        """Test file cleanup works correctly"""
        # Set up mock files
        file1 = MagicMock(spec=Path)
        file1.exists.return_value = True
        
        file2 = MagicMock(spec=Path)
        file2.exists.return_value = True
        
        # Add to created files
        self.agent.created_files = [file1, file2]
        
        # Run cleanup
        count = self.agent.cleanup_files()
        
        # Verify files were deleted
        file1.unlink.assert_called_once()
        file2.unlink.assert_called_once()
        
        # Verify count
        self.assertEqual(count, 2)
        self.assertEqual(len(self.agent.created_files), 0)
    
    def test_cleanup_files_with_errors(self):
        """Test file cleanup handles errors gracefully"""
        # Set up mock files
        file1 = MagicMock(spec=Path)
        file1.exists.return_value = True
        file1.unlink.side_effect = Exception("Permission denied")
        
        file2 = MagicMock(spec=Path)
        file2.exists.return_value = True
        
        file3 = MagicMock(spec=Path)
        file3.exists.return_value = False  # File doesn't exist
        
        # Add to created files
        self.agent.created_files = [file1, file2, file3]
        
        # Run cleanup
        count = self.agent.cleanup_files()
        
        # Verify attempted operations
        file1.unlink.assert_called_once()
        file2.unlink.assert_called_once()
        file3.unlink.assert_not_called()  # Should not try to delete non-existent file
        
        # Verify count (only file2 should be counted)
        self.assertEqual(count, 1)
        self.assertEqual(len(self.agent.created_files), 0)


if __name__ == "__main__":
    unittest.main() 