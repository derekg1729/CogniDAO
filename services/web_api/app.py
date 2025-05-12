import logging
import json
import os
from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import our schemas
from services.web_api.models import ErrorResponse

# Import memory components
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank

# Import routers
from .routes import health as health_router
from .routes import chat as chat_router
from .routes import blocks_router

# Set up logger for this app module
logger = logging.getLogger(__name__)

# Define paths for memory and source data (moved from main.py)
DOLT_DB_PATH = "data/memory_dolt"
CHROMA_PATH = "data/memory_chroma"
CHROMA_COLLECTION = "cogni_memory_poc"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the lifespan of the application, including memory client setup."""
    logger.info("🚀 API starting up...")

    os.makedirs(CHROMA_PATH, exist_ok=True)

    logger.info("🧠 Initializing StructuredMemoryBank...")
    memory_bank_instance = None
    try:
        memory_bank_instance = StructuredMemoryBank(
            dolt_db_path=DOLT_DB_PATH,
            chroma_path=CHROMA_PATH,
            chroma_collection=CHROMA_COLLECTION,
        )
        logger.info("🧠 StructuredMemoryBank initialized.")
        app.state.memory_bank = memory_bank_instance
        logger.info("🧠 Memory bank attached to app.state")
    except Exception as client_e:
        logger.exception(f"❌ Failed to initialize StructuredMemoryBank: {client_e}")
        app.state.memory_bank = None
        logger.warning("🧠 app.state.memory_bank set to None due to initialization error.")

    yield

    logger.info("🌙 API shutting down...")
    if hasattr(app.state, "memory_bank"):
        del app.state.memory_bank
        logger.info("🧠 Memory bank removed from app.state")


app = FastAPI(
    title="Cogni API",
    description="A minimal FastAPI that directly passes user queries to OpenAI, augmented with Cogni memory.",
    version="0.1.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(health_router.router)
app.include_router(chat_router.router)
app.include_router(blocks_router.router, prefix="/api", tags=["Blocks"])

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Log middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware to log all requests and responses."""
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response


# Validation exception handler
@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc: Any):
    """Handle 422 Unprocessable Entity errors and log detailed information."""
    logger.error(f"Validation error (422) on request to: {request.url}")
    logger.error(f"Request headers: {dict(request.headers)}")
    try:
        body = await request.body()
        body_str = body.decode("utf-8")
        logger.error(f"Raw request body: {body_str}")
        try:
            json_body = json.loads(body_str)
            logger.error(f"Parsed JSON body: {json.dumps(json_body, indent=2)}")
        except json.JSONDecodeError:
            pass
    except Exception as e:
        logger.error(f"Could not parse request body: {str(e)}")

    return JSONResponse(
        status_code=422,
        content=ErrorResponse(detail=str(exc), code="VALIDATION_ERROR").model_dump(),
    )
