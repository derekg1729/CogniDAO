import sys
import os
import unittest
import json
from unittest.mock import patch, MagicMock, call
from pathlib import Path

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from infra_core.cogni_agents.git_cogni.git_cogni import GitCogniAgent


class TestGitCogniContextInclusion(unittest.TestCase):
    """Tests that core_context and git_cogni_context are included in all AI calls"""
    
    def setUp(self):
        """Set up test environment before each test"""
        # Create a test agent with a mock agent_root
        self.agent_root = MagicMock(spec=Path)
        self.agent = GitCogniAgent(agent_root=self.agent_root)
        
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
            "diff_length": 10
        }
        
        self.commit2 = {
            "short_sha": "def456",
            "message": "Second test commit",
            "author": "Test Author",
            "date": "2023-01-01",
            "files_count": 1,
            "files": [{"filename": "test2.py", "patch": "test patch 2"}],
            "diff_length": 15
        }
        
        self.pr_data = {
            'commit_info': {
                'commits': [self.commit1, self.commit2]
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
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.create_completion')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.extract_content')
    def test_contexts_in_commit_reviews(self, mock_extract, mock_create):
        """Test that both contexts are included in commit review AI calls"""
        # Set up mocks
        mock_response = {"choices": [{"message": {"content": "Test review"}}]}
        mock_create.return_value = mock_response
        mock_extract.return_value = "Test review"
        
        # Call the review_pr method
        self.agent.review_pr(
            git_cogni_context=self.git_cogni_context,
            core_context=self.core_context,
            pr_data=self.pr_data
        )
        
        # Verify the number of create_completion calls (1 per commit + 1 for verdict)
        self.assertEqual(mock_create.call_count, 3)
        
        # Check that the first two calls (commit reviews) include both contexts
        for i in range(2):  # For each commit review call
            system_message = mock_create.call_args_list[i][1]['system_message']
            self.assertEqual(
                system_message,
                self.git_cogni_context + "\n\n" + self.core_context,
                f"Commit review call {i+1} is missing complete context"
            )
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.create_completion')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.extract_content')
    def test_contexts_in_final_verdict(self, mock_extract, mock_create):
        """Test that both contexts are included in the final verdict AI call"""
        # Set up mocks
        mock_response = {"choices": [{"message": {"content": "APPROVE\nTest verdict"}}]}
        mock_create.return_value = mock_response
        mock_extract.return_value = "APPROVE\nTest verdict"
        
        # Call the review_pr method
        self.agent.review_pr(
            git_cogni_context=self.git_cogni_context,
            core_context=self.core_context,
            pr_data=self.pr_data
        )
        
        # Verify the number of create_completion calls (1 per commit + 1 for verdict)
        self.assertEqual(mock_create.call_count, 3)
        
        # Check that the final call (verdict) includes both contexts
        final_call = mock_create.call_args_list[2]
        system_message = final_call[1]['system_message']
        self.assertEqual(
            system_message,
            self.git_cogni_context + "\n\n" + self.core_context,
            "Final verdict call is missing complete context"
        )
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.create_completion')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.extract_content')
    def test_all_calls_include_consistent_contexts(self, mock_extract, mock_create):
        """Test that contexts are consistently included in all AI calls"""
        # Set up mocks
        mock_response = {"choices": [{"message": {"content": "Test review"}}]}
        mock_create.return_value = mock_response
        mock_extract.return_value = "Test review"
        
        # Call the review_pr method
        self.agent.review_pr(
            git_cogni_context=self.git_cogni_context,
            core_context=self.core_context,
            pr_data=self.pr_data
        )
        
        # Get all system messages from all calls
        system_messages = [
            call_args[1]['system_message'] 
            for call_args in mock_create.call_args_list
        ]
        
        # Check that all system messages are identical and contain both contexts
        expected_system_message = self.git_cogni_context + "\n\n" + self.core_context
        
        for i, message in enumerate(system_messages):
            self.assertEqual(
                message,
                expected_system_message,
                f"AI call #{i+1} has inconsistent context"
            )
        
        # Verify all calls have the same system message
        self.assertTrue(
            all(message == system_messages[0] for message in system_messages),
            "System messages are not consistent across all AI calls"
        )
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.get_guide_for_task')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.create_completion')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.extract_content')
    def test_comprehensive_workflow(self, mock_extract, mock_create, mock_get_guide):
        """Test the entire workflow to verify context inclusion in both commit reviews and final verdict"""
        # Set up mocks
        mock_response = {"choices": [{"message": {"content": "Test review"}}]}
        mock_create.return_value = mock_response
        mock_extract.return_value = "Test review"
        mock_get_guide.return_value = self.git_cogni_context
        
        # Set up core_context as it would be in the actual implementation
        self.agent.core_context = self.core_context
        
        # Prepare test input
        test_input = {
            "pr_url": "https://github.com/test-owner/test-repo/pull/123",
            "pr_info": {"owner": "test-owner", "repo": "test-repo", "number": 123, "success": True},
            "pr_data": self.pr_data
        }
        
        # Call the act method (which calls review_pr)
        self.agent.act(test_input)
        
        # Verify create_completion was called multiple times (once per commit + verdict)
        self.assertTrue(mock_create.call_count >= 3, f"Expected at least 3 AI calls, got {mock_create.call_count}")
        
        # Get all system messages from all calls
        system_messages = [
            call_args[1]['system_message'] 
            for call_args in mock_create.call_args_list
        ]
        
        # Check that all system messages contain both contexts
        expected_system_message = self.git_cogni_context + "\n\n" + self.core_context
        
        for i, message in enumerate(system_messages):
            self.assertEqual(
                message,
                expected_system_message,
                f"AI call #{i+1} is missing complete context"
            )


if __name__ == "__main__":
    unittest.main()
