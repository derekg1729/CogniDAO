"""
Simple Cogni API

A minimal FastAPI that directly passes user queries to OpenAI.

Thank you to Coding-Crashkurse for the clean foundation: https://github.com/Coding-Crashkurse/LangChain-FastAPI-Streaming/blob/main/main.py 
"""

import asyncio
import logging
from typing import AsyncIterable, List, Dict, Optional
import json
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from langchain_community.chat_models import ChatOpenAI
from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain.schema import HumanMessage, AIMessage, SystemMessage

# Import our schemas
from infra_core.models import CompleteQueryRequest, ErrorResponse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    # format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' # Use default for now
)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(
    title="Cogni API",
    description="A minimal FastAPI that directly passes user queries to OpenAI.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication validator
def verify_auth(authorization: str = Header(...)):
    """Verify the Authorization header contains a valid token."""
    api_key = os.getenv('COGNI_API_KEY')
    if not api_key:
        logger.error("COGNI_API_KEY not set in environment variables!")
        raise HTTPException(status_code=500, detail="API authentication not configured")
        
    if authorization != f"Bearer {api_key}":
        logger.warning("Authentication failed - Invalid token")
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    logger.info("Authentication successful")
    return True

# Health check endpoint
@app.get("/healthz")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy"}

# Log middleware to capture request information
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware to log all requests and responses."""
    # Log request
    logger.info(f"Request: {request.method} {request.url}")
    
    # Process request
    response = await call_next(request)
    
    # Log response
    logger.info(f"Response status: {response.status_code}")
    
    return response


async def send_message(message: str, history: Optional[List[Dict[str, str]]] = None) -> AsyncIterable[str]:
    logger.info(f"⚙️ Processing message: '{message}' with history: {history}")
    
    callback = AsyncIteratorCallbackHandler()
    model = ChatOpenAI(
        streaming=True,
        verbose=True,
        callbacks=[callback],
    )

    # Construct LangChain message list
    lc_messages = []
    # Convert history from List[Dict] to LangChain message objects.
    # TODO: Optimize? Explore if LangChain can handle dicts directly or if models can be adjusted.
    if history:
        for msg in history:
            role = msg.get("role")
            content = msg.get("content")
            if not role or not content:
                logger.warning(f"Skipping history message due to missing role/content: {msg}")
                continue
            if role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            elif role == "system":
                lc_messages.append(SystemMessage(content=content))
            else:
                logger.warning(f"Skipping history message due to unknown role: {role}")

    # Add the current user message
    lc_messages.append(HumanMessage(content=message))
    
    logger.info(f"📚 Sending messages to LangChain model: {lc_messages}")
    logger.info("▶️ Creating task with LangChain model")
    task = asyncio.create_task(
        model.agenerate(messages=[lc_messages])
    )

    token_count = 0
    try:
        logger.info("✉️ Starting token streaming...")
        async for token in callback.aiter():
            token_count += 1
            yield token
    except Exception as e:
        logger.error(f"Error during streaming: {e}")
        print(f"Caught exception: {e}")
    finally:
        callback.done.set()
        logger.info(f"🏁 Completed streaming {token_count} tokens")

    await task
    logger.info("✅ Task completed")


@app.post("/chat")
async def stream_chat(request: CompleteQueryRequest, auth=Depends(verify_auth)):
    logger.info("✅ Received streaming chat request.")
    logger.info(f"✨ Message: {request.message}")
    logger.info(f"✨ History: {request.message_history}")
    
    generator = send_message(request.message, request.message_history)
    logger.info("Returning streaming response")
    return StreamingResponse(generator, media_type="text/event-stream")


@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc: Any):
    """
    Handle 422 Unprocessable Entity errors and log detailed information.
    """
    logger.error(f"Validation error (422) on request to: {request.url}")
    
    # Log request headers
    logger.error(f"Request headers: {dict(request.headers)}")
    
    # Log request body
    try:
        body = await request.body()
        body_str = body.decode('utf-8')
        logger.error(f"Raw request body: {body_str}")
        
        # Try to parse as JSON for cleaner logging
        try:
            json_body = json.loads(body_str)
            logger.error(f"Parsed JSON body: {json.dumps(json_body, indent=2)}")
        except json.JSONDecodeError:
            pass
            
    except Exception as e:
        logger.error(f"Could not parse request body: {str(e)}")
    
    # Return the original error response with our error schema
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            detail=str(exc),
            code="VALIDATION_ERROR"
        ).model_dump()
    )