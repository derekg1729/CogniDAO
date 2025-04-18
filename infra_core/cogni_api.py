"""
Simple Cogni API

A minimal FastAPI that directly passes user queries to OpenAI.

Thank you to Coding-Crashkurse for the clean foundation: https://github.com/Coding-Crashkurse/LangChain-FastAPI-Streaming/blob/main/main.py 
"""

import asyncio
import logging
from typing import AsyncIterable
import json
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from langchain_community.chat_models import ChatOpenAI
from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain.schema import HumanMessage

# Import our schemas
from infra_core.models import ChatMessage, ErrorResponse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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


async def send_message(message: str) -> AsyncIterable[str]:
    logger.info(f"Processing message: {message}")
    
    callback = AsyncIteratorCallbackHandler()
    model = ChatOpenAI(
        streaming=True,
        verbose=True,
        callbacks=[callback],
    )

    logger.info("Creating task with LangChain model")
    task = asyncio.create_task(
        model.agenerate(messages=[[HumanMessage(content=message)]])
    )

    token_count = 0
    try:
        logger.info("Starting token streaming")
        async for token in callback.aiter():
            token_count += 1
            if token_count % 10 == 0:
                logger.info(f"Streamed {token_count} tokens so far")
            yield token
    except Exception as e:
        logger.error(f"Error during streaming: {e}")
        print(f"Caught exception: {e}")
    finally:
        callback.done.set()
        logger.info(f"Completed streaming {token_count} tokens")

    await task
    logger.info("Task completed")


@app.post("/chat")
async def stream_chat(message: ChatMessage):
    logger.info(f"Received streaming chat request with message: {message.message}")
    
    generator = send_message(message.message)
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