import sys
import os
import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
from datetime import datetime

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from infra_core.flows.gitcogni.gitcogni_flow import gitcogni_review_flow, parse_pr_url, get_pr_branches, get_pr_commits, prepare_pr_data


class TestGitCogniFlow(unittest.TestCase):
    
    def test_parse_pr_url(self):
        """Test URL parsing functionality"""
        pr_url = "https://github.com/test-owner/test-repo/pull/123"
        result = parse_pr_url(pr_url)
        
        self.assertTrue(result["success"])
        self.assertEqual(result["owner"], "test-owner")
        self.assertEqual(result["repo"], "test-repo")
        self.assertEqual(result["number"], 123)
        
    def test_parse_pr_url_empty(self):
        """Test URL parsing with empty input"""
        result = parse_pr_url(None)
        
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "No PR URL provided")
        
    @patch('infra_core.flows.gitcogni.gitcogni_flow.Github')
    def test_get_pr_branches(self, mock_github):
        """Test branch retrieval with mocked GitHub API"""
        # Setup mock
        mock_repo = mock_github.return_value.get_repo.return_value
        mock_pr = mock_repo.get_pull.return_value
        mock_pr.head.ref = "feature/test-branch"
        mock_pr.base.ref = "main"
        
        # Test data
        pr_info = {
            "owner": "test-owner",
            "repo": "test-repo",
            "number": 123,
            "success": True
        }
        
        # Call function
        result = get_pr_branches(pr_info)
        
        # Verify results
        self.assertTrue(result["success"])
        self.assertEqual(result["source_branch"], "feature/test-branch")
        self.assertEqual(result["target_branch"], "main")
        
        # Verify GitHub API calls
        mock_github.return_value.get_repo.assert_called_once_with("test-owner/test-repo")
        mock_repo.get_pull.assert_called_once_with(123)
    
    @patch('infra_core.flows.gitcogni.gitcogni_flow.Github')
    def test_get_pr_commits(self, mock_github):
        """Test commit retrieval with mocked GitHub data"""
        # Set up the mocks
        mock_repo = mock_github.return_value.get_repo.return_value
        mock_pr = mock_repo.get_pull.return_value
        
        # Mock commits
        mock_commit1 = MagicMock()
        mock_commit1.sha = "abcd1234567890"
        mock_commit1.commit.message = "First commit message"
        mock_commit1.commit.author.name = "Test Author"
        mock_commit1.commit.author.date.isoformat.return_value = "2023-01-01T12:00:00Z"
        
        mock_commit2 = MagicMock()
        mock_commit2.sha = "efgh1234567890"
        mock_commit2.commit.message = "Second commit message"
        mock_commit2.commit.author.name = "Test Author 2"
        mock_commit2.commit.author.date.isoformat.return_value = "2023-01-02T12:00:00Z"
        
        # Set up PR commits list
        mock_pr.get_commits.return_value = [mock_commit1, mock_commit2]
        
        # Mock file data with all fields
        file_data1 = {
            "filename": "test.py",
            "status": "modified",
            "additions": 5,
            "deletions": 2,
            "changes": 7,
            "patch": "diff --git a/test.py b/test.py\n@@ -1,5 +1,10 @@\n+def new_function():\n+    return 42\n def old_function():\n     return True",
            "blob_url": "https://github.com/test-owner/test-repo/blob/abcd123/test.py",
            "raw_url": "https://github.com/test-owner/test-repo/raw/abcd123/test.py",
            "contents_url": "https://api.github.com/repos/test-owner/test-repo/contents/test.py?ref=abcd123"
        }
        
        file_data2 = {
            "filename": "another.py",
            "status": "renamed",
            "previous_filename": "old_name.py",
            "additions": 1,
            "deletions": 1,
            "changes": 2,
            "patch": "diff --git a/another.py b/another.py\n@@ -1 +1 @@\n-old code\n+new code",
            "blob_url": "https://github.com/test-owner/test-repo/blob/abcd123/another.py",
            "raw_url": "https://github.com/test-owner/test-repo/raw/abcd123/another.py",
            "contents_url": "https://api.github.com/repos/test-owner/test-repo/contents/another.py?ref=abcd123"
        }
        
        mock_repo.get_commit.side_effect = lambda sha: MagicMock(
            raw_data={
                "files": [file_data1, file_data2]
            }
        )
        
        # Test data
        pr_info = {
            "owner": "test-owner",
            "repo": "test-repo",
            "number": 123,
            "success": True
        }
        
        # Call the function
        result = get_pr_commits(pr_info)
        
        # Verify results
        self.assertTrue(result["success"])
        self.assertEqual(len(result["commits"]), 2)
        self.assertEqual(result["commits"][0]["short_sha"], "abcd123")
        self.assertEqual(result["commits"][0]["message"], "First commit message")
        self.assertEqual(result["commits"][1]["message"], "Second commit message")
        
        # Verify git diff metrics
        self.assertEqual(result["commits"][0]["files_count"], 2)
        patch_len = len(file_data1["patch"]) + len(file_data2["patch"])
        self.assertEqual(result["commits"][0]["diff_length"], patch_len)
        
        # Verify URL fields are removed
        for file in result["commits"][0]["files"]:
            self.assertNotIn("blob_url", file)
            self.assertNotIn("raw_url", file)
            self.assertNotIn("contents_url", file)
            
        # Verify important fields are kept
        self.assertIn("filename", result["commits"][0]["files"][0])
        self.assertIn("status", result["commits"][0]["files"][0])
        self.assertIn("patch", result["commits"][0]["files"][0])
        
        # Verify renamed file metadata is preserved
        renamed_file = result["commits"][0]["files"][1]
        self.assertEqual(renamed_file["status"], "renamed")
        self.assertEqual(renamed_file["previous_filename"], "old_name.py")
        self.assertEqual(renamed_file["filename"], "another.py")
        
        # Verify GitHub API calls
        mock_github.return_value.get_repo.assert_called_once_with("test-owner/test-repo")
        mock_repo.get_pull.assert_called_once_with(123)
        mock_pr.get_commits.assert_called_once()
    
    @patch('infra_core.flows.gitcogni.gitcogni_flow.datetime')
    def test_prepare_pr_data(self, mock_datetime):
        """Test preparation of PR data structure"""
        # Mock datetime to return a fixed timestamp
        mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T12:00:00"
        
        # Test data
        pr_info = {
            "owner": "test-owner",
            "repo": "test-repo",
            "number": 123,
            "success": True
        }
        
        branch_info = {
            "source_branch": "feature/test-branch",
            "target_branch": "main",
            "success": True
        }
        
        commit_info = {
            "commits": [
                {
                    "sha": "abcd1234567890",
                    "short_sha": "abcd123",
                    "message": "Test commit message",
                    "files_count": 2,
                    "diff_length": 100
                }
            ],
            "success": True
        }
        
        # Call the function
        result = prepare_pr_data(pr_info, branch_info, commit_info)
        
        # Verify structure
        self.assertEqual(result["pr_info"], pr_info)
        self.assertEqual(result["branch_info"], branch_info)
        self.assertEqual(result["commit_info"], commit_info)
        self.assertEqual(result["metadata"]["timestamp"], "2023-01-01T12:00:00")
        self.assertEqual(result["metadata"]["commit_count"], 1)
    
    def test_gitcogni_review_flow_no_url(self):
        """Test the flow when no PR URL is provided"""
        message, pr_data = gitcogni_review_flow(pr_url=None)
        
        # Verify error message
        self.assertEqual(message, "Error: No PR URL provided")
        # Verify no data is returned
        self.assertIsNone(pr_data)
        
    @patch('infra_core.flows.gitcogni.gitcogni_flow.prepare_pr_data')
    @patch('infra_core.flows.gitcogni.gitcogni_flow.Github')
    def test_gitcogni_review_flow(self, mock_github, mock_prepare_data):
        """Test the entire flow with mocked GitHub data"""
        # Setup the mocks
        mock_repo = mock_github.return_value.get_repo.return_value
        mock_pr = mock_repo.get_pull.return_value
        
        # Set the mock values for branches
        mock_pr.head.ref = "feature/test-branch"
        mock_pr.base.ref = "main"
        
        # Mock commits
        mock_commit = MagicMock()
        mock_commit.sha = "abcd1234567890"
        mock_commit.commit.message = "Test commit"
        mock_commit.commit.author.name = "Test Author"
        mock_commit.commit.author.date.isoformat.return_value = "2023-01-01T12:00:00Z"
        
        # Set up PR commits list
        mock_pr.get_commits.return_value = [mock_commit]
        
        # Mock full commit objects with file patches
        patch = "diff --git a/test.py b/test.py\n@@ -1,5 +1,10 @@\n+def new_function():\n+    return True"
        mock_repo.get_commit.return_value = MagicMock(
            raw_data={
                "files": [
                    {"filename": "test.py", "patch": patch}
                ]
            }
        )
        
        # Mock the PR data preparation
        mock_pr_data = {
            "metadata": {
                "commit_count": 1
            }
        }
        mock_prepare_data.return_value = mock_pr_data
        
        # Run the flow with a mock PR URL
        pr_url = "https://github.com/test-owner/test-repo/pull/123"
        message, pr_data = gitcogni_review_flow(pr_url=pr_url)
        
        # Assert the result matches expected output
        self.assertEqual(message, "PR #123 branches: feature/test-branch → main")
        self.assertEqual(pr_data, mock_pr_data)
        
        # Verify that the right repo and PR number were requested
        mock_github.return_value.get_repo.assert_called_with("test-owner/test-repo")
        mock_repo.get_pull.assert_called_with(123)
        mock_pr.get_commits.assert_called_once()
        
        # Verify that prepare_pr_data was called
        mock_prepare_data.assert_called_once()


if __name__ == "__main__":
    unittest.main()
