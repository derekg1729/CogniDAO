# LangGraph Agents Guide

## Local Development

```bash
# Start local MCP server (in separate terminal)
thv run playwright
thv list

# Run LangGraph dev server (connects to local MCP). Current MCP port, discovered via ToolHive "thv list"
PLAYWRIGHT_MCP_URL=<thv mcp url> uv run langgraph dev --port 8002
```

**Test URLs:**
- Studio UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:8002
- API Docs: http://127.0.0.1:8002/docs

## Build & Deploy

After successful local validation, deploy to our docker network. Example:
```bash
# Build LangGraph container
uv run langgraph build --tag cogni-langgraph-playwright-local

# update docker-compose.yml with new image tag, if necessary
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