"""
Tests for the BGE embedding implementation.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
import numpy as np

# Import needed modules - use try/except to handle import path issues
try:
    from legacy_logseq.memory.memory_indexer import init_embedding_function
except ImportError:
    # Add the project root to the path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    from legacy_logseq.memory.memory_indexer import init_embedding_function


class TestBGEEmbedding:
    """Tests for the BGE embedding functionality."""

    def test_bge_embedding_initialization(self):
        """Test creating the BGE embedding function."""
        try:
            # Check if sentence_transformers is installed without importing the class
            import importlib.util

            if importlib.util.find_spec("sentence_transformers") is None:
                pytest.skip("sentence-transformers package not installed")
        except ImportError:
            pytest.skip("sentence-transformers package not installed")

        # Patch the SentenceTransformer to avoid loading model
        with patch("sentence_transformers.SentenceTransformer") as mock_model:
            mock_instance = MagicMock()
            # Mock the encode method to return an object with tolist method
            mock_instance.encode.return_value = np.array([[0.1] * 384])
            mock_model.return_value = mock_instance

            # Initialize the embedding function
            embed_fn = init_embedding_function("bge")

            # Verify the model was initialized with the correct name
            # Since the implementation checks for available devices, we should allow device parameter
            # rather than strictly asserting a call with no device
            mock_model.assert_called_once()
            args, kwargs = mock_model.call_args
            assert args[0] == "BAAI/bge-small-en-v1.5"
            assert "device" in kwargs  # Device parameter should be present

            # Test that the embedding function works
            result = embed_fn(["Test text"])
            assert len(result) == 1
            assert len(result[0]) == 384  # BGE small model has 384 dimensions

    @pytest.mark.slow  # Mark as slow test since it downloads the model
    def test_real_bge_embedding(self):
        """Test the actual BGE embedding model (downloads model, slow)."""
        try:
            # Check if sentence_transformers is installed without importing it
            import importlib.util

            if importlib.util.find_spec("sentence_transformers") is None:
                pytest.skip("sentence-transformers package not installed")
        except ImportError:
            pytest.skip("sentence-transformers package not installed")

        # Only run this test if explicitly requested (it's slow and downloads model)
        if not os.environ.get("RUN_SLOW_TESTS"):
            pytest.skip("Skipping slow test. Set RUN_SLOW_TESTS=1 to run.")

        # Initialize the real embedding function
        embed_fn = init_embedding_function("bge")

        # Test with a simple text
        result = embed_fn(["This is a test sentence for embeddings."])

        # Verify result shape
        assert len(result) == 1
        assert len(result[0]) == 384  # BGE small model has 384 dimensions

        # Verify values are reasonable (floats between -1 and 1)
        assert all(-1 <= x <= 1 for x in result[0])

    def test_integration_with_cogni_graph(self):
        """Test embedding with cogni_graph.md content."""
        try:
            # Check if sentence_transformers is installed without importing the class
            import importlib.util

            if importlib.util.find_spec("sentence_transformers") is None:
                pytest.skip("sentence-transformers package not installed")
        except ImportError:
            pytest.skip("sentence-transformers package not installed")

        # Skip slow test unless explicitly requested
        if not os.environ.get("RUN_SLOW_TESTS"):
            pytest.skip("Skipping slow test. Set RUN_SLOW_TESTS=1 to run.")

        # Check if cogni_graph.md exists
        if not os.path.exists("cogni_graph.md"):
            pytest.skip("cogni_graph.md file not found")

        # Read the content of cogni_graph.md
        with open("cogni_graph.md", "r") as f:
            content = f.read()

        # Initialize the real embedding function
        embed_fn = init_embedding_function("bge")

        # Generate embedding
        embedding = embed_fn([content])[0]

        # Verify embedding dimensions
        assert len(embedding) == 384

        # Verify embedding contains valid values
        assert all(isinstance(x, float) for x in embedding)
        assert all(-1 <= x <= 1 for x in embedding)

        # Print first few values for manual verification
        print(f"First 5 embedding values: {embedding[:5]}")

        return embedding  # Return for optional further inspection
