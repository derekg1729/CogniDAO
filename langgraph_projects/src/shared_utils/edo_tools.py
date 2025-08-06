"""
EDO pattern tools for LangGraph agents.
"""

from typing import Annotated, Dict, Any
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from .logging_utils import get_logger

logger = get_logger(__name__)


# Tool descriptions for EDO agents
GET_MEMORY_REFS_DESCRIPTION = """Access your session's memory context by retrieving relevant memory block references. This tool provides the foundation for EDO workflow continuity by giving you access to previous work and current analysis logs.

## When to Use This Tool
MANDATORY: Use this tool as your FIRST action in every session to establish proper context:

1. Session startup - Call this before any other action to understand your baseline context
2. Context verification - Check what memory blocks are available before proceeding
3. Handoff preparation - Verify you have access to required blocks for next agent

## What You Get
This tool returns a dictionary mapping human-readable names to memory block IDs:
- **"previous_agent_edo_log"**: Work and findings from the previous agent in the EDO chain
- **"current_agent_edo_log"**: Your dedicated analysis log (pre-created, ready for updates)  
- **Additional context blocks**: May include "research_document", "task_breakdown", etc.

## EDO Workflow Requirements
Your EDO workflow MUST follow this sequence:
1. **GET CONTEXT**: Call get_relevant_memory_block_refs() first
2. **READ PREVIOUS WORK**: Use GetMemoryBlock with previous_agent_edo_log ID
3. **ANALYZE**: Understand what's been done and what needs to happen
4. **DOCUMENT**: Update your current_agent_edo_log with findings using UpdateMemoryBlock
5. **ADD NEW REFS**: Use add_memory_block_ref() for any new blocks you discover/create

## Example Usage
```
# Step 1: Get your memory context (ALWAYS FIRST)
refs = get_relevant_memory_block_refs()

# Step 2: Read previous agent's work
previous_work = GetMemoryBlock(block_ids=[refs["previous_agent_edo_log"]])

# Step 3: Update your analysis log with findings
UpdateMemoryBlock(
    block_id=refs["current_agent_edo_log"], 
    text="## Analysis Summary\\nBased on previous work..."
)

# Step 4: Reference new blocks you create
add_memory_block_ref("research_findings", "new-block-uuid")
```

## Critical Success Patterns
- **Always call this first** - Never start work without establishing memory context
- **Check for required blocks** - Verify you have "previous_agent_edo_log" and "current_agent_edo_log" 
- **Use the IDs immediately** - Pass block IDs to GetMemoryBlock to read full content
- **Update your log** - Document your analysis in current_agent_edo_log throughout your work

## Failure Prevention
- Never assume what memory blocks exist - always call this tool to verify
- Don't skip reading previous work - it's essential for EDO continuity
- Don't work in isolation - your analysis must build on previous agent findings
- Don't forget to update your analysis log - it's how you communicate with future agents

This tool ensures proper EDO handoff continuity and prevents agents from working in isolation without understanding the broader context of their task."""

ADD_MEMORY_REF_DESCRIPTION = """Add a new memory block reference to your session context, making it available for future access and ensuring continuity across the EDO chain.

## When to Use This Tool
Use this tool whenever you discover or create memory blocks that are relevant to the current task:

1. **After creating new documents** - Register any CreateMemoryBlock results immediately
2. **When discovering existing blocks** - Add relevant blocks found through search or analysis
3. **For task documentation** - Register task breakdowns, research findings, or analysis documents
4. **Before handoff preparation** - Ensure next agent has access to all relevant context

## What This Tool Does
- Adds the block reference to your session's memory context
- Makes the block accessible via get_relevant_memory_block_refs() for future calls
- Ensures continuity for the next agent in the EDO chain
- Maintains the universal memory reference system across sessions

## Required Parameters
- **block_name**: Human-readable identifier (e.g., "research_findings", "task_analysis", "implementation_plan")
- **block_id**: UUID of the memory block to reference

## EDO Memory Management Pattern
Follow this pattern when working with memory blocks:

```
# 1. Start with context (always first)
refs = get_relevant_memory_block_refs()

# 2. Create new analysis document
result = CreateMemoryBlock(type="doc", title="Research Analysis", content="...")
new_block_id = result["id"]

# 3. IMMEDIATELY register the new block (critical step)
add_memory_block_ref("research_analysis", new_block_id)

# 4. Continue work, knowing the block is now in your context
updated_refs = get_relevant_memory_block_refs()  # Now includes "research_analysis"
```

## Block Naming Conventions
Use descriptive, consistent names:
- **Analysis documents**: "task_analysis", "problem_breakdown", "findings_summary"
- **Research materials**: "research_document", "source_analysis", "literature_review"  
- **Implementation work**: "implementation_plan", "code_design", "architecture_doc"
- **Project management**: "task_breakdown", "progress_report", "milestone_summary"

## Critical Success Requirements
- **Immediate registration** - Call this tool right after creating new blocks
- **Descriptive names** - Use clear, meaningful identifiers for easy reference
- **Context awareness** - Register blocks that will be useful for future agents
- **Handoff preparation** - Ensure next agent has access to all relevant work

## Example Scenarios

### Creating Research Document
```
# Create research document
research_result = CreateMemoryBlock(
    type="doc", 
    title="Market Analysis",
    content="## Key Findings\\n..."
)

# IMMEDIATELY register it
add_memory_block_ref("market_analysis", research_result["id"])
```

### Discovering Existing Block
```
# Found relevant block through search
search_results = GlobalSemanticSearch(query_text="previous implementation")
relevant_block_id = search_results[0]["id"]

# Register for easy access
add_memory_block_ref("previous_implementation", relevant_block_id)
```

## Integration with EDO Workflow
This tool is essential for EDO continuity:
1. **Previous Agent**: Registers important blocks they created/used
2. **Current Agent**: Accesses registered blocks, adds new ones as needed
3. **Next Agent**: Inherits full memory context including new registrations

## Failure Prevention
- Don't create blocks without registering them - they become invisible to future agents
- Don't use generic names - specific identifiers help agents understand content
- Don't skip this step - unregistered blocks break EDO continuity
- Don't register irrelevant blocks - keep the context focused and useful

This tool maintains the universal memory reference system that enables EDO agents to work collaboratively across sessions with full context awareness."""


