# Playwright Control Flow Agent System

A modern Control Flow architecture demonstrating two-person AutoGen teams with Playwright MCP integration.

## Overview

This system moves beyond the legacy "1flow, 1agent" format to implement a proper Control Flow architecture with:

- **Navigator Agent**: Executes web navigation and interactions
- **Observer Agent**: Monitors, guides, and validates navigation
- **Playwright MCP Integration**: Via SSE transport at `toolhive:24162`
- **XML Jinja Templates**: Structured agent prompt management
- **Collaborative Workflow**: Two-agent coordination pattern

## Architecture

```
┌─────────────────────┐    ┌─────────────────────┐
│   Navigator Agent   │    │   Observer Agent    │
│                     │    │                     │
│ • Web Navigation    │◄──►│ • Strategy Guide    │
│ • Element Interact  │    │ • Quality Validation│
│ • Data Extraction   │    │ • Course Correction │
└─────────────────────┘    └─────────────────────┘
           │                          │
           └──────────┬─────────────────┘
                      │
           ┌─────────────────────┐
           │  Playwright MCP    │
           │   toolhive:24162   │
           │                    │
           │ • Page Navigation  │
           │ • Element Control  │
           │ • Form Interaction │
           │ • Screenshot Capture│
           └─────────────────────┘
```

## Components

### 1. XML Jinja Templates

- `prompts/agent/playwright_navigator.j2` - Navigator agent prompt
- `prompts/agent/playwright_observer.j2` - Observer agent prompt

### 2. Prompt Template Renderers

```python
from infra_core.prompt_templates import (
    render_playwright_navigator_prompt,
    render_playwright_observer_prompt,
)
```

### 3. Control Flow System

- `flows/examples/playwright_control_flow.py` - Main Control Flow implementation
- `flows/examples/test_playwright_control_flow.py` - Test script

## Usage

### Environment Variables

```bash
export PLAYWRIGHT_MCP_SSE_URL="http://toolhive:24162/sse"
export NAVIGATION_OBJECTIVE="Navigate to example.com and extract key information"
```

### Running the System

```python
from flows.examples.playwright_control_flow import playwright_control_flow
import asyncio

# Run as Prefect flow
result = await playwright_control_flow()

# Or run test script
python flows/examples/test_playwright_control_flow.py
```

### Prefect Flow Execution

```bash
prefect deployment run playwright_control_flow/default
```

## Key Features

### Modern Architecture
- **Control Flow Pattern**: Moves beyond legacy single-agent flows
- **Specialized Roles**: Navigator and Observer with distinct responsibilities
- **Collaborative Workflow**: Two-agent coordination with clear protocols

### MCP Integration
- **SSE Transport**: Uses established `configure_existing_mcp` helper
- **Tool Adapters**: AutoGen MCP integration via `SseMcpToolAdapter`
- **Playwright Tools**: Full access to web automation capabilities

### Template System
- **XML Jinja Structure**: Clean, maintainable agent prompts
- **Context Variables**: Dynamic tool specs and task context injection
- **Reusable Components**: Centralized prompt management

## Example Navigation Objectives

```python
# Simple page navigation
"Navigate to httpbin.org and extract the page title"

# Form interaction
"Navigate to httpbin.org/forms/post, fill out the form, and submit it"

# Multi-step workflow
"Navigate to example.com, find any links, follow one, and report findings"

# Data extraction
"Navigate to a news website, extract headlines, and summarize content"
```

## Collaboration Protocol

1. **Observer** analyzes objective and provides initial strategy
2. **Navigator** executes navigation steps with real-time reporting  
3. **Observer** validates each step and guides course corrections
4. Both agents collaborate to achieve objective efficiently

## Testing

The system includes comprehensive testing capabilities:

```bash
# Run basic test
python flows/examples/test_playwright_control_flow.py

# Test with custom objective
NAVIGATION_OBJECTIVE="Custom task" python flows/examples/test_playwright_control_flow.py
```

## Integration with Existing Flows

This Control Flow system can be integrated into larger workflows:

```python
from flows.examples.playwright_control_flow import (
    create_playwright_navigation_team,
    run_navigation_mission
)

# Use within larger Prefect flows
async def my_larger_workflow():
    # ... other workflow steps
    
    # Add Control Flow navigation
    team = await create_playwright_navigation_team(tools, specs, context)
    result = await run_navigation_mission(team["agents"], context, objective)
    
    # ... continue workflow
```

This demonstrates a clear evolution from legacy single-agent patterns to modern Control Flow architecture with specialized, collaborative agents. 