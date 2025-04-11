"""
CogniAgent base module

This module provides the abstract base class for all Cogni agents.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


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

        self.load_spirit()

    def load_spirit(self):
        """Load the spirit guide contents from markdown."""
        if self.spirit_path.exists():
            self.spirit = self.spirit_path.read_text()
        else:
            self.spirit = "⚠️ Spirit guide not found."

    def load_core_context(self):
        """Override if this agent requires charter/manifesto/spirit context."""
        self.core_context = None

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
        Record the agent's action output to a markdown file.
        
        Args:
            output: Dictionary of output data
            subdir: Subdirectory to save the output in (e.g., 'sessions', 'reviews')
            prefix: Optional prefix to add to the filename
        """
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
        output_path = self.agent_root / subdir / f"{prefix}{timestamp}.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.format_output_markdown(output))
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