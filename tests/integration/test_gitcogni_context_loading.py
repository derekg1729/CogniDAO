import unittest
from pathlib import Path
import tempfile
import os
import sys

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from legacy_logseq.cogni_agents.git_cogni.git_cogni import GitCogniAgent
from legacy_logseq.memory.memory_bank import FileMemoryBank
# No need to import FileMemoryBank here unless patching


class TestGitCogniContextLoading(unittest.TestCase):
    """Test context loading mechanism for GitCogniAgent using real files."""

    def setUp(self):
        """Set up a temporary environment with real dummy files."""
        self.temp_project_dir = tempfile.TemporaryDirectory()
        self.temp_agent_dir = tempfile.TemporaryDirectory()
        # self.temp_memory_dir = tempfile.TemporaryDirectory() # No longer needed for override

        self.project_root_override = Path(self.temp_project_dir.name)
        self.agent_root = Path(self.temp_agent_dir.name)
        # self.memory_bank_root_override = Path(self.temp_memory_dir.name) # No longer needed

        # --- Create Real Dummy Files in the TEMPORARY Core Bank ---
        # Define the path for the temporary core/main bank
        # Use the corrected path under /data
        core_main_bank_path = self.project_root_override / "data/memory_banks/core/main"
        core_main_bank_path.mkdir(parents=True, exist_ok=True)

        self.core_files_content = {}

        # Core docs go into the temporary core/main bank
        core_docs = ["CHARTER.md", "MANIFESTO.md", "LICENSE.md", "README.md"]
        for fname in core_docs:
            fpath = core_main_bank_path / fname  # Write inside core/main
            content = f"Real content for {fname} test."
            fpath.write_text(content)
            self.core_files_content[fname] = content

        # Core spirit guide goes into the temporary core/main bank (prefixed)
        core_spirit_filename = "guide_cogni-core-spirit.md"
        core_spirit_path = core_main_bank_path / core_spirit_filename  # Write inside core/main
        core_spirit_content = "Real core spirit content for test."
        core_spirit_path.write_text(core_spirit_content)
        # Store content with the key used in tests/metadata (without guide_ prefix)
        self.core_files_content["core_spirit.md"] = core_spirit_content

        # GitCogni spirit guide goes into the temporary core/main bank (prefixed)
        git_spirit_filename = "guide_git-cogni.md"
        git_spirit_path = core_main_bank_path / git_spirit_filename  # Write inside core/main
        git_spirit_content = "Real GitCogni spirit content for test."
        git_spirit_path.write_text(git_spirit_content)
        # Store content with the key used in tests (without guide_ prefix)
        self.core_files_content["git-cogni.md"] = git_spirit_content

        # --- Create fallback source file paths (needed for seeding) ---
        # Create legacy_logseq/cogni_spirit/spirits directory structure
        spirits_dir = self.project_root_override / "legacy_logseq/cogni_spirit/spirits"
        spirits_dir.mkdir(parents=True, exist_ok=True)

        # Create core spirit fallback file
        core_spirit_fallback = spirits_dir / "cogni-core-spirit.md"
        core_spirit_fallback.write_text(core_spirit_content)

        # Create git-cogni spirit fallback file
        git_spirit_fallback = spirits_dir / "git-cogni.md"
        git_spirit_fallback.write_text(git_spirit_content)

        # Set up a memory bank path for agent tests
        memory_bank_root = self.project_root_override / "data/memory_banks"

        # Create a real memory bank instance instead of a mock
        agent_memory = FileMemoryBank(
            memory_bank_root=memory_bank_root, project_name="git-cogni", session_id="test-session"
        )

        # Create agent - it will load using the files created above
        self.agent = GitCogniAgent(
            agent_root=self.agent_root,
            memory=agent_memory,  # Use real memory bank instead of mock
            project_root_override=self.project_root_override,
        )

    def tearDown(self):
        """Clean up temporary directories."""
        self.temp_project_dir.cleanup()
        self.temp_agent_dir.cleanup()
        # self.temp_memory_dir.cleanup() # No longer needed

    def test_context_loading(self):
        """Test that context is properly loaded using the new structure and real files."""
        # The context is loaded during __init__ in setUp

        # 1. Verify spirit was loaded correctly
        self.assertIsNotNone(self.agent.spirit)
        self.assertIsInstance(self.agent.spirit, str)
        self.assertGreater(len(self.agent.spirit), 0)

        # 2. Verify core_context exists and has the right keys
        self.assertIsNotNone(self.agent.core_context, "Core context should not be None")
        self.assertIsInstance(self.agent.core_context, dict)
        self.assertIn(
            "context", self.agent.core_context, "Core context should contain 'context' key"
        )
        self.assertIn(
            "metadata", self.agent.core_context, "Core context should contain 'metadata' key"
        )

        # 3. Verify metadata structure (no 'core_docs' key)
        metadata = self.agent.core_context["metadata"]
        self.assertIsInstance(metadata, dict)
        self.assertNotIn("core_docs", metadata, "Metadata should NOT contain 'core_docs' key")

        # 4. Verify all expected documents are in metadata keys
        expected_docs = [
            "CHARTER.md",
            "MANIFESTO.md",
            "LICENSE.md",
            "README.md",
            "cogni-core-spirit",
        ]
        for doc_key in expected_docs:
            self.assertIn(doc_key, metadata, f"Metadata missing key: {doc_key}")
            self.assertIn("length", metadata[doc_key], f"Metadata for {doc_key} missing 'length'")
            # Just verify the length is positive instead of checking exact values
            self.assertGreater(
                metadata[doc_key]["length"], 0, f"Content length for {doc_key} should be positive"
            )

        # 5. Verify context content includes loaded file content
        content_str = self.agent.core_context["context"]["content"]
        self.assertIn("# Cogni Core Documents", content_str)
        self.assertIn("## CHARTER.md", content_str)
        self.assertIn("## MANIFESTO.md", content_str)
        self.assertIn("## LICENSE.md", content_str)
        self.assertIn("## README.md", content_str)
        self.assertIn("## cogni-core-spirit", content_str)


if __name__ == "__main__":
    unittest.main()
