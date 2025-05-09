#!/usr/bin/env python
"""
Script to load MemoryBlocks from the Dolt database's WORKING SET,
index them into an in-memory LlamaIndex, and allow querying via CLI.

This is for validating the current uncommitted state of data in Dolt
and how it's indexed by LlamaIndex.
"""

import argparse
import logging
from pathlib import Path


from infra_core.memory_system.llama_memory import LlamaMemory
from infra_core.memory_system.dolt_reader import read_memory_blocks_from_working_set

# Assuming this script is in a 'scripts' directory at the root of the workspace.
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

# Add infra_core to sys.path if not running as part of a package or if imports fail
# import sys
# sys.path.insert(0, str(WORKSPACE_ROOT))

# Configure basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Query MemoryBlocks from Dolt DB working set via LlamaIndex."
    )
    parser.add_argument(
        "--dolt-db-path",
        required=True,
        help="Path to the Dolt database directory (e.g., data/memory_dolt).",
    )
    parser.add_argument(
        "--collection-name",
        default="dolt_working_set_query_temp",
        help="ChromaDB collection name for the in-memory LlamaIndex.",
    )
    args = parser.parse_args()

    logger.info(f"Starting query tool for Dolt DB working set at: {args.dolt_db_path}")

    # 1. Read MemoryBlocks from Dolt working set
    memory_blocks = read_memory_blocks_from_working_set(args.dolt_db_path)

    if not memory_blocks:
        logger.info("No MemoryBlocks found in the Dolt working set. Exiting.")
        return

    # 2. Initialize in-memory LlamaMemory
    logger.info("Initializing in-memory LlamaMemory...")
    try:
        llama_memory = LlamaMemory(chroma_path=":memory:", collection_name=args.collection_name)
        if not llama_memory.is_ready():
            logger.error("LlamaMemory failed to initialize. Exiting.")
            return
        logger.info("LlamaMemory initialized successfully.")
    except Exception as e:
        logger.error(f"Exception initializing LlamaMemory: {e}", exc_info=True)
        return

    # 3. Index MemoryBlocks into LlamaMemory
    logger.info(f"Indexing {len(memory_blocks)} MemoryBlocks into LlamaMemory...")
    indexed_count = 0
    for block in memory_blocks:
        try:
            llama_memory.add_block(block)
            indexed_count += 1
        except Exception as e:
            logger.error(f"Error indexing block ID {block.id}: {e}", exc_info=True)

    if indexed_count == 0:
        logger.error("No documents were successfully indexed into LlamaMemory. Exiting query tool.")
        return
    logger.info(f"Successfully indexed {indexed_count} MemoryBlocks. Ready for querying.")

    # 4. Interactive Query Loop
    logger.info("Enter your query. Type 'exit' or 'quit' to stop.")
    while True:
        try:
            query_text = input("Query> ")
            if query_text.lower() in ["exit", "quit"]:
                logger.info("Exiting query tool.")
                break
            if not query_text.strip():
                continue

            logger.info(f"Querying for: '{query_text}'")
            results = llama_memory.query_vector_store(query_text=query_text, top_k=3)

            if (
                results
                and isinstance(results, list)
                and all(hasattr(item, "score") and hasattr(item, "node") for item in results)
            ):
                logger.info(f"Found {len(results)} results:")
                for i, result_item in enumerate(results):  # result_item is NodeWithScore
                    print(f"--- Result {i + 1} (Score: {result_item.score:.4f}) ---")
                    node_data = result_item.node  # Access the node attribute
                    if node_data and hasattr(node_data, "metadata") and node_data.metadata:
                        print(f"  Title: {node_data.metadata.get('title', 'N/A')}")
                        print(f"  Source File: {node_data.metadata.get('source_file', 'N/A')}")
                        print(f"  Block ID: {node_data.id_}")
                    text_snippet = (
                        node_data.get_text()[:250].replace("\n", " ") + "..."
                        if node_data
                        else "N/A"
                    )
                    print(f"  Snippet: {text_snippet}")
                    print("------------------------------------")
            elif results and hasattr(results, "source_nodes") and results.source_nodes:
                logger.info(f"Found {len(results.source_nodes)} results (from Response object):")
                for i, result_item in enumerate(
                    results.source_nodes
                ):  # result_item is NodeWithScore
                    print(f"--- Result {i + 1} (Score: {result_item.score:.4f}) ---")
                    node_data = result_item.node
                    if node_data and hasattr(node_data, "metadata") and node_data.metadata:
                        print(f"  Title: {node_data.metadata.get('title', 'N/A')}")
                        print(f"  Source File: {node_data.metadata.get('source_file', 'N/A')}")
                        print(f"  Block ID: {node_data.id_}")
                    text_snippet = (
                        node_data.get_text()[:250].replace("\n", " ") + "..."
                        if node_data
                        else "N/A"
                    )
                    print(f"  Snippet: {text_snippet}")
                    print("------------------------------------")
            else:
                logger.info("No results found or unexpected result format.")
                if results:
                    logger.info(f"Raw results: {results}")

        except EOFError:
            logger.info("Exiting query tool due to EOF.")
            break
        except KeyboardInterrupt:
            logger.info("\nExiting query tool due to interrupt.")
            break
        except Exception as e:
            logger.error(f"Error during query: {e}", exc_info=True)


if __name__ == "__main__":
    main()
