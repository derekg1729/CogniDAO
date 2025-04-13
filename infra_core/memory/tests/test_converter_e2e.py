"""
E2E test to demonstrate converting files to Logseq format and processing them.

This test:
1. Creates a temporary markdown file with test content
2. Converts it to Logseq format using our converter
3. Indexes the converted file with CogniMemoryClient
4. Verifies all blocks are properly indexed and can be queried
"""

import os
import pytest
import tempfile

from infra_core.memory.memory_client import CogniMemoryClient


class TestConverterE2E:
    """E2E test for converting files to Logseq format and processing them."""
    
    @pytest.fixture
    def test_dirs(self):
        """Create temporary test directories for storage."""
        with tempfile.TemporaryDirectory() as chroma_dir, tempfile.TemporaryDirectory() as archive_dir:
            yield {
                "chroma": chroma_dir,
                "archive": archive_dir
            }
    
    def test_convert_and_index(self, test_dirs):
        """
        Test converting a file to Logseq format and indexing all blocks.
        
        This demonstrates how to:
        1. Create a test file with markdown content
        2. Convert it to Logseq format
        3. Index all blocks without tag filtering
        4. Query the indexed content
        """
        # Setup client
        client = CogniMemoryClient(
            chroma_path=test_dirs["chroma"],
            archive_path=test_dirs["archive"]
        )
        
        print("\n=== 🧪 TEST: CONVERT AND INDEX ===")
        
        # Create temporary directory for test files
        with tempfile.TemporaryDirectory() as test_dir:
            # Create test markdown file with Logseq format directly
            # Note: Each line starts with "- " and includes proper spacing
            # Also each line has unique content to prevent duplicate IDs
            test_content = """- # Test Document Title
- ## Section 1 Header
- This is the first paragraph with some content about section 1.
- More details about section 1 concepts.
- ## Section 2 Header
- This is the second paragraph with information about section 2.
- Additional information for section 2 context.
- ### Subsection 2.1 Header
- This is a detailed subsection with specific technical details.
- ## Section 3 Header
- This is the third section with summary content.
- Final thoughts on the document contents.
"""
            
            # Write test content to file
            test_path = os.path.join(test_dir, "logseq_test_doc.md")
            with open(test_path, "w") as f:
                f.write(test_content)
            
            print(f"Created test Logseq-formatted file at: {test_path}")
            
            # Count bullet points in file
            with open(test_path, "r") as f:
                lines = f.readlines()
                bullet_count = sum(1 for line in lines if line.strip().startswith("-"))
            
            print(f"File has {bullet_count} bullet points")
            
            # Index the file without tag filtering
            print("\n=== 📝 INDEXING FILE WITHOUT TAG FILTERING ===")
            
            num_indexed = client.index_from_logseq(
                logseq_dir=test_dir,
                tag_filter=None,  # None is converted to empty set for "include all blocks"
                verbose=True
            )
            
            print(f"Indexed {num_indexed} blocks from file")
            
            # Assert all bullet points were indexed (excluding empty lines)
            non_empty_bullets = sum(1 for line in lines if line.strip().startswith("-") and len(line.strip()) > 2)
            print(f"File has {non_empty_bullets} non-empty bullet points")
            
            assert num_indexed > 0, "Failed to index any blocks"
            assert num_indexed == non_empty_bullets, f"Expected {non_empty_bullets} blocks, got {num_indexed}"
            
            # Query the indexed content
            print("\n=== 🔍 QUERYING INDEXED CONTENT ===")
            query = "what is in the document?"
            results = client.query(query, n_results=5)
            
            # Validate results
            assert results.blocks, "No results returned for query"
            print(f"Received {len(results.blocks)} results")
            
            # Print results
            for i, block in enumerate(results.blocks):
                print(f"Result {i+1}: {block.text}")
            
            print("\n=== ✅ TEST COMPLETED SUCCESSFULLY ===")
            
    def test_convert_and_filter(self, test_dirs):
        """
        Test converting a file to Logseq format and filtering by tags.
        
        This demonstrates:
        1. Using different tags in the same file
        2. Filtering blocks by specific tags during indexing
        3. Verifying only blocks with those tags are indexed
        """
        # Setup client
        client = CogniMemoryClient(
            chroma_path=test_dirs["chroma"],
            archive_path=test_dirs["archive"]
        )
        
        print("\n=== 🧪 TEST: CONVERT AND FILTER ===")
        
        # Create temporary directory for test files
        with tempfile.TemporaryDirectory() as test_dir:
            # Create test markdown file with section markers for different tags
            original_path = os.path.join(test_dir, "multi_tag_doc.md")
            with open(original_path, "w") as f:
                f.write("""# Multi-tag Test Document

## Section 1 (Important)
This is important content for the project.
This is another important line.

## Section 2 (Reference)
This is reference material.
More reference content here.

## Section 3 (Important)
This is more important content.

## Section 4 (Note)
This is just a note.
Another note line here.
""")
            
            # Convert to Logseq format with custom tag mapping
            logseq_path = os.path.join(test_dir, "multi_tag_doc_logseq.md")
            
            # Read original content
            with open(original_path, "r") as f:
                content = f.read()
            
            # Convert to Logseq format with different tags
            lines = content.split('\n')
            converted_lines = []
            
            for line in lines:
                if not line.strip():
                    converted_lines.append(line)
                    continue
                
                if "Important" in line:
                    converted_lines.append(f"- {line.strip()} #important")
                elif "Reference" in line:
                    converted_lines.append(f"- {line.strip()} #reference")
                elif "Note" in line:
                    converted_lines.append(f"- {line.strip()} #note")
                else:
                    # Tag based on the previous section
                    if any("Important" in line_text for line_text in converted_lines[-5:] if line_text.strip()):
                        converted_lines.append(f"- {line.strip()} #important")
                    elif any("Reference" in line_text for line_text in converted_lines[-5:] if line_text.strip()):
                        converted_lines.append(f"- {line.strip()} #reference")
                    elif any("Note" in line_text for line_text in converted_lines[-5:] if line_text.strip()):
                        converted_lines.append(f"- {line.strip()} #note")
                    else:
                        converted_lines.append(f"- {line.strip()}")
            
            # Write converted content to file
            with open(logseq_path, "w") as f:
                f.write('\n'.join(converted_lines))
            
            print(f"Created multi-tag test file at: {logseq_path}")
            
            # Count blocks by tag
            with open(logseq_path, "r") as f:
                lines = f.readlines()
                important_blocks = sum(1 for line in lines if "#important" in line)
                reference_blocks = sum(1 for line in lines if "#reference" in line)
                note_blocks = sum(1 for line in lines if "#note" in line)
            
            print(f"File contains: {important_blocks} important blocks, {reference_blocks} reference blocks, {note_blocks} note blocks")
            
            # Index only important blocks
            print("\n=== 📝 INDEXING ONLY IMPORTANT BLOCKS ===")
            logseq_dir = os.path.dirname(logseq_path)
            
            num_indexed = client.index_from_logseq(
                logseq_dir=logseq_dir,
                tag_filter="#important",
                verbose=True
            )
            
            print(f"Indexed {num_indexed} important blocks")
            
            # Assert correct number of blocks indexed
            assert num_indexed == important_blocks, f"Expected {important_blocks} important blocks, got {num_indexed}"
            
            # Query the indexed content
            print("\n=== 🔍 QUERYING IMPORTANT CONTENT ===")
            query = "what is important?"
            results = client.query(query, n_results=5)
            
            # Validate results
            assert results.blocks, "No results returned for query"
            print(f"Received {len(results.blocks)} results")
            
            # Print results
            for i, block in enumerate(results.blocks):
                print(f"Result {i+1}: {block.text}")
            
            # Verify all results have the #important tag
            all_have_important_tag = all("#important" in block.tags for block in results.blocks)
            assert all_have_important_tag, "Not all returned blocks have the #important tag"
            
            print("\n=== ✅ TEST COMPLETED SUCCESSFULLY ===") 