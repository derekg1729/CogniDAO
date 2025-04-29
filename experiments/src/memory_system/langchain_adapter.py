"""
LangChain BaseMemory adapter for the Cogni StructuredMemoryBank.
"""

import sys
from pathlib import Path
from typing import Dict, Any, List
import logging
import datetime

from langchain_core.memory import BaseMemory

# Update the import to use pydantic directly instead of langchain_core.pydantic_v1
from pydantic import Field, root_validator
from experiments.src.memory_system.structured_memory_bank import StructuredMemoryBank
from experiments.src.memory_system.schemas.memory_block import MemoryBlock

# --- Path Setup --- START - Ensure project root is in path for imports
script_dir = Path(__file__).parent
project_root_dir = script_dir.parent.parent.parent
if str(project_root_dir) not in sys.path:
    sys.path.insert(0, str(project_root_dir))
# --- Path Setup --- END

logger = logging.getLogger(__name__)


class CogniStructuredMemoryAdapter(BaseMemory):
    """
    LangChain BaseMemory adapter wrapping StructuredMemoryBank.

    This adapter allows LangChain agents/chains to interact with the
    persistent structured memory provided by StructuredMemoryBank.
    It retrieves relevant memory blocks based on input and saves
    conversation context as new memory blocks.
    """

    # Core component
    memory_bank: StructuredMemoryBank

    # Configuration for LangChain interaction
    memory_key: str = "relevant_blocks"  # Key LangChain expects for memory output
    input_key: str = "input"  # Key in input dict holding the query
    output_key: str = "output"  # Key in output dict holding the response

    # Configuration for memory operations
    save_interaction_type: str = "interaction"  # Default type for saved context
    save_tags: List[str] = Field(default_factory=list)  # Optional fixed tags
    top_k_retrieval: int = 5  # Number of blocks to retrieve in load_memory_variables

    # --- Pydantic V1 style setup for BaseMemory compatibility ---
    class Config:
        # Allow non-Pydantic types like StructuredMemoryBank
        arbitrary_types_allowed = True

    @root_validator(pre=True)
    def check_memory_bank_provided(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure memory_bank is provided during initialization."""
        if "memory_bank" not in values or not isinstance(
            values["memory_bank"], StructuredMemoryBank
        ):
            raise ValueError("An instance of StructuredMemoryBank must be provided.")
        return values

    # --- BaseMemory Interface Implementation (Stubs) ---

    @property
    def memory_variables(self) -> List[str]:
        """Defines the variables this memory provider will return."""
        return [self.memory_key]

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, str]:
        """Load relevant memory blocks based on the input.

        Retrieves the query from the inputs dictionary, uses the memory bank's
        semantic query capability, formats the results using the helper method,
        and returns them under the designated memory key.
        """
        logger.debug(f"Loading memory variables for input keys: {list(inputs.keys())}")

        query_text = inputs.get(self.input_key)
        if not query_text:
            logger.warning(
                f"Input key '{self.input_key}' not found in inputs or is empty. Cannot query memory."
            )
            # Return empty string or specific message based on desired behavior
            return {self.memory_key: "Input query not provided."}

        try:
            # Call the memory bank's semantic search
            logger.info(
                f"Querying memory bank with text: '{query_text[:50]}...' (top_k={self.top_k_retrieval})"
            )
            relevant_blocks = self.memory_bank.query_semantic(
                query_text=query_text, top_k=self.top_k_retrieval
            )

            # Format the retrieved blocks into markdown
            formatted_markdown = self._format_blocks_to_markdown(relevant_blocks)
            logger.info(
                f"Formatted {len(relevant_blocks)} blocks into markdown for key '{self.memory_key}'."
            )

            # Return the formatted string under the correct key
            return {self.memory_key: formatted_markdown}

        except Exception as e:
            logger.error(f"Error querying memory bank or formatting blocks: {e}", exc_info=True)
            # Return an error message or empty string in case of failure
            return {self.memory_key: f"Error loading memory: {e}"}

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """Save the interaction context into the memory bank.

        Extracts input and output, sanitizes them to prevent recursive memory growth,
        formats them into a new MemoryBlock, and uses the memory bank's create_memory_block method to persist it.

        Enhanced features:
        - Sanitizes inputs/outputs to remove memory placeholders and prevent recursive memory growth
        - Extracts and adds session information when available
        - Auto-generates tags based on content and session IDs
        - Enriches metadata with model information, timestamps, and other analytics data
        """
        logger.debug(
            f"Saving context for input keys: {list(inputs.keys())}, output keys: {list(outputs.keys())}"
        )

        input_str = inputs.get(self.input_key)
        output_str = outputs.get(self.output_key)

        if input_str is None:
            logger.warning(
                f"Input key '{self.input_key}' not found in inputs. Cannot save context."
            )
            return
        if output_str is None:
            logger.warning(
                f"Output key '{self.output_key}' not found in outputs. Cannot save context."
            )
            return

        # --- SANITIZATION STEP ---
        # Remove memory placeholders to prevent recursive memory storage
        if isinstance(input_str, str) and self.memory_key in input_str:
            logger.warning(
                f"Sanitizing input_str: removing '{self.memory_key}' placeholder before saving."
            )
            input_str = input_str.replace(f"{{{self.memory_key}}}", "").strip()

        # Handle dictionary output from LLM chains
        if isinstance(output_str, dict):
            # Extract just the text content if available
            if "text" in output_str:
                output_str = output_str["text"]
            else:
                # Fallback to string representation
                output_str = str(output_str)

        # Format the block text using the standard template
        block_text = f"[Interaction Record]\nInput: {input_str}\nOutput: {output_str}"

        # --- DYNAMIC TAGGING ---
        # Prepare tags (start with fixed tags, can be expanded with dynamic ones)
        tags = []
        if hasattr(self, "save_tags") and isinstance(self.save_tags, list):
            tags = self.save_tags.copy()

        # Extract session ID if available in inputs
        session_id = None
        if "session_id" in inputs:
            session_id = inputs["session_id"]
            tags.append(f"session:{session_id}")

        # Create timestamp once and reuse formatted versions
        timestamp = datetime.datetime.now()
        timestamp_str = timestamp.strftime("%Y%m%d")
        iso_timestamp = timestamp.isoformat()

        # Add timestamp tag for time-based filtering
        tags.append(f"date:{timestamp_str}")

        # Add interaction type tag
        tags.append(f"type:{self.save_interaction_type}")

        # --- ENHANCED METADATA ---
        # Build enriched metadata dictionary
        metadata = {
            "input_key": self.input_key,
            "output_key": self.output_key,
            "adapter_type": self.__class__.__name__,
            "timestamp": iso_timestamp,
        }

        # Add model information if available
        if "model" in inputs:
            metadata["model"] = inputs["model"]

        # Add session information if available
        if session_id:
            metadata["session_id"] = session_id

        # Add token counts if available
        if "token_count" in inputs:
            metadata["token_count"] = inputs["token_count"]

        # Add latency if available
        if "latency" in inputs:
            metadata["latency_ms"] = inputs["latency"]

        try:
            # Create a new MemoryBlock object with enhanced metadata and tags
            new_block = MemoryBlock(
                type=self.save_interaction_type,
                text=block_text,
                tags=tags,
                metadata=metadata,
                state="draft",
                visibility="internal",
                block_version=1,
                # Let created_at, updated_at, id, schema_version be handled by defaults/bank
            )

            # Call the memory bank's create method
            logger.info(f"Creating new memory block of type '{new_block.type}' via memory bank.")
            success = self.memory_bank.create_memory_block(new_block)

            if success:
                logger.info(
                    f"Successfully saved enhanced context as memory block: {new_block.id}, with tags: {tags}"
                )
            else:
                # create_memory_block logs errors internally, but we add one here too
                logger.error(
                    f"Failed to save context via memory_bank.create_memory_block for block type '{new_block.type}'"
                )

        except Exception as e:
            logger.error(f"Error creating MemoryBlock or saving context: {e}", exc_info=True)

    def clear(self) -> None:
        """Clear memory - currently a no-op or raises NotImplementedError."""
        logger.warning(
            "CogniStructuredMemoryAdapter.clear() called, but clearing strategy is not implemented. Raising NotImplementedError."
        )
        raise NotImplementedError(
            "Clearing strategy for CogniStructuredMemoryAdapter is not defined."
        )

    # --- Helper Methods (Stubs) ---

    def _format_blocks_to_markdown(self, blocks: List[MemoryBlock]) -> str:
        """Formats a list of MemoryBlocks into a single markdown string.

        Follows the format specified in task-3.2:
        ## Memory Block: {block.id}
        **Type**: {block.type}
        **Tags**: {', '.join(block.tags)}
        **Created**: {block.created_at}

        {block.text}
        """
        if not blocks:
            return "No relevant memory blocks found."

        markdown_parts = []
        for block in blocks:
            tags_str = ", ".join(block.tags) if block.tags else "None"
            created_str = block.created_at.isoformat() if block.created_at else "Unknown"
            block_md = (
                f"## Memory Block: {block.id}\n"
                f"**Type**: {block.type}\n"
                f"**Tags**: {tags_str}\n"
                f"**Created**: {created_str}\n"
                f"\n"
                f"{block.text}"
            )
            markdown_parts.append(block_md)

        # Join all markdown parts with a double newline for separation
        return "\n\n".join(markdown_parts)
