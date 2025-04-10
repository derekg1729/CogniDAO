import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from io import StringIO
from pathlib import Path

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from infra_core.cogni_agents.git_cogni.cli import main

class TestGitCogniCLI(unittest.TestCase):
    """Tests for the GitCogni CLI interface"""
    
    @patch('sys.exit')
    @patch('sys.argv', ['git-cogni'])
    @patch('builtins.print')
    def test_no_url_provided(self, mock_print, mock_exit):
        """Test CLI with no PR URL provided"""
        # Call the main function with mocked dependencies
        with patch('infra_core.cogni_agents.git_cogni.cli.GitCogniAgent'):
            main()
        
        # Verify that help was displayed
        mock_print.assert_called()
        self.assertTrue(any("Usage: git-cogni <github-pr-url>" in call[0][0] for call in mock_print.call_args_list))
        
        # Verify exit was called with code 1
        mock_exit.assert_any_call(1)
    
    @patch('sys.exit')
    @patch('sys.argv', ['git-cogni', '--help'])
    @patch('builtins.print')
    def test_help_option(self, mock_print, mock_exit):
        """Test CLI with help option"""
        # Call the main function
        main()
        
        # Verify that help was displayed
        mock_print.assert_called()
        self.assertTrue(any("Usage: git-cogni <github-pr-url>" in call[0][0] for call in mock_print.call_args_list))
        
        # Verify exit was called with code 0
        mock_exit.assert_any_call(0)
    
    @patch('infra_core.cogni_agents.git_cogni.cli.GitCogniAgent')
    @patch('sys.argv', ['git-cogni', 'https://github.com/owner/repo/pull/123'])
    def test_pr_review_success(self, mock_agent_class):
        """Test CLI with successful PR review"""
        # Setup mocks
        mock_logger = MagicMock()
        mock_agent_class.setup_logging.return_value = mock_logger
        
        mock_agent = mock_agent_class.return_value
        mock_agent.review_and_save.return_value = {
            "verdict_decision": "APPROVE",
            "final_verdict": "APPROVE\nGood code",
            "review_file": "/path/to/review.md",
            "commit_reviews": [{"commit_sha": "abc123", "commit_message": "test"}]
        }
        
        # Call main with redirected stdout to capture prints
        with patch('sys.stdout', new=StringIO()) as fake_stdout:
            with patch('sys.exit') as mock_exit:
                main()
                
                # Verify agent was initialized
                mock_agent_class.assert_called_once()
                
                # Verify review_and_save was called with the PR URL
                mock_agent.review_and_save.assert_called_once_with("https://github.com/owner/repo/pull/123", test_mode=False)
                
                # Verify stdout output contains the verdict
                stdout_output = fake_stdout.getvalue()
                self.assertIn("PR Review completed: APPROVE", stdout_output)
                self.assertIn("Review saved to: /path/to/review.md", stdout_output)
    
    @patch('infra_core.cogni_agents.git_cogni.cli.GitCogniAgent')
    @patch('sys.argv', ['git-cogni', 'https://github.com/owner/repo/pull/123'])
    def test_pr_review_error(self, mock_agent_class):
        """Test CLI with PR review error"""
        # Setup mocks
        mock_logger = MagicMock()
        mock_agent_class.setup_logging.return_value = mock_logger
        
        mock_agent = mock_agent_class.return_value
        mock_agent.review_and_save.return_value = {
            "error": "Failed to parse PR URL",
            "pr_url": "https://github.com/owner/repo/pull/123"
        }
        
        # Call main
        with patch('sys.stdout', new=StringIO()) as fake_stdout:
            with patch('sys.exit') as mock_exit:
                main()
                
                # Verify agent was initialized
                mock_agent_class.assert_called_once()
                
                # Verify review_and_save was called with the PR URL
                mock_agent.review_and_save.assert_called_once_with("https://github.com/owner/repo/pull/123", test_mode=False)
                
                # Verify error was logged and printed
                mock_logger.error.assert_called()
                mock_exit.assert_called_once_with(1)
                
                # Check stdout for error message
                stdout_output = fake_stdout.getvalue()
                self.assertIn("Error: Failed to parse PR URL", stdout_output)
    
    @patch('infra_core.cogni_agents.git_cogni.cli.GitCogniAgent')
    @patch('sys.argv', ['git-cogni', 'https://github.com/owner/repo/pull/123'])
    def test_pr_review_exception(self, mock_agent_class):
        """Test CLI with exception during review"""
        # Setup mocks
        mock_logger = MagicMock()
        mock_agent_class.setup_logging.return_value = mock_logger
        
        mock_agent = mock_agent_class.return_value
        mock_agent.review_and_save.side_effect = Exception("Unexpected error")
        
        # Call main
        with patch('sys.stdout', new=StringIO()) as fake_stdout:
            with patch('sys.exit') as mock_exit:
                main()
                
                # Verify agent was initialized
                mock_agent_class.assert_called_once()
                
                # Verify review_and_save was called with the PR URL
                mock_agent.review_and_save.assert_called_once_with("https://github.com/owner/repo/pull/123", test_mode=False)
                
                # Verify exception was logged
                mock_logger.exception.assert_called()
                
                # Verify exit with code 1
                mock_exit.assert_called_once_with(1)
                
                # Check stdout for error message
                stdout_output = fake_stdout.getvalue()
                self.assertIn("Unexpected error: Unexpected error", stdout_output)

    @patch('infra_core.cogni_agents.git_cogni.cli.GitCogniAgent')
    @patch('sys.argv', ['git-cogni', 'https://github.com/owner/repo/pull/123', '--test'])
    def test_test_mode(self, mock_agent_class):
        """Test CLI with test mode enabled"""
        # Setup mocks
        mock_logger = MagicMock()
        mock_agent_class.setup_logging.return_value = mock_logger
        
        mock_agent = mock_agent_class.return_value
        mock_agent.review_and_save.return_value = {
            "verdict_decision": "APPROVE",
            "final_verdict": "APPROVE\nGood code",
            "review_file": "/path/to/review.md",
            "commit_reviews": [{"commit_sha": "abc123", "commit_message": "test"}]
        }
        
        # Call main with redirected stdout to capture prints
        with patch('sys.stdout', new=StringIO()) as fake_stdout:
            with patch('sys.exit') as mock_exit:
                main()
                
                # Verify agent was initialized
                mock_agent_class.assert_called_once()
                
                # Verify review_and_save was called with the PR URL and test_mode=True
                mock_agent.review_and_save.assert_called_once_with("https://github.com/owner/repo/pull/123", test_mode=True)
                
                # Verify stdout output contains the verdict
                stdout_output = fake_stdout.getvalue()
                self.assertIn("PR Review completed: APPROVE", stdout_output)
                self.assertIn("Review saved to: /path/to/review.md", stdout_output)


if __name__ == "__main__":
    unittest.main() 