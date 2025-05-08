"""
CogniMemoryStorage: CrewAI memory implementation for Cogni's memory system.

This class adapts Cogni's StructuredMemoryBank to work with CrewAI's memory system,
enabling CrewAI agents to persist and retrieve thoughts using Cogni's memory system.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import uuid4

from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.schemas.memory_block import MemoryBlock

logger = logging.getLogger(__name__)

# Constants
MEMORY_TYPE = "knowledge"  # Default type for CrewAI thoughts


class CogniMemoryStorage:
    """CrewAI memory implementation using Cogni's StructuredMemoryBank."""

    def __init__(self, memory_bank: StructuredMemoryBank):
        """Initialize the memory storage with a StructuredMemoryBank instance.

        Args:
            memory_bank: The StructuredMemoryBank instance to use for storage and retrieval.
        """
        self.memory_bank = memory_bank
        logger.info("Initialized CogniMemoryStorage with StructuredMemoryBank")

    def save(self, thought: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Save a thought to the memory system.

        Args:
            thought: The text content to save.
            metadata: Optional metadata to associate with the thought.

        Returns:
            bool: True if the thought was successfully saved, False otherwise.
        """
        try:
            # Create a MemoryBlock from the thought
            block = MemoryBlock(
                id=f"crewai_{uuid4().hex}",
                type=MEMORY_TYPE,
                text=thought,
                tags=["crewai", "thought"],
                metadata=metadata or {},
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            # Save using StructuredMemoryBank
            success = self.memory_bank.create_memory_block(block)
            if success:
                logger.info(f"Successfully saved CrewAI thought: {block.id}")
            else:
                logger.error(f"Failed to save CrewAI thought: {block.id}")
            return success

        except Exception as e:
            error_msg = f"Error saving CrewAI thought: {e}"
            logger.error(error_msg, exc_info=True)
            return False

    def search(self, query: str, top_k: int = 5) -> List[str]:
        """Search for thoughts using semantic search.

        Args:
            query: The search query text.
            top_k: Maximum number of results to return.

        Returns:
            List[str]: List of matching thought texts.
        """
        try:
            # Limit top_k to reasonable range
            top_k = min(top_k, 20)

            # Use StructuredMemoryBank's semantic search
            blocks = self.memory_bank.query_semantic(query, top_k=top_k)

            # Extract text content from blocks
            thoughts = [block.text for block in blocks]
            logger.info(f"Found {len(thoughts)} thoughts matching query: {query}")
            return thoughts

        except Exception as e:
            logger.error(f"Error searching CrewAI thoughts: {e}", exc_info=True)
            return []

    def reset(self) -> bool:
        """Reset the memory system.

        Note:
            This method is not yet implemented. It will eventually:
            1. Clear LlamaIndex session cache
            2. Create new Dolt branch named agent_{timestamp}

        Returns:
            bool: False since the functionality is not yet implemented.
        """
        logger.warning("Reset functionality not yet implemented")
        return False
