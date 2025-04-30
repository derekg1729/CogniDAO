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
        output_data = outputs.get(self.output_key)

        if input_str is None:
            logger.warning(
                f"Input key '{self.input_key}' not found in inputs. Cannot save context."
            )
            return
        if output_data is None:
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

        # Extract output text and metadata from the new dictionary format
        output_str = None
        output_metadata = {}

        if isinstance(output_data, dict):
            if "output" in output_data:
                if isinstance(output_data["output"], dict):
                    # Handle nested dictionary output
                    if "text" in output_data["output"]:
                        output_str = output_data["output"]["text"]
                    else:
                        # Convert the entire output dictionary to string
                        output_str = str(output_data["output"])
                else:
                    # Handle direct string output
                    output_str = str(output_data["output"])

                # Extract metadata if present
                if "metadata" in output_data:
                    output_metadata = output_data["metadata"]
            else:
                # Fallback to string representation if not in expected format
                output_str = str(output_data)
        else:
            output_str = str(output_data)

        try:
            # Prepare input for the tool
            tool_input = {
                "input_text": input_str,
                "output_text": output_str,
                "session_id": inputs.get("session_id"),
                "model": inputs.get("model"),
                "token_count": inputs.get("token_count"),
                "latency_ms": inputs.get("latency"),
                "tags": self.save_tags.copy(),
            }

            # Add adapter-specific metadata
            metadata = {
                "input_key": self.input_key,
                "output_key": self.output_key,
                "adapter_type": self.__class__.__name__,
                "timestamp": datetime.now().isoformat(),
            }

            # Add model information if available
            if "model" in inputs:
                metadata["model"] = inputs["model"]

            # Add session information if available
            if "session_id" in inputs:
                metadata["session_id"] = inputs["session_id"]

            # Add token counts if available
            if "token_count" in inputs:
                metadata["token_count"] = inputs["token_count"]

            # Add latency if available
            if "latency" in inputs:
                metadata["latency_ms"] = inputs["latency"]

            # Add output metadata
            metadata.update(output_metadata)

            # Use the LogInteractionBlockTool
            result = log_interaction_block_tool(
                **tool_input, memory_bank=self.memory_bank, metadata=metadata
            )

            if result["success"]:
                logger.info(f"Successfully saved context as memory block: {result['id']}")
            else:
                logger.error(
                    f"Failed to save context via LogInteractionBlockTool: {result.get('error', 'Unknown error')}"
                )

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
