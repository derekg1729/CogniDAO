import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from legacy_logseq.flows.gitcogni.gitcogni_flow import gitcogni_review_flow
from legacy_logseq.cogni_agents.git_cogni.git_cogni import GitCogniAgent

# Create an instance of GitCogniAgent to access its methods for testing
_agent = GitCogniAgent(agent_root=Path("legacy_logseq/cogni_agents/git_cogni"), memory=MagicMock())
parse_pr_url = _agent.parse_pr_url
get_pr_branches = _agent.get_pr_branches
get_pr_commits = _agent.get_pr_commits
prepare_pr_data = _agent.prepare_pr_data


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

    @patch("legacy_logseq.cogni_agents.git_cogni.git_cogni.Github")
    def test_get_pr_branches(self, mock_github):
        """Test branch retrieval with mocked GitHub API"""
        # Setup mock
        mock_repo = mock_github.return_value.get_repo.return_value
        mock_pr = mock_repo.get_pull.return_value
        mock_pr.head.ref = "feature/test-branch"
        mock_pr.base.ref = "main"

        # Test data
        pr_info = {"owner": "test-owner", "repo": "test-repo", "number": 123, "success": True}

        # Call function
        result = get_pr_branches(pr_info)

        # Verify results
        self.assertTrue(result["success"])
        self.assertEqual(result["source_branch"], "feature/test-branch")
        self.assertEqual(result["target_branch"], "main")

        # Verify GitHub API calls
        mock_github.return_value.get_repo.assert_called_once_with("test-owner/test-repo")
        mock_repo.get_pull.assert_called_once_with(123)

    def test_get_pr_commits(self):
        """Test commit retrieval using direct testing"""
        # Create a minimal mock with just the necessary functionality
        agent = GitCogniAgent(
            agent_root=Path("legacy_logseq/cogni_agents/git_cogni"), memory=MagicMock()
        )

        # Create test PR info
        pr_info = {"owner": "test-owner", "repo": "test-repo", "number": 123, "success": True}

        # Mock the Github module correctly
        with patch("legacy_logseq.cogni_agents.git_cogni.git_cogni.Github") as mock_github:
            # Mock the Github client
            mock_repo = mock_github.return_value.get_repo.return_value
            mock_pr = mock_repo.get_pull.return_value

            # Mock a commit with files
            mock_commit = MagicMock()
            mock_commit.sha = "abcd1234"
            mock_commit.commit.message = "Test commit message"
            mock_commit.commit.author.name = "Test Author"
            mock_commit.commit.author.date.isoformat.return_value = "2023-01-01T12:00:00Z"

            # Mock get_commits to return our mock commit
            mock_pr.get_commits.return_value = [mock_commit]

            # Mock get_commit to return a commit with files
            mock_file_data = {
                "filename": "test.py",
                "status": "modified",
                "additions": 5,
                "deletions": 2,
                "changes": 7,
                "patch": "test patch",
                "blob_url": "https://github.com/test/test",
                "raw_url": "https://raw.github.com/test/test",
                "contents_url": "https://api.github.com/repos/test/test",
            }

            mock_commit_obj = MagicMock()
            mock_commit_obj.raw_data = {"files": [mock_file_data]}
            mock_repo.get_commit.return_value = mock_commit_obj

            # Call the function
            result = agent.get_pr_commits(pr_info)

            # Assert results
            self.assertTrue(result["success"])
            self.assertEqual(len(result["commits"]), 1)
            self.assertEqual(result["commits"][0]["short_sha"], "abcd123")

            # Check that the URL fields are removed
            self.assertNotIn("blob_url", result["commits"][0]["files"][0])

    @patch("legacy_logseq.cogni_agents.git_cogni.git_cogni.datetime")
    def test_prepare_pr_data(self, mock_datetime):
        """Test preparation of PR data structure"""
        # Mock datetime to return a fixed timestamp
        mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T12:00:00"

        # Test data
        pr_info = {"owner": "test-owner", "repo": "test-repo", "number": 123, "success": True}

        branch_info = {
            "source_branch": "feature/test-branch",
            "target_branch": "main",
            "success": True,
        }

        commit_info = {
            "commits": [
                {
                    "sha": "abcd1234567890",
                    "short_sha": "abcd123",
                    "message": "Test commit message",
                    "files_count": 2,
                    "diff_length": 100,
                }
            ],
            "success": True,
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

    @patch("prefect.get_run_logger")
    @patch("legacy_logseq.flows.gitcogni.gitcogni_flow.GitCogniAgent")
    @patch("legacy_logseq.cogni_agents.git_cogni.git_cogni.Github")
    def test_gitcogni_review_flow(self, mock_github, mock_agent_class, mock_get_logger):
        """Test the entire flow with mocked GitHub data"""
        # Mock logger
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Mock GitCogniAgent instance
        mock_agent = mock_agent_class.return_value

        # Mock the parse_pr_url method to return success
        mock_agent.parse_pr_url.return_value = {
            "owner": "test-owner",
            "repo": "test-repo",
            "number": 123,
            "success": True,
            "error": None,
        }

        # Mock the review_and_save method
        review_result = {
            "pr_info": {
                "owner": "test-owner",
                "repo": "test-repo",
                "number": 123,
                "source_branch": "feature/test-branch",
                "target_branch": "main",
            },
            "commit_reviews": [
                {"commit_sha": "abcd123", "commit_message": "Test commit", "review": "Good code"}
            ],
            "final_verdict": "APPROVE",
            "verdict_decision": "APPROVE",
            "timestamp": "2023-01-01T12:00:00Z",
            "review_file": "/path/to/review_file.md",
        }
        mock_agent.review_and_save.return_value = review_result

        # Run the flow with a mock PR URL
        pr_url = "https://github.com/test-owner/test-repo/pull/123"
        message, pr_data = gitcogni_review_flow(pr_url=pr_url)

        # Verify GitCogniAgent initialization and parse_pr_url call
        mock_agent_class.assert_called_once()
        mock_agent.parse_pr_url.assert_called_once_with(pr_url)

        # Verify review_and_save was called
        mock_agent.review_and_save.assert_called_once_with(pr_url, test_mode=False)

        # Verify basic structure of the returned data
        self.assertIsNotNone(pr_data)
        self.assertEqual(pr_data, review_result)

    @patch("prefect.get_run_logger")
    @patch("legacy_logseq.flows.gitcogni.gitcogni_flow.GitCogniAgent")
    def test_gitcogni_review_flow_test_mode(self, mock_agent_class, mock_get_logger):
        """Test the flow with test mode enabled"""
        # Setup mocks
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Mock GitCogniAgent instance
        mock_agent = mock_agent_class.return_value

        # Mock the parse_pr_url method to return success
        mock_agent.parse_pr_url.return_value = {
            "owner": "test-owner",
            "repo": "test-repo",
            "number": 123,
            "success": True,
            "error": None,
        }

        # Mock the review_and_save method
        review_result = {
            "pr_info": {
                "owner": "test-owner",
                "repo": "test-repo",
                "number": 123,
                "source_branch": "feature/test-branch",
                "target_branch": "main",
            },
            "commit_reviews": [
                {"commit_sha": "abcd123", "commit_message": "Test commit", "review": "Good code"}
            ],
            "final_verdict": "APPROVE",
            "verdict_decision": "APPROVE",
            "timestamp": "2023-01-01T12:00:00Z",
            "review_file": "/path/to/review_file.md",
        }
        mock_agent.review_and_save.return_value = review_result

        # Run the flow with a mock PR URL and test_mode=True
        pr_url = "https://github.com/test-owner/test-repo/pull/123"
        message, pr_data = gitcogni_review_flow(pr_url=pr_url, test_mode=True)

        # Verify GitCogniAgent initialization
        mock_agent_class.assert_called_once()

        # Verify parse_pr_url was called
        mock_agent.parse_pr_url.assert_called_once_with(pr_url)

        # Verify review_and_save was called with test_mode=True
        mock_agent.review_and_save.assert_called_once_with(pr_url, test_mode=True)

        # Verify basic structure of the returned data
        self.assertIsNotNone(pr_data)
        self.assertEqual(pr_data, review_result)


if __name__ == "__main__":
    unittest.main()
