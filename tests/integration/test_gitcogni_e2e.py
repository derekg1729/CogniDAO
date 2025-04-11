import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json
import datetime

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from infra_core.flows.gitcogni.gitcogni_flow import gitcogni_review_flow
from infra_core.cogni_agents.git_cogni.git_cogni import GitCogniAgent


class TestGitCogniE2E(unittest.TestCase):
    """End-to-end integration test for GitCogni"""
    
    def setUp(self):
        """Set up the test environment"""
        # Create a temp dir for test outputs
        self.test_dir = Path("tests/integration/tmp")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
        # Create agent root for test
        self.agent_root = self.test_dir / "git_cogni"
        self.agent_root.mkdir(exist_ok=True)
        
    def tearDown(self):
        """Clean up test environment"""
        # Remove test files
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def _mock_pr_info(self):
        """Create mock PR info for GitHub API responses"""
        return {
            "owner": "derekg1729",
            "repo": "CogniDAO",
            "number": 2,
            "success": True
        }
        
    def _mock_branch_info(self):
        """Create mock branch info for GitHub API responses"""
        return {
            "source_branch": "preview/clean-prefect-logseq-presence",
            "target_branch": "main",
            "success": True
        }
        
    def _mock_commits(self):
        """Create mock commit data for GitHub API responses"""
        # Based on real commits from the PR, but simplified
        return {
            "commits": [
                {
                    "sha": "7c26fab",
                    "short_sha": "7c26fab",
                    "message": "v1 context loader, barely rag, first md mock thought",
                    "author": "derekg1729",
                    "date": "2025-04-06T19:19:00Z",
                    "files": [
                        {
                            "filename": "infra_core/cogni_spirit/context.py",
                            "status": "added",
                            "additions": 120,
                            "deletions": 0,
                            "changes": 120,
                            "patch": "Context loader setup for spirit guides..."
                        }
                    ],
                    "files_count": 1,
                    "diff_length": 250
                },
                {
                    "sha": "32c3110",
                    "short_sha": "32c3110",
                    "message": "first raw thought from openAI call with full guide context",
                    "author": "derekg1729",
                    "date": "2025-04-06T20:30:00Z",
                    "files": [
                        {
                            "filename": "infra_core/openai_handler.py",
                            "status": "added",
                            "additions": 80,
                            "deletions": 0,
                            "changes": 80,
                            "patch": "OpenAI handler implementation..."
                        }
                    ],
                    "files_count": 1,
                    "diff_length": 200
                },
                {
                    "sha": "f0e4896",
                    "short_sha": "f0e4896",
                    "message": "actual full context ritual thought, with proper prefect deployment script",
                    "author": "derekg1729",
                    "date": "2025-04-06T22:45:00Z",
                    "files": [
                        {
                            "filename": "infra_core/flows/rituals/ritual_of_presence.py",
                            "status": "added",
                            "additions": 150,
                            "deletions": 0,
                            "changes": 150,
                            "patch": "Ritual of presence implementation..."
                        }
                    ],
                    "files_count": 1,
                    "diff_length": 300
                },
                {
                    "sha": "0fd0ec6",
                    "short_sha": "0fd0ec6",
                    "message": "Fix: Restore correct content in marketing-spirit.md",
                    "author": "derekg1729",
                    "date": "2025-04-07T09:15:00Z",
                    "files": [
                        {
                            "filename": "infra_core/cogni_spirit/guides/marketing-spirit.md",
                            "status": "modified",
                            "additions": 1,
                            "deletions": 2,
                            "changes": 3,
                            "patch": "Fix planted issue in spirit guide..."
                        }
                    ],
                    "files_count": 1,
                    "diff_length": 50
                }
            ],
            "success": True
        }

    @patch('infra_core.cogni_agents.git_cogni.git_cogni.initialize_openai_client')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.create_completion')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.extract_content')
    @patch('infra_core.flows.gitcogni.gitcogni_flow.GitCogniAgent')
    def test_gitcogni_e2e_flow(self, 
                               mock_agent_class,
                               mock_extract_content, 
                               mock_create_completion, 
                               mock_init_openai):
        """Test the complete GitCogni flow end-to-end with mocked dependencies"""
        # Setup mock OpenAI client
        mock_openai = MagicMock()
        mock_init_openai.return_value = mock_openai
        
        # Setup mock agent
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        
        # Setup parse_pr_url method to return success
        mock_agent.parse_pr_url.return_value = self._mock_pr_info()
        
        # Setup the review_and_save method to return a properly formatted mock result
        mock_review_result = {
            "pr_info": {
                "owner": "derekg1729",
                "repo": "CogniDAO",
                "number": 2,
                "source_branch": "preview/clean-prefect-logseq-presence",
                "target_branch": "main"
            },
            "commit_reviews": [
                {
                    "commit_sha": "7c26fab",
                    "commit_message": "v1 context loader, barely rag, first md mock thought", 
                    "review": "Good code structure, but lacks tests. ⭐⭐⭐"
                },
                {
                    "commit_sha": "32c3110",
                    "commit_message": "first raw thought from openAI call with full guide context", 
                    "review": "API integration works, but lacks tests. ⭐⭐⭐"
                },
                {
                    "commit_sha": "f0e4896",
                    "commit_message": "actual full context ritual thought, with proper prefect deployment script", 
                    "review": "Good implementation, but lacks tests. ⭐⭐⭐"
                },
                {
                    "commit_sha": "0fd0ec6",
                    "commit_message": "Fix: Restore correct content in marketing-spirit.md", 
                    "review": "Good fix for the spirit guide issue. ⭐⭐⭐⭐⭐"
                }
            ],
            "final_verdict": "# Final Verdict\n\nThis PR introduces important functionality but lacks tests. REQUEST_CHANGES",
            "verdict_decision": "REQUEST_CHANGES",
            "review_file": f"{self.agent_root}/reviews/test_review.md"
        }
        mock_agent.review_and_save.return_value = mock_review_result
        
        # Setup completion responses - simulate realistic responses
        mock_commit_review_response = {"choices": [{"message": {"content": """
# Review of Commit

## Code Quality and Simplicity
The code/changes are well-structured and concise.

## Alignment Between Code and Commit Message
The commit message accurately describes the changes.

## Potential Issues
No major issues detected.

## Suggestions for Improvement
Consider adding tests for this functionality.

## Rating
⭐⭐⭐⭐
"""}}]}
        
        mock_verdict_response = {"choices": [{"message": {"content": """
# Final Verdict: PR #2 in derekg1729/CogniDAO

## Summary of Changes
This PR introduces several key components for the CogniDAO project:
- Context loading for spirit guides
- OpenAI integration
- Ritual of presence implementation
- Fix for marketing-spirit.md

## Consistent Issues
- Lack of corresponding tests
- Some parts could use more error handling

## Recommendations
- Add tests for the implemented functionality
- Improve error handling in API calls

## Final Decision
REQUEST_CHANGES

Reviewed by git-cogni
Guided by git-cogni.md
Reviewed on: 2025-04-08
"""}}]}
        
        # Setup extract_content responses
        mock_extract_content.side_effect = lambda response: response["choices"][0]["message"]["content"]
        
        # Setup create_completion to return different responses for commit reviews vs verdict
        def mock_completion_side_effect(*args, **kwargs):
            # Check the prompt to determine if it's a commit review or verdict
            prompt = kwargs.get('user_prompt', '')
            if "Review this specific commit in isolation" in prompt:
                return mock_commit_review_response
            else:
                return mock_verdict_response
        
        mock_create_completion.side_effect = mock_completion_side_effect
        
        # Execute the flow
        pr_url = "https://github.com/derekg1729/CogniDAO/pull/2"
        message, results = gitcogni_review_flow(pr_url=pr_url, test_mode=True)
        
        # Verify the flow executed successfully
        self.assertIsNotNone(results)
        
        # Verify that the agent's review_and_save method was called with expected parameters
        mock_agent.review_and_save.assert_called_once_with(pr_url, test_mode=True)
        
        # Verify the expected results format
        self.assertEqual(results["verdict_decision"], "REQUEST_CHANGES")
        self.assertEqual(len(results["commit_reviews"]), 4)
        self.assertIn("final_verdict", results)


if __name__ == '__main__':
    unittest.main() 