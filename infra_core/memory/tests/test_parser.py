"""
Tests for the Logseq parser component.
"""

import os
import tempfile
import shutil
import pytest
from pathlib import Path


from infra_core.memory.parser import LogseqParser


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
                
            # Create a journal file
            with open(os.path.join(temp_dir, "2023_04_01.md"), "w") as f:
                f.write("---\ntitle: Journal\n---\n")
                f.write("- Morning #thought about the day\n")
                f.write("- Reference to ((block-123))\n")

            yield temp_dir
        finally:
            shutil.rmtree(temp_dir)

    def test_find_markdown_files(self, test_logseq_dir):
        """Test the parser can find markdown files in the directory."""
        # Verify test data is correct
        md_files = list(Path(test_logseq_dir).glob("*.md"))
        assert len(md_files) == 3
        
        # Use the parser to find markdown files
        parser = LogseqParser(test_logseq_dir)
        md_files = parser.get_markdown_files()
        assert len(md_files) == 3
        assert all(file.endswith(".md") for file in md_files)

    def test_extract_blocks_with_tags(self, test_logseq_dir):
        """Test the parser can extract blocks with specific tags."""
        # Verify test data is correct
        assert os.path.exists(os.path.join(test_logseq_dir, "test1.md"))
        assert os.path.exists(os.path.join(test_logseq_dir, "test2.md"))
        
        # Use the parser to extract blocks
        parser = LogseqParser(test_logseq_dir)
        blocks = parser.extract_all_blocks()
        
        # Should find 5 blocks with tags of interest
        assert len(blocks) == 5
        
        # Verify tags are extracted correctly
        thought_blocks = [b for b in blocks if "#thought" in b["tags"]]
        broadcast_blocks = [b for b in blocks if "#broadcast" in b["tags"]]
        approved_blocks = [b for b in blocks if "#approved" in b["tags"]]
        
        assert len(thought_blocks) == 3
        assert len(broadcast_blocks) == 2
        assert len(approved_blocks) == 1

    def test_block_metadata(self, test_logseq_dir):
        """Test that extracted blocks have correct metadata."""
        parser = LogseqParser(test_logseq_dir)
        blocks = parser.extract_all_blocks()
        
        # Check metadata
        for block in blocks:
            assert block["id"]  # Should have a unique ID
            assert block["source_file"]  # Should have source file
            assert block["tags"]  # Should have tags
            assert block["text"]  # Should have text content
            
        # Test specific metadata from journal file
        journal_blocks = [b for b in blocks if b["source_file"] == "2023_04_01.md"]
        assert len(journal_blocks) > 0
        
        for block in journal_blocks:
            assert block["source_uri"] is not None
            assert "logseq://" in block["source_uri"]
            assert block["metadata"]["file_date"] is not None

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
            
            # Verify test data is correct
            assert os.path.exists(os.path.join(temp_dir, "malformed.md"))
            
            # Test parser with malformed content
            parser = LogseqParser(temp_dir, target_tags={"#tag"})
            blocks = parser.extract_all_blocks()
            
            # Should not crash and should find the valid block with #tag
            assert len(blocks) == 1
            assert "#tag" in blocks[0]["tags"]
        finally:
            shutil.rmtree(temp_dir)
            
    def test_create_memory_blocks(self, test_logseq_dir):
        """Test creation of MemoryBlock objects from parsed data."""
        parser = LogseqParser(test_logseq_dir)
        memory_blocks = parser.create_memory_blocks()
        
        # Should create MemoryBlock objects
        assert len(memory_blocks) == 5
        
        # Check that objects have correct structure
        for block in memory_blocks:
            assert hasattr(block, "id")
            assert hasattr(block, "text")
            assert hasattr(block, "tags")
            assert hasattr(block, "source_file")
            
    def test_block_references(self, test_logseq_dir):
        """Test extraction of block references."""
        parser = LogseqParser(test_logseq_dir, target_tags={"#thought"})
        blocks = parser.extract_all_blocks()
        
        # Find journal block that has reference in its text
        journal_blocks = [b for b in blocks if b["source_file"] == "2023_04_01.md"]
        assert len(journal_blocks) > 0
        
        # Add reference block for testing
        with open(os.path.join(test_logseq_dir, "references.md"), "w") as f:
            f.write("- This is a #thought with a ((block-123)) reference\n")
            
        # Re-parse with modified content
        parser = LogseqParser(test_logseq_dir, target_tags={"#thought"})
        blocks = parser.extract_all_blocks()
        
        # Find block with reference
        ref_blocks = [b for b in blocks if b["references"]]
        assert len(ref_blocks) == 1
        assert "block-123" in ref_blocks[0]["references"] 