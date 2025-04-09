import sys
import os
import unittest
from unittest.mock import patch

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from infra_core.flows.gitcogni.gitcogni_flow import gitcogni_review_flow, parse_pr_url, get_pr_branches


class TestGitCogniFlow(unittest.TestCase):
    
    def test_parse_pr_url(self):
        """Test URL parsing functionality"""
        pr_url = "https://github.com/derekg1729/CogniDAO/pull/3"
        result = parse_pr_url(pr_url)
        
        self.assertTrue(result["success"])
        self.assertEqual(result["owner"], "derekg1729")
        self.assertEqual(result["repo"], "CogniDAO")
        self.assertEqual(result["number"], 3)
        
    @patch('infra_core.flows.gitcogni.gitcogni_flow.Github')
    def test_get_pr_branches_with_dummy_data(self, mock_github):
        """Test branch retrieval with dummy data"""
        pr_info = {
            "owner": "derekg1729",
            "repo": "CogniDAO",
            "number": 3,
            "success": True
        }
        
        result = get_pr_branches(pr_info, use_dummy_data=True)
        
        self.assertTrue(result["success"])
        self.assertEqual(result["source_branch"], "feature/test-branch")
        self.assertEqual(result["target_branch"], "main")
        
        # Make sure Github wasn't called
        mock_github.assert_not_called()
        
    @patch('infra_core.flows.gitcogni.gitcogni_flow.Github')
    def test_gitcogni_review_flow_with_real_data(self, mock_github):
        """Test the entire flow with mocked GitHub data to match the manual test"""
        # Setup the mock
        mock_repo = mock_github.return_value.get_repo.return_value
        mock_pr = mock_repo.get_pull.return_value
        
        # Set the mock values to match the actual PR
        mock_pr.head.ref = "cogni_graph"
        mock_pr.base.ref = "main"
        
        # Run the flow
        pr_url = "https://github.com/derekg1729/CogniDAO/pull/3"
        result = gitcogni_review_flow(pr_url=pr_url)
        
        # Assert the result matches expected output
        self.assertEqual(result, "PR #3 branches: cogni_graph → main")
        
        # Verify that the right repo and PR number were requested
        mock_github.return_value.get_repo.assert_called_once_with("derekg1729/CogniDAO")
        mock_repo.get_pull.assert_called_once_with(3)


if __name__ == "__main__":
    unittest.main()
