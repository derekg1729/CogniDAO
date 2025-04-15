import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from infra_core.cogni_agents.git_cogni.git_cogni import GitCogniAgent


class TestGitCogniThreaded(unittest.TestCase):
    """Tests for the thread-based GitCogniAgent implementation."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a test agent with a mock agent_root
        self.agent_root = MagicMock(spec=Path)
        self.agent = GitCogniAgent(agent_root=self.agent_root, memory=MagicMock())
        
        # Mock logger
        self.agent.logger = MagicMock()
        
        # Mock OpenAI client
        self.agent.openai_client = MagicMock()
        
        # Set up test PR data
        self.pr_data = {
            'commit_info': {
                'commits': [
                    {
                        'short_sha': 'abc123',
                        'message': 'Test commit',
                        'author': 'Test Author',
                        'date': '2023-01-01',
                        'files_count': 1,
                        'files': [{'filename': 'test.py', 'patch': 'test patch'}],
                        'diff_length': 10
                    }
                ],
                'success': True
            },
            'pr_info': {
                'owner': 'test-owner',
                'repo': 'test-repo',
                'number': 123,
                'success': True
            },
            'branch_info': {
                'source_branch': 'feature',
                'target_branch': 'main',
                'success': True
            }
        }
        
        # Mock _combine_contexts to return a simple string
        self.agent._combine_contexts = MagicMock(return_value="Combined context")
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.create_thread')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.thread_completion')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.extract_content')
    def test_review_pr_creates_thread(self, mock_extract, mock_thread_completion, mock_create_thread):
        """Test that review_pr creates a thread and assistant."""
        # Set up mocks
        mock_create_thread.return_value = ("thread_123", "asst_123")
        mock_thread_completion.return_value = {"choices": [{"message": {"content": "Test review"}}]}
        mock_extract.return_value = "Test review"
        
        # Call review_pr
        self.agent.review_pr(
            git_cogni_context="Test git_cogni_context",
            core_context="Test core_context",
            pr_data=self.pr_data
        )
        
        # Verify create_thread was called
        mock_create_thread.assert_called_once_with(
            self.agent.openai_client, 
            "Combined context"
        )
        
        # Verify thread_id and assistant_id were stored
        self.assertEqual(self.agent.thread_id, "thread_123")
        self.assertEqual(self.agent.assistant_id, "asst_123")
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.create_thread')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.thread_completion')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.extract_content')
    def test_review_pr_uses_thread_for_commits(self, mock_extract, mock_thread_completion, mock_create_thread):
        """Test that review_pr uses thread for commit reviews."""
        # Set up mocks
        mock_create_thread.return_value = ("thread_123", "asst_123")
        mock_thread_completion.return_value = {"choices": [{"message": {"content": "Test review"}}]}
        mock_extract.return_value = "Test review"
        
        # Call review_pr
        self.agent.review_pr(
            git_cogni_context="Test git_cogni_context",
            core_context="Test core_context",
            pr_data=self.pr_data
        )
        
        # Verify thread_completion was called for the commit
        mock_thread_completion.assert_any_call(
            client=self.agent.openai_client,
            thread_id="thread_123",
            assistant_id="asst_123",
            user_prompt=unittest.mock.ANY  # Don't check exact prompt
        )
        
        # Get the first call arguments
        first_call_args = mock_thread_completion.call_args_list[0]
        
        # Verify prompt contains commit details
        self.assertIn("abc123", first_call_args[1]["user_prompt"])
        self.assertIn("Test commit", first_call_args[1]["user_prompt"])
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.create_thread')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.thread_completion')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.extract_content')
    def test_review_pr_uses_thread_for_verdict(self, mock_extract, mock_thread_completion, mock_create_thread):
        """Test that review_pr uses thread for final verdict."""
        # Set up mocks
        mock_create_thread.return_value = ("thread_123", "asst_123")
        mock_thread_completion.return_value = {"choices": [{"message": {"content": "Test review"}}]}
        
        # Make it easier to distinguish calls with different extract_content results
        def extract_side_effect(response):
            content = response["choices"][0]["message"]["content"]
            if "APPROVE" in content:
                return "APPROVE Test verdict"
            return "Test review"
        
        mock_extract.side_effect = extract_side_effect
        
        # Make it easier to distinguish calls
        def thread_completion_side_effect(client, thread_id, assistant_id, user_prompt):
            if "verdict" in user_prompt.lower() or "final" in user_prompt.lower():
                return {"choices": [{"message": {"content": "APPROVE Test verdict"}}]}
            return {"choices": [{"message": {"content": "Test commit review"}}]}
        
        mock_thread_completion.side_effect = thread_completion_side_effect
        
        # Call review_pr
        results = self.agent.review_pr(
            git_cogni_context="Test git_cogni_context",
            core_context="Test core_context",
            pr_data=self.pr_data
        )
        
        # Verify thread_completion was called multiple times
        self.assertGreaterEqual(mock_thread_completion.call_count, 2)
        
        # Get the last call arguments
        last_call_args = mock_thread_completion.call_args_list[-1]
        
        # Verify the last call was for the verdict
        self.assertIn("verdict", last_call_args[1]["user_prompt"].lower())
        
        # Verify thread IDs were used correctly
        for call_args in mock_thread_completion.call_args_list:
            self.assertEqual(call_args[1]["thread_id"], "thread_123")
            self.assertEqual(call_args[1]["assistant_id"], "asst_123")
        
        # Verify final verdict is stored in results
        self.assertIn("final_verdict", results)
        self.assertEqual(results["verdict_decision"], "APPROVE")
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.create_thread')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.thread_completion')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.extract_content')
    def test_review_pr_multiple_commits(self, mock_extract, mock_thread_completion, mock_create_thread):
        """Test that review_pr handles multiple commits correctly."""
        # Set up more test commits
        self.pr_data['commit_info']['commits'].append({
            'short_sha': 'def456',
            'message': 'Second test commit',
            'author': 'Test Author',
            'date': '2023-01-02',
            'files_count': 2,
            'files': [{'filename': 'test2.py', 'patch': 'test patch 2'}],
            'diff_length': 15
        })
        
        # Set up mocks
        mock_create_thread.return_value = ("thread_123", "asst_123")
        mock_thread_completion.return_value = {"choices": [{"message": {"content": "Test review"}}]}
        mock_extract.return_value = "Test review"
        
        # Call review_pr
        self.agent.review_pr(
            git_cogni_context="Test git_cogni_context",
            core_context="Test core_context",
            pr_data=self.pr_data
        )
        
        # Verify thread_completion was called for each commit plus verdict (3 times)
        self.assertEqual(mock_thread_completion.call_count, 3)
        
        # Get the first two call arguments
        first_call = mock_thread_completion.call_args_list[0]
        second_call = mock_thread_completion.call_args_list[1]
        
        # Verify prompts contain the correct commit details
        self.assertIn("abc123", first_call[1]["user_prompt"])
        self.assertIn("def456", second_call[1]["user_prompt"])


if __name__ == "__main__":
    unittest.main()

