import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from legacy_logseq.cogni_agents.git_cogni.git_cogni import GitCogniAgent


class TestGitCogniContextInclusion(unittest.TestCase):
    """Tests that core_context and git_cogni_context are included in all AI calls"""

    def setUp(self):
        """Set up test environment before each test"""
        # Create a test agent with a mock agent_root
        self.agent_root = MagicMock(spec=Path)
        self.agent = GitCogniAgent(agent_root=self.agent_root, memory=MagicMock())

        # Mock the OpenAI client
        self.agent.openai_client = MagicMock()

        # Mock the logger
        self.agent.logger = MagicMock()
        self.agent.monitor_token_usage = MagicMock()

        # Set up test data
        self.git_cogni_context = "Git Cogni spirit guide content"
        self.core_context = "Charter content\nManifesto content"  # String version for the test

        # Test PR data
        self.commit1 = {
            "short_sha": "abc123",
            "message": "First test commit",
            "author": "Test Author",
            "date": "2023-01-01",
            "files_count": 1,
            "files": [{"filename": "test.py", "patch": "test patch"}],
            "diff_length": 10,
        }

        self.commit2 = {
            "short_sha": "def456",
            "message": "Second test commit",
            "author": "Test Author",
            "date": "2023-01-01",
            "files_count": 1,
            "files": [{"filename": "test2.py", "patch": "test patch 2"}],
            "diff_length": 15,
        }

        self.pr_data = {
            "commit_info": {"commits": [self.commit1, self.commit2]},
            "pr_info": {"owner": "test-owner", "repo": "test-repo", "number": 123},
            "branch_info": {"source_branch": "feature", "target_branch": "main"},
        }

    @patch("legacy_logseq.cogni_agents.git_cogni.git_cogni.create_thread")
    @patch("legacy_logseq.cogni_agents.git_cogni.git_cogni.thread_completion")
    @patch("legacy_logseq.cogni_agents.git_cogni.git_cogni.extract_content")
    def test_contexts_in_commit_reviews(
        self, mock_extract, mock_thread_completion, mock_create_thread
    ):
        """Test that both contexts are included in commit review AI calls"""
        # Set up mocks
        mock_create_thread.return_value = ("thread_123", "asst_123")
        mock_thread_completion.return_value = {"choices": [{"message": {"content": "Test review"}}]}
        mock_extract.return_value = "Test review"

        # Call the review_pr method
        self.agent.review_pr(
            git_cogni_context=self.git_cogni_context,
            core_context=self.core_context,
            pr_data=self.pr_data,
        )

        # Verify create_thread was called with combined context
        mock_create_thread.assert_called_once()
        combined_context = mock_create_thread.call_args[0][1]
        self.assertIn(self.git_cogni_context, combined_context)
        self.assertIn(self.core_context, combined_context)

        # Verify thread_completion was called multiple times
        self.assertEqual(mock_thread_completion.call_count, 3)  # 2 commits + final verdict

        # Check that all thread_completion calls use the same thread ID
        for call_args in mock_thread_completion.call_args_list:
            self.assertEqual(call_args[1]["thread_id"], "thread_123")
            self.assertEqual(call_args[1]["assistant_id"], "asst_123")

    @patch("legacy_logseq.cogni_agents.git_cogni.git_cogni.create_thread")
    @patch("legacy_logseq.cogni_agents.git_cogni.git_cogni.thread_completion")
    @patch("legacy_logseq.cogni_agents.git_cogni.git_cogni.extract_content")
    def test_contexts_in_final_verdict(
        self, mock_extract, mock_thread_completion, mock_create_thread
    ):
        """Test that both contexts are included in the final verdict AI call"""
        # Set up mocks
        mock_create_thread.return_value = ("thread_123", "asst_123")
        mock_thread_completion.return_value = {"choices": [{"message": {"content": "Test review"}}]}
        mock_extract.return_value = "Test review"

        # Set up different responses for different calls
        def side_effect(client, thread_id, assistant_id, user_prompt):
            if "verdict" in user_prompt.lower() or "final" in user_prompt.lower():
                return {"choices": [{"message": {"content": "APPROVE Test verdict"}}]}
            return {"choices": [{"message": {"content": "Test commit review"}}]}

        mock_thread_completion.side_effect = side_effect

        # Call the review_pr method
        self.agent.review_pr(
            git_cogni_context=self.git_cogni_context,
            core_context=self.core_context,
            pr_data=self.pr_data,
        )

        # Verify create_thread was called with combined context
        mock_create_thread.assert_called_once()
        combined_context = mock_create_thread.call_args[0][1]
        self.assertIn(self.git_cogni_context, combined_context)
        self.assertIn(self.core_context, combined_context)

        # Get the last call (final verdict)
        last_call = mock_thread_completion.call_args_list[-1]

        # Verify last call is for verdict
        self.assertIn("verdict", last_call[1]["user_prompt"].lower())

    @patch("legacy_logseq.cogni_agents.git_cogni.git_cogni.create_thread")
    @patch("legacy_logseq.cogni_agents.git_cogni.git_cogni.thread_completion")
    @patch("legacy_logseq.cogni_agents.git_cogni.git_cogni.extract_content")
    def test_all_calls_include_consistent_contexts(
        self, mock_extract, mock_thread_completion, mock_create_thread
    ):
        """Test that threads are used consistently for all API calls"""
        # Set up mocks
        mock_create_thread.return_value = ("thread_123", "asst_123")
        mock_thread_completion.return_value = {"choices": [{"message": {"content": "Test review"}}]}
        mock_extract.return_value = "Test review"

        # Call the review_pr method
        self.agent.review_pr(
            git_cogni_context=self.git_cogni_context,
            core_context=self.core_context,
            pr_data=self.pr_data,
        )

        # Verify create_thread was called exactly once
        mock_create_thread.assert_called_once()

        # Verify thread_completion was called multiple times
        self.assertEqual(mock_thread_completion.call_count, 3)  # 2 commits + final verdict

        # Check that all API calls use the same thread
        for call_args in mock_thread_completion.call_args_list:
            self.assertEqual(call_args[1]["thread_id"], "thread_123")
            self.assertEqual(call_args[1]["assistant_id"], "asst_123")

    @patch("legacy_logseq.cogni_agents.base.CogniAgent.get_guide_for_task")
    @patch("legacy_logseq.cogni_agents.git_cogni.git_cogni.create_thread")
    @patch("legacy_logseq.cogni_agents.git_cogni.git_cogni.thread_completion")
    @patch("legacy_logseq.cogni_agents.git_cogni.git_cogni.extract_content")
    def test_comprehensive_workflow(
        self, mock_extract, mock_thread_completion, mock_create_thread, mock_get_guide
    ):
        """Test the entire workflow to verify context inclusion in both commit reviews and final verdict"""
        # Set up mocks
        mock_create_thread.return_value = ("thread_123", "asst_123")
        mock_thread_completion.return_value = {"choices": [{"message": {"content": "Test review"}}]}
        mock_extract.return_value = "Test review"
        mock_get_guide.return_value = self.git_cogni_context

        # Set up core_context as it would be in the actual implementation
        self.agent.core_context = self.core_context

        # Prepare test input
        test_input = {
            "pr_url": "https://github.com/test-owner/test-repo/pull/123",
            "pr_info": {"owner": "test-owner", "repo": "test-repo", "number": 123, "success": True},
            "pr_data": self.pr_data,
        }

        # Call the act method (which calls review_pr)
        self.agent.act(test_input)

        # Verify create_thread was called once
        mock_create_thread.assert_called_once()

        # Verify thread_completion was called multiple times
        self.assertGreaterEqual(mock_thread_completion.call_count, 3)

        # Verify all calls used the same thread
        for call_args in mock_thread_completion.call_args_list:
            self.assertEqual(call_args[1]["thread_id"], "thread_123")
            self.assertEqual(call_args[1]["assistant_id"], "asst_123")

        # Check context was combined in create_thread call
        combined_context = mock_create_thread.call_args[0][1]
        self.assertIn(self.git_cogni_context, combined_context)
        self.assertIn(self.core_context, combined_context)


if __name__ == "__main__":
    unittest.main()
