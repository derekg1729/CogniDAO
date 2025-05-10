# Task:[Create Memory MCP Server]
:type: Task
:status: todo
:project: [project-cogni_memory_architecture]
:owner: 

## Description
Implement a Memory Control Protocol (MCP) server that provides a standardized API for Cursor and other tools to interact with the Cogni Memory Architecture. This server will enable intelligent memory operations through a clean HTTP/WebSocket interface.

## Action Items
- [ ] Define MCP server API endpoints for memory operations
- [ ] Implement FastAPI server with core memory operations
- [ ] Create WebSocket interface for real-time memory updates
- [ ] Add authentication and rate limiting
- [ ] Implement endpoints for querying, saving, and archiving memory blocks
- [ ] Create specialized endpoints for Cursor integration
- [ ] Add logging and monitoring

## Deliverables
1. A `memory_mcp_server.py` module with:
   - FastAPI application with RESTful endpoints
   - WebSocket connections for streaming updates
   - Integration with CogniMemoryClient

2. API endpoints for memory operations:
   ```
   POST /memory/query - Search memory with semantic query
   POST /memory/save - Store new memory blocks
   POST /memory/archive - Archive older memory blocks
   GET /memory/blocks/{id} - Retrieve specific memory block
   GET /memory/health - Server health check
   WS /memory/updates - WebSocket for real-time updates
   ```

3. Cursor-specific API extensions:
   ```
   POST /cursor/context - Get relevant context for code editing
   POST /cursor/save-interaction - Store cursor interactions as memory
   ```

4. Configuration options for rate limiting, authentication, and performance tuning

## Test Criteria
- [ ] Test API endpoints with mock requests:
```python
def test_memory_query_endpoint():
    from fastapi.testclient import TestClient
    from memory_mcp_server import app
    
    client = TestClient(app)
    response = client.post(
        "/memory/query",
        json={"query": "test memory", "n_results": 3}
    )
    
    # Verify response structure
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "query" in data
    assert len(data["results"]) <= 3
```

- [ ] Test WebSocket communication:
```python
def test_memory_updates_websocket():
    import websockets
    import asyncio
    import json
    
    async def test_ws():
        # Connect to WebSocket
        async with websockets.connect("ws://localhost:8000/memory/updates") as websocket:
            # Send authentication message
            await websocket.send(json.dumps({"type": "auth", "token": "test_token"}))
            
            # Subscribe to updates
            await websocket.send(json.dumps({"type": "subscribe", "topics": ["memory_added"]}))
            
            # Wait for confirmation
            response = await websocket.recv()
            data = json.loads(response)
            assert data["type"] == "subscription_confirmed"
    
    asyncio.run(test_ws())
```

- [ ] Test Cursor integration endpoints:
```python
def test_cursor_context_endpoint():
    from fastapi.testclient import TestClient
    from memory_mcp_server import app
    
    client = TestClient(app)
    response = client.post(
        "/cursor/context",
        json={
            "file_path": "example.py",
            "code_context": "def sample_function():\n    # Need to implement",
            "query": "similar implementations"
        }
    )
    
    # Verify context is returned
    assert response.status_code == 200
    data = response.json()
    assert "context_blocks" in data
```

- [ ] Verify server performance with simulated load
- [ ] Test authentication and rate limiting
- [ ] Validate error handling with malformed requests

## Notes
- Design for low latency to support real-time code assistance
- Implement clean separation between API layer and memory operations
- Consider using Pydantic for request/response validation
- Follow RESTful API design principles
- Ensure proper error handling and informative error messages
- Include comprehensive logging

## Dependencies
- FastAPI for HTTP API 
- WebSockets for real-time communication
- CogniMemoryClient from task-build_cogni_memory_client
- Authentication mechanism (JWT or API keys) 