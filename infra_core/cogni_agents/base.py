"""
Refactored CogniAgent base module
Replaces memory_client with CogniMemoryBank
"""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# Import the centralized constant
from infra_core.constants import MEMORY_BANKS_ROOT

# Import BaseCogniMemory for type hinting
from infra_core.memory.memory_bank import CogniMemoryBank, BaseCogniMemory


class CogniAgent(ABC):
    """
    Base abstract class for Cogni Agents.
    Provides core functionality like spirit/context loading and action recording.
    Requires a memory bank instance to be passed during initialization.
    """

    def __init__(self, name: str, spirit_path: Path, agent_root: Path, memory: BaseCogniMemory, project_root_override: Optional[Path] = None):
        """
        Initializes the CogniAgent.

        Args:
            name (str): The unique name of the agent instance.
            spirit_path (Path): Path to the agent's specific spirit guide markdown file (relative to project root).
            agent_root (Path): Root directory for agent-specific non-memory outputs (if any).
            memory (BaseCogniMemory): The memory bank instance this agent should use for runtime operations.
            project_root_override (Optional[Path]): Optional override for the project root path.
        """
        self.name = name
        self.spirit_path = spirit_path # Path relative to project root, used by load_spirit
        self.agent_root = agent_root # Path for potential external outputs, TBD if needed
        self.memory = memory # Assign the provided memory bank instance
        self.spirit = None
        self.core_context = None

        # Determine project root for fallbacks when loading static context/guides
        self.project_root = project_root_override or Path(__file__).resolve().parent.parent.parent

        # REMOVED internal memory bank creation logic
        # The agent now expects the memory bank for its operational context
        # (e.g., flow session bank) to be provided externally.

        # Load agent-specific data (uses methods that will be refactored next)
        self.load_spirit()
        self.load_core_context()

    def load_spirit(self):
        """Loads the agent's specific spirit guide, attempting to read from the agent's memory bank first, falling back to the canonical path and seeding the bank."""
        # Determine the expected filename convention (e.g., guide_agent-name.md)
        # Uses the filename part of the spirit_path (e.g., "git-cogni" from ".../git-cogni.md")
        spirit_name = self.spirit_path.stem
        bank_filename = f"guide_{spirit_name}.md"

        # Determine the canonical fallback path
        fallback_path = self.project_root / self.spirit_path

        # Use the agent's own memory bank instance (self.memory)
        spirit_text = self.memory.load_or_seed_file(
            file_name=bank_filename,
            fallback_path=fallback_path
        )

        if spirit_text is not None:
            self.spirit = spirit_text
        else:
            # Raise an error if spirit couldn't be loaded/seeded
            error_msg = (
                f"Spirit guide '{bank_filename}' could not be loaded from bank "
                f"or seeded from fallback path: {fallback_path}"
            )
            raise FileNotFoundError(error_msg)
        
        # OLD DIRECT READ LOGIC:
        # # Construct the absolute path to the spirit file
        # spirit_full_path = self.project_root / self.spirit_path
        # try:
        #     # Read directly from the canonical file path
        #     self.spirit = spirit_full_path.read_text()
        # except FileNotFoundError:
        #     print(f"Warning: Spirit guide file not found at expected path: {spirit_full_path}")
        #     self.spirit = "⚠️ Spirit guide not found."
        # except Exception as e:
        #     print(f"Error reading spirit guide file {spirit_full_path}: {e}")
        #     self.spirit = "⚠️ Error loading spirit guide."

    def load_core_context(self):
        """Loads core context documents (Charter, Manifesto, Core Spirit) from the central core memory bank."""
        # Define the location of the central core memory bank.
        # Use the absolute path defined in constants, do NOT prepend self.project_root
        core_bank_root = Path(MEMORY_BANKS_ROOT)
        core_bank = CogniMemoryBank(
            memory_bank_root=core_bank_root,
            project_name="core", 
            session_id="main"
        )
        
        # Core documents expected in the central bank
        # Mapping: filename in core bank -> key in context dict / section header
        doc_files = {
            "CHARTER.md": "CHARTER.md",
            "MANIFESTO.md": "MANIFESTO.md",
            "LICENSE.md": "LICENSE.md", 
            "README.md": "README.md",
            "guide_cogni-core-spirit.md": "cogni-core-spirit" # Changed filename to match guide convention
        }
        
        # Define fallback paths for core documents relative to project root
        # Define BEFORE the loop so it's accessible in the error message formatting
        fallback_map = {
            "CHARTER.md": self.project_root / "CHARTER.md",
            "MANIFESTO.md": self.project_root / "MANIFESTO.md",
            "LICENSE.md": self.project_root / "LICENSE.md",
            "README.md": self.project_root / "README.md",
            # Assuming the canonical source for the core spirit guide is here:
            "guide_cogni-core-spirit.md": self.project_root / "infra_core/cogni_spirit/spirits/cogni-core-spirit.md"
        }

        context_parts = ["# Cogni Core Documents"]
        metadata = {}

        # Define critical core files that MUST exist
        critical_files = ["CHARTER.md", "guide_cogni-core-spirit.md"]

        for bank_filename, context_key in doc_files.items():
            # Read directly from the core_bank instance, using fallback if needed
            text = core_bank.load_or_seed_file(
                file_name=bank_filename,
                fallback_path=fallback_map.get(bank_filename) # Get path from map
            )

            if text:
                context_parts.append(f"## {context_key}\n\n{text}")
                metadata[context_key] = {"length": len(text)}
            else:
                # Handle missing core documents
                # Construct the fallback path string safely, handling None
                fallback_path_str = str(fallback_map.get(bank_filename)) if fallback_map.get(bank_filename) else "[No Fallback Defined]"
                error_msg = (
                    f"Core document '{bank_filename}' could not be loaded from core bank "
                    f"or seeded from fallback path: {fallback_path_str}"
                )
                if bank_filename in critical_files:
                    raise FileNotFoundError(error_msg)
                else:
                    # Print warning for non-critical missing files
                    print(f"Warning: {error_msg}")

        # File system fallback and writing to session memory are REMOVED.

        full_context = "\n".join(context_parts)
        # Store the loaded context and metadata on the agent instance
        self.core_context = {
            "context": {"role": "system", "content": full_context},
            "metadata": metadata
        }

    def get_guide_for_task(self, task: str, guides: Optional[List[str]] = None) -> Dict[str, Any]:
        """Gets context from specified spirit guides, reading them from the central core memory bank."""
        guides = guides or ["cogni-core-spirit"] # Default guide
        context_parts = [f"# Cogni Spirit Context for: {task}"]

        # Define the location of the central core memory bank, respecting project_root_override
        core_bank_root = self.project_root / "infra_core/memory/banks"
        core_bank = CogniMemoryBank(
            memory_bank_root=core_bank_root, # Use calculated path
            project_name="core",
            session_id="main"
        )

        for guide in guides:
            # Convention: Filename in core bank is "guide_<guide_name>.md"
            core_bank_filename = f"guide_{guide}.md"
            
            # Read directly from the core_bank instance
            content = core_bank._read_file(core_bank_filename)

            # Filesystem fallback and writing to session memory are REMOVED.

            if content:
                context_parts.append(f"## {guide}\n\n{content}")
            else:
                 # Log a warning if a specific guide is missing from the central bank
                print(f"Warning: Guide '{core_bank_filename}' not found in core memory bank at {core_bank_root}.") # Updated log

        # Return the combined context as a dictionary suitable for system messages
        return {"role": "system", "content": "\n".join(context_parts)}

    def prepare_input(self, *args, **kwargs):
        return {}

    @abstractmethod
    def act(self, prepared_input: Dict[str, Any]) -> Dict[str, Any]:
        pass

    def record_action(self, output: Dict[str, Any], subdir: str = "sessions", prefix: str = "") -> None:
        """
        Formats output as Markdown, saves it to a file within the **memory bank session**,
        and logs a pointer to it in the session's decisions.jsonl.

        Args:
            output (Dict[str, Any]): Data returned by the agent's act method.
            subdir (str): **UNUSED** - Kept for signature compatibility if needed elsewhere, but ignored.
            prefix (str): Prefix for the filename (e.g., 'thought_', 'reflection_').

        Returns:
            None: This method now primarily performs logging within the memory bank.
        """
        # 1. Format output data as Markdown
        output_markdown = self.format_output_markdown(output)
        
        # 2. Generate descriptive filename for the Markdown file
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        agent_name_slug = self.__class__.__name__ # Get agent class name
        markdown_filename = f"{agent_name_slug}_{prefix}{timestamp}.md" 

        # 3. Save the Markdown file directly into the current memory bank session
        try:
            # Use write_context to save the non-JSON markdown content
            self.memory.write_context(markdown_filename, output_markdown, is_json=False) 
        except Exception as e:
             # Log error specific to writing context file
             print(f"Error writing memory context file {markdown_filename}: {e}") # Replace with logger
             # Decide if we should still log the decision or return/raise
             # For now, we'll proceed to log the decision attempt

        # 4. Log metadata (including a pointer to the MD file) to decisions.jsonl
        try:
            self.memory.log_decision({
                "agent_name": self.name, 
                "agent_class": agent_name_slug, 
                "action_type": prefix, # Log the type of action
                "markdown_filename": markdown_filename, # Pointer to the saved MD file
                # Timestamp added automatically by log_decision
            })
        except Exception as e:
             # Log error specific to logging decision
             print(f"Error logging decision for action {markdown_filename}: {e}") # Replace with logger

        # 5. External file writing is REMOVED
        # No longer returning the external path
        return None

    def format_output_markdown(self, data: Dict[str, Any]) -> str:
        lines = [f"# CogniAgent Output — {self.name}\n", f"**Generated**: {datetime.utcnow().isoformat()}\n"]
        for k, v in data.items():
            if isinstance(v, dict):
                lines.append(f"## {k}")
                for sub_k, sub_v in v.items():
                    lines.append(f"**{sub_k}**:\n{sub_v}\n")
            else:
                lines.append(f"## {k}\n{v}\n")
        
        lines.append("---")
        lines.append(f"> Agent: {self.name}")
        lines.append(f"> Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        return "\n".join(lines)