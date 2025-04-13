# Task:[Implement Agent Base with Memory Client]
:type: Task
:status: todo
:project: [Agent Memory Integration]

## Current Status
The architecture for integrating memory client with agents has been designed in the [[task-design-agent-memory-architecture]] task. Now we need to implement the Agent base class that uses CogniMemoryClient directly.

## Description
Implement the base Agent class that integrates CogniMemoryClient for context loading and querying. This will serve as the foundation for all agents and provide standardized memory access patterns.

## Action Items
- [ ] Create or modify infra_core/cogni_agents/agent_base.py
  - [ ] Add CogniMemoryClient initialization
  - [ ] Implement context loading methods
  - [ ] Implement provider formatting utilities
  - [ ] Add memory querying capabilities
- [ ] Implement core functionality:
  - [ ] `__init__` with configuration options
  - [ ] `load_core_context` to load primary documents
  - [ ] `load_spirit_guide` to load specific guides
  - [ ] `query_relevant_context` for semantic search
  - [ ] `_format_for_provider` utility method
- [ ] Write comprehensive tests
  - [ ] Test with mock memory client
  - [ ] Verify all core methods work
  - [ ] Test provider formatting
  - [ ] Compare outputs with current context.py implementation
- [ ] Create usage documentation
  - [ ] Add docstrings to all methods
  - [ ] Create usage examples

## Deliverables
1. Implemented Agent base class with MemoryClient integration
2. Comprehensive test suite
3. Usage documentation with examples

## Test Criteria
- [ ] All tests pass
- [ ] Test coverage at least 90%
- [ ] Verify outputs match expected format for each provider
- [ ] Confirm behavior matches or improves upon context.py functionality

## Implementation Details

