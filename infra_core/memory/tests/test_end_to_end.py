"""
End-to-end tests for the complete Cogni Memory Architecture.
"""

import os
import tempfile
import shutil
import pytest


class TestEndToEnd:
    """Complete end-to-end tests for the memory architecture."""
    
    @pytest.fixture
    def test_environment(self):
        """Set up a complete test environment for end-to-end testing."""
        # Create temporary directories
        test_root = tempfile.mkdtemp()
        logseq_dir = os.path.join(test_root, "logseq")
        output_dir = os.path.join(test_root, "cogni-memory")
        
        os.makedirs(logseq_dir)
        
        try:
            # Create test Logseq files with a mix of tagged and untagged content
            with open(os.path.join(logseq_dir, "journal.md"), "w") as f:
                f.write("- First test thought #thought\n")
                f.write("- This is an important announcement #broadcast #approved\n")
                f.write("- Just a regular block without tags\n")
                f.write("- Another thought to consider #thought\n")
                f.write("- Critical update notification #broadcast\n")
            
            with open(os.path.join(logseq_dir, "notes.md"), "w") as f:
                f.write("- Some notes about the project\n")
                f.write("- Important concept to remember #thought\n")
                f.write("- Announcement for team members #broadcast\n")
            
            yield {
                "root": test_root,
                "logseq_dir": logseq_dir,
                "output_dir": output_dir
            }
        finally:
            shutil.rmtree(test_root)
    
    @pytest.mark.skip(reason="Integration test for when all components are implemented")
    def test_complete_memory_pipeline(self, test_environment):
        """
        Test the complete memory pipeline from parsing to embedding to querying.
        
        This test will be enabled once all components are implemented.
        """
        # This test is already properly skipped with the decorator
        
        # Code to uncomment when all components are implemented:
        # # Step 1: Run the memory indexer
        # memory_indexer_path = os.path.join(os.path.dirname(__file__), "..", "memory_indexer.py")
        # subprocess.run([
        #     "python", memory_indexer_path,
        #     "--logseq-dir", test_environment["logseq_dir"],
        #     "--output-dir", test_environment["output_dir"]
        # ], check=True)
        # 
        # # Step 2: Import all necessary components
        # from infra_core.memory.client import CogniMemoryClient
        # from infra_core.memory.memory_tool import memory_tool
        # 
        # # Step 3: Create client to interact with the memory system
        # client = CogniMemoryClient(
        #     chroma_path=os.path.join(test_environment["output_dir"], "chroma"),
        #     archive_path=os.path.join(test_environment["output_dir"], "archive")
        # )
        # 
        # # Step 4: Query for thought-tagged content
        # thought_results = client.query("thought", n_results=10)
        # 
        # # Verify thought results
        # assert len(thought_results.blocks) >= 3
        # assert all("#thought" in block.tags for block in thought_results.blocks)
        # 
        # # Step 5: Query for broadcast-tagged content
        # broadcast_results = client.query("broadcast", n_results=10)
        # 
        # # Verify broadcast results
        # assert len(broadcast_results.blocks) >= 3
        # assert all("#broadcast" in block.tags for block in broadcast_results.blocks)
        # 
        # # Step 6: Add a new memory block
        # new_block = {
        #     "text": "New memory created during testing #thought",
        #     "tags": ["#thought"],
        #     "source_file": "test_generated.md"
        # }
        # client.save_blocks([new_block])
        # 
        # # Step 7: Verify new block is searchable
        # new_results = client.query("new memory created", n_results=1)
        # assert len(new_results.blocks) == 1
        # assert "New memory created" in new_results.blocks[0].text
        # 
        # # Step 8: Archive some blocks
        # client.archive_blocks([thought_results.blocks[0]])
        # 
        # # Step 9: Verify archive contains the block
        # archive_files = list(Path(os.path.join(test_environment["output_dir"], "archive", "blocks")).glob("*.json"))
        # assert len(archive_files) >= 1
        # 
        # with open(archive_files[0], "r") as f:
        #     archived_data = json.load(f)
        #     assert "#thought" in archived_data["tags"]
        # 
        # # Step 10: Test memory tool integration
        # tool_results = memory_tool(
        #     input_text="important announcement",
        #     n_results=2,
        #     chroma_path=os.path.join(test_environment["output_dir"], "chroma")
        # )
        # 
        # # Verify tool results
        # assert len(tool_results["results"]) > 0
        # assert "announcement" in json.dumps(tool_results["results"]).lower()
    
    def test_verify_test_data(self, test_environment):
        """Verify test data was created correctly."""
        # This test ensures our fixture is working correctly
        journal_path = os.path.join(test_environment["logseq_dir"], "journal.md")
        notes_path = os.path.join(test_environment["logseq_dir"], "notes.md")
        
        assert os.path.exists(journal_path)
        assert os.path.exists(notes_path)
        
        # Count tagged blocks
        thought_count = 0
        broadcast_count = 0
        
        with open(journal_path, "r") as f:
            content = f.read()
            thought_count += content.count("#thought")
            broadcast_count += content.count("#broadcast")
        
        with open(notes_path, "r") as f:
            content = f.read()
            thought_count += content.count("#thought")
            broadcast_count += content.count("#broadcast")
        
        # Verify we have the expected number of tagged blocks
        assert thought_count == 3
        assert broadcast_count == 3 