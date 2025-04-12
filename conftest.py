"""
Common fixtures for testing the Cogni Memory Architecture.
"""

import os
import tempfile
import shutil
import pytest
import sys

# Ensure project root is in the Python path for test discovery from any location
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Configure pytest
pytest_plugins = []


@pytest.fixture
def sample_logseq_dir():
    """
    Create a temporary directory with sample Logseq markdown files.
    
    This fixture creates markdown files with various tagged and untagged blocks
    that can be used for testing the parser and indexer.
    """
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
            f.write("- More content without tags\n")
        
        with open(os.path.join(temp_dir, "mixed.md"), "w") as f:
            f.write("- Multiple tags in one block #thought #broadcast\n")
            f.write("- Some complex formatting with *italic* and **bold** #approved\n")
            f.write("- Block with a [[Page Link]] #thought\n")
            f.write("- Regular content without any special formatting or tags\n")

        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)


@pytest.fixture
def sample_memory_blocks():
    """
    Create sample memory block data for testing.
    
    This fixture provides a list of dictionaries that mimic the structure
    of MemoryBlock objects, without requiring the actual implementation.
    These can be used to test storage and client components.
    """
    return [
        {
            "id": "test-block-1",
            "text": "Test block with #thought tag",
            "tags": ["#thought"],
            "source_file": "test1.md",
            "embedding": [0.1] * 1536  # Mock embedding vector
        },
        {
            "id": "test-block-2",
            "text": "Test block with #broadcast tag",
            "tags": ["#broadcast"],
            "source_file": "test2.md",
            "embedding": [0.2] * 1536
        },
        {
            "id": "test-block-3",
            "text": "Test block with #broadcast and #approved tags",
            "tags": ["#broadcast", "#approved"],
            "source_file": "test2.md",
            "embedding": [0.3] * 1536
        },
        {
            "id": "test-block-4",
            "text": "Multiple tags in one block #thought #broadcast",
            "tags": ["#thought", "#broadcast"],
            "source_file": "mixed.md",
            "embedding": [0.4] * 1536
        }
    ]


@pytest.fixture
def test_storage_dirs():
    """
    Create temporary directories for testing storage components.
    
    This fixture creates directories for ChromaDB and Archive storage,
    and cleans them up after the tests.
    """
    chroma_dir = tempfile.mkdtemp()
    archive_dir = tempfile.mkdtemp()
    try:
        # Create archive subdirectories
        os.makedirs(os.path.join(archive_dir, "blocks"))
        os.makedirs(os.path.join(archive_dir, "index"))
        
        yield {"chroma": chroma_dir, "archive": archive_dir}
    finally:
        shutil.rmtree(chroma_dir)
        shutil.rmtree(archive_dir) 