```python
# agent_base.py
import os
from typing import Dict, List, Optional, Union, Any

from infra_core.memory.memory_client import CogniMemoryClient
from infra_core.memory.schema import QueryResult


class Agent:
    """Base class for Cogni agents with integrated memory capabilities."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize an agent with a memory client.
        
        Args:
            config: Optional configuration dictionary with memory paths and settings
        """
        self.config = config or {}
        
        # Initialize memory client
        self.memory = CogniMemoryClient(
            chroma_path=self.config.get('memory_chroma_path', 
                os.environ.get('COGNI_MEMORY_CHROMA_PATH', './memory/chroma')),
            archive_path=self.config.get('memory_archive_path',
                os.environ.get('COGNI_MEMORY_ARCHIVE_PATH', './memory/archive')),
            collection_name=self.config.get('memory_collection', 'cogni-memory')
        )
        
        # Initialize empty context
        self.context = {}
    
    def load_core_context(self, provider: str = "openai") -> Union[Dict, str]:
        """
        Load core context for the agent including Charter, Manifesto, etc.
        
        Args:
            provider: AI model provider format to use
            
        Returns:
            Formatted context for the specified provider
        """
        # Define core documents to load
        core_docs = {
            "CHARTER": "CHARTER.md",
            "MANIFESTO": "MANIFESTO.md",
            "LICENSE": "LICENSE.md",
            "README": "README.md"
        }
        
        # Load each document
        loaded_docs = {}
        for doc_name, doc_path in core_docs.items():
            try:
                loaded_docs[doc_name] = self.memory.get_page(doc_path)
            except Exception as e:
                loaded_docs[doc_name] = f"Error loading {doc_name}: {str(e)}"
        
        # Format context
        context_text = "# Cogni Core Documents\n\n"
        for doc_name, content in loaded_docs.items():
            context_text += f"## {doc_name}\n\n{content}\n\n"
        
        # Add core spirit guide
        try:
            core_spirit = self.load_spirit_guide("cogni-core-spirit", provider="raw")
            context_text += f"## Core Spirit Guide\n\n{core_spirit}\n\n"
        except Exception as e:
            context_text += f"## Core Spirit Guide\n\nError loading core spirit guide: {str(e)}\n\n"
        
        # Format for provider
        return self._format_for_provider(context_text, provider)
    
    def load_spirit_guide(self, guide_name: str, provider: str = "openai") -> Union[Dict, str]:
        """
        Load a specific spirit guide.
        
        Args:
            guide_name: Name of the guide (without .md extension)
            provider: AI model provider format to use
            
        Returns:
            Formatted guide for the specified provider
        """
        guide_path = f"infra_core/cogni_spirit/spirits/{guide_name}.md"
        guide_content = self.memory.get_page(guide_path)
        
        # If provider is "raw", return unformatted content
        if provider.lower() == "raw":
            return guide_content
        
        # Format for provider
        return self._format_for_provider(f"# {guide_name}\n\n{guide_content}", provider)
    
    def load_multiple_guides(self, guide_names: List[str], provider: str = "openai") -> Union[Dict, str]:
        """
        Load multiple spirit guides.
        
        Args:
            guide_names: List of guide names (without .md extension)
            provider: AI model provider format to use
            
        Returns:
            Formatted guides for the specified provider
        """
        context_text = "# Cogni Spirit Guides\n\n"
        
        for guide_name in guide_names:
            try:
                guide_content = self.load_spirit_guide(guide_name, provider="raw")
                context_text += f"## {guide_name}\n\n{guide_content}\n\n"
            except Exception as e:
                context_text += f"## {guide_name}\n\nError loading guide: {str(e)}\n\n"
        
        # Format for provider
        return self._format_for_provider(context_text, provider)
    
    def query_relevant_context(self, query: str, n_results: int = 3, 
                              filter_tags: Optional[List[str]] = None,
                              provider: str = "openai") -> Union[Dict, str]:
        """
        Query memory for relevant context.
        
        Args:
            query: Search query string
            n_results: Number of results to return
            filter_tags: Optional list of tags to filter results
            provider: AI model provider format to use
            
        Returns:
            Formatted relevant context for the specified provider
        """
        results = self.memory.query(
            query_text=query, 
            n_results=n_results,
            filter_tags=filter_tags
        )
        
        # If no results, return empty context
        if not results.blocks:
            return self._format_for_provider("# Relevant Context\n\nNo relevant context found.", provider)
        
        # Extract and format results
        context_text = "# Relevant Context\n\n"
        for block in results.blocks:
            context_text += f"## From: {block.source_file}\n\n{block.text}\n\n"
            if block.tags:
                context_text += f"Tags: {', '.join(block.tags)}\n\n"
        
        # Format for provider
        return self._format_for_provider(context_text, provider)
    
    def _format_for_provider(self, text: str, provider: str) -> Union[Dict, str]:
        """
        Format text for specific AI provider.
        
        Args:
            text: Raw text to format
            provider: AI model provider name
            
        Returns:
            Formatted text for the specified provider
        """
        if provider.lower() == "openai":
            return {
                "role": "system",
                "content": text
            }
        elif provider.lower() == "anthropic":
            return f"<context>\n{text}\n</context>"
        else:
            return text
```

## Example Test Case
```python
def test_agent_load_core_context():
    """Test that the Agent can load core context."""
    # Create mock memory client
    mock_memory = MagicMock()
    mock_memory.get_page.side_effect = lambda path: f"Content of {path}"
    
    # Create agent with mock
    agent = Agent()
    agent.memory = mock_memory
    
    # Call method
    context = agent.load_core_context()
    
    # Verify calls
    mock_memory.get_page.assert_any_call("CHARTER.md")
    mock_memory.get_page.assert_any_call("MANIFESTO.md")
    
    # Verify format
    assert context["role"] == "system"
    assert "Content of CHARTER.md" in context["content"]
    assert "Content of MANIFESTO.md" in context["content"]
```

## Dependencies
- Completed [[task-design-agent-memory-architecture]]
- CogniMemoryClient implementation
- Understanding of existing agent needs 