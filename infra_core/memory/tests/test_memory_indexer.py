"""
Tests for the memory indexer entry point.
"""

import os
import tempfile
import shutil
import pytest
import subprocess
import sys
import importlib.util


class TestMemoryIndexer:
    """Tests for the memory indexer entry point."""
    
    @pytest.fixture
    def test_environment(self):
        """Create a test environment with sample Logseq files."""
        # Create temporary directories
        logseq_dir = tempfile.mkdtemp()
        output_dir = tempfile.mkdtemp()
        
        try:
            # Create test Logseq files
            with open(os.path.join(logseq_dir, "journal.md"), "w") as f:
                f.write("- Test entry with #thought tag\n")
                f.write("- Another entry with #broadcast tag\n")
                f.write("- Entry with both #broadcast and #approved tags\n")
                f.write("- Regular entry without tags\n")
            
            yield {"logseq_dir": logseq_dir, "output_dir": output_dir}
        finally:
            shutil.rmtree(logseq_dir)
            shutil.rmtree(output_dir)
    
    def test_indexer_command_line(self, test_environment, monkeypatch):
        """Test the memory indexer command-line interface."""
        # Verify test data is correct
        assert os.path.exists(test_environment["logseq_dir"])
        assert os.path.exists(test_environment["output_dir"])
        
        # Set environment variable for OpenAI API key
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-for-testing")
        
        # Memory indexer doesn't support command line args yet, so we'll modify it directly
        memory_indexer_path = os.path.join(os.path.dirname(__file__), "..", "memory_indexer.py")
        
        # Create a temporary modified version of memory_indexer.py with our test paths
        temp_indexer_path = os.path.join(test_environment["output_dir"], "test_memory_indexer.py")
        with open(memory_indexer_path, "r") as src, open(temp_indexer_path, "w") as dst:
            content = src.read()
            content = content.replace('LOGSEQ_DIR = "./logseq"', f'LOGSEQ_DIR = "{test_environment["logseq_dir"]}"')
            content = content.replace('VECTOR_DB_DIR = "./cogni-memory/chroma"', 
                                     f'VECTOR_DB_DIR = "{os.path.join(test_environment["output_dir"], "chroma")}"')
            # Add code to use the mock embedding model
            content = content.replace('if __name__ == "__main__":', 
                                    'if __name__ == "__main__":\n    # Use mock embedding for tests')
            content = content.replace('    run_indexing()', 
                                    '    run_indexing(embed_model="mock")')
            dst.write(content)
        
        # Run the modified indexer
        try:
            result = subprocess.run([
                sys.executable, temp_indexer_path
            ], capture_output=True, text=True, check=True)
            
            # Check if process ran successfully
            assert result.returncode == 0
            
            # Check if output mentions expected operations
            assert "Scanning Logseq directory" in result.stdout
            assert "Indexed" in result.stdout
            
            # Check if output directory was created with expected structure
            chroma_dir = os.path.join(test_environment["output_dir"], "chroma")
            assert os.path.exists(chroma_dir)
        except subprocess.CalledProcessError as e:
            pytest.fail(f"Memory indexer process failed: {e.stdout}\n{e.stderr}")
    
    def test_indexer_creates_chroma_collection(self, test_environment):
        """Test that the indexer creates a ChromaDB collection using direct import."""
        # Skip if chromadb is not available
        try:
            import chromadb
        except ImportError:
            pytest.skip("ChromaDB not installed")
        
        # Directly import the memory_indexer module
        memory_indexer_path = os.path.join(os.path.dirname(__file__), "..", "memory_indexer.py")
        spec = importlib.util.spec_from_file_location("memory_indexer", memory_indexer_path)
        memory_indexer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(memory_indexer)
        
        # Run indexing with mock embedding function directly
        chroma_dir = os.path.join(test_environment["output_dir"], "chroma")
        total_indexed = memory_indexer.run_indexing(
            logseq_dir=test_environment["logseq_dir"],
            vector_db_dir=chroma_dir,
            embed_model="mock"
        )
        
        # Check that we indexed the expected number of blocks (3 tagged blocks in our test file)
        assert total_indexed == 3
        
        # Verify the ChromaDB collection was created
        assert os.path.exists(chroma_dir)
        
        # Check if we can open the collection
        client = chromadb.PersistentClient(path=chroma_dir)
        collection = client.get_collection("cogni-memory")
        assert collection.count() == 3
    
    def test_indexer_with_custom_tags(self, test_environment):
        """Test the indexer with custom tag filters."""
        # Skip if chromadb is not available
        try:
            import chromadb
        except ImportError:
            pytest.skip("ChromaDB not installed")
        
        # Directly import the memory_indexer module
        memory_indexer_path = os.path.join(os.path.dirname(__file__), "..", "memory_indexer.py")
        spec = importlib.util.spec_from_file_location("memory_indexer", memory_indexer_path)
        memory_indexer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(memory_indexer)
        
        # Run indexing with only #broadcast tag filter
        chroma_dir = os.path.join(test_environment["output_dir"], "chroma_broadcast_only")
        total_indexed = memory_indexer.run_indexing(
            logseq_dir=test_environment["logseq_dir"],
            vector_db_dir=chroma_dir,
            embed_model="mock",
            target_tags={"#broadcast"}
        )
        
        # Check that we indexed the expected number of blocks (2 blocks with #broadcast tag)
        assert total_indexed == 2
        
        # Verify the ChromaDB collection was created
        assert os.path.exists(chroma_dir)
        
        # Check if we can open the collection
        client = chromadb.PersistentClient(path=chroma_dir)
        collection = client.get_collection("cogni-memory")
        assert collection.count() == 2
        
        # Get all entries instead of using query
        results = collection.get()
        
        # Verify the documents contain broadcast tags
        assert len(results["documents"]) == 2
        assert all("broadcast" in doc.lower() for doc in results["documents"])
    
    def test_end_to_end_memory_indexing(self, test_environment):
        """Test the complete end-to-end memory indexing process."""
        # Skip until CogniMemoryClient is implemented
        pytest.skip("Full memory indexing pipeline not yet implemented (CogniMemoryClient missing)") 