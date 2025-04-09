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
    
    def __init__(self, guides_dir: Optional[str] = "../.."):
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


@task
def get_core_context(spirit_context: SpiritContext, provider: str = "openai") -> Union[str, Dict]:
    """
    Prefect task to get core context including Charter, Manifesto, License, README only.
    
    Args:
        spirit_context: SpiritContext instance
        provider: AI provider name
        
    Returns:
        Formatted context for the specified provider
    """
    # Get core document paths
    repo_root = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".."))
    core_docs = {
        "CHARTER": os.path.join(repo_root, "CHARTER.md"),
        "MANIFESTO": os.path.join(repo_root, "MANIFESTO.md"),
        "LICENSE": os.path.join(repo_root, "LICENSE.md"),
        "README": os.path.join(repo_root, "README.md")
    }
    
    # Build core context
    context_parts = ["# Cogni Core Context\n"]
    
    # Add core documents
    for doc_name, doc_path in core_docs.items():
        try:
            if os.path.exists(doc_path):
                with open(doc_path, "r", encoding="utf-8") as f:
                    content = f.read()
                context_parts.append(f"## {doc_name}\n\n{content}\n")
        except Exception as e:
            context_parts.append(f"## {doc_name}\n\nError loading document: {str(e)}\n")
    
    # Combine all context
    full_context = "\n".join(context_parts)
    
    # Format for provider
    if provider.lower() == "openai":
        return {
            "role": "system",
            "content": full_context
        }
    elif provider.lower() == "anthropic":
        return f"<context>\n{full_context}\n</context>"
    else:
        return full_context


@task
def get_all_context(spirit_context: SpiritContext, provider: str = "openai") -> Union[str, Dict]:
    """
    Prefect task to get ALL core context including Charter, Manifesto, License, README and all spirit guides.
    
    Args:
        spirit_context: SpiritContext instance
        provider: AI provider name
        
    Returns:
        Formatted context for the specified provider
    """
    # Get all spirit guides
    all_guides = spirit_context.get_all_guides()
    guide_names = list(all_guides.keys())
    
    # Get core document paths
    repo_root = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".."))
    core_docs = {
        "CHARTER": os.path.join(repo_root, "CHARTER.md"),
        "MANIFESTO": os.path.join(repo_root, "MANIFESTO.md"),
        "LICENSE": os.path.join(repo_root, "LICENSE.md"),
        "README": os.path.join(repo_root, "README.md")
    }
    
    # Build full context
    context_parts = ["# Cogni Core Context\n"]
    
    # Add core documents
    for doc_name, doc_path in core_docs.items():
        try:
            if os.path.exists(doc_path):
                with open(doc_path, "r", encoding="utf-8") as f:
                    content = f.read()
                context_parts.append(f"## {doc_name}\n\n{content}\n")
        except Exception as e:
            context_parts.append(f"## {doc_name}\n\nError loading document: {str(e)}\n")
    
    # Add all spirit guides
    context_parts.append("# Spirit Guides\n")
    for guide_name in guide_names:
        guide_content = spirit_context.get_guide(guide_name)
        if guide_content:
            context_parts.append(f"## {guide_name}\n\n{guide_content}\n")
    
    # Combine all context
    full_context = "\n".join(context_parts)
    
    # Format for provider
    if provider.lower() == "openai":
        return {
            "role": "system",
            "content": full_context
        }
    elif provider.lower() == "anthropic":
        return f"<context>\n{full_context}\n</context>"
    else:
        return full_context


@task
def get_complete_context(provider: str = "openai") -> Dict:
    """
    Single comprehensive function to get all context with detailed metadata.
    Loads all core documents and spirit guides with proper attribution.
    
    Args:
        provider: AI provider name format
        
    Returns:
        Dict containing the formatted context and detailed metadata
    """
    # Create a new context instance
    spirit_context = SpiritContext()
    
    # Get all spirit guides
    all_guides = spirit_context.get_all_guides()
    guide_names = list(all_guides.keys())
    
    # Find repository root by looking for common repository markers
    def find_repo_root():
        """Find the repository root by walking up from the current file."""
        # Start with the directory containing this file
        current_path = os.path.dirname(os.path.abspath(__file__))
        
        # Walk up the directory tree to find the repository root
        while current_path and current_path != '/':
            # Check for common repository markers
            if (os.path.exists(os.path.join(current_path, ".git")) or
                os.path.exists(os.path.join(current_path, "README.md")) or
                os.path.exists(os.path.join(current_path, "CHARTER.md")) or
                os.path.exists(os.path.join(current_path, "MANIFESTO.md"))):
                return current_path
            
            # Move up one directory
            current_path = os.path.dirname(current_path)
        
        # Fallback to the hardcoded path if we can't find the repo root
        return "/Users/derek/dev/cogni"
    
    # Get the repository root
    repo_root = find_repo_root()
    
    # Define core documents
    core_docs = {
        "CHARTER": os.path.join(repo_root, "CHARTER.md"),
        "MANIFESTO": os.path.join(repo_root, "MANIFESTO.md"),
        "LICENSE": os.path.join(repo_root, "LICENSE.md"),
        "README": os.path.join(repo_root, "README.md")
    }
    
    # Track metadata for each section
    metadata = {
        "core_docs": {},
        "spirit_guides": {},
        "total_sections": 0
    }
    
    # Build full context
    context_parts = ["# Cogni Core Context\n"]
    
    # Add core documents
    for doc_name, doc_path in core_docs.items():
        try:
            if os.path.exists(doc_path):
                with open(doc_path, "r", encoding="utf-8") as f:
                    content = f.read()
                context_parts.append(f"## {doc_name}\n\n{content}\n")
                metadata["core_docs"][doc_name] = {
                    "length": len(content)
                }
                metadata["total_sections"] += 1
            else:
                metadata["core_docs"][doc_name] = {
                    "length": 0,
                    "error": "File not found"
                }
        except Exception as e:
            context_parts.append(f"## {doc_name}\n\nError loading document: {str(e)}\n")
            metadata["core_docs"][doc_name] = {
                "length": 0,
                "error": str(e)
            }
    
    # Add all spirit guides
    context_parts.append("# Spirit Guides\n")
    
    for guide_name in guide_names:
        guide_content = spirit_context.get_guide(guide_name)
        if guide_content:
            context_parts.append(f"## {guide_name}\n\n{guide_content}\n")
            metadata["spirit_guides"][guide_name] = {
                "length": len(guide_content)
            }
            metadata["total_sections"] += 1
    
    # Combine all context
    full_context = "\n".join(context_parts)
    
    # Calculate totals
    metadata["total_core_docs_length"] = sum(doc.get("length", 0) for doc in metadata["core_docs"].values())
    metadata["total_spirit_guides_length"] = sum(guide["length"] for guide in metadata["spirit_guides"].values())
    metadata["total_context_length"] = len(full_context)
    
    # Format for provider
    result = {}
    
    if provider.lower() == "openai":
        result["context"] = {
            "role": "system",
            "content": full_context
        }
    elif provider.lower() == "anthropic":
        result["context"] = f"<context>\n{full_context}\n</context>"
    else:
        result["context"] = full_context
    
    # Add metadata
    result["metadata"] = metadata
    
    return result

# Alias for backwards compatibility
get_all_core_context = get_all_context