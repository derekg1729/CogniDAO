import unittest
from pathlib import Path
import tempfile
import os
import sys

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from infra_core.cogni_agents.git_cogni.git_cogni import GitCogniAgent
# No need to import CogniMemoryBank here unless patching


class TestGitCogniContextLoading(unittest.TestCase):
    """Test context loading mechanism for GitCogniAgent using real files."""

    def setUp(self):
        """Set up a temporary environment with real dummy files."""
        self.temp_project_dir = tempfile.TemporaryDirectory()
        self.temp_agent_dir = tempfile.TemporaryDirectory()
        self.temp_memory_dir = tempfile.TemporaryDirectory()

        self.project_root_override = Path(self.temp_project_dir.name)
        self.agent_root = Path(self.temp_agent_dir.name)
        self.memory_bank_root_override = Path(self.temp_memory_dir.name)

        # --- Create Real Dummy Files --- 
        # Core docs at the project root override level
        self.core_files_content = {}
        core_docs = ["CHARTER.md", "MANIFESTO.md", "LICENSE.md", "README.md"]
        for fname in core_docs:
            fpath = self.project_root_override / fname
            content = f"Real content for {fname} test."
            fpath.write_text(content)
            self.core_files_content[fname] = content
        
        # Core spirit guide
        core_spirit_rel_path = Path("infra_core/cogni_spirit/spirits/cogni-core-spirit.md")
        core_spirit_dir = self.project_root_override / core_spirit_rel_path.parent
        core_spirit_dir.mkdir(parents=True, exist_ok=True)
        core_spirit_path = core_spirit_dir / core_spirit_rel_path.name
        core_spirit_content = "Real core spirit content for test."
        core_spirit_path.write_text(core_spirit_content)
        self.core_files_content["core_spirit.md"] = core_spirit_content # Memory filename

        # GitCogni spirit guide
        git_spirit_rel_path = Path("infra_core/cogni_spirit/spirits/git-cogni.md")
        git_spirit_dir = self.project_root_override / git_spirit_rel_path.parent
        git_spirit_dir.mkdir(parents=True, exist_ok=True) # Ensure dir exists
        git_spirit_path = git_spirit_dir / git_spirit_rel_path.name
        git_spirit_content = "Real GitCogni spirit content for test."
        git_spirit_path.write_text(git_spirit_content)
        self.core_files_content["git-cogni.md"] = git_spirit_content # Memory filename
        
        # Create agent - it will load using the files created above
        self.agent = GitCogniAgent(
            agent_root=self.agent_root,
            memory_bank_root_override=self.memory_bank_root_override,
            project_root_override=self.project_root_override 
        )

    def tearDown(self):
        """Clean up temporary directories."""
        self.temp_project_dir.cleanup()
        self.temp_agent_dir.cleanup()
        self.temp_memory_dir.cleanup()

    def test_context_loading(self):
        """Test that context is properly loaded using the new structure and real files."""
        # The context is loaded during __init__ in setUp
        
        # 1. Verify spirit was loaded correctly
        self.assertEqual(self.agent.spirit, self.core_files_content["git-cogni.md"])
        
        # 2. Verify core_context exists and has the right keys
        self.assertIsNotNone(self.agent.core_context, "Core context should not be None")
        self.assertIsInstance(self.agent.core_context, dict)
        self.assertIn('context', self.agent.core_context, "Core context should contain 'context' key")
        self.assertIn('metadata', self.agent.core_context, "Core context should contain 'metadata' key")
        
        # 3. Verify metadata structure (no 'core_docs' key)
        metadata = self.agent.core_context['metadata']
        self.assertIsInstance(metadata, dict)
        self.assertNotIn('core_docs', metadata, "Metadata should NOT contain 'core_docs' key")

        # 4. Verify all expected documents are in metadata keys
        expected_docs = ["CHARTER.md", "MANIFESTO.md", "LICENSE.md", "README.md", "core_spirit"]
        for doc_key in expected_docs:
            self.assertIn(doc_key, metadata, f"Metadata missing key: {doc_key}")
            self.assertIn("length", metadata[doc_key], f"Metadata for {doc_key} missing 'length'")
            # Check length matches content created in setUp
            if doc_key == "core_spirit":
                 self.assertEqual(metadata[doc_key]["length"], len(self.core_files_content["core_spirit.md"]))
            else:
                 self.assertEqual(metadata[doc_key]["length"], len(self.core_files_content[doc_key]))

        # 5. Verify context content includes loaded file content
        content_str = self.agent.core_context['context']['content']
        self.assertIn("# Cogni Core Documents", content_str)
        self.assertIn("## CHARTER.md\n\nReal content for CHARTER.md test.", content_str)
        self.assertIn("## MANIFESTO.md\n\nReal content for MANIFESTO.md test.", content_str)
        self.assertIn("## LICENSE.md\n\nReal content for LICENSE.md test.", content_str)
        self.assertIn("## README.md\n\nReal content for README.md test.", content_str)
        self.assertIn("## cogni-core-spirit\n\nReal core spirit content for test.", content_str)


if __name__ == '__main__':
    unittest.main() 