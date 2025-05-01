"""
LangChain BaseMemory adapter for the Cogni StructuredMemoryBank.
"""

import sys
from pathlib import Path
from typing import Dict, Any, List
import logging
from datetime import datetime

from langchain_core.memory import BaseMemory

# Update the import to use pydantic directly instead of langchain_core.pydantic_v1
from pydantic import Field, root_validator
from experiments.src.memory_system.structured_memory_bank import StructuredMemoryBank
from experiments.src.memory_system.schemas.memory_block import MemoryBlock
from .tools.agent_facing.log_interaction_block_tool import log_interaction_block_tool
from .schemas.metadata.log import LogMetadata

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
    save_interaction_type: str = "log"  # Default type for saved context
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
        """Load relevant memory blocks based on input."""
        # Extract input text
        input_text = inputs.get(self.input_key)
        if not input_text:
            logger.warning(f"No input text found for key '{self.input_key}'")
            return {self.memory_key: "Input query not provided."}

        # Query memory bank for relevant blocks
        try:
            relevant_blocks = self.memory_bank.query_semantic(
                query_text=input_text, top_k=self.top_k_retrieval
            )
            return {self.memory_key: self._format_blocks_to_markdown(relevant_blocks)}
        except Exception as e:
            logger.error(f"Error querying memory blocks: {e}", exc_info=True)
            return {self.memory_key: f"Error loading memory: {e}"}

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """Save the interaction context into the memory bank.

        Uses the LogInteractionBlockTool to create a new memory block with
        enhanced metadata and tagging.
        """
        logger.debug(
            f"Saving context for input keys: {list(inputs.keys())}, output keys: {list(outputs.keys())}"
        )

        input_str = inputs.get(self.input_key)

        # Try both the configured output_key and the common default 'text' key
        original_output = outputs.get(self.output_key) or outputs.get("text")

        if input_str is None:
            logger.warning(
                f"Input key '{self.input_key}' not found in inputs. Cannot save context."
            )
            return
        if original_output is None:
            logger.warning(
                f"Neither '{self.output_key}' nor 'text' key found in outputs. Cannot save context."
            )
            return

        # --- SANITIZATION STEP ---
        # Remove memory placeholders to prevent recursive memory storage
        if isinstance(input_str, str) and self.memory_key in input_str:
            logger.warning(
                f"Sanitizing input_str: removing '{self.memory_key}' placeholder before saving."
            )
            input_str = input_str.replace(f"{{{self.memory_key}}}", "").strip()

        try:
            # Prepare input for the LogInteractionBlockTool
            tool_input = {
                "input_text": input_str,
                "output_text": original_output,
                # Map LangChain context keys to LogInteractionBlockInput fields
                "model": inputs.get("model"),
                "token_count": inputs.get("token_count"),
                "latency_ms": inputs.get("latency"),  # Input key from chain is 'latency'
                "tags": self.save_tags + [f"date:{datetime.now().strftime('%Y%m%d')}"],
                # Pass session_id as x_session_id
                "x_session_id": inputs.get("session_id"),
                # Pass parent_block_id if available in inputs
                "x_parent_block_id": inputs.get("parent_block_id"),
                # Set created_by for x_agent_id fallback in core tool
                "created_by": inputs.get("user_id", "agent"),
                # Metadata dict for LogInteractionBlockTool specific extras (currently none)
                # User-defined metadata should be passed within inputs["metadata"] if needed
                "metadata": inputs.get("metadata", {}),
            }

            # Add session tag if session ID exists
            if tool_input["x_session_id"]:
                tool_input["tags"].append(f"session:{tool_input['x_session_id']}")

            # Final check for None output_text after processing
            if tool_input.get("output_text") is None:
                logger.warning(
                    f"Neither '{self.output_key}' nor recognized text keys found in outputs. Cannot save context."
                )
                return

            # --- Metadata Filtering --- START
            # Filter the combined metadata to only include keys valid for LogMetadata
            # This prevents ValidationErrors due to `extra = forbid`
            valid_metadata_keys = set(LogMetadata.model_fields.keys())
            if isinstance(tool_input.get("metadata"), dict):
                filtered_user_metadata = {
                    k: v for k, v in tool_input["metadata"].items() if k in valid_metadata_keys
                }
                tool_input["metadata"] = filtered_user_metadata
            # --- Metadata Filtering --- END

            # Clean up None values before calling the tool
            tool_input_cleaned = {k: v for k, v in tool_input.items() if v is not None}

            # Use the tool to create the memory block
            logger.debug(f"Calling log_interaction_block_tool with input: {tool_input_cleaned}")
            result = log_interaction_block_tool(memory_bank=self.memory_bank, **tool_input_cleaned)
            if not result.success:
                logger.error(f"Failed to create memory block: {result.error}")
            else:
                logger.info(f"Successfully saved context as memory block: {result.id}")
        except Exception as e:
            logger.error(f"Error saving context: {e}", exc_info=True)

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
        """Format memory blocks into a markdown string."""
        if not blocks:
            return "No relevant memory blocks found."

        lines = []
        for block in blocks:
            # Add block ID and type
            lines.append(f"### Memory Block {block.id} ({block.type})")

            # Add tags if present
            if block.tags:
                lines.append(f"Tags: {', '.join(block.tags)}")

            # Add creation date
            lines.append(f"Created: {block.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

            # Add the main content
            lines.append("\nContent:")
            lines.append(block.text)

            # Add a separator between blocks
            lines.append("\n---\n")

        return "\n".join(lines)
