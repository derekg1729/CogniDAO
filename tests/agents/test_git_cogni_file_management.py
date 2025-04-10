import sys
import os
import unittest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
import json

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from infra_core.cogni_agents.git_cogni.git_cogni import GitCogniAgent


class TestFileManagement(unittest.TestCase):
    """Tests for file management in GitCogniAgent"""
    
    def setUp(self):
        """Set up test environment before each test"""
        # Create a test agent with a mock agent_root
        self.agent_root = MagicMock(spec=Path)
        self.agent = GitCogniAgent(agent_root=self.agent_root)
        self.agent.logger = MagicMock()  # Mock logger
    
    def test_record_action_tracking(self):
        """Test that created files are properly tracked"""
        # Setup the mocks
        with patch('pathlib.Path.mkdir', autospec=True) as mock_mkdir, \
             patch('pathlib.Path.write_text', autospec=True) as mock_write_text:
            
            # Configure the mock path to resolve and exist properly
            output_path = MagicMock(spec=Path)
            self.agent_root.__truediv__.return_value = output_path
            output_path.__truediv__.return_value = output_path
            output_path.resolve.return_value = output_path
            output_path.parent.exists.return_value = False  # Force mkdir to be called
            
            # Call record_action
            test_data = {"test": "data"}
            
            # Use direct mocking of CogniAgent parent class method
            with patch('infra_core.cogni_agents.base.CogniAgent.record_action', 
                      return_value=output_path) as mock_record_action:
                
                result = self.agent.record_action(test_data, subdir="test", prefix="prefix_")
                
                # Verify parent method was called
                mock_record_action.assert_called_once()
                
                # Verify that created file was tracked
                self.assertIn(output_path, self.agent.created_files)
    
    def test_cleanup_files(self):
        """Test cleaning up created files"""
        # Create mock files
        file1 = MagicMock(spec=Path)
        file1.exists.return_value = True
        
        file2 = MagicMock(spec=Path)
        file2.exists.return_value = True
        
        file3 = MagicMock(spec=Path)
        file3.exists.return_value = False  # This file doesn't exist
        
        # Add files to tracking list
        self.agent.created_files = [file1, file2, file3]
        
        # Call cleanup
        count = self.agent.cleanup_files()
        
        # Verify only existing files were deleted
        self.assertEqual(count, 2)
        file1.unlink.assert_called_once()
        file2.unlink.assert_called_once()
        file3.unlink.assert_not_called()
        
        # Verify tracking list was cleared
        self.assertEqual(len(self.agent.created_files), 0)
    
    def test_cleanup_files_with_errors(self):
        """Test cleanup handling when file deletion fails"""
        # Create mock files
        file1 = MagicMock(spec=Path)
        file1.exists.return_value = True
        file1.unlink.side_effect = Exception("Permission denied")
        
        file2 = MagicMock(spec=Path)
        file2.exists.return_value = True
        
        # Add files to tracking list
        self.agent.created_files = [file1, file2]
        
        # Call cleanup
        count = self.agent.cleanup_files()
        
        # Verify behavior
        self.assertEqual(count, 1)  # Only one file was successfully deleted
        file1.unlink.assert_called_once()
        file2.unlink.assert_called_once()
        
        # Verify warning was logged for failed deletion
        self.agent.logger.warning.assert_called_once()
        
        # Verify tracking list was cleared
        self.assertEqual(len(self.agent.created_files), 0)
    
    def test_review_and_save_file_naming(self):
        """Test file naming based on verdict"""
        # Mock record_action and other dependencies directly
        with patch.object(self.agent, 'load_core_context'), \
             patch.object(self.agent, 'prepare_input'), \
             patch.object(self.agent, 'act'), \
             patch.object(self.agent, 'record_action') as mock_record:
            
            # Setup mocks for prepare_input
            self.agent.prepare_input.return_value = {
                "pr_url": "https://github.com/test-owner/test-repo/pull/123",
                "pr_info": {"success": True, "owner": "test-owner", "repo": "test-repo", "number": 123},
                "branches": {"success": True},
                "commits": {"success": True, "commits": [{"sha": "abc123"}]},
                "pr_data": {"metadata": {"commit_count": 1}}
            }
            
            # Setup mocks for act
            self.agent.act.return_value = {
                "pr_info": {"owner": "test-owner", "repo": "test-repo", "number": 123},
                "final_verdict": "Final verdict: APPROVE",
                "verdict_decision": "APPROVE",
                "commit_reviews": [{"commit_sha": "abc123", "review": "Good commit"}]
            }
            
            # Setup mock for record_action
            output_path = MagicMock(spec=Path)
            output_path.__str__.return_value = "/fake/path/test-owner_test-repo_123_approve_timestamp.json"
            mock_record.return_value = output_path
            
            # Call review_and_save
            result = self.agent.review_and_save("https://github.com/test-owner/test-repo/pull/123")
            
            # Verify record_action was called with the correct prefix
            call_args = mock_record.call_args[1]
            self.assertEqual(call_args["subdir"], "reviews")
            self.assertIn("test-owner_test-repo_123_approve_", call_args["prefix"])
    
    def test_review_and_save_test_mode_cleanup(self):
        """Test review_and_save cleanup in test mode"""
        # Patch agent methods directly
        with patch.object(self.agent, 'load_core_context'), \
             patch.object(self.agent, 'prepare_input'), \
             patch.object(self.agent, 'act'), \
             patch.object(self.agent, 'record_action'), \
             patch.object(self.agent, 'cleanup_files') as mock_cleanup:
            
            # Setup mocks
            self.agent.prepare_input.return_value = {
                "pr_url": "https://github.com/test-owner/test-repo/pull/123",
                "pr_info": {"success": True, "owner": "test-owner", "repo": "test-repo", "number": 123},
                "branches": {"success": True},
                "commits": {"success": True, "commits": [{"sha": "abc123"}]},
                "pr_data": {"metadata": {"commit_count": 1}}
            }
            
            # Mock act to return a simple result
            self.agent.act.return_value = {
                "final_verdict": "APPROVE",
                "verdict_decision": "APPROVE"
            }
            
            # Mock record_action to return a path
            output_path = MagicMock(spec=Path)
            self.agent.record_action.return_value = output_path
            
            # Call review_and_save with test_mode=True
            result = self.agent.review_and_save("https://github.com/test-owner/test-repo/pull/123", test_mode=True)
            
            # Verify cleanup was called
            mock_cleanup.assert_called_once()


if __name__ == '__main__':
    unittest.main() 