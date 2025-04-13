"""
True End-to-End test for the CogniMemoryClient with real Logseq data.

Tests the complete pipeline: scan → index → transform → query with minimal commands.
"""

import os
import pytest
import tempfile
from pathlib import Path

from infra_core.memory.memory_client import CogniMemoryClient


class TestRealLogseqE2E:
    """End-to-end test with real data, minimal mocking, and simple assertions."""
    
    @pytest.fixture
    def test_dirs(self):
        """Create temporary test directories."""
        import tempfile
        with tempfile.TemporaryDirectory() as chroma_dir, tempfile.TemporaryDirectory() as archive_dir:
            yield {
                "chroma": chroma_dir,
                "archive": archive_dir
            }
    
    def test_e2e_pipeline(self, test_dirs):
        """
        Tests the complete memory pipeline in 4 simple steps:
        1. SCAN: Find the project's markdown files
        2. INDEX: Index the markdown content directly (no conversion needed with improved parser)
        3. TRANSFORM: Let the system handle embedding and storage
        4. QUERY: Retrieve relevant information and assert it's meaningful
        """
        # Find project root
        project_root = self._find_project_root()
        
        # Initialize client
        client = CogniMemoryClient(
            chroma_path=test_dirs["chroma"],
            archive_path=test_dirs["archive"]
        )
        
        print("\n=== 🧪 RUNNING E2E MEMORY PIPELINE TEST ===")
        print(f"Project root: {project_root}")
        
        # STEP 1: SCAN - Find the key documents
        print("\n=== 📑 STEP 1: SCAN MARKDOWN FILES ===")
        # Look for key documents
        found_docs = []
        key_files = ["CHARTER.md", "MANIFESTO.md", "cogni_graph.md"]
        
        for filename in key_files:
            file_path = os.path.join(project_root, filename)
            if os.path.exists(file_path):
                found_docs.append(file_path)
                print(f"Found: {filename} at {file_path}")
        
        # If no key files found, try to look for any markdown files
        if not found_docs:
            print("No key files found, looking for any markdown files...")
            for md_file in Path(project_root).glob("**/*.md"):
                # Skip env files or other likely non-important directories
                skip_dirs = ["env", "node_modules", ".git", "__pycache__"]
                if not any(d in str(md_file) for d in skip_dirs):
                    found_docs.append(str(md_file))
                    print(f"Found alternative file: {md_file}")
                    if len(found_docs) >= 3:  # Limit to 3 files for test
                        break
        
        assert found_docs, "No markdown files found to test with"
        
        # Create a temporary directory to store test files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Copy files to the temporary directory
            copied_files = []
            for doc_path in found_docs:
                # Create a file copy in the temp directory
                doc_name = os.path.basename(doc_path)
                copied_path = os.path.join(temp_dir, f"{doc_name}")
                copied_files.append(copied_path)
                
                # Copy the file content
                with open(doc_path, 'r', encoding='utf-8') as src, open(copied_path, 'w', encoding='utf-8') as dst:
                    content = src.read()
                    dst.write(content)
                print(f"Copied {doc_name} to temporary directory")
            
            # Count content lines in files
            print("\n=== 📏 ANALYZING FILES ===")
            total_lines = 0
            content_lines = 0
            for doc in copied_files:
                with open(doc, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    doc_lines = len(lines)
                    doc_content = doc_lines - sum(1 for line in lines if not line.strip())
                    print(f"File {os.path.basename(doc)}: {doc_lines} lines, {doc_content} content lines")
                    total_lines += doc_lines
                    content_lines += doc_content
            
            print(f"Total: {total_lines} lines, {content_lines} content lines across all files")
            
            # STEP 2: INDEX - Process the markdown files directly
            print("\n=== 📝 STEP 2: INDEX CONTENT ===")
            # Process the files in the temp directory
            num_indexed = client.index_from_logseq(
                logseq_dir=temp_dir,
                tag_filter=None,  # Include all blocks regardless of tags
                verbose=True
            )
            
            print(f"Indexed {num_indexed} blocks from files")
            
            # Expected percentage based on content lines vs indexed
            if content_lines > 0:
                indexing_ratio = (num_indexed / content_lines) * 100
                print(f"Indexing ratio: {indexing_ratio:.2f}% of content lines indexed")
                
            assert num_indexed > 0, "Failed to index any blocks"
            
            # STEP 3: TRANSFORM - No explicit step needed, handled by index_from_logseq
            print("\n=== 🔄 STEP 3: TRANSFORM - COMPLETE ===")
            print("Transformation to embeddings handled automatically by index_from_logseq")
            
            # STEP 4: QUERY - Retrieve and verify results
            print("\n=== 🔍 STEP 4: QUERY AND VERIFY ===")
            # Test with key queries about Cogni
            queries = [
                "What is Cogni?",
                "What is the purpose of the project?",
                "How does the memory system work?",
                "Describe the core functionality",
            ]
            
            successful_queries = 0
            for query in queries:
                print(f"\nQuery: '{query}'")
                results = client.query(query, n_results=3)
                
                # Verify we got results
                if results and len(results.blocks) > 0:
                    print(f"✅ Returned {len(results.blocks)} results")
                    # Print the first result (abbreviated)
                    block = results.blocks[0]
                    preview = block.text[:150] + ("..." if len(block.text) > 150 else "")
                    print(f"First result: {preview}")
                    print(f"Source: {block.source_file}")
                    print(f"Tags: {block.tags}")
                    successful_queries += 1
                    
                    # Check for duplicates in results
                    block_ids = [b.id for b in results.blocks]
                    if len(block_ids) != len(set(block_ids)):
                        print("⚠️ WARNING: Duplicate blocks detected in results")
                else:
                    print("❌ No results for query")
            
            # Assert that at least 50% of queries returned results
            success_rate = successful_queries / len(queries)
            assert success_rate >= 0.5, f"Only {successful_queries}/{len(queries)} queries returned results"
            
            print("\n=== ✅ E2E PIPELINE TEST COMPLETED SUCCESSFULLY ===")
            print(f"Indexed {num_indexed} blocks, {successful_queries}/{len(queries)} queries successful")
    
    def test_direct_markdown_extraction(self, test_dirs):
        """
        Tests that the improved parser can extract content directly from standard markdown files
        without requiring conversion to Logseq format.
        """
        # Find project root
        project_root = self._find_project_root()
        
        # Initialize client
        client = CogniMemoryClient(
            chroma_path=test_dirs["chroma"],
            archive_path=test_dirs["archive"]
        )
        
        print("\n=== 🧪 RUNNING DIRECT MARKDOWN EXTRACTION TEST ===")
        print(f"Project root: {project_root}")
        
        # Find a standard markdown file for testing
        found_docs = []
        key_files = ["CHARTER.md", "MANIFESTO.md", "cogni_graph.md"]
        
        for filename in key_files:
            file_path = os.path.join(project_root, filename)
            if os.path.exists(file_path):
                found_docs.append(file_path)
                print(f"Found: {filename} at {file_path}")
                break  # Just need one file for this test
        
        # If no key files found, try to look for any markdown file
        if not found_docs:
            print("No key files found, looking for any markdown file...")
            for md_file in Path(project_root).glob("**/*.md"):
                # Skip env files or other likely non-important directories
                skip_dirs = ["env", "node_modules", ".git", "__pycache__"]
                if not any(d in str(md_file) for d in skip_dirs):
                    found_docs.append(str(md_file))
                    print(f"Found alternative file: {md_file}")
                    break  # Just need one file
        
        assert found_docs, "No markdown files found to test with"
        test_file = found_docs[0]
        
        # Analyze for content metrics
        print("\n=== 📏 ANALYZING FILE CONTENT ===")
        
        # Copy the file to a temporary directory for direct indexing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Copy the file
            direct_file = os.path.join(temp_dir, os.path.basename(test_file))
            with open(test_file, 'r', encoding='utf-8') as src, open(direct_file, 'w', encoding='utf-8') as dst:
                content = src.read()
                dst.write(content)
            
            # Analyze content
            with open(direct_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                total_lines = len(lines)
                bullet_lines = sum(1 for line in lines if line.strip().startswith('-') or line.strip().startswith('*'))
                content_lines = total_lines - sum(1 for line in lines if not line.strip())
                print(f"File: {total_lines} lines, {bullet_lines} bullet points, {content_lines} content lines")
            
            # Index directly with improved parser
            direct_indexed = client.index_from_logseq(
                logseq_dir=temp_dir,
                tag_filter=None,  # Include all blocks
                verbose=True
            )
            print(f"Indexed blocks: {direct_indexed}")
            
            # Calculate capture percentage
            content_capture = (direct_indexed / max(1, content_lines)) * 100
            bullet_capture = (direct_indexed / max(1, bullet_lines)) * 100 if bullet_lines > 0 else 0
            
            print(f"Content capture: {content_capture:.1f}%")
            if bullet_lines > 0:
                print(f"Bullet points capture: {bullet_capture:.1f}%")
            
            # Compare with previous 7% mentioned in handoff doc
            print("\n=== 📊 EXTRACTION IMPROVEMENT ===")
            print("Previous parser (mentioned in handoff): Only captured 7% of content")
            print(f"Improved parser: Capturing {content_capture:.1f}% of content")
            
            # Verify significant improvement in content capture
            # The handoff doc mentioned only 7% was captured before
            assert content_capture > 50, "Should capture more than 50% of content"
            
            # Query the index with a related query
            print("\n=== 🔍 TESTING QUERY RESULTS ===")
            query = "What is the main purpose?"
            results = client.query(query, n_results=3)
            
            print(f"Query results: {len(results.blocks)} results")
            if results and len(results.blocks) > 0:
                # Print the first result (abbreviated)
                block = results.blocks[0]
                preview = block.text[:150] + ("..." if len(block.text) > 150 else "")
                print(f"First result: {preview}")
            
            # Verify we get reasonable results from the direct indexing
            assert len(results.blocks) > 0, "Should find results via direct indexing"
            
            print("\n=== ✅ DIRECT EXTRACTION TEST COMPLETED SUCCESSFULLY ===")
    
    def _find_project_root(self):
        """Find the project root directory containing markdown files."""
        current_dir = os.path.abspath(os.path.dirname(__file__))
        
        # Go up to 4 levels looking for cogni_graph.md
        for _ in range(4):
            if os.path.exists(os.path.join(current_dir, "cogni_graph.md")):
                return current_dir
            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir:  # Reached filesystem root
                break
            current_dir = parent_dir
        
        # If not found in parent directories, check if it's in the workspace root
        if os.path.exists("/Users/derek/dev/cogni/cogni_graph.md"):
            return "/Users/derek/dev/cogni"
        
        # Just return current directory as fallback
        return os.path.abspath(os.path.dirname(__file__)) 
    


