"""
Simple Cogni API

A minimal FastAPI that directly passes user queries to OpenAI.

Thank you to Coding-Crashkurse for the clean foundation: https://github.com/Coding-Crashkurse/LangChain-FastAPI-Streaming/blob/main/main.py 
"""

import asyncio
import logging
from typing import AsyncIterable

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_community.chat_models import ChatOpenAI
from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain.schema import HumanMessage
from pydantic import BaseModel

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI()
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


class Message(BaseModel):
    message: str


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
async def stream_chat(message: Message):
    logger.info(f"Received streaming chat request with message: {message.message}")
    
    generator = send_message(message.message)
    logger.info("Returning streaming response")
    return StreamingResponse(generator, media_type="text/event-stream")