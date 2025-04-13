"""
Tests for the Logseq parser component.
"""

import os
import tempfile
import shutil
import pytest
from pathlib import Path
from datetime import datetime


from infra_core.memory.parser import LogseqParser


class TestLogseqParser:
    """Test suite for LogseqParser."""
    
    @pytest.fixture
    def create_test_file(self):
        """Fixture to create a test file with specified content."""
        def _create_file(path, filename, content):
            """Inner function to create a file."""
            file_path = path / filename
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return str(file_path)
        return _create_file

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
        
        # Use the parser to extract blocks with specific tags
        parser = LogseqParser(test_logseq_dir, target_tags={"#thought", "#broadcast", "#approved"})
        blocks = parser.extract_all_blocks()
        
        # Should find 5 blocks with tags of interest
        assert len(blocks) == 5
        
        # Verify the blocks have the expected tags
        for block in blocks:
            assert block["tags"], f"Block should have tags: {block}"
            assert any(tag in ["#thought", "#broadcast", "#approved"] for tag in block["tags"])

    def test_block_metadata(self, test_logseq_dir):
        """Test that extracted blocks have correct metadata."""
        parser = LogseqParser(test_logseq_dir, target_tags={"#thought", "#broadcast", "#approved"})
        blocks = parser.extract_all_blocks()
        
        # Check metadata
        for block in blocks:
            assert block["id"]  # Should have a unique ID
            assert block["source_file"]  # Should have source file
            assert block["tags"]  # Should have tags
            
        # Test specific metadata from journal file
        journal_blocks = [b for b in blocks if b["source_file"] == "2023_04_01.md"]
        assert len(journal_blocks) > 0
        
        for block in journal_blocks:
            assert block["source_uri"] is not None
            assert "logseq://" in block["source_uri"]
            assert block["metadata"]["file_date"] is not None

    def test_malformed_markdown(self, create_test_file, tmp_path):
        """Test parser handles malformed markdown without crashing."""
        # Prepare a test file with malformed markdown
        test_file = create_test_file(tmp_path, "malformed.md", """
        - Incomplete #tag
        * Missing bracket [ 
        - Extra close ))
        - Unmatched `backtick
        """)
        
        # Parse the file
        parser = LogseqParser(str(tmp_path))
        blocks = parser.extract_blocks_from_file(test_file)
        
        # Should extract 4 blocks despite the malformed content
        assert len(blocks) == 4

    def test_standard_markdown_extraction(self, create_test_file, tmp_path):
        """Test parser can extract content from standard markdown with headers and paragraphs."""
        # Create a test file with standard markdown (no bullet points)
        test_file = create_test_file(tmp_path, "standard_markdown.md", """
        # Main Header
        
        This is a paragraph with some #important content.
        It spans multiple lines but should be treated as one block.
        
        ## Subheader
        
        Another paragraph with different content.
        This should be a separate block from the first paragraph.
        
        # Second Main Header #section
        
        Final paragraph with #tags and content.
        """)
        
        # Parse the file with no tag filtering
        parser = LogseqParser(str(tmp_path))
        blocks = parser.extract_blocks_from_file(test_file)
        
        # Should extract at least 6 blocks: 3 headers and 3 paragraphs
        assert len(blocks) >= 6
        
        # Print blocks for debugging
        print("\nExtracted blocks:")
        for i, block in enumerate(blocks):
            print(f"  {i+1}. '{block['text'][:50]}...'")
        
        # Check for header blocks
        header_blocks = [b for b in blocks if "Main Header" in b["text"] or "Subheader" in b["text"] or "Second Main Header" in b["text"]]
        assert len(header_blocks) >= 3
        
        # Check for paragraph blocks by content
        paragraph_blocks = [b for b in blocks if "#important" in b["text"] or "different content" in b["text"] or "#tags" in b["text"]]
        assert len(paragraph_blocks) >= 3
        
        # Verify tag extraction still works
        tagged_blocks = [b for b in blocks if b["tags"] and "#important" in b["tags"]]
        assert len(tagged_blocks) > 0

    def test_mixed_content_extraction(self, create_test_file, tmp_path):
        """Test parser handles mixed content: headers, paragraphs, and bullet points."""
        # Create a test file with mixed markdown
        test_file = create_test_file(tmp_path, "mixed_content.md", """
        # Mixed Content
        
        Regular paragraph #test.
        
        - Bullet point 1 #bullet
        - Bullet point 2
        
        ## Subheader
        
        Another paragraph.
        
        * Star bullet point #star
        """)
        
        # Parse the file
        parser = LogseqParser(str(tmp_path))
        blocks = parser.extract_blocks_from_file(test_file)
        
        # Should extract blocks for: 2 headers, 2 paragraphs, 3 bullet points
        assert len(blocks) >= 7
        
        # Check for bullet points
        bullet_blocks = [b for b in blocks if "#bullet" in b.get("text", "")]
        assert len(bullet_blocks) > 0
        
        # Check for paragraphs
        paragraph_blocks = [b for b in blocks if "#test" in b.get("text", "")]
        assert len(paragraph_blocks) > 0
        
        # Check for star bullets
        star_blocks = [b for b in blocks if "#star" in b.get("text", "")]
        assert len(star_blocks) > 0

    def test_create_memory_blocks(self, test_logseq_dir):
        """Test creation of MemoryBlock objects from parsed data."""
        parser = LogseqParser(test_logseq_dir, target_tags={"#thought", "#broadcast", "#approved"})
        memory_blocks = parser.create_memory_blocks()
        
        # Should create MemoryBlock objects
        assert len(memory_blocks) == 5
        
        # Each memory block should have correct attributes
        for block in memory_blocks:
            assert isinstance(block.id, str)
            assert isinstance(block.text, str)
            assert isinstance(block.tags, list) and block.tags
            assert isinstance(block.source_file, str)
            assert isinstance(block.created_at, datetime)
            assert block.embedding is None  # No embeddings yet

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

    def test_parse_without_conversion_to_logseq(self, create_test_file, tmp_path):
        """Test parser can extract content from standard markdown without requiring conversion to Logseq format."""
        # Create a standard markdown file (no bullet points)
        test_file = create_test_file(tmp_path, "standard_doc.md", """
        # Cogni Documentation
        
        This is regular paragraph content in standard markdown format.
        It has multiple lines and should be parsed as one block.
        
        ## Features
        
        Here's a list of features:
        
        # Implementation
        
        The implementation includes multiple components.
        This paragraph discusses the details.
        """)
        
        # Calculate content statistics
        with open(test_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            total_lines = len(lines)
            bullet_lines = sum(1 for line in lines if line.strip().startswith('-') or line.strip().startswith('*'))
            non_bullet_lines = total_lines - bullet_lines - sum(1 for line in lines if not line.strip())
        
        # Parse the file with no tag filtering
        parser = LogseqParser(str(tmp_path))
        blocks = parser.extract_blocks_from_file(test_file)
        
        # Should have extracted blocks despite no bullet points
        assert len(blocks) > 0
        
        # Calculate what percentage of non-empty content was captured
        percentage_captured = (len(blocks) / max(1, non_bullet_lines)) * 100
        
        # Print stats for clarity
        print("\nStandard markdown parsing stats:")
        print(f"Total lines: {total_lines}")
        print(f"Bullet point lines: {bullet_lines}")
        print(f"Non-bullet content lines: {non_bullet_lines}")
        print(f"Blocks extracted: {len(blocks)}")
        print("Blocks content:")
        for i, block in enumerate(blocks):
            print(f"  {i+1}. '{block['text'][:50]}...'")
        print(f"Percentage of content captured: {percentage_captured:.1f}%")
        
        # Verify we captured a significant portion of the content
        # The original issue mentioned only 7% was captured (93% was lost)
        assert percentage_captured > 50, "Should capture more than 50% of content"
        
        # Check that we got both headers and paragraphs - find paragraphs by content
        header_blocks = [b for b in blocks if "Cogni Documentation" in b["text"] or "Features" in b["text"] or "Implementation" in b["text"]]
        paragraph_blocks = [b for b in blocks if "regular paragraph" in b["text"] or "list of features" in b["text"] or "multiple components" in b["text"]]
        
        assert len(header_blocks) >= 3, "Should capture all headers"
        assert len(paragraph_blocks) >= 2, "Should capture all paragraphs" 