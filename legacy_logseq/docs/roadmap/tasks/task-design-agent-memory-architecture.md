# Task:[Design Agent Memory Architecture]
:type: Task
:status: todo
:project: [Agent Memory Integration]

## Current Status
We currently use context.py to load spirit guides and core documents for our agents. This creates an unnecessary layer between agents and memory, limiting agents' ability to leverage our improved memory system.

## Description
Design a clean, future-proof architecture for agents to directly use CogniMemoryClient for all context and memory operations. This will establish the foundation for the entire project and guide implementation of the Agent base class.

## Action Items
- [ ] Analyze current agent context loading in detail
  - [ ] Document existing context.py function calls from agents
  - [ ] Identify what content is being loaded and how it's structured
  - [ ] Map the transformation from raw files to formatted context
- [ ] Design the Agent base class integration with MemoryClient
  - [ ] Define required context loading methods
  - [ ] Specify how MemoryClient will be instantiated and configured
  - [ ] Design patterns for standardized context querying
  - [ ] Establish conventions for context formatting by provider
- [ ] Create class diagrams showing relationships
  - [ ] Agent base to MemoryClient
  - [ ] Agent specializations to base class
  - [ ] Configuration flow
- [ ] Define standard patterns for:
  - [ ] Agent initialization with memory client
  - [ ] Context loading & formatting
  - [ ] Relevant context retrieval
  - [ ] Context composition

## Deliverables
1. Architecture document with class diagrams
2. Integration patterns document with code examples
3. API design for the Agent base class
4. Migration strategy for existing agents

## Test Criteria
- [ ] Validate design meets all existing agent needs
- [ ] Verify design leverages full capabilities of MemoryClient 
- [ ] Ensure design is testable with clear mock patterns

## Implementation Notes
Example Agent base class design:

```python
# agent_base.py
from legacy_logseq.memory.memory_client import CogniMemoryClient

class Agent:
    def __init__(self, config=None):
        """
        Initialize an agent with a memory client.
        
        Args:
            config: Optional configuration dictionary with memory paths and settings
        """
        self.config = config or {}
        self.memory = CogniMemoryClient(
            chroma_path=self.config.get('memory_chroma_path', './memory/chroma'),
            archive_path=self.config.get('memory_archive_path', './memory/archive'),
            collection_name=self.config.get('memory_collection', 'cogni-memory')
        )
        self.context = {}
        
    def load_core_context(self, provider="openai"):
        """
        Load core context for the agent.
        
        Args:
            provider: AI model provider format to use
            
        Returns:
            Formatted context for the specified provider
        """
        # Load core documents
        charter = self.memory.get_page("CHARTER.md")
        manifesto = self.memory.get_page("MANIFESTO.md")
        
        # Format context
        context_text = f"# Core Documents\n\n## Charter\n\n{charter}\n\n## Manifesto\n\n{manifesto}"
        
        # Format for provider
        return self._format_for_provider(context_text, provider)
        
    def load_spirit_guide(self, guide_name, provider="openai"):
        """
        Load a specific spirit guide.
        
        Args:
            guide_name: Name of the guide (without .md extension)
            provider: AI model provider format to use
            
        Returns:
            Formatted guide for the specified provider
        """
        guide_path = f"legacy_logseq/cogni_spirit/spirits/{guide_name}.md"
        guide_content = self.memory.get_page(guide_path)
        
        # Format for provider
        return self._format_for_provider(guide_content, provider)
    
    def query_relevant_context(self, query, n_results=3, provider="openai"):
        """
        Query memory for relevant context.
        
        Args:
            query: Search query string
            n_results: Number of results to return
            provider: AI model provider format to use
            
        Returns:
            Formatted relevant context for the specified provider
        """
        results = self.memory.query(query, n_results=n_results)
        
        # Extract and format results
        context_text = "# Relevant Context\n\n"
        for block in results.blocks:
            context_text += f"## {block.source_file}\n\n{block.text}\n\n"
        
        # Format for provider
        return self._format_for_provider(context_text, provider)
    
    def _format_for_provider(self, text, provider):
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

## Dependencies
- Complete understanding of context.py usage
- CogniMemoryClient implementation (get_page and query methods)
- Knowledge of existing agent architectures 