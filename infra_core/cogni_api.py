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
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from langchain_community.chat_models import ChatOpenAI
from langchain.callbacks import AsyncIteratorCallbackHandler
from langchain.schema import HumanMessage, AIMessage, SystemMessage

# Import our schemas
from infra_core.models import CompleteQueryRequest, ErrorResponse
# Import memory components
from infra_core.memory.memory_client import CogniMemoryClient

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    # format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' # Use default for now
)
logger = logging.getLogger(__name__)

load_dotenv()

# Define paths for memory and source data
API_INDEXED_FILES_DIR = "./api_indexed_files"
MEMORY_CHROMA_PATH = "infra_core/memory/chroma"
MEMORY_ARCHIVE_PATH = "infra_core/memory/archive" # Needs to exist for client

# Lifespan context to hold shared resources like the memory client
# lifespan_context = {} # No longer needed

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the lifespan of the application, including memory client setup."""
    logger.info("🚀 API starting up...")
    
    # Ensure necessary directories exist
    logger.info(f"Ensuring directory exists: {MEMORY_CHROMA_PATH}")
    os.makedirs(MEMORY_CHROMA_PATH, exist_ok=True)
    logger.info(f"Ensuring directory exists: {MEMORY_ARCHIVE_PATH}")
    os.makedirs(MEMORY_ARCHIVE_PATH, exist_ok=True)
    logger.info(f"Ensuring directory exists: {API_INDEXED_FILES_DIR}")
    os.makedirs(API_INDEXED_FILES_DIR, exist_ok=True) # Ensure source dir exists too

    # Initialize Memory Client
    logger.info("🧠 Initializing CogniMemoryClient...")
    memory_client_instance = None # Define variable in outer scope
    try:
        memory_client_instance = CogniMemoryClient(
            chroma_path=MEMORY_CHROMA_PATH,
            archive_path=MEMORY_ARCHIVE_PATH,
            collection_name="cogni-memory" # Default collection name
        )
        logger.info("🧠 CogniMemoryClient initialized.")

        # Index Charter on startup
        logger.info(f"📚 Indexing files from: {API_INDEXED_FILES_DIR}")
        try:
            # Use tag_filter=set() to index all blocks regardless of tags
            indexed_count = memory_client_instance.index_from_logseq(
                logseq_dir=API_INDEXED_FILES_DIR,
                tag_filter=set(),
                verbose=True # Enable verbose logging for indexing
            )
            logger.info(f"✅ Successfully indexed {indexed_count} blocks from {API_INDEXED_FILES_DIR}.")
        except FileNotFoundError:
             logger.error(f" Indexed files directory not found: {API_INDEXED_FILES_DIR}. Skipping indexing.")
        except Exception as index_e:
            logger.exception(f"❌ Error during indexing from {API_INDEXED_FILES_DIR}: {index_e}")

        # Warm-up the embedding model AFTER client initialization attempt
        if hasattr(memory_client_instance, 'embedding_function'):
            try:
                logger.info("🔥 Warming up embedding model...")
                # Embed a dummy string to trigger model download/load
                _ = memory_client_instance.embedding_function.embed_query("warmup")
                logger.info("✅ Embedding model warmed up successfully.")
            except Exception as warmup_e:
                logger.error(f"⚠️ Failed to warm up embedding model: {warmup_e}")

        # Store the client directly on app.state
        app.state.memory_client = memory_client_instance
        logger.info("🧠 Memory client attached to app.state")
        
    except Exception as client_e:
        logger.exception(f"❌ Failed to initialize CogniMemoryClient: {client_e}")
        app.state.memory_client = None # Indicate failure on app.state
        logger.warning("🧠 app.state.memory_client set to None due to initialization error.")

    # Warm-up the embedding model AFTER client initialization attempt
    if hasattr(app.state, 'memory_client') and app.state.memory_client:
        try:
            logger.info("🔥 Warming up embedding model...")
            # Perform a dummy query to trigger embedding model download/load
            _ = app.state.memory_client.query(query_text="warmup", n_results=1)
            logger.info("✅ Embedding model warmed up successfully.")
        except AttributeError:
             logger.error("⚠️ Failed to warm up: memory_client has no attribute 'embedding_function'")
        except Exception as warmup_e:
            logger.error(f"⚠️ Failed to warm up embedding model: {warmup_e}")

    yield # Yield nothing, state is attached directly

    # --- Shutdown ---
    logger.info("🌙 API shutting down...")
    # Clean up the state if needed
    if hasattr(app.state, 'memory_client'):
         del app.state.memory_client
         logger.info("🧠 Memory client removed from app.state")
    # lifespan_context.clear() # No longer needed


app = FastAPI(
    title="Cogni API",
    description="A minimal FastAPI that directly passes user queries to OpenAI, augmented with Cogni memory.",
    version="0.1.0",
    lifespan=lifespan # Pass the lifespan manager
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
async def stream_chat(body: CompleteQueryRequest, fastapi_request: Request, auth=Depends(verify_auth)):
    logger.info("✅ Received streaming chat request.")
    logger.info(f"✨ Message: {body.message}")
    logger.info(f"✨ History: {body.message_history}")

    # Access memory client from app state (set by lifespan manager)
    memory_client: Optional[CogniMemoryClient] = None
    try:
        memory_client = fastapi_request.app.state.memory_client
    except AttributeError:
        logger.warning("🧠 Memory client not found in app state.")
    
    augmented_message = body.message # Default to original message
    context_str = "No context retrieved."

    if memory_client:
        try:
            logger.info(f"🧠 Querying memory for: '{body.message}'")
            # Query the memory index
            query_results = memory_client.query(
                query_text=body.message, 
                n_results=3 # Adjust n_results as needed
            )
            
            context_blocks = query_results.blocks
            if context_blocks:
                logger.info(f"🧠 Found {len(context_blocks)} relevant blocks.")
                # Format context for the LLM
                context_str = "\n---\n".join([block.text for block in context_blocks])
                
                # Prepare the augmented message for the LLM
                augmented_message = (
                    f"Based on the following context from the CogniDAO Charter:\n\n"
                    f"---CONTEXT---\n{context_str}\n---END CONTEXT---\n"
                    f"Answer the user's question: {body.message}"
                )
                logger.info("✨ Augmented message with context.")
            else:
                logger.info("🧠 No relevant blocks found in memory.")
                
        except Exception as e:
            logger.error(f"🧠 Memory query failed: {e}")
            # Proceed with the original message if query fails
            context_str = f"Memory query failed: {e}" # Include error in context info if needed
    else:
        logger.warning("🧠 Memory client not available. Proceeding without context.")
        context_str = "Memory client not available."

    # Log the final message being sent (potentially augmented)
    # Avoid logging full context string if it's very long in production
    logger.info(f"💬 Sending to LLM (message possibly augmented):\nContext Retrieved: {context_str[:200]}...\nAugmented Prompt Start: {augmented_message[:200]}...") 

    # Pass the (potentially augmented) message and history to the LLM stream generator
    generator = send_message(augmented_message, body.message_history)
    logger.info("▶️ Returning streaming response.")
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