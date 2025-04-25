# Task:[Create Markdown Export Utility]
:type: Task
:status: completed
:project: [project-langchain-memory-integration]

## Current Status
- [x] Task design document created (this file)
- [ ] Requirements analysis completed
- [ ] Utility interface designed
- [ ] Basic formatting methods implemented
- [ ] Memory block export implemented
- [ ] Agent output export implemented
- [ ] Tests completed
A method `export_history_markdown` was added to `FileMemoryBank` and tested successfully.

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
- [x] Design simple Markdown format for conversation history (e.g., using `### Human:` and `### AI:` headers).
- [x] Implement an `export_history_markdown()` method within the `FileMemoryBank` class or as a standalone function.
  - [x] This method should read `history.json` using existing `read_history_dicts()`.
  - [x] It should iterate through the message dictionaries and format them into a single Markdown string.
  - [x] Consider how to handle different message types if the structure evolves beyond simple human/ai pairs. (Current implementation handles basic 'type' and 'data.content').
- [x] Add a test case for the Markdown export in the `if __name__ == "__main__":` block of `cogni_memory_bank.py`.
- [x] Optional: Consider adding a helper function to write the exported Markdown to a file (e.g., `session_export.md`) within the session directory. (Added as part of the test using `write_context`).

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
- [x] Running the export function/method produces a valid Markdown string.
- [x] The Markdown output accurately reflects the content and order of messages in `history.json`.
- [x] The test case in `cogni_memory_bank.py` passes.

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