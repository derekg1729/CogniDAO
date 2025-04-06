"""
Cogni Spirit Context Module

This module provides functionality to load spirit guides as context
for specific AI model provider API calls.
"""

import os
import glob
import json
from typing import List, Dict, Optional, Union
from prefect import task


class SpiritContext:
    """Manages and provides access to Cogni spirit guides for AI context."""
    
    def __init__(self, guides_dir: Optional[str] = None):
        """
        Initialize the SpiritContext.
        
        Args:
            guides_dir: Directory containing spirit guide markdown files.
                        Defaults to the guides directory within the module.
        """
        if guides_dir is None:
            module_dir = os.path.dirname(os.path.abspath(__file__))
            self.guides_dir = os.path.join(module_dir, "guides")
        else:
            self.guides_dir = guides_dir
            
        self.guides_cache: Dict[str, str] = {}
        self._load_guides()
    
    def _load_guides(self) -> None:
        """Load all spirit guides from the guides directory."""
        guide_files = glob.glob(os.path.join(self.guides_dir, "*.md"))
        
        for file_path in guide_files:
            guide_name = os.path.basename(file_path).replace(".md", "")
            with open(file_path, "r", encoding="utf-8") as f:
                self.guides_cache[guide_name] = f.read()
    
    def get_guide(self, guide_name: str) -> Optional[str]:
        """
        Get a specific spirit guide by name.
        
        Args:
            guide_name: Name of the guide (without .md extension)
            
        Returns:
            The guide content as a string, or None if not found
        """
        return self.guides_cache.get(guide_name)
    
    def get_all_guides(self) -> Dict[str, str]:
        """
        Get all spirit guides.
        
        Returns:
            Dictionary mapping guide names to their content
        """
        return self.guides_cache.copy()
    
    def get_context_for_task(self, task: str, guides: Optional[List[str]] = None) -> str:
        """
        Get spirit guide context formatted for a specific task.
        
        Args:
            task: Description of the task being performed
            guides: List of specific guide names to include. 
                   If None, includes core guides.
                   
        Returns:
            Formatted context string for API calls
        """
        if guides is None:
            # Default to core guides if none specified
            guides = ["cogni-core-spirit", "cogni-core-valuing"]
        
        context_parts = [f"# Cogni Spirit Context for: {task}\n"]
        
        for guide in guides:
            guide_content = self.get_guide(guide)
            if guide_content:
                context_parts.append(f"## {guide}\n\n{guide_content}\n")
        
        return "\n".join(context_parts)
    
    def format_for_provider(self, 
                           task: str, 
                           guides: Optional[List[str]] = None,
                           provider: str = "openai") -> Union[str, Dict]:
        """
        Format spirit guide context for specific AI provider APIs.
        
        Args:
            task: Description of the task
            guides: List of guides to include (default: core guides)
            provider: AI provider name (e.g., "openai", "anthropic")
            
        Returns:
            Formatted context in provider-specific format
        """
        context = self.get_context_for_task(task, guides)
        
        if provider.lower() == "openai":
            return {
                "role": "system",
                "content": context
            }
        elif provider.lower() == "anthropic":
            return f"<context>\n{context}\n</context>"
        else:
            # Default to raw context
            return context


@task
def load_spirit_context(guides_dir: Optional[str] = None) -> SpiritContext:
    """
    Prefect task to load the spirit context.
    
    Args:
        guides_dir: Optional directory for guide files
        
    Returns:
        SpiritContext instance
    """
    return SpiritContext(guides_dir)


@task
def get_guide_for_task(
    spirit_context: SpiritContext,
    task: str,
    guides: Optional[List[str]] = None,
    provider: str = "openai"
) -> Union[str, Dict]:
    """
    Prefect task to get formatted guide context for a task.
    
    Args:
        spirit_context: SpiritContext instance
        task: Description of the task
        guides: List of guide names to include
        provider: AI provider name
        
    Returns:
        Formatted context for the specified provider
    """
    return spirit_context.format_for_provider(task, guides, provider)