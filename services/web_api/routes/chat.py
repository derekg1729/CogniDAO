from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
import httpx
import json
import logging

# Import verify_auth from auth_utils.py
from ..auth_utils import verify_auth

logger = logging.getLogger(__name__)

router = APIRouter(tags=["v1/Chat"])

BASE = "http://langgraph-cogni-presence:8000"  # LangGraph Server
ASSISTANT = "cogni_presence"


# ----- tiny helper ----------------------------------------------------
async def _lg(event: str, method: str = "get", **kw):
    async with httpx.AsyncClient(timeout=None) as c:
        try:
            r = await getattr(c, method)(f"{BASE}{event}", **kw)
            r.raise_for_status()
            return r
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error for {method.upper()} {BASE}{event}: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Request error for {method.upper()} {BASE}{event}: {e}")
            raise


# ----- main entry-point -----------------------------------------------
@router.post("/chat", response_class=StreamingResponse)
async def chat(req: Request, auth=Depends(verify_auth)):
    body = await req.json()
    user_msg = body["message"]

    logger.info(f"📡 Proxying message to LangGraph: {user_msg[:100]}...")

    # 1️⃣ thread (reuse cookie if supplied)
    tid = body.get("thread_id") or (await _lg("/threads", "post", json={})).json()["thread_id"]

    # 2️⃣ optional memory → system msg
    if blocks := body.get("memory", []):
        ctx = "\n\n".join(f"---\n{b}" for b in blocks)
        await _lg(f"/threads/{tid}/history", "post", json={"role": "system", "content": ctx})

    # 3️⃣ user message
    await _lg(f"/threads/{tid}/history", "post", json={"role": "user", "content": user_msg})

    # 4️⃣ start run
    run = (
        await _lg(
            f"/threads/{tid}/runs",
            "post",
            json={
                "assistant_id": ASSISTANT,
                "stream": True,
                "input": {"messages": [{"role": "user", "content": user_msg}]},
            },
        )
    ).json()["run_id"]

    logger.info(f"🏃 Started run {run} on thread {tid}")

    # 5️⃣ stream SSE → client
    async def event_stream():
        async with httpx.AsyncClient(timeout=None) as c:
            async with c.stream(
                "GET",
                f"{BASE}/threads/{tid}/runs/{run}/stream",
                headers={"Accept": "text/event-stream"},
            ) as s:
                async for line in s.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if data.get("event") == "messages/partial":
                            for m in data["data"]:
                                if m.get("type") == "ai":
                                    yield m["content"]
                        if data.get("event") == "messages/complete":
                            break

    return StreamingResponse(event_stream(), media_type="text/event-stream")
