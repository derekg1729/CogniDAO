"""
Memory tool for agent integration with the Cogni Memory Architecture.

This module provides a simple function-based interface for agents to:
1. Query Cogni memory for relevant context
2. Save new memories
3. Manage memory operations
"""

from typing import Dict, List, Optional, Any

from infra_core.memory.memory_client import CogniMemoryClient
from infra_core.memory.schema import MemoryBlock


def memory_tool(
    input_text: str,
    operation: str = "query",
    n_results: int = 5,
    include_archived: bool = False,
    filter_tags: Optional[List[str]] = None,
    chroma_path: str = "./cogni-memory/chroma",
    archive_path: str = "./cogni-memory/archive",
    collection_name: str = "cogni-memory",
    blocks_to_save: Optional[List[Dict[str, Any]]] = None,
    block_ids_to_archive: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Unified memory tool for agents to interact with Cogni Memory Architecture.
    
    Args:
        input_text: Query text for search operations
        operation: Type of operation to perform ("query", "save", "archive", "get", "count")
        n_results: Number of results to return for query operations
        include_archived: Whether to include archived blocks in query results
        filter_tags: Optional filter for specific tags
        chroma_path: Path to ChromaDB storage
        archive_path: Path to archive storage
        collection_name: Name of the ChromaDB collection
        blocks_to_save: List of memory blocks to save (for "save" operation)
        block_ids_to_archive: List of block IDs to archive (for "archive" operation)
        
    Returns:
        Dictionary with operation results
    """
    # Initialize client
    try:
        client = CogniMemoryClient(
            chroma_path=chroma_path,
            archive_path=archive_path,
            collection_name=collection_name
        )
    except Exception as e:
        return {
            "operation": operation,
            "error": f"Failed to initialize memory client: {str(e)}",
            "success": False
        }
    
    if operation == "query":
        # Query memories
        try:
            results = client.query(
                query_text=input_text,
                n_results=n_results,
                include_archived=include_archived,
                filter_tags=filter_tags
            )
            
            # Format result for agent consumption
            return {
                "operation": "query",
                "query": input_text,
                "results": [block.model_dump() for block in results.blocks],
                "result_count": results.total_results
            }
        except Exception as e:
            return {
                "operation": "query",
                "error": f"Query failed: {str(e)}",
                "success": False,
                "query": input_text,
                "results": []
            }
    
    elif operation == "save":
        if not blocks_to_save:
            return {
                "operation": "save",
                "error": "No blocks provided to save",
                "success": False
            }
        
        # Convert dictionaries to MemoryBlock objects
        memory_blocks = []
        for block in blocks_to_save:
            # Handle case where text is the only required field
            if "text" in block and isinstance(block["text"], str):
                # Fill in defaults for missing fields
                if "tags" not in block:
                    block["tags"] = []
                if "source_file" not in block:
                    block["source_file"] = "agent_memory.md"
                
                memory_blocks.append(MemoryBlock(**block))
        
        # Save blocks
        try:
            client.save_blocks(memory_blocks)
            return {
                "operation": "save",
                "success": True,
                "saved_count": len(memory_blocks),
                "block_ids": [block.id for block in memory_blocks]
            }
        except Exception as e:
            return {
                "operation": "save",
                "error": f"Save failed: {str(e)}",
                "success": False
            }
    
    elif operation == "archive":
        if not block_ids_to_archive:
            return {
                "operation": "archive",
                "error": "No block IDs provided to archive",
                "success": False
            }
        
        # Archive blocks
        try:
            client.archive_blocks(block_ids_to_archive)
            return {
                "operation": "archive",
                "success": True,
                "archived_count": len(block_ids_to_archive),
                "block_ids": block_ids_to_archive
            }
        except Exception as e:
            return {
                "operation": "archive",
                "error": f"Archive failed: {str(e)}",
                "success": False
            }
    
    elif operation == "get":
        # Get a specific block by ID
        block_id = input_text.strip()
        try:
            block = client.get_block_by_id(block_id)
            
            if block:
                return {
                    "operation": "get",
                    "success": True,
                    "block": block.model_dump()
                }
            else:
                return {
                    "operation": "get",
                    "success": False,
                    "error": f"Block with ID {block_id} not found"
                }
        except Exception as e:
            return {
                "operation": "get",
                "success": False,
                "error": f"Get failed: {str(e)}"
            }
    
    elif operation == "count":
        # Count blocks in storage
        try:
            counts = client.count_blocks()
            return {
                "operation": "count",
                "success": True,
                "counts": counts
            }
        except Exception as e:
            return {
                "operation": "count",
                "success": False,
                "error": f"Count failed: {str(e)}"
            }
    
    else:
        return {
            "operation": operation,
            "error": f"Unknown operation: {operation}",
            "success": False
        }


def quick_query(query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """
    Simplified function to quickly query memory.
    
    Args:
        query_text: Query text to search for
        n_results: Number of results to return
        
    Returns:
        List of memory blocks as dictionaries
    """
    result = memory_tool(input_text=query_text, n_results=n_results)
    return result.get("results", []) 