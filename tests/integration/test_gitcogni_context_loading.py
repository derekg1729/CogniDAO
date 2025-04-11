import sys
import os
import unittest
from pathlib import Path

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from infra_core.cogni_agents.git_cogni.git_cogni import GitCogniAgent


class TestGitCogniContextLoading(unittest.TestCase):
    """Integration test for GitCogni context loading functionality"""
    
    def setUp(self):
        """Set up test environment"""
        # Create a real agent instance with test logger
        self.agent = GitCogniAgent(
            agent_root=Path("infra_core/cogni_agents/git_cogni")
        )
        # Configure the logger to capture output
        self.log_messages = []
        self.agent.logger.handlers = []
        
        # Add a handler that captures log messages
        import logging
        class TestLogHandler(logging.Handler):
            def __init__(self, message_list):
                super().__init__()
                self.message_list = message_list
                
            def emit(self, record):
                self.message_list.append(self.format(record))
        
        handler = TestLogHandler(self.log_messages)
        formatter = logging.Formatter('%(levelname)-8s | %(message)s')
        handler.setFormatter(formatter)
        self.agent.logger.addHandler(handler)
        self.agent.logger.setLevel(logging.INFO)
        
    def test_context_loading(self):
        """Test that context is properly loaded with at least 5 documents"""
        # Load context documents - this should load real files
        self.agent.load_core_context()
        
        # Verify core_context exists
        self.assertIsNotNone(self.agent.core_context, "Core context should not be None")
        
        # Verify metadata exists
        self.assertIn('metadata', self.agent.core_context, "Core context should contain metadata")
        
        # Verify core_docs exists in metadata
        metadata = self.agent.core_context['metadata']
        self.assertIn('core_docs', metadata, "Metadata should contain core_docs")
        
        # Count the number of documents
        core_doc_count = len(metadata.get('core_docs', {}))
        core_spirit_count = 1 if 'core_spirit' in metadata else 0
        total_doc_count = core_doc_count + core_spirit_count
        
        # This is our key assertion - verify at least 5 documents are loaded
        self.assertGreaterEqual(
            total_doc_count, 5, 
            f"Expected at least 5 documents, but only {total_doc_count} were loaded"
        )
        
        # Print which documents were found, for diagnostic purposes
        for doc_name, doc_info in metadata.get('core_docs', {}).items():
            if doc_info.get('length', 0) > 0:
                print(f"Loaded document: {doc_name} ({doc_info.get('length', 0)} chars)")
            else:
                print(f"Failed to load document: {doc_name}")
        
        if 'core_spirit' in metadata:
            print(f"Loaded core_spirit ({metadata['core_spirit'].get('length', 0)} chars)")
        else:
            print("Failed to load core_spirit")


if __name__ == "__main__":
    unittest.main() 