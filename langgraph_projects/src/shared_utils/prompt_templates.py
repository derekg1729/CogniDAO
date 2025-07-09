"""
Prompt Templates Module for LangGraph Projects

Provides LangChain ChatPromptTemplate for LangGraph agent system messages.
Centralizes all prompt management for consistent and maintainable agent creation.
"""

from typing import Any, List
from langchain_core.prompts import ChatPromptTemplate


def generate_tool_specs_from_mcp_tools(mcp_tools: List[Any]) -> str:
    """
    Generate tool specifications string from MCP tools list

    Args:
        mcp_tools: List of MCP tool objects

    Returns:
        Formatted tool specifications string
    """
    if not mcp_tools:
        return "## Available MCP Tools:\n\nNo tools currently available."
        
    tool_specs = []
    for tool in mcp_tools:
        try:
            # Extract schema information safely
            schema_info = ""
            if hasattr(tool, "schema") and tool.schema and isinstance(tool.schema, dict):
                # Get input schema if available
                input_schema = tool.schema.get("input_schema", {})
                if isinstance(input_schema, dict):
                    properties = input_schema.get("properties", {})
                    required = input_schema.get("required", [])

                    if properties and isinstance(properties, dict):
                        args_info = []
                        for prop_name, prop_details in properties.items():
                            if isinstance(prop_details, dict):
                                prop_type = prop_details.get("type", "unknown")
                                is_required = "(required)" if prop_name in required else "(optional)"
                                args_info.append(f"{prop_name}: {prop_type} {is_required}")
                        if args_info:
                            schema_info = f" | Args: {', '.join(args_info)}"

            # Build concise tool specification
            tool_name = getattr(tool, 'name', 'Unknown')
            tool_desc = getattr(tool, 'description', 'No description')
            tool_spec = f"{tool_name}: {tool_desc}{schema_info}"
            tool_specs.append(tool_spec)
            
        except Exception:
            # Fallback for problematic tools
            tool_name = getattr(tool, 'name', 'Unknown')
            tool_specs.append(f"{tool_name}: Available tool")

    # Create formatted tool specs string (keep under 1.5k tokens)
    tool_specs_text = """## Available MCP Tools:

Example usage:
- navigate: {"url": "https://example.com"}
- screenshot: {"name": "page_capture.png"}

Tools:
""" + "\n".join(f"• {spec}" for spec in tool_specs[:12])  # Limit to top 12 tools

    if len(tool_specs_text) > 1400:  # Trim if too long
        tool_specs_text = tool_specs_text[:1400] + "\n... (more tools available)"

    return tool_specs_text


# Playwright Navigator Template
PLAYWRIGHT_NAVIGATOR_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a skilled web navigator specializing in CogniDAO application testing with Playwright automation.

**Mission:** Navigate and test the CogniDAO knowledge management system, focusing on memory blocks, work items, chat functionality, and graph visualization.

## CogniDAO Expertise

**System Knowledge:** CogniDAO is a Next.js knowledge management system with memory blocks, work items, chat, and graph visualization

**🎯 PRIMARY TARGET:** {target_url}

**Core Routes:**
- **HIGH PRIORITY:** / - Home page with hero, featured blocks, chat interface
- **HIGH PRIORITY:** /explore - Content discovery with search and filters
- **HIGH PRIORITY:** /blocks/[id] - Individual memory block viewing
- **HIGH PRIORITY:** /work-items - Project management functionality
- **MEDIUM PRIORITY:** /graph - Interactive data visualization
- **MEDIUM PRIORITY:** /blocks - Memory blocks listing
- **LOW PRIORITY:** /node/[slug] - Knowledge node pages

## Navigation Expertise

**Skills:**
- CogniDAO page navigation and URL handling
- Memory block interaction and content verification
- Chat interface testing and streaming responses
- Search and filtering functionality
- Work items management testing
- Graph visualization interaction
- API endpoint validation

## Workflow Approach

1. **Identify** the CogniDAO testing objective and route priority
2. **Navigate** to the target URL: {target_url}
3. **Verify** page loads and core elements render
4. **Test** key interactive features (chat, search, filters)
5. **Validate** API calls and data loading
6. **Report** detailed findings to Observer partner

## Collaboration Style

- **Communicate clearly** with the Observer about what you're doing
- **Report any issues** or unexpected behavior immediately
- **Ask for guidance** when navigation paths are ambiguous
- **Share screenshots** when visual confirmation is needed

## Tool Specifications

{tool_specs}

## Current Task Context

{task_context}

## Focus

You are the hands-on navigator. Execute web interactions efficiently while keeping your Observer partner informed of your progress and findings.""")
])


# Cogni Presence Template
COGNI_PRESENCE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a helpful **CogniDAO assistant** 🤖 

**Primary Tools:** 
- 📋 `GetActiveWorkItems` - Show current tasks
- 🔍 `GlobalSemanticSearch` - Find relevant information  
- 📊 `GlobalMemoryInventory` - Browse memory blocks

**Response Style:**
✅ **Concise** answers with strategic emojis  
📝 Use `code blocks` for tool names  
🎯 Structure with **bold headers** when helpful

**Important:** Leave branch/namespace parameters empty in tool calls.

{tool_specs}

{task_context}""")
])


# Convenience functions for backwards compatibility
def render_playwright_navigator_prompt(
    tool_specs: str, 
    task_context: str = "", 
    target_url: str = "http://host.docker.internal:3000"
) -> str:
    """Render playwright navigator agent prompt"""
    return PLAYWRIGHT_NAVIGATOR_PROMPT.format(
        tool_specs=tool_specs,
        task_context=task_context,
        target_url=target_url
    )


def render_playwright_observer_prompt(
    tool_specs: str, 
    task_context: str = "", 
    target_url: str = "http://host.docker.internal:3000"
) -> str:
    """Render playwright observer agent prompt"""
    # Note: No observer template exists yet, fallback to navigator
    return PLAYWRIGHT_NAVIGATOR_PROMPT.format(
        tool_specs=tool_specs,
        task_context=task_context,
        target_url=target_url
    )


