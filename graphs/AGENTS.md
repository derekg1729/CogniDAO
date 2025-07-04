# LangGraph Agents Guide

Our first langgraph example:

## Build & Deploy
```bash
# Build LangGraph container
uv run langgraph build --tag cogni-langgraph-playwright-local

# Deploy all services  
./deploy/deploy.sh local

# Test endpoints
curl http://localhost:8000/health  # Main API
curl http://localhost:8081/health  # LangGraph service
```

## Example Structure
- **Graph**: `graphs/playwright_basic/graph.py:compile_graph`
- **Config**: `graphs/playwright_basic/langgraph.json` 
- **Dependencies**: `graphs/playwright_basic/pyproject.toml`
- **Docker**: Uses MCP URL `http://toolhive:58462/sse#playwright`

## Key Files
- `langgraph.json` - CLI build config with dependencies and graph reference
- `pyproject.toml` - Python dependencies (LangGraph, MCP adapters, Redis)
- `graph.py` - StateGraph with compile_graph() function