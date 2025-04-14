"""
Refactored CogniAgent base module
Replaces memory_client with CogniMemoryBank
"""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from infra_core.memory.memory_bank import CogniMemoryBank


class CogniAgent(ABC):
    """
    Abstract base class for all Cogni agents.
    Each agent represents an autonomous entity with a specific role and spirit guide.
    """

    def __init__(self, name: str, spirit_path: Path, agent_root: Path, memory_bank_root_override: Optional[Path] = None, project_root_override: Optional[Path] = None):
        self.name = name
        self.spirit_path = spirit_path
        self.agent_root = agent_root
        self.spirit = None
        self.core_context = None

        # Determine project root for fallbacks
        self.project_root = project_root_override or Path(__file__).resolve().parent.parent.parent

        # Resolve memory bank location
        if memory_bank_root_override:
            memory_bank_root = memory_bank_root_override
        else:
            # Use self.project_root for consistency if no override
            memory_bank_root = self.project_root / "infra_core/memory/memory_banks"

        # Initialize memory bank (one folder per agent)
        self.memory = CogniMemoryBank(
            memory_bank_root=memory_bank_root,
            project_name="cogni_agents",
            session_id=self.name  # simple and stable session id
        )

        # Load agent-specific data
        self.load_spirit()
        self.load_core_context()

    def load_spirit(self):
        """Load the spirit guide contents from markdown using memory bank."""
        # Attempt to read from memory first using the filename
        spirit_text = self.memory._read_file(self.spirit_path.name)
        
        # If not in memory, check filesystem relative to project_root
        # Construct the potential path relative to the (potentially overridden) project root
        fallback_path = self.project_root / self.spirit_path 
        
        if not spirit_text and fallback_path.exists():
            try:
                spirit_text = fallback_path.read_text()
                # Write to memory bank if successfully read from filesystem
                self.memory.write_context(self.spirit_path.name, spirit_text)
            except Exception as e:
                # Log error reading fallback file
                print(f"Error reading spirit fallback file {fallback_path}: {e}") # Replace with logger
                spirit_text = None # Ensure spirit is None if read fails

        # Set final spirit value
        self.spirit = spirit_text or "⚠️ Spirit guide not found."

    def load_core_context(self):
        """Load core context documents (charter, manifesto, etc)."""
        doc_files = ["CHARTER.md", "MANIFESTO.md", "LICENSE.md", "README.md"]
        context_parts = ["# Cogni Core Documents"]
        metadata = {}
        
        # Determine the project root to find the core files
        # Use the instance's project_root attribute
        project_root_for_core_files = self.project_root

        for fname in doc_files:
            text = self.memory._read_file(fname)
            if not text:
                # Construct the absolute path relative to the project root
                file_path = project_root_for_core_files / fname
                if file_path.exists():
                    text = file_path.read_text()
                    self.memory.write_context(fname, text)
            if text:
                context_parts.append(f"## {fname}\n\n{text}")
                metadata[fname] = {"length": len(text)}

        # Load core spirit
        core_spirit_relative_path = "infra_core/cogni_spirit/spirits/cogni-core-spirit.md"
        core_spirit_filename = "core_spirit.md" # Use a simplified filename for the memory bank
        spirit_text = self.memory._read_file(core_spirit_filename)
        if not spirit_text:
            spirit_path_abs = project_root_for_core_files / core_spirit_relative_path
            if spirit_path_abs.exists():
                spirit_text = spirit_path_abs.read_text()
                self.memory.write_context(core_spirit_filename, spirit_text)
        if spirit_text:
            context_parts.append(f"## cogni-core-spirit\n\n{spirit_text}")
            metadata["core_spirit"] = {"length": len(spirit_text)}

        full_context = "\n".join(context_parts)
        self.core_context = {
            "context": {"role": "system", "content": full_context},
            "metadata": metadata
        }

    def get_guide_for_task(self, task: str, guides: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get context from specific spirit guides for a task."""
        guides = guides or ["cogni-core-spirit"]
        context_parts = [f"# Cogni Spirit Context for: {task}"]

        # Determine the project root to find the guide files
        # Use the instance's project_root attribute
        project_root_for_guides = self.project_root

        for guide in guides:
            guide_filename_in_memory = f"guide_{guide}.md" # Filename for memory bank
            guide_relative_path = f"infra_core/cogni_spirit/spirits/{guide}.md" # Relative path in repo
            
            content = self.memory._read_file(guide_filename_in_memory)
            if not content:
                guide_path_abs = project_root_for_guides / guide_relative_path
                if guide_path_abs.exists():
                    content = guide_path_abs.read_text()
                    self.memory.write_context(guide_filename_in_memory, content)
            if content:
                context_parts.append(f"## {guide}\n\n{content}")

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