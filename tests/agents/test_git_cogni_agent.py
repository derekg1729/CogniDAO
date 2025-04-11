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
            
            mock_path_class.return_value = mock_spirit_path
            mock_path_class.side_effect = lambda p: mock_spirit_path
            
            # Set up agent root
            self.agent_root = MagicMock(spec=Path)
            
            # Create the test agent
            self.agent = GitCogniAgent(agent_root=self.agent_root)
            
            # Store the mock for verification
            self.mock_path_class = mock_path_class
    
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
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.get_core_documents')
    def test_load_core_context(self, mock_get_core):
        """Test loading core context documents"""
        # Set up mock
        mock_context = {"charter": "Charter content", "manifesto": "Manifesto content"}
        mock_get_core.return_value = mock_context
        
        # Test the method
        self.agent.load_core_context()
        mock_get_core.assert_called_once()
        self.assertEqual(self.agent.core_context, mock_context)
    
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
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.get_guide_for_task')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.review_pr')
    def test_act(self, mock_review, mock_get_guide, mock_init_client):
        """Test act method with PR review flow"""
        # Set up mocks
        mock_client = MagicMock()
        mock_init_client.return_value = mock_client
        
        mock_spirit_guide = "Git Cogni spirit guide content"
        mock_get_guide.return_value = mock_spirit_guide
        
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
        
        # Verify guide retrieval
        mock_get_guide.assert_called_once_with(
            task="Reviewing PR #123 in test-owner/test-repo",
            guides=["git-cogni"]
        )
        
        # Verify review call
        mock_review.assert_called_once_with(
            git_cogni_context=mock_spirit_guide,
            core_context=self.agent.core_context,
            pr_data=test_input["pr_data"]
        )
        
        # Verify result
        self.assertEqual(result["pr_url"], test_input["pr_url"])
        self.assertEqual(result["task_description"], "Reviewing PR #123 in test-owner/test-repo")
        self.assertEqual(result["verdict"], "APPROVE")
        self.assertEqual(result["summary"], "Good PR")
        self.assertEqual(result["commit_reviews"], [{"sha": "abc123", "feedback": "Looks good"}])
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.prepare_input')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.act')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.record_action')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.load_core_context')
    def test_review_and_save_success(self, mock_load, mock_record, mock_act, mock_prepare):
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
            "timestamp": "2023-01-01T12:00:00"
        }
        mock_act.return_value = results
        
        mock_record.return_value = Path("/fake/path/review.md")
        
        # Call the method
        result = self.agent.review_and_save("https://github.com/test-owner/test-repo/pull/123")
        
        # Verify calls
        mock_load.assert_called_once()
        mock_prepare.assert_called_once_with("https://github.com/test-owner/test-repo/pull/123")
        mock_act.assert_called_once_with(input_data)
        
        # Verify record_action calls - expect only one call for the review
        self.assertEqual(mock_record.call_count, 1)
        self.assertEqual(mock_record.call_args[0][0], results)
        self.assertEqual(mock_record.call_args[1]["subdir"], "reviews")
        
        # Verify result
        self.assertEqual(result, results)
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.prepare_input')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.record_action')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.load_core_context')
    def test_review_and_save_pr_parse_error(self, mock_load, mock_record, mock_prepare):
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
        
        # Verify error was recorded
        mock_record.assert_called_once()
        error_data = mock_record.call_args[0][0]
        self.assertEqual(error_data["error"], "Failed to parse PR URL: Invalid URL format")
        self.assertEqual(mock_record.call_args[1]["subdir"], "errors")
        
        # Verify error result was returned
        self.assertEqual(result["error"], "Failed to parse PR URL: Invalid URL format")
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.prepare_input')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.record_action')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.load_core_context')
    def test_review_and_save_branch_error(self, mock_load, mock_record, mock_prepare):
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
        
        # Verify error was recorded
        mock_record.assert_called_once()
        error_data = mock_record.call_args[0][0]
        self.assertEqual(error_data["error"], "Failed to get branch info: API error")
        self.assertEqual(mock_record.call_args[1]["subdir"], "errors")
        
        # Verify error result was returned
        self.assertEqual(result["error"], "Failed to get branch info: API error")
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.prepare_input')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.record_action')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.load_core_context')
    def test_review_and_save_commit_error(self, mock_load, mock_record, mock_prepare):
        """Test the review_and_save method with commit retrieval error"""
        # Set up mock with failed commit info
        input_data = {
            "pr_url": "https://github.com/test-owner/test-repo/pull/123",
            "pr_info": {"success": True, "owner": "test-owner", "repo": "test-repo", "number": 123},
            "branches": {"success": True},
            "commits": {"success": False, "error": "Failed to get commit data"},
            "pr_data": {}
        }
        mock_prepare.return_value = input_data
        
        # Call the method
        result = self.agent.review_and_save("https://github.com/test-owner/test-repo/pull/123")
        
        # Verify error was recorded
        mock_record.assert_called_once()
        error_data = mock_record.call_args[0][0]
        self.assertEqual(error_data["error"], "Failed to get commit info: Failed to get commit data")
        self.assertEqual(mock_record.call_args[1]["subdir"], "errors")
        
        # Verify error result was returned
        self.assertEqual(result["error"], "Failed to get commit info: Failed to get commit data")

    def test_cleanup_files(self):
        """Test cleaning up created files"""
        # Set up mock files
        mock_file1 = MagicMock()
        mock_file1.exists.return_value = True
        mock_file2 = MagicMock() 
        mock_file2.exists.return_value = True
        mock_file3 = MagicMock()
        mock_file3.exists.return_value = True
        
        # Add files to the agent's tracking list
        self.agent.created_files = [mock_file1, mock_file2, mock_file3]
        
        # Call the cleanup method
        count = self.agent.cleanup_files()
        
        # Verify all files were deleted
        self.assertEqual(count, 3)
        mock_file1.unlink.assert_called_once()
        mock_file2.unlink.assert_called_once()
        mock_file3.unlink.assert_called_once()
        
        # Verify the created_files list was reset
        self.assertEqual(len(self.agent.created_files), 0)
    
    def test_cleanup_files_with_errors(self):
        """Test cleaning up files with some errors"""
        # Set up mock files
        mock_file1 = MagicMock()
        mock_file1.exists.return_value = True
        mock_file1.unlink.side_effect = Exception("Permission denied")
        
        mock_file2 = MagicMock()
        mock_file2.exists.return_value = True
        
        # Add files to the agent's tracking list
        self.agent.created_files = [mock_file1, mock_file2]
        
        # Call the cleanup method
        count = self.agent.cleanup_files()
        
        # Verify only one file was successfully deleted
        self.assertEqual(count, 1)
        mock_file1.unlink.assert_called_once()
        mock_file2.unlink.assert_called_once()
        
        # Verify the created_files list was reset
        self.assertEqual(len(self.agent.created_files), 0)


if __name__ == "__main__":
    unittest.main() 