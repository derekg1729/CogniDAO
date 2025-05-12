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

# Import memory components - Updated for Dolt + LlamaIndex
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.schemas.memory_block import MemoryBlock

# Import doc query tool
from infra_core.memory_system.tools.agent_facing.query_doc_memory_block_tool import (
    query_doc_memory_block,
    QueryDocMemoryBlockInput,
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    # format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' # Use default for now
)
logger = logging.getLogger(__name__)

load_dotenv()

# Define paths for memory and source data
API_INDEXED_FILES_DIR = "./api_indexed_files"

# Define paths for Dolt and LlamaIndex storage
DOLT_DB_PATH = "data/memory_dolt"  # Path to Dolt database
CHROMA_PATH = "data/memory_chroma"  # Path to ChromaDB storage
CHROMA_COLLECTION = "cogni_memory_poc"  # Name of ChromaDB collection

# Lifespan context to hold shared resources like the memory client
# lifespan_context = {} # No longer needed


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the lifespan of the application, including memory client setup."""
    logger.info("🚀 API starting up...")

    # Ensure necessary directories exist
    os.makedirs(CHROMA_PATH, exist_ok=True)
    logger.info(f"Ensuring directory exists: {API_INDEXED_FILES_DIR}")
    os.makedirs(API_INDEXED_FILES_DIR, exist_ok=True)  # Ensure source dir exists too

    # Initialize StructuredMemoryBank
    logger.info("🧠 Initializing StructuredMemoryBank...")
    memory_bank_instance = None  # Define variable in outer scope
    try:
        memory_bank_instance = StructuredMemoryBank(
            dolt_db_path=DOLT_DB_PATH,
            chroma_path=CHROMA_PATH,
            chroma_collection=CHROMA_COLLECTION,
        )
        logger.info("🧠 StructuredMemoryBank initialized.")

        # Store the memory bank directly on app.state
        app.state.memory_bank = memory_bank_instance
        logger.info("🧠 Memory bank attached to app.state")

    except Exception as client_e:
        logger.exception(f"❌ Failed to initialize StructuredMemoryBank: {client_e}")
        app.state.memory_bank = None  # Indicate failure on app.state
        logger.warning("🧠 app.state.memory_bank set to None due to initialization error.")

    yield  # Yield nothing, state is attached directly

    # --- Shutdown ---
    logger.info("🌙 API shutting down...")
    # Clean up the state if needed
    if hasattr(app.state, "memory_bank"):
        del app.state.memory_bank
        logger.info("🧠 Memory bank removed from app.state")


app = FastAPI(
    title="Cogni API",
    description="A minimal FastAPI that directly passes user queries to OpenAI, augmented with Cogni memory.",
    version="0.1.0",
    lifespan=lifespan,  # Pass the lifespan manager
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
    api_key = os.getenv("COGNI_API_KEY")
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


# Updated to include source blocks
async def send_message(
    message: str,
    memory_blocks: Optional[List[MemoryBlock]] = None,
    history: Optional[List[Dict[str, str]]] = None,
) -> AsyncIterable[str]:
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

    # Prepare context from memory blocks if available
    if memory_blocks and len(memory_blocks) > 0:
        # Convert memory blocks to a context string
        context_blocks = []
        logger.info("📚 Preparing context from memory blocks:")
        for i, block in enumerate(memory_blocks):
            # Extract title from metadata if it exists
            title = block.metadata.get("title", "Memory Block")
            logger.info(f"  📄 Block {i + 1}: {title}")

            # Format the block text for the context
            formatted_block = f"--- {title} ---\n{block.text}"
            context_blocks.append(formatted_block)

            # Log a preview of what we're adding to the context
            preview = block.text.replace("\n", " ")[:100]
            if len(block.text) > 100:
                preview += "..."
            logger.info(f"    Preview: {preview}")

        context_str = "\n\n".join(context_blocks)

        # Create augmented message with context
        augmented_message = (
            f"Based on the following context information:\n\n"
            f"---CONTEXT START---\n{context_str}\n---CONTEXT END---\n\n"
            f"Please answer the user's question: {message}"
        )

        logger.info(f"📝 Created augmented message with {len(memory_blocks)} memory blocks")
        logger.info(f"❓ Original user question: {message}")

        # Add as a user message
        lc_messages.append(HumanMessage(content=augmented_message))
    else:
        # No context available, use original message
        logger.info("⚠️ No memory blocks available, using original message without context")
        lc_messages.append(HumanMessage(content=message))

    logger.info(f"📡 Sending {len(lc_messages)} messages to LangChain model")
    logger.info("▶️ Creating task with LangChain model")
    task = asyncio.create_task(model.agenerate(messages=[lc_messages]))

    # Stream tokens directly without including source blocks in the response
    token_count = 0
    full_response = ""
    try:
        logger.info("✉️ Starting token streaming...")
        async for token in callback.aiter():
            token_count += 1
            # Log important tokens for debugging
            if (
                token_count <= 5
                or token_count % 20 == 0
                or token_count >= 80
                and token_count % 10 == 0
            ):
                logger.info(f"📤 Token {token_count}: {token}")
            full_response += token
            # Simply yield the token text directly
            yield token
    except Exception as e:
        logger.error(f"Error during streaming: {e}")
        print(f"Caught exception: {e}")
    finally:
        callback.done.set()
        logger.info(f"🏁 Completed streaming {token_count} tokens")
        # Log a truncated version of the full response
        truncated_response = full_response
        if len(full_response) > 300:
            truncated_response = full_response[:150] + " ... " + full_response[-150:]
        logger.info(f"📄 Response summary: {truncated_response}")

    await task
    logger.info("✅ Task completed")


@app.post("/chat")
async def stream_chat(
    body: CompleteQueryRequest, fastapi_request: Request, auth=Depends(verify_auth)
):
    logger.info("✅ Received streaming chat request.")
    logger.info(f"✨ Message: {body.message}")
    logger.info(f"✨ History: {body.message_history}")

    # Access memory bank from app state
    memory_bank = None
    try:
        memory_bank = fastapi_request.app.state.memory_bank
    except AttributeError:
        logger.warning("🧠 Memory bank not found in app state.")

    # Variable to store retrieved memory blocks
    memory_blocks = []

    # Query the memory system if available
    if memory_bank:
        try:
            logger.info(f"🧠 Querying memory for: '{body.message}'")

            # Use the doc-specific query tool instead of query_semantic
            query_input = QueryDocMemoryBlockInput(
                query_text=body.message,
                top_k=3,  # Return top 3 documents
                tag_filters=["core-document"],  # Add tag filter to get core documentation
                # Explicitly set type filter to "doc" - this is handled by the tool but being explicit
                # The underlying QueryDocMemoryBlockTool forces type="doc"
            )

            # Log the input parameters
            logger.info(f"🧠 Calling query_doc_memory_block with input: {query_input}")

            # Execute the query for document blocks only
            query_result = query_doc_memory_block(query_input, memory_bank)

            # Log the query result
            logger.info(
                f"🧠 Doc query result success: {query_result.success}, blocks count: {len(query_result.blocks) if query_result.blocks else 0}"
            )

            if query_result.success and query_result.blocks:
                logger.info(f"🧠 Found {len(query_result.blocks)} relevant document blocks.")
                memory_blocks = query_result.blocks

                # Log what was found - with detailed information
                logger.info("🧠 Retrieved blocks details:")
                for i, block in enumerate(memory_blocks):
                    # Extract meaningful information for logging
                    title = block.metadata.get("title", "[No Title]")
                    doc_type = block.type
                    tags_str = ", ".join(block.tags) if block.tags else "None"

                    # Format preview with line breaks replaced
                    preview = (
                        block.text.replace("\n", " ")[:100] + "..."
                        if len(block.text) > 100
                        else block.text.replace("\n", " ")
                    )

                    # Log comprehensive information about each block
                    logger.info(f"  🔖 Block {i + 1}: {title}")
                    logger.info(f"    📋 ID: {block.id}")
                    logger.info(f"    📚 Type: {doc_type}")
                    logger.info(f"    🏷️ Tags: {tags_str}")
                    logger.info(f"    📄 Preview: {preview}")

                    # Log additional metadata if available
                    if block.metadata:
                        metadata_str = ", ".join(
                            [f"{k}: {v}" for k, v in block.metadata.items() if k != "title"]
                        )
                        logger.info(f"    ℹ️ Other Metadata: {metadata_str}")
            else:
                logger.info("🧠 No relevant document blocks found.")
                if query_result.error:
                    logger.error(f"🧠 Query error: {query_result.error}")

        except Exception as e:
            logger.error(f"🧠 Memory query failed: {e}", exc_info=True)
    else:
        logger.warning("🧠 Memory bank not available. Proceeding without memory augmentation.")

    # Pass memory blocks to the message handler
    generator = send_message(
        message=body.message, memory_blocks=memory_blocks, history=body.message_history
    )

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
        body_str = body.decode("utf-8")
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
        content=ErrorResponse(detail=str(exc), code="VALIDATION_ERROR").model_dump(),
    )
