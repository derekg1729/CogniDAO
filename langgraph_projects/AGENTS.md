# LangGraph Agents Guide

## New Monorepo Structure ✨

This project has been refactored into a clean monorepo structure with shared utilities and consolidated dependencies:

```
langgraph_projects/
├── pyproject.toml          ← Root workspace dependencies (35 lines, streamlined)
├── langgraph.json          ← Graph registry (points to src/ packages)
└── src/
    ├── shared_utils/       ← Shared utilities (6 modules, ~800 lines)
    │   ├── mcp_client.py   ← MCP connection management with fallback
    │   ├── model_binding.py ← Cached model binding and configuration
    │   ├── state_types.py  ← Common TypedDict definitions and prompts
    │   ├── error_handling.py ← Custom exceptions and error patterns
    │   └── logging_utils.py ← Consistent logging configuration
    ├── cogni_presence/     ← CogniDAO presence graph (75 lines, clean)
    │   ├── graph.py        ← Graph definition using shared utilities
    │   ├── agent.py        ← Agent logic separated from infrastructure
    │   └── main.py         ← Entry point for LangGraph deployment
    └── playwright_poc/     ← Browser automation graph (75 lines, clean)
        ├── graph.py        ← Graph definition using shared utilities
        ├── agent.py        ← Agent logic separated from infrastructure
        └── main.py         ← Entry point for LangGraph deployment
```

## Key Improvements

- **Single pyproject.toml**: Consolidated from 2 separate files (32+43 lines) to 1 streamlined file (35 lines)
- **Shared utilities**: Eliminated code duplication, ~800 lines of reusable infrastructure
- **Clean graphs**: Reduced from 233-line monolithic `build_graph.py` to 75-line focused graph definitions
- **Separation of concerns**: Infrastructure (MCP, models, state) vs business logic (graphs, agents)
- **Proper error handling**: Graceful fallbacks when MCP servers unavailable

## Local Development

First, install the package in development mode:
```bash
# Install package and dependencies
uv pip install -e .

# Start local MCP server (in separate terminal)
thv run playwright
thv list

# Run LangGraph dev server (connects to local MCP)
PLAYWRIGHT_MCP_URL=<thv mcp url> uv run langgraph dev --port 8002
```

**Test URLs:**
- Studio UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:8002
- API Docs: http://127.0.0.1:8002/docs

## Build & Deploy

After successful local validation, deploy to our docker network:
```bash
# Build LangGraph container
uv run langgraph build --tag cogni-langgraph-playwright-local

# Update docker-compose.yml with new image tag, if necessary
# Deploy all services  
./deploy/deploy.sh local

# Test endpoints
curl http://localhost:8000/health  # Main API
curl http://localhost:8081/health  # LangGraph service
```

## Testing

Run the full test suite:
```bash
# Test graphs tox environment
uv run tox -e graphs

# Test all environments
uv run tox
```