#!/usr/bin/env python3
"""
Script to sync MemoryBlocks from a Dolt database into LlamaIndex.
This script retrieves MemoryBlocks from Dolt and indexes them into LlamaIndex's
vector and graph stores using the LlamaMemory system.
"""

import argparse
import logging
import sys
from pathlib import Path
import time

# --- Path setup --- #
# Add project root to Python path for imports
script_path = Path(__file__).resolve()
project_root = script_path.parent.parent.parent
sys.path.insert(0, str(project_root))

# --- Import local modules --- #
from experiments.src.memory_system.dolt_reader import read_memory_blocks  # noqa: E402
from experiments.src.memory_system.llama_memory import LlamaMemory, DEFAULT_CHROMA_PATH  # noqa: E402

# --- Configure logging --- #
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def sync_dolt_to_llamaindex(
    dolt_db_path: str,
    llama_storage_path: str = DEFAULT_CHROMA_PATH,
    branch: str = 'main'
) -> bool:
    """
    Syncs MemoryBlocks from a Dolt DB to LlamaIndex.
    
    Args:
        dolt_db_path: Path to the Dolt database
        llama_storage_path: Path for LlamaIndex/ChromaDB storage
        branch: Dolt branch to read from
    
    Returns:
        bool: True if sync was successful, False otherwise
    """
    success = True
    logger.info(f"Starting sync from Dolt DB at {dolt_db_path} (branch: {branch}) to LlamaIndex at {llama_storage_path}")
    
    try:
        # 1. Initialize LlamaMemory
        logger.info("Initializing LlamaMemory...")
        llama_memory = LlamaMemory(chroma_path=llama_storage_path)
        
        if not llama_memory.is_ready():
            logger.error("Failed to initialize LlamaMemory properly")
            return False
        
        # 2. Read MemoryBlocks from Dolt
        logger.info(f"Reading MemoryBlocks from Dolt DB at {dolt_db_path}...")
        memory_blocks = read_memory_blocks(dolt_db_path, branch=branch)
        logger.info(f"Retrieved {len(memory_blocks)} MemoryBlocks from Dolt")
        
        if not memory_blocks:
            logger.warning("No memory blocks found in Dolt DB. Nothing to sync.")
            return True
        
        # 3. Sync each block to LlamaIndex
        logger.info("Starting to index MemoryBlocks to LlamaIndex...")
        start_time = time.time()
        
        for i, block in enumerate(memory_blocks):
            try:
                logger.debug(f"Processing block {i+1}/{len(memory_blocks)}: ID={block.id}, Type={block.type}")
                llama_memory.add_block(block)
                if (i + 1) % 10 == 0:
                    logger.info(f"Progress: {i+1}/{len(memory_blocks)} blocks processed")
            except Exception as e:
                logger.error(f"Error indexing block {block.id}: {e}")
                success = False
        
        elapsed_time = time.time() - start_time
        logger.info(f"Indexing completed in {elapsed_time:.2f} seconds")
        
        # 4. Verify indexing
        if success:
            logger.info("All blocks processed. Performing verification query...")
            if memory_blocks:
                # Try a simple query to verify indexing worked
                sample_block = memory_blocks[0]
                if sample_block.tags:
                    query_text = f"type:{sample_block.type} tag:{sample_block.tags[0]}"
                else:
                    query_text = f"type:{sample_block.type}"
                
                results = llama_memory.query_vector_store(query_text, top_k=1)
                if results and len(results) > 0:
                    logger.info("Verification query returned results. Indexing appears successful.")
                else:
                    logger.warning("Verification query returned no results. Indexing may not be working correctly.")
        
        return success
    
    except Exception as e:
        logger.error(f"Sync failed with error: {e}", exc_info=True)
        return False

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Sync MemoryBlocks from Dolt database to LlamaIndex"
    )
    
    parser.add_argument(
        "--dolt-path", 
        type=str, 
        required=True,
        help="Path to the Dolt database directory"
    )
    
    parser.add_argument(
        "--llamaindex-path", 
        type=str, 
        default=DEFAULT_CHROMA_PATH,
        help=f"Path to store LlamaIndex/ChromaDB files (default: {DEFAULT_CHROMA_PATH})"
    )
    
    parser.add_argument(
        "--branch", 
        type=str, 
        default="main",
        help="Dolt branch to read from (default: main)"
    )
    
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    logger.info("Starting Dolt to LlamaIndex sync...")
    
    result = sync_dolt_to_llamaindex(
        dolt_db_path=args.dolt_path,
        llama_storage_path=args.llamaindex_path,
        branch=args.branch
    )
    
    if result:
        logger.info("Sync completed successfully!")
        sys.exit(0)
    else:
        logger.error("Sync completed with errors. Check the logs for details.")
        sys.exit(1) 