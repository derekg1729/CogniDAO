from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
import httpx
import json
import logging

# Import verify_auth from auth_utils.py
from ..auth_utils import verify_auth

BASE = "http://langgraph-cogni-presence:8000"
ASSISTANT = "cogni_presence"
log = logging.getLogger(__name__)
router = APIRouter(tags=["v1/Chat"])


async def lg(path, method, client, **kw):
    r = await getattr(client, method)(f"{BASE}{path}", **kw)
    r.raise_for_status()
    return r


@router.post("/chat", response_class=StreamingResponse)
async def chat(req: Request, auth=Depends(verify_auth)):
    body = await req.json()
    user_msg = body["message"]

    log.info(f"Chat request from user: {user_msg}")

    # Use manual client management for streaming
    client = httpx.AsyncClient()
    try:
        # Create thread
        thread_resp = await lg("/threads", "post", client, json={})
        thread_id = thread_resp.json()["thread_id"]
        log.info(f"Created thread: {thread_id}")

        # Create run with proper input format
        run_data = {
            "assistant_id": ASSISTANT,
            "input": {
                "messages": [{"role": "user", "content": user_msg}]
            },  # Added required input field
            "stream": True,
        }
        run_resp = await lg(f"/threads/{thread_id}/runs", "post", client, json=run_data)
        run_id = run_resp.json()["run_id"]
        log.info(f"Created run: {run_id}")

        # Stream the results
        async def generate():
            try:
                stream_path = f"/threads/{thread_id}/runs/{run_id}/stream"
                async with client.stream("GET", f"{BASE}{stream_path}") as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_text():
                        if chunk.strip():
                            yield f"data: {chunk}\n\n"
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
        return {"error": str(e)}
