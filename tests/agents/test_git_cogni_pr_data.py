import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from infra_core.cogni_agents.git_cogni.git_cogni import GitCogniAgent


class TestPRDataProcessing(unittest.TestCase):
    """Tests for PR data processing in GitCogniAgent"""
    
    def setUp(self):
        """Set up test environment before each test"""
        # Create a test agent with a mock agent_root
        self.agent_root = MagicMock(spec=Path)
        self.agent = GitCogniAgent(agent_root=self.agent_root, memory=MagicMock())
        self.agent.logger = MagicMock()  # Mock logger
    
    def test_monitor_token_usage(self):
        """Test token monitoring functionality"""
        # Test with a short string
        self.agent.monitor_token_usage("test-operation", "This is a test string")
        
        # Verify log was called with expected format
        self.agent.logger.info.assert_called_once()
        log_args = self.agent.logger.info.call_args[0][0]
        self.assertIn("TOKEN MONITOR", log_args)
        self.assertIn("test-operation", log_args)
        
        # The actual implementation logs word and character count, not the content
        self.assertIn("words", log_args.lower())
        self.assertIn("chars", log_args.lower())
        
        # Reset mock
        self.agent.logger.reset_mock()
        
        # Test with a longer string
        long_string = "This is a longer test string with more content to test token monitoring " * 10
        self.agent.monitor_token_usage("long-operation", long_string)
        
        # Verify log contains word count and character count
        self.agent.logger.info.assert_called_once()
        log_args = self.agent.logger.info.call_args[0][0]
        self.assertIn("TOKEN MONITOR", log_args)
        self.assertIn("long-operation", log_args)
        
        # Should contain word count and character length
        self.assertIn("words", log_args.lower())
        self.assertIn("chars", log_args.lower())
    
    def test_prepare_pr_data(self):
        """Test preparation of PR data in a structured format"""
        # Setup test data
        pr_info = {
            "owner": "test-owner",
            "repo": "test-repo",
            "number": 123,
            "success": True
        }
        
        branch_info = {
            "source_branch": "feature-branch",
            "target_branch": "main",
            "success": True
        }
        
        commit_info = {
            "commits": [
                {
                    "sha": "abc123def456",
                    "short_sha": "abc123d",
                    "message": "Test commit message",
                    "author": "Test Author",
                    "date": "2023-01-01T12:00:00Z",
                    "files": [
                        {
                            "filename": "test.py",
                            "status": "modified",
                            "additions": 10,
                            "deletions": 5,
                            "changes": 15,
                            "patch": "test patch"
                        }
                    ],
                    "files_count": 1,
                    "diff_length": 100
                }
            ],
            "success": True
        }
        
        # Mock datetime to return a fixed value
        with patch('infra_core.cogni_agents.git_cogni.git_cogni.datetime') as mock_datetime:
            mock_now = MagicMock()
            mock_now.isoformat.return_value = "2023-01-01T12:00:00Z"
            mock_datetime.now.return_value = mock_now
            
            # Call the function
            result = self.agent.prepare_pr_data(pr_info, branch_info, commit_info)
            
            # Verify structure
            self.assertEqual(result["pr_info"], pr_info)
            self.assertEqual(result["branch_info"], branch_info)
            self.assertEqual(result["commit_info"], commit_info)
            
            # Verify metadata
            self.assertEqual(result["metadata"]["timestamp"], "2023-01-01T12:00:00Z")
            self.assertEqual(result["metadata"]["commit_count"], 1)
    
    def test_prepare_input(self):
        """Test preparation of input data for agent action"""
        # Mock the component methods
        with patch.object(self.agent, 'parse_pr_url') as mock_parse, \
             patch.object(self.agent, 'get_pr_branches') as mock_branches, \
             patch.object(self.agent, 'get_pr_commits') as mock_commits, \
             patch.object(self.agent, 'prepare_pr_data') as mock_prepare_data:
            
            # Setup mocks
            pr_url = "https://github.com/test-owner/test-repo/pull/123"
            
            mock_pr_info = {"owner": "test-owner", "repo": "test-repo", "number": 123, "success": True}
            mock_parse.return_value = mock_pr_info
            
            mock_branch_info = {"source_branch": "feature-branch", "target_branch": "main", "success": True}
            mock_branches.return_value = mock_branch_info
            
            mock_commit_info = {"commits": [{"sha": "abc123"}], "success": True}
            mock_commits.return_value = mock_commit_info
            
            mock_pr_data = {"test": "data"}
            mock_prepare_data.return_value = mock_pr_data
            
            # Call the function
            result = self.agent.prepare_input(pr_url)
            
            # Verify calls were made in correct sequence
            mock_parse.assert_called_once_with(pr_url)
            mock_branches.assert_called_once_with(mock_pr_info)
            mock_commits.assert_called_once_with(mock_pr_info)
            mock_prepare_data.assert_called_once_with(mock_pr_info, mock_branch_info, mock_commit_info)
            
            # Verify result structure
            self.assertEqual(result["pr_url"], pr_url)
            self.assertEqual(result["pr_info"], mock_pr_info)
            self.assertEqual(result["branches"], mock_branch_info)
            self.assertEqual(result["commits"], mock_commit_info)
            self.assertEqual(result["pr_data"], mock_pr_data)


if __name__ == '__main__':
    unittest.main() 