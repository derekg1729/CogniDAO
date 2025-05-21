#!/usr/bin/env python3
"""
Test file to verify if tag filtering works properly with core-document tags.
"""

import logging
from infra_core.memory_system.dolt_reader import read_memory_blocks_by_tags
from infra_core.memory_system.llama_memory import LlamaMemory, IN_MEMORY_PATH
from infra_core.constants import MEMORY_DOLT_ROOT

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_dolt_query_by_tags():
    """Test querying Dolt DB directly by tags."""
    logger.info("=== Testing Dolt query by tags ===")

    # Query Dolt for blocks with the "core-document" tag
    blocks = read_memory_blocks_by_tags(MEMORY_DOLT_ROOT, ["core-document"])

    # Print details for each block
    for i, block in enumerate(blocks):
        logger.info(f"Block {i + 1}: ID={block.id}, Type={block.type}, Tags={block.tags}")

    # Assert that blocks were found
    assert len(blocks) > 0, "No blocks with 'core-document' tag found in Dolt"

    # Assert that all returned blocks have the core-document tag
    for block in blocks:
        assert "core-document" in block.tags, f"Block {block.id} missing 'core-document' tag"


def test_llamaindex_query_by_tags():
    """Test querying LlamaIndex by tags."""
    logger.info("=== Testing LlamaIndex query by tags ===")

    # Use in-memory ChromaDB to avoid dimension conflicts with persistent collection
    llama_memory = LlamaMemory(chroma_path=IN_MEMORY_PATH, collection_name="test_tags_collection")

    # First, index the core documents from Dolt to ensure there's something to query
    blocks = read_memory_blocks_by_tags(MEMORY_DOLT_ROOT, ["core-document"])
    assert len(blocks) > 0, "No core documents found in Dolt!"

    # Add blocks to the in-memory collection
    for block in blocks:
        logger.info(f"Adding block {block.id} with tags {block.tags}")
        llama_memory.add_block(block)

    # Perform a query for "philosophy" with filter for "core-document"
    query_results = llama_memory.query_vector_store("philosophy core", top_k=10)

    logger.info(f"Query returned {len(query_results)} results")

    # Check each result for the "core-document" tag
    core_docs = []
    for i, node_with_score in enumerate(query_results):
        node = node_with_score.node
        tags_str = node.metadata.get("tags", "")
        logger.info(f"Result {i + 1}: ID={node.id_}, Tags={tags_str}")

        # Check if "core-document" is in the tags
        if "core-document" in tags_str:
            core_docs.append(node)

    logger.info(f"Found {len(core_docs)} results with 'core-document' in tags")

    # Assert that at least one result has the core-document tag
    assert len(core_docs) > 0, "No results with 'core-document' tag found in LlamaIndex"


def test_reindex_core_docs():
    """Test reindexing core documents from Dolt to LlamaIndex."""
    logger.info("=== Testing reindexing core documents ===")

    # 1. Get core documents from Dolt
    blocks = read_memory_blocks_by_tags(MEMORY_DOLT_ROOT, ["core-document"])
    assert len(blocks) > 0, "No core documents found in Dolt!"

    logger.info(f"Found {len(blocks)} core documents in Dolt")

    # 2. Use in-memory ChromaDB to avoid dimension conflicts
    llama_memory = LlamaMemory(
        chroma_path=IN_MEMORY_PATH, collection_name="test_reindex_collection"
    )

    # 3. Add each document to LlamaIndex
    for block in blocks:
        logger.info(f"Adding block {block.id} with tags {block.tags}")
        llama_memory.add_block(block)

    # 4. Verify they can be found
    query_results = llama_memory.query_vector_store("philosophy core spirit", top_k=5)
    assert len(query_results) > 0, "No results returned after reindexing"

    # Check if any results have "core-document" in tags
    found_core_docs = False
    for i, node_with_score in enumerate(query_results):
        node = node_with_score.node
        tags_str = node.metadata.get("tags", "")
        logger.info(
            f"Result {i + 1}: ID={node.id_}, Tags={tags_str}, Score={node_with_score.score}"
        )

        if "core-document" in tags_str:
            found_core_docs = True

    assert found_core_docs, "No core-document tags found in query results after reindexing"
