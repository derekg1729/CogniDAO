import sys
import os
import unittest
from typing import Dict, List, Optional, Union

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from infra_core.cogni_spirit.context import SpiritContext, get_core_context, get_guide_for_task


class TestSpiritContext(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment with a real SpiritContext instance."""
        # Use the correct "spirits" directory instead of the default "guides"
        module_dir = os.path.dirname(os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                                                 'infra_core', 'cogni_spirit', 'context.py')))
        spirits_dir = os.path.join(module_dir, "spirits")
        self.spirit_context = SpiritContext(guides_dir=spirits_dir)
    
    def test_get_core_context_returns_guides(self):
        """Test that get_core_context returns a properly structured context object."""
        # Call the function
        result = get_core_context(self.spirit_context, provider="openai")
        
        # Verify the result is a dictionary with the expected structure for OpenAI
        self.assertIsInstance(result, dict)
        self.assertIn("context", result)
        self.assertIn("metadata", result)
        
        # Check the context structure
        context = result["context"]
        self.assertIn("role", context)
        self.assertEqual(context["role"], "system")
        self.assertIn("content", context)
        
        # Verify the content includes important core documents
        content = context["content"]
        print(content)
        self.assertIn("# Cogni Core Documents", content)
        self.assertIn("## CHARTER", content)
        self.assertIn("## MANIFESTO", content)
        self.assertIn("## LICENSE", content)
        self.assertIn("## README", content)
        

    
    def test_get_guide_for_task_returns_spirit_guide(self):
        """Test that get_guide_for_task returns the specified guide content."""
        # Get the git-cogni guide for a task
        task_description = "Reviewing a pull request"
        result = get_guide_for_task(
            self.spirit_context,
            task=task_description,
            guides=["git-cogni"],
            provider="openai"
        )
        
        # Verify the result is a dictionary with the expected structure for OpenAI
        self.assertIsInstance(result, dict)
        self.assertIn("role", result)
        self.assertEqual(result["role"], "system")
        self.assertIn("content", result)
        
        # Verify the content includes the git-cogni guide content
        content = result["content"]
        self.assertIn(f"# Cogni Spirit Context for: {task_description}", content)
        self.assertIn("## git-cogni", content)
        
        # Verify specific content from the actual git-cogni.md file
        self.assertIn("You are `git-cogni`", content)
        self.assertIn("Core Directives", content)
        self.assertIn("Simplicity is Sacred", content)
        self.assertIn("Untested Code is Untrusted Code", content)
        
        # Test with Anthropic provider
        anthropic_result = get_guide_for_task(
            self.spirit_context,
            task=task_description,
            guides=["git-cogni"],
            provider="anthropic"
        )
        self.assertIsInstance(anthropic_result, str)
        self.assertTrue(anthropic_result.startswith("<context>"))
        self.assertTrue(anthropic_result.endswith("</context>"))
        self.assertIn("git-cogni", anthropic_result)
    
    def test_get_guide_default_guides(self):
        """Test that get_guide_for_task uses default guides when none specified."""
        # Call with no guides specified - should use defaults
        result = get_guide_for_task(
            self.spirit_context,
            task="Default guides test",
            provider="openai"
        )
        
        # Verify content includes default guides
        content = result["content"]
        self.assertIn("# Cogni Spirit Context for: Default guides test", content)
        self.assertIn("## cogni-core-spirit", content)
        self.assertIn("## cogni-core-valuing", content)
        
        # Look for actual content from the real cogni-core-spirit.md file
        self.assertIn("Cogni Core Spirit", content)


if __name__ == "__main__":
    unittest.main()
