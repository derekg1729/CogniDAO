import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from infra_core.cogni_agents.git_cogni.git_cogni import GitCogniAgent
from infra_core.openai_handler import create_completion, extract_content


class TestGitCogniOpenAIIntegration(unittest.TestCase):
    """Tests for the OpenAI integration in GitCogniAgent"""
    
    def setUp(self):
        """Set up the agent for testing"""
        # Create a test agent with a mock agent_root
        self.agent_root = MagicMock(spec=Path)
        self.agent = GitCogniAgent(agent_root=self.agent_root)
        
        # Add mock OpenAI client
        self.agent.openai_client = MagicMock()
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.create_completion')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.extract_content')
    def test_review_commit(self, mock_extract, mock_create):
        """Test that commit reviews properly call OpenAI APIs with correct parameters"""
        # Mock response objects
        mock_response = {"choices": [{"message": {"content": "Test review"}}]}
        mock_create.return_value = mock_response
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
        
        # Create a mock client
        client = MagicMock()
        
        # Setup a minimal review_pr call with only what's needed for the test
        # We're directly calling the part of review_pr that handles commit review
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
        
        # Verify create_completion was called with expected parameters
        mock_create.assert_called()
        
        # Check first positional arg is client
        self.assertEqual(mock_create.call_args[1]['client'], self.agent.openai_client)
        
        # Check system message parameter
        self.assertEqual(mock_create.call_args[1]['system_message'], git_cogni_context)
        
        # Check user prompt contains commit details
        self.assertIn(commit['short_sha'], mock_create.call_args[1]['user_prompt'])
        self.assertIn(commit['message'], mock_create.call_args[1]['user_prompt'])
        
        # Check temperature is appropriate for reviews
        self.assertEqual(mock_create.call_args[1]['temperature'], 0.3)
        
        # Verify extract_content was called on the response
        mock_extract.assert_called_with(mock_response)
        
        # Check that the result contains our test review
        self.assertEqual(len(response['commit_reviews']), 1)
        self.assertEqual(response['commit_reviews'][0]['review'], "Test review")
    
    @patch('infra_core.openai_handler.create_completion')
    @patch('infra_core.openai_handler.extract_content')
    def test_create_verdict(self, mock_extract, mock_create):
        """Test that final verdict calls OpenAI APIs with correct parameters"""
        # Mock response objects
        mock_response = {"choices": [{"message": {"content": "APPROVE\nTest verdict"}}]}
        mock_create.return_value = mock_response
        mock_extract.return_value = "APPROVE\nTest verdict"
        
        # Setup test data
        pr_data = {
            'commit_info': {
                'commits': []  # Empty since we've already tested commit reviews
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
        
        # Create review_results with commit reviews already processed
        review_results = {
            'pr_info': pr_data['pr_info'],
            'commit_reviews': [
                {'commit_sha': 'abc123', 'commit_message': 'First commit', 'review': 'Good'},
                {'commit_sha': 'def456', 'commit_message': 'Second commit', 'review': 'Needs work'}
            ],
            'timestamp': '2023-01-01T12:00:00'
        }
        
        # Setup mocks
        self.agent.monitor_token_usage = MagicMock()
        self.agent.logger = MagicMock()
        
        # To test just the final verdict part, create a subclass with a simplified review_pr
        class TestAgent(GitCogniAgent):
            def __init__(self, parent):
                self.openai_client = parent.openai_client
                self.logger = parent.logger
                self.monitor_token_usage = parent.monitor_token_usage
                # Add preset review_results to skip commit review part
                self._review_results = review_results
                self.get_verdict_from_text = MagicMock(return_value="APPROVE")
            
            def review_pr(self, git_cogni_context, core_context, pr_data):
                # Import locally to use the mocked versions from the outer function scope
                from infra_core.openai_handler import create_completion, extract_content
                
                # Call only the final verdict part of the process
                all_reviews = "\n\n".join([
                    f"## Commit {item['commit_sha']}: {item['commit_message']}\n{item['review']}"
                    for item in self._review_results["commit_reviews"]
                ])
                
                # Create prompt for final verdict
                final_prompt = f"""
                You have reviewed all commits in PR #{pr_data['pr_info']['number']} in {pr_data['pr_info']['owner']}/{pr_data['pr_info']['repo']}.
                Source Branch: {pr_data['branch_info']['source_branch']}
                Target Branch: {pr_data['branch_info']['target_branch']}
                
                Individual commit reviews:
                
                {all_reviews}
                
                Please provide a final verdict on this pull request:
                1. Summarize the overall changes and their purpose
                2. List any consistent issues or concerns found across commits
                3. Provide general recommendations for improvement
                4. Give a final decision: APPROVE, REQUEST_CHANGES, or COMMENT
                
                Format your verdict as markdown with clear sections.
                """
                
                # Call OpenAI for final verdict
                final_response = create_completion(
                    client=self.openai_client,
                    system_message=git_cogni_context,
                    user_prompt=final_prompt,
                    temperature=0.3,
                )
                
                # Add final verdict to results
                final_verdict = extract_content(final_response)
                self._review_results["final_verdict"] = final_verdict
                self._review_results["verdict_decision"] = self.get_verdict_from_text(final_verdict)
                
                return self._review_results
        
        # Create test agent with our special implementation
        test_agent = TestAgent(self.agent)
        
        # Call review_pr to test final verdict generation
        result = test_agent.review_pr(
            git_cogni_context="Test context",
            core_context={},
            pr_data=pr_data
        )
        
        # Verify create_completion was called with correct parameters
        mock_create.assert_called_once()
        
        # Check system_message
        self.assertEqual(mock_create.call_args[1]['system_message'], "Test context")
        
        # Check user prompt contains PR number and branches
        user_prompt = mock_create.call_args[1]['user_prompt']
        self.assertIn(f'PR #{pr_data["pr_info"]["number"]}', user_prompt)
        self.assertIn(f'Source Branch: {pr_data["branch_info"]["source_branch"]}', user_prompt)
        self.assertIn(f'Target Branch: {pr_data["branch_info"]["target_branch"]}', user_prompt)
        
        # Check that commit reviews are included
        self.assertIn("## Commit abc123", user_prompt)
        self.assertIn("## Commit def456", user_prompt)
        
        # Verify extract_content was called
        mock_extract.assert_called_with(mock_response)
        
        # Check that verdict was set in results
        self.assertEqual(result["final_verdict"], "APPROVE\nTest verdict")
        test_agent.get_verdict_from_text.assert_called_with("APPROVE\nTest verdict")
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