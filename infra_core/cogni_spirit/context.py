"""
Cogni Spirit Context Module

This module provides functionality to load spirit guides as context
for specific AI model provider API calls.
"""

import os
import glob
from typing import List, Dict, Optional, Union

# Cache for loaded guides
_GUIDES_CACHE: Dict[str, str] = {}

def _get_spirits_dir() -> str:
    """Get the path to the spirits directory."""
    module_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(module_dir, "spirits")

def _load_guides(guides_dir: Optional[str] = None) -> Dict[str, str]:
    """
    Load all spirit guides from the specified directory.
    
    Args:
        guides_dir: Directory containing spirit guide markdown files.
                   Defaults to the spirits directory within the module.
    
    Returns:
        Dictionary mapping guide names to their content
    """
    global _GUIDES_CACHE
    
    # If guides are already loaded and no custom dir specified, return cache
    if _GUIDES_CACHE and guides_dir is None:
        return _GUIDES_CACHE
    
    # Determine guides directory
    if guides_dir is None:
        guides_dir = _get_spirits_dir()
    
    # Load guides
    guides = {}
    guide_files = glob.glob(os.path.join(guides_dir, "*.md"))
    
    for file_path in guide_files:
        guide_name = os.path.basename(file_path).replace(".md", "")
        with open(file_path, "r", encoding="utf-8") as f:
            guides[guide_name] = f.read()
    
    # Update cache if using default directory
    if guides_dir == _get_spirits_dir():
        _GUIDES_CACHE = guides
    
    return guides

def get_guide(guide_name: str, guides_dir: Optional[str] = None) -> Optional[str]:
    """
    Get a specific spirit guide by name.
    
    Args:
        guide_name: Name of the guide (without .md extension)
        guides_dir: Optional custom directory to load guides from
        
    Returns:
        The guide content as a string, or None if not found
    """
    guides = _load_guides(guides_dir)
    return guides.get(guide_name)

def get_specific_guides(guides: List[str], 
                       provider: str = "openai", 
                       guides_dir: Optional[str] = None) -> Union[str, Dict]:
    """
    Get specific guides formatted for the specified provider.
    
    Args:
        guides: List of guide names to include
        provider: AI provider name (e.g., "openai", "anthropic")
        guides_dir: Optional custom directory to load guides from
        
    Returns:
        Formatted content in provider-specific format
    """
    all_guides = _load_guides(guides_dir)
    
    context_parts = ["# Cogni Spirit Guides\n"]
    
    for guide in guides:
        guide_content = all_guides.get(guide)
        if guide_content:
            context_parts.append(f"## {guide}\n\n{guide_content}\n")
    
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
        # Default to raw context
        return full_context

def get_core_documents(provider: str = "openai", guides_dir: Optional[str] = None) -> Union[str, Dict]:
    """
    Get core documents including Charter, Manifesto, and core spirit guide.
    
    Args:
        provider: AI provider name
        guides_dir: Optional custom directory to load guides from
        
    Returns:
        Formatted content for the specified provider
    """
    # Find repository root
    module_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(module_dir, "../.."))
    
    # Define core documents
    core_docs = {
        "CHARTER": os.path.join(repo_root, "CHARTER.md"),
        "MANIFESTO": os.path.join(repo_root, "MANIFESTO.md"),
        "LICENSE": os.path.join(repo_root, "LICENSE.md"),
        "README": os.path.join(repo_root, "README.md")
    }
    
    # Build context
    context_parts = ["# Cogni Core Documents\n"]
    
    # Track metadata for backward compatibility
    metadata = {
        "core_docs": {},
        "total_sections": 0
    }
    
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
    
    # Add cogni-core-spirit
    core_spirit = get_guide("cogni-core-spirit", guides_dir)
    if core_spirit:
        context_parts.append(f"## cogni-core-spirit\n\n{core_spirit}\n")
        metadata["core_spirit"] = {
            "length": len(core_spirit)
        }
        metadata["total_sections"] += 1
    
    # Combine all context
    full_context = "\n".join(context_parts)
    
    # Calculate totals for backward compatibility
    metadata["total_core_docs_length"] = sum(doc.get("length", 0) for doc in metadata["core_docs"].values())
    metadata["total_context_length"] = len(full_context)
    
    # Format for provider and maintain backward compatibility structure
    if provider.lower() == "openai":
        formatted_context = {
            "role": "system",
            "content": full_context
        }
    elif provider.lower() == "anthropic":
        formatted_context = f"<context>\n{full_context}\n</context>"
    else:
        formatted_context = full_context
    
    # Return in the format expected by ritual_of_presence.py
    return {
        "context": formatted_context,
        "metadata": metadata
    }

def get_guide_for_task(
    spirit_context=None,  # Kept for API compatibility, but not used
    task: str = "",
    guides: Optional[List[str]] = None,
    provider: str = "openai",
    guides_dir: Optional[str] = None
) -> Union[str, Dict]:
    """
    Get formatted guide context for a task.
    
    Args:
        spirit_context: Ignored, kept for API compatibility
        task: Description of the task
        guides: List of guide names to include
        provider: AI provider name
        guides_dir: Optional custom directory to load guides from
        
    Returns:
        Formatted context for the specified provider
    """
    if guides is None:
        guides = ["cogni-core-spirit", "cogni-core-valuing"]
    
    # Prepare context with task description
    raw_context = get_specific_guides(guides, provider="raw", guides_dir=guides_dir)
    
    # Add task description
    context_with_task = f"# Cogni Spirit Context for: {task}\n\n{raw_context}"
    
    # Format for provider
    if provider.lower() == "openai":
        return {
            "role": "system",
            "content": context_with_task
        }
    elif provider.lower() == "anthropic":
        return f"<context>\n{context_with_task}\n</context>"
    else:
        return context_with_task

def get_core_context(
    spirit_context=None,  # Kept for API compatibility, but not used
    provider: str = "openai",
    guides_dir: Optional[str] = None
) -> Union[str, Dict]:
    """
    Get core context including Charter, Manifesto, License, README.
    
    Args:
        spirit_context: Ignored, kept for API compatibility
        provider: AI provider name
        guides_dir: Optional custom directory to load guides from
        
    Returns:
        Formatted context for the specified provider
    """
    return get_core_documents(provider, guides_dir)