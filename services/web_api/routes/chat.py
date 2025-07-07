from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
import json
import logging

# Import verify_auth from auth_utils.py
from ..auth_utils import verify_auth
from ..models import ChatMessage

BASE = "http://langgraph-cogni-presence:8000"
ASSISTANT = "cogni_presence"
log = logging.getLogger(__name__)
router = APIRouter(tags=["v1/Chat"])


async def lg(path, method, client, **kw):
    r = await getattr(client, method)(f"{BASE}{path}", **kw)
    r.raise_for_status()
    return r


@router.post("/chat", response_class=StreamingResponse)
async def chat(chat_request: ChatMessage, auth=Depends(verify_auth)):
    user_msg = chat_request.message

    log.info(f"Chat request from user: {user_msg}")

    # Use manual client management for streaming
    client = httpx.AsyncClient()
    try:
        # Create thread
        thread_resp = await lg("/threads", "post", client, json={})
        thread_id = thread_resp.json()["thread_id"]
        log.info(f"Created thread: {thread_id}")

        # Create run with proper Server API streaming format
        run_data = {
            "assistant_id": ASSISTANT,
            "input": {"messages": [{"role": "user", "content": user_msg}]},
            # Token-level streaming in Server API requires "messages-tuple" mode
            "stream_mode": "messages-tuple",
        }

        # Use dedicated streaming endpoint that creates run AND streams output
        stream_path = f"/threads/{thread_id}/runs/stream"
        log.info(f"Starting streaming run with: {stream_path}")

        # Stream the results
        async def generate():
            try:
                async with client.stream("POST", f"{BASE}{stream_path}", json=run_data) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_text():
                        if chunk.strip():
                            yield chunk
            except Exception as e:
                log.error(f"Streaming error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    except Exception as e:
        log.error(f"Chat endpoint error: {e}")
        await client.aclose()
        # Return proper JSON error response with correct content-type
        return JSONResponse(
            status_code=200,  # Keep 200 for consistency with existing tests
            content={"error": str(e)},
            headers={"Content-Type": "application/json"},
        )
