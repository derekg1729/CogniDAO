# Chat API → LangGraph Proxy

## Architecture
- `chat.py` optimized to ~45 lines, proxies to LangGraph instead of direct LangChain
- LangGraph service has 38 MCP tools available (GetActiveWorkItems, etc.)
- Single AsyncClient per request (not per API call) for better performance

## Endpoints
- **Docker network**: `langgraph-cogni-presence:8000` (internal)
- **Local access**: `localhost:8002` (LangGraph), `localhost:8000` (API)

## Flow
1. POST `/threads` → get thread_id
2. POST `/threads/{id}/history` → add messages (both system & user)
3. POST `/threads/{id}/runs` → start run with `{"assistant_id":"cogni_presence","stream":true}` (no input.messages)
4. GET `/threads/{thread_id}/runs/{run_id}/stream` → stream SSE events

## Streaming Format
- LangGraph streams proper **SSE format** via `/threads/{thread_id}/runs/{run_id}/stream`
- Returns `content-type: text/event-stream; charset=utf-8`
- Parse `data:` lines, look for `messages/partial` events with `ai` type messages
- Handle `messages/complete` event to terminate stream

## Auth
- Requires `Authorization: Bearer ${COGNI_API_KEY}$` header
- Note: API key forwarding to LangGraph not yet implemented

## Deployment
**CRITICAL**: After code changes, rebuild and redeploy containers:

```bash
# From project root
docker-compose down
docker-compose build web_api
docker-compose up -d

# Or rebuild specific service
docker-compose build web_api && docker-compose up -d web_api
```

- Web API runs on `localhost:8000`
- LangGraph runs on `localhost:8002`
- Check health: `docker-compose ps`

## Testing
- Example test curl:
```bash
curl -X POST "http://localhost:8000/api/v1/chat" -H "Authorization: Bearer ${COGNI_API_KEY}" -H "Content-Type: application/json" -d '{"message": "Hello - this is a test user message"}'
```