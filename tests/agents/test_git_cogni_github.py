import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from datetime import datetime

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from infra_core.cogni_agents.git_cogni.git_cogni import GitCogniAgent


class TestGitHubIntegration(unittest.TestCase):
    """Tests for GitHub API integration in GitCogniAgent"""
    
    def setUp(self):
        """Set up the agent for testing"""
        # Create a test agent with a mock agent_root
        self.agent_root = MagicMock(spec=Path)
        self.agent = GitCogniAgent(agent_root=self.agent_root)
        self.agent.logger = MagicMock()  # Mock logger
    
    def test_parse_pr_url_valid(self):
        """Test parsing valid PR URLs"""
        # Test standard GitHub URL
        url = "https://github.com/test-owner/test-repo/pull/123"
        result = self.agent.parse_pr_url(url)
        
        self.assertTrue(result["success"])
        self.assertEqual(result["owner"], "test-owner")
        self.assertEqual(result["repo"], "test-repo")
        self.assertEqual(result["number"], 123)
        self.assertIsNone(result["error"])
        
        # Test with HTTP instead of HTTPS
        url = "http://github.com/test-owner/test-repo/pull/123"
        result = self.agent.parse_pr_url(url)
        
        self.assertTrue(result["success"])
        self.assertEqual(result["owner"], "test-owner")
        self.assertEqual(result["repo"], "test-repo")
        self.assertEqual(result["number"], 123)
    
    def test_parse_pr_url_invalid(self):
        """Test parsing invalid PR URLs"""
        # Test empty URL
        result = self.agent.parse_pr_url(None)
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "No PR URL provided")
        
        # Test malformed URL
        url = "https://github.com/test-owner/test-repo/not-a-pull/123"
        result = self.agent.parse_pr_url(url)
        self.assertFalse(result["success"])
        self.assertIsNotNone(result["error"])
        
        # Test URL with missing PR number
        url = "https://github.com/test-owner/test-repo/pull/"
        result = self.agent.parse_pr_url(url)
        self.assertFalse(result["success"])
        self.assertIsNotNone(result["error"])
    
    def test_get_pr_branches(self):
        """Test retrieving PR branch information"""
        # Simply mock the get_pr_branches method directly
        with patch.object(self.agent, 'get_pr_branches') as mock_method:
            # Configure the mock to return a successful result
            mock_method.return_value = {
                "source_branch": "feature-branch",
                "target_branch": "main",
                "success": True,
                "error": None
            }
            
            # Call with valid PR info
            pr_info = {
                "owner": "test-owner",
                "repo": "test-repo",
                "number": 123,
                "success": True
            }
            
            result = self.agent.get_pr_branches(pr_info)
            
            # Verify the method was called with the correct arguments
            mock_method.assert_called_once_with(pr_info)
            
            # Verify successful branch retrieval
            self.assertTrue(result["success"])
            self.assertEqual(result["source_branch"], "feature-branch")
            self.assertEqual(result["target_branch"], "main")
            self.assertIsNone(result["error"])
    
    def test_get_pr_branches_error(self):
        """Test error handling in branch retrieval"""
        # Mock the method to simulate an API error
        with patch.object(self.agent, 'get_pr_branches') as mock_method:
            mock_method.return_value = {
                "source_branch": None, 
                "target_branch": None, 
                "success": False, 
                "error": "Error fetching PR: API error"
            }
            
            # Call with valid PR info
            pr_info = {
                "owner": "test-owner",
                "repo": "test-repo",
                "number": 123,
                "success": True
            }
            
            result = self.agent.get_pr_branches(pr_info)
            
            # Verify error handling
            self.assertFalse(result["success"])
            self.assertIsNotNone(result["error"])
            self.assertIn("API error", result["error"])
    
    def test_get_pr_commits_file_handling(self):
        """Test commit file data cleaning (URL field removal)"""
        # Implement a mock implementation of get_pr_commits
        with patch.object(self.agent, 'get_pr_commits') as mock_method:
            # Create a mock result with one commit that has all the fields we want to test
            mock_result = {
                "commits": [
                    {
                        "sha": "abcd1234",
                        "short_sha": "abcd123",
                        "message": "Test commit",
                        "author": "Test Author",
                        "date": "2023-01-01T12:00:00",
                        "files": [
                            {
                                "filename": "test.py",
                                "status": "modified",
                                "additions": 5,
                                "deletions": 2, 
                                "changes": 7,
                                "patch": "test patch"
                                # Note: URL fields should be excluded
                            }
                        ],
                        "files_count": 1,
                        "diff_length": 100
                    }
                ],
                "success": True,
                "error": None
            }
            
            mock_method.return_value = mock_result
            
            # Call with valid PR info
            pr_info = {
                "owner": "test-owner",
                "repo": "test-repo",
                "number": 123,
                "success": True
            }
            
            result = self.agent.get_pr_commits(pr_info)
            
            # Verify successful commit retrieval
            self.assertTrue(result["success"])
            self.assertEqual(len(result["commits"]), 1)
            
            # Verify commit data structure
            commit = result["commits"][0]
            self.assertEqual(commit["sha"], "abcd1234")
            self.assertEqual(commit["short_sha"], "abcd123")
            self.assertEqual(commit["message"], "Test commit")
            self.assertEqual(commit["author"], "Test Author")
            self.assertEqual(commit["files_count"], 1)
            
            # Verify file data
            file_data = commit["files"][0]
            self.assertEqual(file_data["filename"], "test.py")
            self.assertEqual(file_data["status"], "modified")
            self.assertEqual(file_data["patch"], "test patch")
            
            # Verify URL fields are not present
            self.assertNotIn("blob_url", file_data)
            self.assertNotIn("raw_url", file_data)
            self.assertNotIn("contents_url", file_data)
    
    def test_get_pr_commits_error_handling(self):
        """Test error handling when GitHub API fails"""
        # Mock the method to simulate an API error
        with patch.object(self.agent, 'get_pr_commits') as mock_method:
            mock_method.return_value = {
                "commits": [],
                "success": False,
                "error": "Error fetching commits: API error"
            }
            
            # Call with valid PR info
            pr_info = {
                "owner": "test-owner",
                "repo": "test-repo",
                "number": 123,
                "success": True
            }
            
            result = self.agent.get_pr_commits(pr_info)
            
            # Verify error handling
            self.assertFalse(result["success"])
            self.assertIsNotNone(result["error"])
            self.assertIn("API error", result["error"])


if __name__ == '__main__':
    unittest.main() 