"""
True Minimal E2E tests for CogniMemoryClient.

These tests demonstrate the core memory pipeline functionality:
1. Load a single file (charter.md), index it, and query for charter content
2. Scan Logseq database for #thought tags, index them, and query

Purpose:
- Verify the complete pipeline functions without mocks
- Test with real embedding generation
- Validate tag filtering works correctly
- Ensure search results are relevant to queries
- Check for result deduplication

These tests follow Cogni's core principles:
- Clarity over control: Simple, focused tests that verify core functionality
- Meaning over motion: Real content extraction and search, not just API testing
- Simplicity over scale: Minimal test cases that demonstrate the full pipeline
"""

import os
import pytest
import tempfile

from legacy_logseq.memory.memory_client import CogniMemoryClient


class TestTrueE2E:
    """Truly minimal E2E tests with real embeddings and no mocking."""

    @pytest.fixture
    def test_dirs(self):
        """Create temporary test directories for storage."""
        with (
            tempfile.TemporaryDirectory() as chroma_dir,
            tempfile.TemporaryDirectory() as archive_dir,
        ):
            yield {"chroma": chroma_dir, "archive": archive_dir}

    def test_single_file_query(self, test_dirs):
        """
        Test 1: Single file indexing and querying

        - Creates a test charter file with proper Logseq format
        - Indexes its contents with real embeddings
        - Queries "what is our charter about?"
        - Validates meaningful results were returned
        """
        # Setup client
        client = CogniMemoryClient(
            chroma_path=test_dirs["chroma"], archive_path=test_dirs["archive"]
        )

        print("\n=== 🧪 TEST 1: SINGLE FILE INDEXING AND QUERY ===")

        # Create temporary directory with test charter file
        with tempfile.TemporaryDirectory() as test_dir:
            # Create test charter file with Logseq format (matching the working test format)
            charter_content = """- #charter Our Charter
- #charter #mission Our mission is to empower communities through shared knowledge.
- #charter #governance The DAO is governed by community members with equal voting rights.
- #charter #values Transparency in all operations
- #charter #values Collaboration across teams
- #charter #values Innovation in technology
"""
            charter_path = os.path.join(test_dir, "charter.md")
            with open(charter_path, "w") as f:
                f.write(charter_content)

            print(f"Created test charter.md at: {charter_path}")

            # Index the file with real embeddings
            num_indexed = client.index_from_logseq(
                logseq_dir=test_dir,
                tag_filter="#charter",  # Filter for charter blocks
                verbose=True,
            )

            print(f"Indexed {num_indexed} charter blocks from test charter.md")
            assert num_indexed > 0, "Failed to index any blocks from test charter.md"

            # Query about the charter
            query = "what is our charter about?"
            print(f"\nQuerying: '{query}'")
            results = client.query(query, n_results=3)

            # Validate results
            assert results.blocks, "No results returned for query"
            print(f"Received {len(results.blocks)} results")

            # Display first result
            first_block = results.blocks[0]
            print(f"First result: {first_block.text}")

            # Validate that we got meaningful content back (specific to charter)
            found_keywords = False
            charter_keywords = ["mission", "governance", "values", "empower", "communities", "dao"]

            for keyword in charter_keywords:
                for block in results.blocks:
                    if keyword.lower() in block.text.lower():
                        found_keywords = True
                        print(f"Found keyword: {keyword}")
                        break

            assert found_keywords, "No charter-related content found in query results"

    def test_tag_filtering(self, test_dirs):
        """
        Test 2: Scan and query blocks with specific tags

        - Creates test markdown with #thought tags
        - Scans and indexes only blocks with #thought tags using real embeddings
        - Queries "what are our thoughts about?"
        - Validates blocks returned have #thought tag
        """
        # Setup client
        client = CogniMemoryClient(
            chroma_path=test_dirs["chroma"], archive_path=test_dirs["archive"]
        )

        print("\n=== 🧪 TEST 2: TAG FILTERING AND QUERY ===")

        # Create temporary directory with test markdown
        with tempfile.TemporaryDirectory() as test_dir:
            # Create test files with #thought tags in Logseq format
            with open(os.path.join(test_dir, "thoughts.md"), "w") as f:
                f.write("- #thought This is a thought about AI systems\n")
                f.write("- This is a regular note without a tag\n")
                f.write("- #thought Another thought about user interfaces\n")
                f.write("- #broadcast This is a broadcast message\n")
                f.write("- #thought A third thought about database design\n")

            print(f"Created test markdown file with #thought tags in {test_dir}")

            # Index only #thought blocks with real embeddings
            num_indexed = client.index_from_logseq(
                logseq_dir=test_dir,
                tag_filter="#thought",  # Only index blocks with #thought tag
                verbose=True,
            )

            print(f"Indexed {num_indexed} #thought blocks")
            assert num_indexed == 3, f"Expected 3 #thought blocks, got {num_indexed}"

            # Query about thoughts
            query = "what are our thoughts about?"
            print(f"\nQuerying: '{query}'")
            results = client.query(query, n_results=5)

            # Validate results
            assert results.blocks, "No results returned for query"
            print(f"Received {len(results.blocks)} results")

            # Verify all returned blocks have #thought tag
            all_have_thought_tag = all("#thought" in block.tags for block in results.blocks)
            assert all_have_thought_tag, "Some returned blocks don't have #thought tag"

            # Display thoughts found
            for i, block in enumerate(results.blocks):
                print(f"Thought {i + 1}: {block.text}")

            # Verify no duplicates in results
            block_ids = [block.id for block in results.blocks]
            assert len(block_ids) == len(set(block_ids)), "Duplicate blocks found in results"
