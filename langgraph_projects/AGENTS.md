# LangGraph Agents Guide

<if: Developing Langgraph features> You must read langgraph_projects/AGENTS-langgraph-quick-ref.md</if>

Overview of current structure, not necessarily the right structure

```
langgraph_projects/
├── pyproject.toml          ← Root workspace dependencies (35 lines, streamlined)
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
    ├── simple_cogni_graph/ ← Simplified CogniDAO graph for examples/development
    │   ├── graph.py        ← Graph definition using shared utilities
    │   ├── agent.py        ← Agent logic separated from infrastructure
    │   └── main.py         ← Entry point for LangGraph deployment
    ├── layered_cogni_agent/ ← Layered CogniDAO agent architecture
    │   ├── graph.py        ← Graph definition using shared utilities
    │   ├── agent.py        ← Agent logic separated from infrastructure
    │   └── main.py         ← Entry point for LangGraph deployment
    └── playwright_poc/     ← Browser automation graph (75 lines, clean)
        ├── graph.py        ← Graph definition using shared utilities
        ├── agent.py        ← Agent logic separated from infrastructure
        └── main.py         ← Entry point for LangGraph deployment
```

Root langgraph.json defines the langgraph build, pointed at this langgraph_projects repo

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

## Adding a New Graph

To add a new graph to the project, follow these steps:

### 1. Create New Subdirectory
Create a new directory under `src/` with the following structure:
```bash
mkdir -p src/your_new_graph/{tests,utils}
```

### 2. Create Core Files
Create the required files in your new directory:

**`src/your_new_graph/agent.py`** - Agent logic:

Choose one of three patterns:
- **Standard React Agent**: See `src/simple_cogni_agent/agent.py` for implementation
- **DeepAgent Pattern**: See `src/edo_layered_agent/agent.py` for implementation with persistent memory and task delegation
- **Supervisor Agent Pattern **: see `src/cogni_presence/graph.py` 


### 3. Register in langgraph.json
Add your new graph to the root `langgraph.json` file:
```json
{
    "graphs": {
        "cogni_presence": "./langgraph_projects/src/cogni_presence/main.py:graph",
        "playwright_poc": "./langgraph_projects/src/playwright_poc/main.py:graph",
        "simple_cogni_graph": "./langgraph_projects/src/simple_cogni_graph/main.py:graph",
        "your_new_graph": "./langgraph_projects/src/your_new_graph/main.py:graph"
    }
}
```

### 4. Update Documentation
Update this `AGENTS.md` file to include your new graph in the directory structure above.

### 5. Test Your Graph
```bash
# Test locally
langgraph dev --port XXXX

# Test your specific graph
curl -X POST http://localhost:XXXX/your_new_graph/invoke \
  -H "Content-Type: application/json" \
  -d '{"input": {"messages": [{"role": "user", "content": "Hello"}]}}'
```