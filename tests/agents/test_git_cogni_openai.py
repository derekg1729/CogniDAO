import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from infra_core.cogni_agents.git_cogni.git_cogni import GitCogniAgent


class TestGitCogniOpenAIIntegration(unittest.TestCase):
    """Tests for the OpenAI integration in GitCogniAgent"""
    
    def setUp(self):
        """Set up the agent for testing"""
        # Create a test agent with a mock agent_root
        self.agent_root = MagicMock(spec=Path)
        self.agent = GitCogniAgent(agent_root=self.agent_root)
        
        # Add mock OpenAI client
        self.agent.openai_client = MagicMock()
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.create_thread')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.thread_completion')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.extract_content')
    def test_review_commit(self, mock_extract, mock_thread_completion, mock_create_thread):
        """Test that commit reviews properly call OpenAI APIs with correct parameters"""
        # Mock response objects
        mock_create_thread.return_value = ("thread_123", "asst_123")
        mock_thread_completion.return_value = {"choices": [{"message": {"content": "Test review"}}]}
        mock_extract.return_value = "Test review"
        
        # Create test PR data with a single commit
        commit = {
            "short_sha": "abc123",
            "message": "Test commit",
            "author": "Test Author",
            "date": "2023-01-01",
            "files_count": 1,
            "files": [{"filename": "test.py", "patch": "test patch"}],
            "diff_length": 10
        }
        
        # Setup a minimal review_pr call with only what's needed for the test
        self.agent.monitor_token_usage = MagicMock()  # Mock token monitoring
        self.agent.logger = MagicMock()  # Mock logger
        
        # Create context for commit review
        git_cogni_context = "Test context"
        
        # Call OpenAI API for commit review
        response = self.agent.review_pr(
            git_cogni_context=git_cogni_context,
            core_context={},
            pr_data={
                'commit_info': {'commits': [commit]},
                'pr_info': {'owner': 'test', 'repo': 'test', 'number': 1},
                'branch_info': {'source_branch': 'test', 'target_branch': 'main'}
            }
        )
        
        # Verify create_thread was called with expected parameters
        mock_create_thread.assert_called_once()
        self.assertEqual(mock_create_thread.call_args[0][0], self.agent.openai_client)
        
        # Verify thread_completion was called
        mock_thread_completion.assert_called()
        
        # Check that thread_completion calls include the right parameters
        call_args = mock_thread_completion.call_args_list[0][1]
        self.assertEqual(call_args["client"], self.agent.openai_client)
        self.assertEqual(call_args["thread_id"], "thread_123")
        self.assertEqual(call_args["assistant_id"], "asst_123")
        
        # Check user prompt contains commit details
        self.assertIn(commit['short_sha'], call_args["user_prompt"])
        self.assertIn(commit['message'], call_args["user_prompt"])
        
        # Verify extract_content was called on the response
        mock_extract.assert_called_with(mock_thread_completion.return_value)
        
        # Check that the result contains our test review
        self.assertEqual(len(response['commit_reviews']), 1)
        self.assertEqual(response['commit_reviews'][0]['review'], "Test review")
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.create_thread')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.thread_completion')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.extract_content')
    def test_create_verdict(self, mock_extract, mock_thread_completion, mock_create_thread):
        """Test that final verdict calls OpenAI APIs with correct parameters"""
        # Mock response objects
        mock_create_thread.return_value = ("thread_123", "asst_123")
        
        # Different responses for different prompts
        def side_effect(client, thread_id, assistant_id, user_prompt):
            if "verdict" in user_prompt.lower() or "final" in user_prompt.lower():
                return {"choices": [{"message": {"content": "APPROVE\nTest verdict"}}]}
            return {"choices": [{"message": {"content": "Test commit review"}}]}
        
        mock_thread_completion.side_effect = side_effect
        
        # Extract returns different outputs based on input
        def extract_side_effect(response):
            content = response["choices"][0]["message"]["content"]
            return content
        
        mock_extract.side_effect = extract_side_effect
        
        # Setup test data
        pr_data = {
            'commit_info': {
                'commits': [{
                    "short_sha": "abc123",
                    "message": "Test commit",
                    "author": "Test Author",
                    "date": "2023-01-01",
                    "files_count": 1,
                    "files": [{"filename": "test.py", "patch": "test patch"}],
                    "diff_length": 10
                }]
            },
            'pr_info': {
                'owner': 'test-owner',
                'repo': 'test-repo',
                'number': 123
            },
            'branch_info': {
                'source_branch': 'feature',
                'target_branch': 'main'
            }
        }
        
        # Setup mocks
        self.agent.monitor_token_usage = MagicMock()
        self.agent.logger = MagicMock()
        self.agent.get_verdict_from_text = MagicMock(return_value="APPROVE")
        
        # Call review_pr
        result = self.agent.review_pr(
            git_cogni_context="Test context",
            core_context={},
            pr_data=pr_data
        )
        
        # Verify thread_completion was called at least twice (commit + verdict)
        self.assertGreaterEqual(mock_thread_completion.call_count, 2)
        
        # Get last call which should be the verdict
        verdict_call = mock_thread_completion.call_args_list[-1]
        
        # Check that call is for verdict
        user_prompt = verdict_call[1]["user_prompt"]
        self.assertTrue(
            "verdict" in user_prompt.lower() or 
            "final" in user_prompt.lower() or 
            "decision" in user_prompt.lower()
        )
        
        # Check user prompt contains PR number and branches
        self.assertIn(f'PR #{pr_data["pr_info"]["number"]}', user_prompt)
        self.assertIn(f'Branch: {pr_data["branch_info"]["source_branch"]}', user_prompt)
        self.assertIn(f'Branch: {pr_data["branch_info"]["target_branch"]}', user_prompt)
        
        # Check that final verdict is in results
        self.assertIn("final_verdict", result)
        self.assertEqual(result["verdict_decision"], "APPROVE")
    
    def test_get_verdict_from_text(self):
        """Test extraction of verdict decision from text"""
        # Test APPROVE verdict
        approve_text = "Final decision: APPROVE\nThis PR looks good."
        self.assertEqual(self.agent.get_verdict_from_text(approve_text), "APPROVE")
        
        # Test REQUEST_CHANGES verdict
        changes_text = "I recommend REQUEST_CHANGES due to code issues."
        self.assertEqual(self.agent.get_verdict_from_text(changes_text), "REQUEST_CHANGES")
        
        # Test COMMENT verdict (default when neither APPROVE nor REQUEST_CHANGES)
        comment_text = "This PR has minor issues."
        self.assertEqual(self.agent.get_verdict_from_text(comment_text), "COMMENT")


if __name__ == '__main__':
    unittest.main() 