@tool(description=GET_MEMORY_REFS_DESCRIPTION)
def get_relevant_memory_block_refs(
    refs: Annotated[Dict[str, str], InjectedState("relevant_memory_block_refs")]
) -> Dict[str, str]:
    """Get all relevant memory block references from current LangGraph state.
    
    Returns:
        Dict mapping block_name -> block_id
        - Guaranteed to include: "previous_agent_edo_log", "current_agent_edo_log"
        - May include additional blocks: "context_block_1", "research_document", etc.
        
    Example return:
        {
            "previous_agent_edo_log": "f4b04e1f-8985-440d-8b16-3a3c6365f82f",
            "current_agent_edo_log": "a1b2c3d4-5678-90ab-cdef-123456789abc",
            "context_block_1": "e5f6g7h8-9012-34ij-klmn-567890abcdef"
        }
    
    Usage:
        refs = get_relevant_memory_block_refs()
        previous_work = GetMemoryBlock(block_ids=[refs["previous_agent_edo_log"]])
        UpdateMemoryBlock(block_id=refs["current_agent_edo_log"], content="My analysis...")
    """
    logger.info(f"🔍 Agent requested {len(refs or {})} memory block references")
    return refs or {}


def add_ref_delta(block_name: str, block_id: str) -> Dict[str, Any]:
    """Return a lean state delta that adds/updates a memory-block reference."""
    return {"relevant_memory_block_refs": {block_name: block_id}}


@tool(description=ADD_MEMORY_REF_DESCRIPTION)
def add_memory_block_ref(
    block_name: Annotated[str, "Human-readable name for the memory block (e.g., 'research_document')"],
    block_id: Annotated[str, "UUID of the memory block to reference"],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """Add a new memory block reference to the current context.
    
    Use this when you discover or create new memory blocks that are relevant
    to the current task. This makes them available for future reference.
    
    Args:
        block_name: Human-readable name (e.g., "research_document", "task_breakdown")
        block_id: UUID of the memory block to reference
    """
    # Use the helper to create lean state delta
    delta = add_ref_delta(block_name, block_id)
    
    logger.info(f"📝 Adding memory reference: {block_name} → {block_id}")
    
    return Command(
        update={
            **delta,
            "messages": [ToolMessage(
                content=f"✅ Added memory reference: {block_name} → {block_id}",
                tool_call_id=tool_call_id
            )]
        }
    )



# @tool
# def write_handoff_summary(
#     summary: Annotated[str, "Concise 2-3 sentence handoff summary for the next agent"],
#     call_id: Annotated[str, InjectedToolCallId]
# ) -> Command:
#     """
#     Write a handoff summary to the EDO state for the next agent.
    
#     Use this tool to communicate your decision and findings to the next agent
#     in the EDO chain. The summary should be concise (2-3 sentences) and 
#     actionable.
    
#     Args:
#         summary: Clear, concise handoff summary for the next agent
#         call_id: Tool call ID (automatically injected by LangGraph)
        
#     Returns:
#         Command object that updates the state
#     """
#     summary = summary.strip()
    
#     if not summary:
#         raise ValueError("Handoff summary cannot be empty")
    
#     if len(summary) > 500:
#         raise ValueError("Handoff summary must be ≤ 500 characters")
    
#     logger.info(f"📝 Writing handoff summary: {summary[:100]}...")
    
#     return Command(update={
#         "edo_handoff_summary": summary,
#         "messages": [
#             ToolMessage(
#                 content=f"📝 Handoff summary stored: {summary[:50]}...",
#                 tool_call_id=call_id
#             )
#         ]
#     })