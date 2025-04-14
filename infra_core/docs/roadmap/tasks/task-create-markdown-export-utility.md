# Task:[Create Markdown Export Utility]
:type: Task
:status: todo
:project: [project-langchain-memory-integration]

## Current Status
- [x] Task design document created (this file)
- [ ] Requirements analysis completed
- [ ] Utility interface designed
- [ ] Basic formatting methods implemented
- [ ] Memory block export implemented
- [ ] Agent output export implemented
- [ ] Tests completed

## Description
Create a minimal Markdown export utility to convert JSON memory data into human-readable output formatting when needed. This utility will provide basic rendering of memory blocks and agent outputs into Markdown format, ensuring human readability while keeping the implementation simple and focused.

## Input
- JSON-structured memory blocks (from MCPFileMemory)
- Agent output data
- Basic formatting requirements

## Output
- Simple Markdown export utility module
- Basic formatting functions for memory blocks and agent outputs
- File export capabilities
- Minimal test suite

## Action Items
- [ ] **Analyze Current Formatting:**
  - [ ] Review existing `format_output_markdown()` methods
  - [ ] Identify minimal required formatting capabilities
  - [ ] Create simplified utility interface

- [ ] **Design Minimal Utility Interface:**
  - [ ] Define core module structure
  - [ ] Create essential formatting interfaces
  - [ ] Document the API

- [ ] **Implement Core Formatting Functions:**
  - [ ] Create basic memory block formatter
  - [ ] Implement basic agent output formatter
  - [ ] Add simple file writing utilities

- [ ] **Implement Testing:**
  - [ ] Create unit tests for core functionality
  - [ ] Test with sample data
  - [ ] Verify output format

## Deliverables
1. `markdown_renderer.py` utility module
2. Core formatting functions
3. Basic file export capabilities
4. Minimal test suite

## Implementation Details
```python
"""
Markdown export utility for Cogni.

This module provides simple functions for exporting JSON data to Markdown format.
"""

from typing import Dict, List, Any, Union
from pathlib import Path
import os
from datetime import datetime

def format_memory_block(block: Dict[str, Any]) -> str:
    """
    Format a memory block as Markdown.
    
    Args:
        block: Memory block dictionary
        
    Returns:
        Formatted Markdown string
    """
    lines = []
    
    # Add header with source
    if "source_file" in block:
        lines.append(f"## Memory from: {block['source_file']}")
    else:
        lines.append("## Memory Block")
    
    # Add creation timestamp
    if "created_at" in block:
        lines.append(f"**Created**: {block['created_at']}")
    
    # Add tags if present
    if "tags" in block and block["tags"]:
        tags = [f"#{tag}" if not tag.startswith('#') else tag for tag in block["tags"]]
        lines.append(f"**Tags**: {' '.join(tags)}")
    
    # Add content
    if "content" in block:
        lines.append("\n" + block["content"] + "\n")
    elif "text" in block:
        lines.append("\n" + block["text"] + "\n")
    
    return "\n".join(lines)


def format_agent_output(data: Dict[str, Any], agent_name: str = "") -> str:
    """
    Format agent output as Markdown.
    
    Args:
        data: Dictionary of output data
        agent_name: Optional agent name
        
    Returns:
        Formatted markdown string
    """
    lines = [f"# Agent Output — {agent_name}" if agent_name else "# Agent Output", ""]
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
    if agent_name:
        lines.append(f"> Agent: {agent_name}")
    lines.append(f"> Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    return "\n".join(lines)


def write_markdown(content: str, filepath: Union[str, Path], append: bool = False) -> Path:
    """
    Write content to a Markdown file.
    
    Args:
        content: Markdown content to write
        filepath: Path to the file
        append: Whether to append to the file (default: False)
        
    Returns:
        Path to the saved file
    """
    # Convert string path to Path object
    if isinstance(filepath, str):
        filepath = Path(filepath)
    
    # Create directory if it doesn't exist
    if not filepath.parent.exists():
        filepath.parent.mkdir(parents=True, exist_ok=True)
    
    # Write the file
    mode = "a" if append else "w"
    with open(filepath, mode, encoding="utf-8") as f:
        f.write(content)
        
        # Add newline if appending and content doesn't end with one
        if append and not content.endswith("\n"):
            f.write("\n")
    
    return filepath
```

## Test Criteria
- Memory blocks are formatted correctly
- Agent outputs are formatted consistently
- File operations handle paths correctly
- Error handling is basic but functional

## Integration Points
- **MCPFileMemory**: Source of memory blocks to format
- **CogniAgent**: For agent output formatting
- **File System**: For storing formatted output

## Notes
- Keep the implementation minimal for v1
- Focus only on essential formatting features
- Skip complex formatting options, templates, and advanced features
- Prioritize reliability over flexibility
- This utility is optional - JSON is the primary storage format

## Dependencies
- JSON schema for memory blocks
- Basic file system access
- Python datetime and pathlib 