"""
CogniAgent base module

This module provides the abstract base class for all Cogni agents.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from infra_core.memory.memory_client import CogniMemoryClient


class CogniAgent(ABC):
    """
    Abstract base class for all Cogni agents.
    
    Each agent represents an autonomous entity with a specific role and spirit guide.
    Agents load their spirit guide, prepare inputs, act based on their guide,
    and record their actions.
    """
    
    def __init__(self, name: str, spirit_path: Path, agent_root: Path):
        """
        Initialize a new CogniAgent.
        
        Args:
            name: The name of the agent
            spirit_path: Path to the spirit guide markdown file
            agent_root: Root directory for agent outputs
        """
        self.name = name
        self.spirit_path = spirit_path
        self.agent_root = agent_root
        self.spirit = None
        self.core_context = None
        
        # Initialize memory client
        self.memory_client = CogniMemoryClient(
            chroma_path="infra_core/memory/chroma",
            archive_path="infra_core/memory/archive",
            collection_name="cogni-memory"
        )

        # Load the spirit guide
        self.load_spirit()

    def load_spirit(self):
        """Load the spirit guide contents from markdown using memory client."""
        try:
            spirit_path_str = str(self.spirit_path)
            self.spirit = self.memory_client.get_page(spirit_path_str)
            if not self.spirit:
                # Fallback to direct file access if memory client doesn't find it
                if self.spirit_path.exists():
                    self.spirit = self.spirit_path.read_text()
                else:
                    self.spirit = "⚠️ Spirit guide not found."
        except Exception:
            # Fallback to direct file access on any error
            if self.spirit_path.exists():
                self.spirit = self.spirit_path.read_text()
            else:
                self.spirit = "⚠️ Spirit guide not found."

    def load_core_context(self):
        """
        Load core context documents using memory client.
        
        This loads the charter, manifesto, and other core documents
        for use by agents when making decisions.
        """
        # Document paths
        doc_paths = {
            "CHARTER": "CHARTER.md",
            "MANIFESTO": "MANIFESTO.md",
            "LICENSE": "LICENSE.md",
            "README": "README.md"
        }
        
        # Dictionary to hold document metadata
        metadata = {"core_docs": {}}
        
        # Build context with document content
        document_count = 0
        context_parts = ["# Cogni Core Documents\n"]
        
        # Load each core document
        for doc_name, doc_path in doc_paths.items():
            try:
                content = self.memory_client.get_page(doc_path)
                if content:
                    context_parts.append(f"## {doc_name}\n\n{content}\n")
                    metadata["core_docs"][doc_name] = {
                        "length": len(content)
                    }
                    document_count += 1
                else:
                    metadata["core_docs"][doc_name] = {
                        "length": 0,
                        "error": "File not found or empty"
                    }
            except Exception as e:
                context_parts.append(f"## {doc_name}\n\nError loading document: {str(e)}\n")
                metadata["core_docs"][doc_name] = {
                    "length": 0,
                    "error": str(e)
                }
        
        # Add cogni-core-spirit
        try:
            core_spirit = self.memory_client.get_page("infra_core/cogni_spirit/spirits/cogni-core-spirit.md")
            if core_spirit:
                context_parts.append(f"## cogni-core-spirit\n\n{core_spirit}\n")
                metadata["core_spirit"] = {
                    "length": len(core_spirit)
                }
                document_count += 1
        except Exception:
            # Silently skip if core spirit guide not found
            pass
        
        # Combine all context parts
        full_context = "\n".join(context_parts)
        
        # Calculate totals for backward compatibility
        metadata["total_core_docs_length"] = sum(doc.get("length", 0) for doc in metadata["core_docs"].values())
        metadata["total_context_length"] = len(full_context)
        metadata["total_sections"] = document_count
        
        # Format for openai provider (for backward compatibility)
        formatted_context = {
            "role": "system",
            "content": full_context
        }
        
        # Store in the format expected by agents
        self.core_context = {
            "context": formatted_context,
            "metadata": metadata
        }

    def get_guide_for_task(self, task: str, guides: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get a formatted guide context for a specific task.
        
        Args:
            task: Description of the task
            guides: List of guide names to include (without .md extension)
                    Default is ["cogni-core-spirit"]
                    
        Returns:
            Dictionary with formatted guide content for OpenAI
        """
        if guides is None:
            guides = ["cogni-core-spirit"]
        
        # Build context parts
        context_parts = [f"# Cogni Spirit Context for: {task}\n"]
        
        # Load each guide
        for guide in guides:
            try:
                guide_path = f"infra_core/cogni_spirit/spirits/{guide}.md"
                guide_content = self.memory_client.get_page(guide_path)
                if guide_content:
                    context_parts.append(f"## {guide}\n\n{guide_content}\n")
            except Exception:
                # Skip if guide not found
                pass
        
        # Combine context parts
        full_context = "\n".join(context_parts)
        
        # Format for openai (for backward compatibility)
        return {
            "role": "system",
            "content": full_context
        }

    def prepare_input(self, *args, **kwargs):
        """Prepare inputs for the agent to act upon. Override per agent."""
        return {}

    @abstractmethod
    def act(self, prepared_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform the agent's primary behavior. Must be implemented.
        
        Args:
            prepared_input: Dictionary of prepared inputs
            
        Returns:
            Dictionary containing the action results
        """
        pass

    def record_action(self, output: Dict[str, Any], subdir: str = "sessions", prefix: str = ""):
        """
        Record the agent's action output to a markdown file using memory client.
        
        Args:
            output: Dictionary of output data
            subdir: Subdirectory to save the output in (e.g., 'sessions', 'reviews')
            prefix: Optional prefix to add to the filename
            
        Returns:
            Path to the saved file
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        if prefix:
            filename = f"{prefix}{timestamp}.md"
        else:
            filename = f"{self.name}_{timestamp}.md"
        
        # Determine output directory
        if subdir:
            output_dir = self.agent_root / subdir
        else:
            output_dir = self.agent_root
        
        # Create directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Format output as markdown
        output_content = self.format_output_markdown(output)
        
        # Determine full output path
        output_path = output_dir / filename
        
        # Write using memory client
        self.memory_client.write_page(
            filepath=str(output_path),
            content=output_content,
            append=False
        )
        
        return output_path

    def format_output_markdown(self, data: Dict[str, Any]) -> str:
        """
        Format the output data as markdown.
        
        Args:
            data: Dictionary of output data
            
        Returns:
            Formatted markdown string
        """
        lines = [f"# CogniAgent Output — {self.name}", ""]
        lines.append(f"**Generated**: {datetime.utcnow().isoformat()}")
        lines.append("")
        
        for k, v in data.items():
            if isinstance(v, dict):
                lines.append(f"## {k}")
                for sub_k, sub_v in v.items():
                    lines.append(f"**{sub_k}**:\n{sub_v}\n")
            else:
                lines.append(f"## {k}")
                lines.append(f"{v}\n")
        
        lines.append("---")
        lines.append(f"> Agent: {self.name}")
        lines.append(f"> Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        return "\n".join(lines) 