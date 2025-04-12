"""
Tests for the Logseq parser component.
"""

import os
import tempfile
import shutil
import pytest
from pathlib import Path


# Placeholder for actual imports once modules are created
# from infra_core.memory.parser import LogseqParser


class TestLogseqParser:
    """Tests for the LogseqParser class."""

    @pytest.fixture
    def test_logseq_dir(self):
        """Create a temporary directory with test Logseq markdown files."""
        temp_dir = tempfile.mkdtemp()
        try:
            # Create test files
            with open(os.path.join(temp_dir, "test1.md"), "w") as f:
                f.write("- Test block with #thought tag\n")
                f.write("- Regular block without tags\n")
                f.write("- Another #thought with some context\n")

            with open(os.path.join(temp_dir, "test2.md"), "w") as f:
                f.write("- Test block with #broadcast tag\n")
                f.write("- Test block with #broadcast and #approved tags\n")

            yield temp_dir
        finally:
            shutil.rmtree(temp_dir)

    def test_find_markdown_files(self, test_logseq_dir):
        """Test the parser can find markdown files in the directory."""
        # Verify test data is correct before skipping
        md_files = list(Path(test_logseq_dir).glob("*.md"))
        assert len(md_files) == 2
        
        # Skip the actual test until parser is implemented
        pytest.skip("Parser not yet implemented")
        
        # Code to uncomment when parser is implemented:
        # parser = LogseqParser(test_logseq_dir)
        # md_files = parser.get_markdown_files()
        # assert len(md_files) == 2
        # assert all(file.endswith(".md") for file in md_files)

    def test_extract_blocks_with_tags(self, test_logseq_dir):
        """Test the parser can extract blocks with specific tags."""
        # Verify test data is correct before skipping
        assert os.path.exists(os.path.join(test_logseq_dir, "test1.md"))
        assert os.path.exists(os.path.join(test_logseq_dir, "test2.md"))
        
        # Skip the actual test until parser is implemented
        pytest.skip("Parser not yet implemented")
        
        # Code to uncomment when parser is implemented:
        # parser = LogseqParser(test_logseq_dir)
        # blocks = parser.extract_all_blocks()
        # 
        # # Should find 3 blocks with tags of interest
        # assert len(blocks) == 3
        # 
        # # Verify tags are extracted correctly
        # thought_blocks = [b for b in blocks if "#thought" in b.tags]
        # broadcast_blocks = [b for b in blocks if "#broadcast" in b.tags]
        # approved_blocks = [b for b in blocks if "#approved" in b.tags]
        # 
        # assert len(thought_blocks) == 2
        # assert len(broadcast_blocks) == 2
        # assert len(approved_blocks) == 1

    def test_block_metadata(self, test_logseq_dir):
        """Test that extracted blocks have correct metadata."""
        # Skip test until parser is implemented
        pytest.skip("Parser not yet implemented")
        
        # Code to uncomment when parser is implemented:
        # parser = LogseqParser(test_logseq_dir)
        # blocks = parser.extract_all_blocks()
        # 
        # # Check metadata
        # for block in blocks:
        #     assert block.id  # Should have a unique ID
        #     assert block.source_file  # Should have source file
        #     assert block.tags  # Should have tags
        #     assert block.text  # Should have text content

    def test_malformed_markdown(self):
        """Test the parser handles malformed markdown gracefully."""
        # Create a temp dir with malformed markdown
        temp_dir = tempfile.mkdtemp()
        try:
            # Create malformed test file
            with open(os.path.join(temp_dir, "malformed.md"), "w") as f:
                f.write("Not a valid block format\n")
                f.write("- Incomplete block with #tag but no closing\n")
                f.write("Random text\n")
            
            # Verify test data is correct before skipping
            assert os.path.exists(os.path.join(temp_dir, "malformed.md"))
            
            # Skip the actual test until parser is implemented
            pytest.skip("Parser not yet implemented")
            
            # Code to uncomment when parser is implemented:
            # parser = LogseqParser(temp_dir)
            # blocks = parser.extract_all_blocks()
            # 
            # # Should not crash and should find the valid block
            # assert len(blocks) <= 1  # At most one block might be valid
        finally:
            shutil.rmtree(temp_dir) 