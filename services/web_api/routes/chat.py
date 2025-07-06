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

    log.info(f"📡 Proxying message to LangGraph: {user_msg[:100]}...")

    # 5️⃣ stream - FIXED: Create client inside streaming function to avoid scoping issue
    async def events():
        async with httpx.AsyncClient(timeout=None) as c:
            # 1️⃣ create / reuse thread
            tid = (
                body.get("thread_id")
                or (await lg("/threads", "post", c, json={})).json()["thread_id"]
            )

            # 2️⃣ memory context → system
            if blocks := body.get("memory", []):
                ctx = "\n\n".join(f"---\n{b}" for b in blocks)
                await lg(
                    f"/threads/{tid}/history", "post", c, json={"role": "system", "content": ctx}
                )

            # 3️⃣ user message
            await lg(
                f"/threads/{tid}/history", "post", c, json={"role": "user", "content": user_msg}
            )

            # 4️⃣ run
            run_id = (
                await lg(
                    f"/threads/{tid}/runs",
                    "post",
                    c,
                    json={"assistant_id": ASSISTANT, "stream": True},
                )
            ).json()["run_id"]

            log.info(f"🏃 Started run {run_id} on thread {tid}")

            # 5️⃣ stream - Use correct endpoint
            async with c.stream(
                "GET",
                f"{BASE}/threads/{tid}/runs/{run_id}/stream",
                headers={"Accept": "text/event-stream"},
            ) as s:
                async for line in s.aiter_lines():
                    if line.startswith("data: "):
                        evt = json.loads(line[6:])
                        if evt.get("event") == "messages/partial":
                            for m in evt["data"]:
                                if m["type"] == "ai":
                                    yield f"data: {json.dumps({'content': m['content']})}\n\n"
                        if evt.get("event") == "messages/complete":
                            return

    return StreamingResponse(events(), media_type="text/event-stream")
