"""
Storage components for Cogni Memory Architecture.

This module provides:
1. ChromaStorage - For vector database storage of actively used memory blocks
2. ArchiveStorage - For JSON-based cold storage of older blocks
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

import chromadb

from infra_core.memory.schema import MemoryBlock, ArchiveIndex, IndexMetadata


class ChromaStorage:
    """
    ChromaDB storage for vector embeddings and active memory blocks.
    This is the "hot" storage for frequently accessed memories.
    """
    
    def __init__(self, persist_directory: str, collection_name: str = "cogni-memory"):
        """
        Initialize ChromaDB storage.
        
        Args:
            persist_directory: Directory to store ChromaDB files
            collection_name: Name of the ChromaDB collection
        """
        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name
        
        # Create directory if it doesn't exist
        os.makedirs(self.persist_directory, exist_ok=True)
        
        # Initialize client and collection
        self.client = chromadb.PersistentClient(path=str(self.persist_directory))
        
        try:
            self.collection = self.client.get_collection(name=self.collection_name)
        except ValueError:
            # Collection doesn't exist, create it
            self.collection = self.client.create_collection(name=self.collection_name)
    
    def add_blocks(self, blocks: List[Union[MemoryBlock, Dict]]):
        """
        Add memory blocks to ChromaDB.
        
        Args:
            blocks: List of MemoryBlock objects or dictionaries
        """
        if not blocks:
            return
        
        # Convert dictionaries to MemoryBlock objects if needed
        memory_blocks = []
        for block in blocks:
            if isinstance(block, dict):
                memory_blocks.append(MemoryBlock(**block))
            else:
                memory_blocks.append(block)
        
        # Prepare data for ChromaDB
        ids = [block.id for block in memory_blocks]
        embeddings = [block.embedding for block in memory_blocks if block.embedding is not None]
        documents = [block.text for block in memory_blocks]
        
        # Convert tags lists to comma-separated strings for ChromaDB metadata
        metadatas = []
        for block in memory_blocks:
            metadata = {
                "tags": ", ".join(block.tags),
                "source": block.source_file
            }
            if block.source_uri:
                metadata["source_uri"] = block.source_uri
            metadatas.append(metadata)
        
        # Add to collection
        self.collection.add(
            ids=ids,
            embeddings=embeddings if embeddings else None,
            documents=documents,
            metadatas=metadatas
        )
    
    def query(self, query_text: str, n_results: int = 5, filter_tags: Optional[List[str]] = None):
        """
        Query the ChromaDB collection.
        
        Args:
            query_text: Text to search for
            n_results: Number of results to return
            filter_tags: Optional filter for specific tags
        
        Returns:
            Dictionary with query results
        """
        # Build where clause if filter_tags is provided
        where = None
        if filter_tags:
            # This is a simplification - in a real implementation, you'd need more
            # sophisticated filtering since tags are stored as a comma-separated string
            tag_string = ", ".join(filter_tags)
            where = {"tags": {"$contains": tag_string}}
        
        # Execute query
        return self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where
        )
    
    def delete_blocks(self, block_ids: List[str]):
        """
        Delete blocks from ChromaDB.
        
        Args:
            block_ids: List of block IDs to delete
        """
        if not block_ids:
            return
        
        self.collection.delete(ids=block_ids)


class ArchiveStorage:
    """
    JSON-based archive storage for older memory blocks.
    This is the "cold" storage for less frequently accessed memories.
    """
    
    def __init__(self, archive_directory: str):
        """
        Initialize archive storage.
        
        Args:
            archive_directory: Directory to store archived blocks
        """
        self.archive_directory = Path(archive_directory)
        self.blocks_directory = self.archive_directory / "blocks"
        self.index_directory = self.archive_directory / "index"
        
        # Create directories if they don't exist
        os.makedirs(self.blocks_directory, exist_ok=True)
        os.makedirs(self.index_directory, exist_ok=True)
    
    def archive_blocks(self, blocks: List[Union[MemoryBlock, Dict]]):
        """
        Archive memory blocks.
        
        Args:
            blocks: List of MemoryBlock objects or dictionaries
        """
        if not blocks:
            return
        
        # Convert dictionaries to MemoryBlock objects if needed
        memory_blocks = []
        for block in blocks:
            if isinstance(block, dict):
                memory_blocks.append(MemoryBlock(**block))
            else:
                memory_blocks.append(block)
        
        # Store each block as a JSON file
        for block in memory_blocks:
            # Generate source URI if not present
            if not block.source_uri:
                block.source_uri = f"logseq://{block.created_at.date().isoformat()}#{block.id}"
            
            # Store block as JSON
            block_path = self.blocks_directory / f"{block.id}.json"
            with open(block_path, "w") as f:
                json.dump(block.to_dict(), f, indent=2)
        
        # Update index
        self._update_index()
    
    def _update_index(self):
        """Update the archive index with all blocks in the archive."""
        # Create index data
        index_metadata = IndexMetadata(
            updated_at=datetime.now()
        )
        
        # Initialize blocks dictionary
        blocks_dict = {}
        
        # Scan blocks directory
        block_files = list(self.blocks_directory.glob("*.json"))
        index_metadata.block_count = len(block_files)
        
        # Read each block file and add to index
        for block_file in block_files:
            with open(block_file, "r") as f:
                block_data = json.load(f)
                
                # Store minimal metadata in the index
                blocks_dict[block_data["id"]] = {
                    "text": block_data["text"],
                    "tags": block_data["tags"],
                    "source_file": block_data["source_file"],
                    "source_uri": block_data["source_uri"],
                    "created_at": block_data["created_at"]
                }
        
        # Create index
        index = ArchiveIndex(
            metadata=index_metadata,
            blocks=blocks_dict
        )
        
        # Write current index
        current_index_path = self.index_directory / "latest.json"
        with open(current_index_path, "w") as f:
            f.write(index.model_dump_json(indent=2))
        
        # Create timestamped version for versioning
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        version_path = self.index_directory / f"index_{timestamp}.json"
        shutil.copy(current_index_path, version_path)
    
    def retrieve_block(self, block_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a block from the archive.
        
        Args:
            block_id: ID of the block to retrieve
            
        Returns:
            Block data as a dictionary or None if not found
        """
        block_path = self.blocks_directory / f"{block_id}.json"
        if not block_path.exists():
            return None
        
        with open(block_path, "r") as f:
            return json.load(f)
    
    def search_by_tags(self, tags: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search archived blocks by tags.
        
        Args:
            tags: List of tags to search for
            limit: Maximum number of results to return
            
        Returns:
            List of matching blocks
        """
        # Load index
        index_path = self.index_directory / "latest.json"
        if not index_path.exists():
            return []
        
        with open(index_path, "r") as f:
            index_data = json.load(f)
        
        # Find matching blocks
        results = []
        for block_id, block_data in index_data["blocks"].items():
            # Check if any of the search tags are in the block tags
            block_tags = block_data["tags"]
            if isinstance(block_tags, str):
                block_tags = [tag.strip() for tag in block_tags.split(",")]
            
            if any(tag in block_tags for tag in tags):
                # Retrieve full block data
                full_block = self.retrieve_block(block_id)
                if full_block:
                    results.append(full_block)
                
                # Stop if we've reached the limit
                if len(results) >= limit:
                    break
        
        return results


class CombinedStorage:
    """
    Combined storage interface that manages both hot and cold storage.
    Provides a unified interface for clients to interact with memory.
    """
    
    def __init__(self, vector_db_dir: str, archive_dir: str):
        """
        Initialize combined storage.
        
        Args:
            vector_db_dir: Directory for vector database
            archive_dir: Directory for archive storage
        """
        self.chroma = ChromaStorage(vector_db_dir)
        self.archive = ArchiveStorage(archive_dir)
    
    def add_blocks(self, blocks: List[Union[MemoryBlock, Dict]]):
        """
        Add blocks to hot storage (ChromaDB).
        
        Args:
            blocks: List of MemoryBlock objects or dictionaries
        """
        self.chroma.add_blocks(blocks)
    
    def archive_blocks(self, block_ids: List[str]):
        """
        Move blocks from hot storage to cold storage.
        
        Args:
            block_ids: List of block IDs to archive
        """
        # Query blocks from ChromaDB
        # Note: This is a simplified approach. In a real implementation,
        # you'd need to reconstruct the full MemoryBlock objects.
        results = self.chroma.collection.get(ids=block_ids)
        
        # Convert to MemoryBlock objects
        blocks = []
        for i, block_id in enumerate(results["ids"]):
            text = results["documents"][i]
            metadata = results["metadatas"][i]
            
            # Parse tags from metadata
            tags = [tag.strip() for tag in metadata["tags"].split(",")]
            
            # Create block
            block = MemoryBlock(
                id=block_id,
                text=text,
                tags=tags,
                source_file=metadata["source"],
                source_uri=metadata.get("source_uri")
            )
            blocks.append(block)
        
        # Archive blocks
        self.archive.archive_blocks(blocks)
        
        # Delete from hot storage
        self.chroma.delete_blocks(block_ids)
    
    def query(self, query_text: str, n_results: int = 5, include_archived: bool = False, 
              filter_tags: Optional[List[str]] = None):
        """
        Query memory blocks.
        
        Args:
            query_text: Text to search for
            n_results: Number of results to return
            include_archived: Whether to include archived blocks
            filter_tags: Optional filter for specific tags
            
        Returns:
            Dictionary with query results
        """
        # Query hot storage
        hot_results = self.chroma.query(query_text, n_results, filter_tags)
        
        # If not including archived, return hot results only
        if not include_archived:
            return hot_results
        
        # If including archived but no tags filter, we can't efficiently search archives
        # as they don't have embeddings for similarity search
        # This is a simplified implementation
        if filter_tags:
            # If we have tags, search archives by tags
            archived_results = self.archive.search_by_tags(filter_tags, limit=n_results)
            
            # Combine results (in a real implementation, you'd need more sophisticated merging)
            # This is just a placeholder approach
            combined_ids = hot_results["ids"][0] + [block["id"] for block in archived_results]
            combined_documents = hot_results["documents"][0] + [block["text"] for block in archived_results]
            combined_metadatas = hot_results["metadatas"][0] + [
                {
                    "tags": ", ".join(block["tags"]) if isinstance(block["tags"], list) else block["tags"],
                    "source": block["source_file"],
                    "archived": True
                }
                for block in archived_results
            ]
            
            # Construct combined results
            return {
                "ids": [combined_ids[:n_results]],
                "documents": [combined_documents[:n_results]],
                "metadatas": [combined_metadatas[:n_results]],
                "distances": hot_results["distances"]  # Note: Archived blocks don't have distances
            }
        
        return hot_results 