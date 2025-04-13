# Task:[Replace context.py with memory_client]
:type: Task
:status: todo
:project: [project-cogni_memory_architecture]

## Current Status
The `infra_core/cogni_spirit/context.py` module currently handles loading spirit guides and core documents. We need to replace it with the more robust `CogniMemoryClient` functionality while maintaining the same behavior. This is our second attempt, with focus on minimal, targeted changes.

## Description
Instead of replacing every context.py call in consuming code, we'll implement the context.py functions directly in CogniMemoryClient and update context.py to delegate to them. This approach minimizes code changes and risk while providing a clear migration path.

## Action Items
- [ ] Scan codebase and identify all context.py functions that need to be implemented
  - [ ] get_guide(guide_name, guides_dir=None)
  - [ ] get_specific_guides(guides, provider="openai", guides_dir=None)
  - [ ] get_core_documents(provider="openai", guides_dir=None)
  - [ ] get_guide_for_task(task="", guides=None, provider="openai", guides_dir=None)
  - [ ] get_core_context(provider="openai", guides_dir=None)
- [ ] Add these functions to CogniMemoryClient with identical signatures
  - [ ] Implement each function using existing memory_client methods (get_page(), scan_logseq())
  - [ ] Ensure exact output format compatibility (for different providers: OpenAI, Anthropic)
- [ ] Update context.py to import and delegate to CogniMemoryClient
  - [ ] Keep the same function signatures
  - [ ] Make context.py a thin compatibility layer
- [ ] Write tests to verify the new implementations match the original behavior
- [ ] Add deprecation notes to context.py documenting the migration path

## Deliverables
1. Updated CogniMemoryClient with new methods matching context.py functions
2. Updated context.py that delegates to CogniMemoryClient 
3. Tests that verify the same behavior is maintained
4. Documentation noting the deprecation path

## Test Criteria
- [ ] All existing tests pass with the new implementation
- [ ] New tests verify CogniMemoryClient methods match original context.py behavior
- [ ] Integration tests confirm system-wide behavior is unchanged
- [ ] Verify that output formatting for different providers (OpenAI, Anthropic) is maintained

## Implementation Guidance
- **Be Minimal**: Every line of code must be earned. Make the smallest possible change that maintains behavior.
- **Be Targeted**: Focus only on the specific function being implemented.
- **Be Thorough**: Test each implementation against the original before moving to the next.

## Function-Specific Implementation Guide

### Add to CogniMemoryClient:
```python
def get_guide(self, guide_name: str, guides_dir: Optional[str] = None) -> Optional[str]:
    """
    Get a specific spirit guide by name.
    
    Args:
        guide_name: Name of the guide (without .md extension)
        guides_dir: Optional custom directory to load guides from
        
    Returns:
        The guide content as a string, or None if not found
    """
    # Default guides directory logic
    if guides_dir is None:
        module_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        guides_dir = os.path.join(module_dir, "cogni_spirit", "spirits")
    
    # Get the guide using get_page
    guide_path = os.path.join(guides_dir, f"{guide_name}.md")
    try:
        return self.get_page(guide_path)
    except:
        return None
```

### Update context.py to delegate:
```python
def get_guide(guide_name: str, guides_dir: Optional[str] = None) -> Optional[str]:
    """
    Get a specific spirit guide by name.
    
    Args:
        guide_name: Name of the guide (without .md extension)
        guides_dir: Optional custom directory to load guides from
        
    Returns:
        The guide content as a string, or None if not found
    """
    # Import here to avoid circular imports
    from infra_core.memory.memory_client import CogniMemoryClient
    
    # Create client instance
    memory_client = CogniMemoryClient(
        chroma_path=os.environ.get("COGNI_MEMORY_CHROMA_PATH", "./memory/chroma"),
        archive_path=os.environ.get("COGNI_MEMORY_ARCHIVE_PATH", "./memory/archive")
    )
    
    # Delegate to memory client
    return memory_client.get_guide(guide_name, guides_dir)
```

## Notes
- This is our second attempt - focus on extreme precision and minimal changes
- The goal is to make context.py a thin delegation layer that can be safely deprecated later
- Using this pattern reduces risk and minimizes changes to consuming code
- Add appropriate deprecation warnings in context.py docstrings 