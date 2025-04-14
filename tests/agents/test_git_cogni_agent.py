import sys
import os
import unittest
from unittest.mock import patch, MagicMock, call
from pathlib import Path
import tempfile

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from infra_core.cogni_agents.git_cogni.git_cogni import GitCogniAgent
from infra_core.memory.memory_bank import CogniMemoryBank


class TestGitCogniAgent(unittest.TestCase):
    """Tests for the GitCogniAgent implementation"""
    
    def setUp(self):
        """Set up test environment before each test using temporary directories."""
        # Create temporary directories for project root, agent root, and memory bank
        self.temp_project_dir = tempfile.TemporaryDirectory()
        self.temp_agent_dir = tempfile.TemporaryDirectory()
        self.temp_memory_dir = tempfile.TemporaryDirectory()

        self.project_root_override = Path(self.temp_project_dir.name)
        self.agent_root = Path(self.temp_agent_dir.name)
        self.memory_bank_root_override = Path(self.temp_memory_dir.name)

        # Create dummy core files in the temp project root for fallback testing
        self.core_files_content = {}
        core_docs = ["CHARTER.md", "MANIFESTO.md", "LICENSE.md", "README.md"]
        for fname in core_docs:
            fpath = self.project_root_override / fname
            content = f"Dummy content for {fname}"
            fpath.write_text(content)
            self.core_files_content[fname] = content
        
        # Dummy core spirit guide
        core_spirit_rel_path = Path("infra_core/cogni_spirit/spirits/cogni-core-spirit.md")
        core_spirit_dir = self.project_root_override / core_spirit_rel_path.parent
        core_spirit_dir.mkdir(parents=True, exist_ok=True)
        core_spirit_path = core_spirit_dir / core_spirit_rel_path.name
        core_spirit_content = "Dummy core spirit content"
        core_spirit_path.write_text(core_spirit_content)
        self.core_files_content["core_spirit.md"] = core_spirit_content # Store with memory filename

        # Create dummy agent spirit file within the temporary project root
        spirit_rel_path = Path("infra_core/cogni_spirit/spirits/git-cogni.md")
        spirit_dir = self.project_root_override / spirit_rel_path.parent
        spirit_dir.mkdir(parents=True, exist_ok=True)
        self.spirit_file_path = spirit_dir / spirit_rel_path.name
        self.spirit_file_path.write_text("Dummy Git Cogni spirit")

        # Create the test agent IN setUp, injecting the temporary paths
        # Mocks for memory interaction during init need to be active *around* this call
        # We will patch specific tests that need to verify init calls.
        self.agent = GitCogniAgent(
            agent_root=self.agent_root,
            memory_bank_root_override=self.memory_bank_root_override,
            project_root_override=self.project_root_override
        )
            
        # Mock the record_action method AFTER agent init to simplify output checks
        # This is still useful for tests focusing on other logic.
        self.original_record_action = self.agent.record_action
        self.agent.record_action = MagicMock(return_value=self.agent_root / "fake_output.md")
            
    def tearDown(self):
        """Clean up after each test"""
        # Clean up temporary directories
        self.temp_project_dir.cleanup()
        self.temp_agent_dir.cleanup()
        self.temp_memory_dir.cleanup()
        
        # Restore original record_action method if it was replaced
        if hasattr(self, 'original_record_action') and hasattr(self, 'agent'):
            self.agent.record_action = self.original_record_action
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.initialize_openai_client')
    def test_initialize_client(self, mock_init_client):
        """Test OpenAI client initialization"""
        # Set up mock
        mock_client = MagicMock()
        mock_init_client.return_value = mock_client
        
        # Test first call
        self.assertIsNone(self.agent.openai_client)
        self.agent._initialize_client()
        mock_init_client.assert_called_once()
        self.assertEqual(self.agent.openai_client, mock_client)
        
        # Test second call (should not initialize again)
        mock_init_client.reset_mock()
        self.agent._initialize_client()
        mock_init_client.assert_not_called()
    
    @patch.object(CogniMemoryBank, 'write_context')
    @patch.object(CogniMemoryBank, '_read_file')
    def test_load_core_context(self, mock_read_file, mock_write_context):
        """Test loading core context documents using CogniMemoryBank and fallbacks."""
        
        # --- Test Setup --- 
        # Define side effect for the __init__ call (load_spirit + load_core_context)
        # This mock needs to be active *during* the setUp call, which is tricky.
        # Alternative: Re-run load_core_context explicitly and check calls.
        
        def read_side_effect(*args, **kwargs):
            filename = args[0]
            # Simulate core files needing fallback, spirit already loaded by setUp (unmocked)
            if filename == self.spirit_file_path.name:
                return "Dummy Git Cogni spirit" # Simulate already loaded
            if filename == "CHARTER.md":
                return "Charter from Memory"
            if filename == "MANIFESTO.md":
                return None # Force fallback
            if filename == "LICENSE.md":
                return "License from Memory"
            if filename == "README.md":
                return None # Force fallback
            if filename == "core_spirit.md":
                return None # Force fallback
            return None # Default case
        mock_read_file.side_effect = read_side_effect

        # Reset mocks to clear any calls made during setUp's unmocked init
        mock_read_file.reset_mock()
        mock_write_context.reset_mock()

        # --- Execution --- 
        # Explicitly call load_core_context to test its logic with mocks active
        self.agent.load_core_context() 

        # --- Verification --- 
        # 1. Check that _read_file was attempted for all core files
        expected_read_calls = [
            # call(self.spirit_file_path.name), # Not called again if loaded in init
            call("CHARTER.md"),
            call("MANIFESTO.md"),
            call("LICENSE.md"),
            call("README.md"),
            call("core_spirit.md") # From load_core_context
        ]
        mock_read_file.assert_has_calls(expected_read_calls, any_order=True)

        # 2. Check that write_context was called for fallbacks
        expected_write_calls = [
            # call(self.spirit_file_path.name, self.spirit_file_path.read_text()), # Not written again
            call("MANIFESTO.md", self.core_files_content["MANIFESTO.md"]),
            call("README.md", self.core_files_content["README.md"]),
            call("core_spirit.md", self.core_files_content["core_spirit.md"])
        ]
        mock_write_context.assert_has_calls(expected_write_calls, any_order=True)
        self.assertEqual(mock_write_context.call_count, len(expected_write_calls))

        # 3. Verify the final core_context structure and content
        self.assertIsNotNone(self.agent.core_context)
        self.assertIn("context", self.agent.core_context)
        self.assertIn("metadata", self.agent.core_context)
        content = self.agent.core_context["context"]["content"]
        self.assertIn("## CHARTER.md\n\nCharter from Memory", content)
        self.assertIn(f"## MANIFESTO.md\n\n{self.core_files_content['MANIFESTO.md']}", content)
        self.assertIn("## LICENSE.md\n\nLicense from Memory", content)
        self.assertIn(f"## README.md\n\n{self.core_files_content['README.md']}", content)
        self.assertIn(f"## cogni-core-spirit\n\n{self.core_files_content['core_spirit.md']}", content)
        metadata = self.agent.core_context["metadata"]
        self.assertNotIn("core_docs", metadata)
        self.assertIn("CHARTER.md", metadata)
        self.assertEqual(metadata["CHARTER.md"]["length"], len("Charter from Memory"))
        self.assertIn("MANIFESTO.md", metadata)
        self.assertEqual(metadata["MANIFESTO.md"]["length"], len(self.core_files_content["MANIFESTO.md"]))
        self.assertIn("LICENSE.md", metadata)
        self.assertEqual(metadata["LICENSE.md"]["length"], len("License from Memory"))
        self.assertIn("README.md", metadata)
        self.assertEqual(metadata["README.md"]["length"], len(self.core_files_content["README.md"]))
        self.assertIn("core_spirit", metadata)
        self.assertEqual(metadata["core_spirit"]["length"], len(self.core_files_content["core_spirit.md"]))
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.get_pr_commits')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.get_pr_branches')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.parse_pr_url')
    def test_prepare_input(self, mock_parse, mock_branches, mock_commits):
        """Test prepare_input method with successful PR data retrieval"""
        # Set up mocks
        mock_pr_info = {"owner": "test-owner", "repo": "test-repo", "number": 123, "success": True}
        mock_parse.return_value = mock_pr_info
        
        mock_branch_info = {"source_branch": "feature", "target_branch": "main", "success": True}
        mock_branches.return_value = mock_branch_info
        
        mock_commit_info = {"commits": [{"sha": "abcd1234"}], "success": True}
        mock_commits.return_value = mock_commit_info
        
        # Test the method
        result = self.agent.prepare_input("https://github.com/test-owner/test-repo/pull/123")
        
        # Verify calls
        mock_parse.assert_called_once_with("https://github.com/test-owner/test-repo/pull/123")
        mock_branches.assert_called_once_with(mock_pr_info)
        mock_commits.assert_called_once_with(mock_pr_info)
        
        # Verify result
        self.assertEqual(result["pr_url"], "https://github.com/test-owner/test-repo/pull/123")
        self.assertEqual(result["pr_info"], mock_pr_info)
        self.assertEqual(result["branches"], mock_branch_info)
        self.assertEqual(result["commits"], mock_commit_info)
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.initialize_openai_client')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.review_pr')
    @patch.object(CogniMemoryBank, 'write_context')
    @patch.object(CogniMemoryBank, '_read_file')
    def test_act(self, mock_read_file, mock_write_context, mock_review, mock_init_client):
        """Test act method with PR review flow using CogniMemoryBank"""
        # --- Test Setup ---
        mock_client = MagicMock()
        mock_init_client.return_value = mock_client
        mock_review_results = {
            "verdict": "APPROVE",
            "summary": "Good PR",
            "commit_reviews": [{"sha": "abc123", "feedback": "Looks good"}]
        }
        mock_review.return_value = mock_review_results
        
        # Mock memory reads ONLY for the get_guide_for_task call within act
        # Assume init loaded everything correctly (tested elsewhere)
        def read_side_effect_for_act(*args, **kwargs):
            filename = args[0]
            if filename == "guide_git-cogni.md": 
                return None # Simulate guide NOT in memory for this call
            # Important: Return a default value for other reads that might happen unexpectedly
            # If we didn't mock during setUp, init calls might happen here if not careful
            # return "Loaded from memory unexpectedly" # Or raise an error 
            return None # For now, assume other reads are handled
        mock_read_file.side_effect = read_side_effect_for_act

        # Get expected guide content from dummy file for fallback write check
        expected_guide_content = self.spirit_file_path.read_text()

        # Reset mocks AFTER setUp but BEFORE act is called
        mock_read_file.reset_mock()
        mock_write_context.reset_mock()
        # Re-apply side effect after reset
        mock_read_file.side_effect = read_side_effect_for_act 

        test_input = {
            "pr_url": "https://github.com/test-owner/test-repo/pull/123",
            "pr_info": {"owner": "test-owner", "repo": "test-repo", "number": 123, "success": True},
            "branches": {"success": True, "source_branch": "feat/test", "target_branch": "main"},
            "commits": {"success": True, "commits": [{"sha": "abc123ff"}]},
            "pr_data": {"files": [], "metadata": {"commit_count": 1}}
        }
        
        # --- Execution --- 
        # Use the agent created in setUp
        result = self.agent.act(test_input)
        
        # --- Verification --- 
        mock_init_client.assert_called_once()
        
        # Verify memory calls related to get_guide_for_task within act:
        mock_read_file.assert_called_once_with("guide_git-cogni.md")
        mock_write_context.assert_called_once_with("guide_git-cogni.md", expected_guide_content)
        
        mock_review.assert_called_once()
        
        # Verify structure of the final result
        self.assertEqual(result["pr_url"], test_input["pr_url"])
        self.assertEqual(result["task_description"], "Reviewing PR #123 in test-owner/test-repo")
        self.assertEqual(result["verdict"], "APPROVE")
        self.assertEqual(result["summary"], "Good PR")
        self.assertEqual(result["commit_reviews"], [{"sha": "abc123", "feedback": "Looks good"}])
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.prepare_input')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.act')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.load_core_context')
    def test_review_and_save_success(self, mock_load, mock_act, mock_prepare):
        """Test the review_and_save method with successful flow"""
        # Set up mocks
        mock_load.return_value = None
        
        input_data = {
            "pr_url": "https://github.com/test-owner/test-repo/pull/123",
            "pr_info": {"success": True, "owner": "test-owner", "repo": "test-repo", "number": 123},
            "branches": {"success": True},
            "commits": {
                "success": True,
                "commits": [{"sha": "abcd1234", "message": "Test commit"}]
            },
            "pr_data": {
                "metadata": {
                    "commit_count": 1
                }
            }
        }
        mock_prepare.return_value = input_data
        
        results = {
            "verdict": "APPROVE",
            "summary": "Good PR",
            "timestamp": "2023-01-01T12:00:00",
            "pr_info": {"owner": "test-owner", "repo": "test-repo", "number": 123},
            "final_verdict": "APPROVE",
            "verdict_decision": "APPROVE"
        }
        mock_act.return_value = results
        
        # Call the method
        result = self.agent.review_and_save("https://github.com/test-owner/test-repo/pull/123")
        
        # Verify calls
        mock_load.assert_called_once()
        mock_prepare.assert_called_once_with("https://github.com/test-owner/test-repo/pull/123")
        mock_act.assert_called_once_with(input_data)
        
        # Verify that record_action was called
        self.agent.record_action.assert_called_once()
        
        # Verify result
        # Check against the path returned by the mock in setUp
        expected_path = self.agent_root / "fake_output.md"
        # Compare string representations
        self.assertEqual(result["review_file"], str(expected_path))
        self.assertEqual(result["verdict"], results["verdict"])
        self.assertEqual(result["summary"], results["summary"])
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.prepare_input')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.load_core_context')
    def test_review_and_save_pr_parse_error(self, mock_load, mock_prepare):
        """Test the review_and_save method with PR parsing error"""
        # Set up mock with failed PR info
        input_data = {
            "pr_url": "https://github.com/test-owner/test-repo/pull/123",
            "pr_info": {"success": False, "error": "Invalid URL format"},
            "branches": {},
            "commits": {},
            "pr_data": {}
        }
        mock_prepare.return_value = input_data
        
        # Call the method
        result = self.agent.review_and_save("invalid-url")
        
        # Verify that record_action was called
        self.agent.record_action.assert_called_once()
        
        # Verify error result was returned
        self.assertEqual(result["error"], "Failed to parse PR URL: Invalid URL format")
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.prepare_input')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.load_core_context')
    def test_review_and_save_branch_error(self, mock_load, mock_prepare):
        """Test the review_and_save method with branch retrieval error"""
        # Set up mock with failed branch info
        input_data = {
            "pr_url": "https://github.com/test-owner/test-repo/pull/123",
            "pr_info": {"success": True, "owner": "test-owner", "repo": "test-repo", "number": 123},
            "branches": {"success": False, "error": "API error"},
            "commits": {},
            "pr_data": {}
        }
        mock_prepare.return_value = input_data
        
        # Call the method
        result = self.agent.review_and_save("https://github.com/test-owner/test-repo/pull/123")
        
        # Verify that record_action was called
        self.agent.record_action.assert_called_once()
        
        # Verify error result was returned
        self.assertEqual(result["error"], "Failed to get branch info: API error")
    
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.prepare_input')
    @patch('infra_core.cogni_agents.git_cogni.git_cogni.GitCogniAgent.load_core_context')
    def test_review_and_save_commit_error(self, mock_load, mock_prepare):
        """Test the review_and_save method with commit retrieval error"""
        # Set up mock with failed commit info
        input_data = {
            "pr_url": "https://github.com/test-owner/test-repo/pull/123",
            "pr_info": {"success": True, "owner": "test-owner", "repo": "test-repo", "number": 123},
            "branches": {"success": True},
            "commits": {"success": False, "error": "API error"},
            "pr_data": {}
        }
        mock_prepare.return_value = input_data
        
        # Call the method
        result = self.agent.review_and_save("https://github.com/test-owner/test-repo/pull/123")
        
        # Verify that record_action was called
        self.agent.record_action.assert_called_once()
        
        # Verify error result was returned
        self.assertEqual(result["error"], "Failed to get commit info: API error")
    
    def test_cleanup_files(self):
        """Test file cleanup works correctly"""
        # Set up mock files
        file1 = MagicMock(spec=Path)
        file1.exists.return_value = True
        
        file2 = MagicMock(spec=Path)
        file2.exists.return_value = True
        
        # Add to created files
        self.agent.created_files = [file1, file2]
        
        # Run cleanup
        count = self.agent.cleanup_files()
        
        # Verify files were deleted
        file1.unlink.assert_called_once()
        file2.unlink.assert_called_once()
        
        # Verify count
        self.assertEqual(count, 2)
        self.assertEqual(len(self.agent.created_files), 0)
    
    def test_cleanup_files_with_errors(self):
        """Test file cleanup handles errors gracefully"""
        # Set up mock files
        file1 = MagicMock(spec=Path)
        file1.exists.return_value = True
        file1.unlink.side_effect = Exception("Permission denied")
        
        file2 = MagicMock(spec=Path)
        file2.exists.return_value = True
        
        file3 = MagicMock(spec=Path)
        file3.exists.return_value = False  # File doesn't exist
        
        # Add to created files
        self.agent.created_files = [file1, file2, file3]
        
        # Run cleanup
        count = self.agent.cleanup_files()
        
        # Verify attempted operations
        file1.unlink.assert_called_once()
        file2.unlink.assert_called_once()
        file3.unlink.assert_not_called()  # Should not try to delete non-existent file
        
        # Verify count (only file2 should be counted)
        self.assertEqual(count, 1)
        self.assertEqual(len(self.agent.created_files), 0)


if __name__ == "__main__":
    unittest.main() 