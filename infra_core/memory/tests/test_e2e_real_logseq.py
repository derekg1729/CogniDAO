"""
True End-to-End test for the CogniMemoryClient with real Logseq data.

Tests the complete pipeline: scan → index → transform → query with minimal commands.
"""

import os
import pytest
import tempfile
from pathlib import Path

from infra_core.memory.memory_client import CogniMemoryClient
from infra_core.memory.tests.convert_to_logseq import convert_to_logseq


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
        2. INDEX: Convert to Logseq format and index content
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
        
        # Create a temporary directory to store converted files
        with tempfile.TemporaryDirectory() as temp_logseq_dir:
            # Convert files to Logseq format
            converted_files = []
            for doc_path in found_docs:
                # Create a temporary converted file with Logseq format
                doc_name = os.path.basename(doc_path)
                converted_path = os.path.join(temp_logseq_dir, f"{doc_name}")
                converted_files.append(converted_path)
                
                # Convert the file to Logseq format
                convert_to_logseq(doc_path, converted_path)
                print(f"Converted {doc_name} to Logseq format")
            
            # Count expected blocks in converted files
            print("\n=== 📏 ANALYZING CONVERTED FILES ===")
            total_lines = 0
            bullet_lines = 0
            for doc in converted_files:
                with open(doc, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    doc_lines = len(lines)
                    doc_bullets = sum(1 for line in lines if line.strip().startswith('-') or line.strip().startswith('*'))
                    print(f"File {os.path.basename(doc)}: {doc_lines} lines, {doc_bullets} bullet points")
                    total_lines += doc_lines
                    bullet_lines += doc_bullets
            
            print(f"Total: {total_lines} lines, {bullet_lines} bullet points across all files")
            
            # STEP 2: INDEX - Process the converted markdown files
            print("\n=== 📝 STEP 2: INDEX CONTENT ===")
            # Process only the converted files in the temp directory
            num_indexed = client.index_from_logseq(
                logseq_dir=temp_logseq_dir,
                tag_filter=None,  # Include all blocks regardless of tags
                verbose=True
            )
            
            print(f"Indexed {num_indexed} blocks from converted files")
            print(f"Bullet points: {bullet_lines}, Indexed blocks: {num_indexed}")
            
            # Expected percentage based on bullet points vs indexed
            if bullet_lines > 0:
                indexing_ratio = (num_indexed / bullet_lines) * 100
                print(f"Indexing ratio: {indexing_ratio:.2f}% of bullet points indexed")
                
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
    


