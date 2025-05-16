from fastapi import FastAPI
from contextlib import asynccontextmanager

from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from .core.config import settings
from .api.endpoints import memory_tools


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize StructuredMemoryBank and store in app state
    print(f"Initializing StructuredMemoryBank with Dolt path: {settings.COGNI_DOLT_DIR}")
    print(f"Chroma path: {settings.CHROMA_PATH}, Collection: {settings.CHROMA_COLLECTION_NAME}")
    try:
        app.state.memory_bank = StructuredMemoryBank(
            dolt_db_path=settings.COGNI_DOLT_DIR,
            chroma_path=settings.CHROMA_PATH,
            chroma_collection=settings.CHROMA_COLLECTION_NAME,
        )
        print("StructuredMemoryBank initialized successfully.")
    except Exception as e:
        print(f"Error initializing StructuredMemoryBank: {e}")
        # Optionally, re-raise or handle to prevent app startup if critical
        app.state.memory_bank = None  # Ensure it's None if initialization fails
    yield
    # Shutdown: Clean up resources if any (not strictly needed for SMB in this MVP)
    print("Shutting down MCP server.")


app = FastAPI(
    title="Cogni MCP Server",
    version="0.1.0",
    description="MCP Server for Cogni Tools, enabling interaction with the Memory System.",
    lifespan=lifespan,
)

app.include_router(memory_tools.router)


@app.get("/healthz", tags=["Health"])
async def health_check():
    """Perform a health check."""
    if hasattr(app.state, "memory_bank") and app.state.memory_bank is not None:
        # Could add a more specific check to memory_bank if it has a status method
        return {"status": "ok", "memory_bank_initialized": True}
    return {
        "status": "ok",
        "memory_bank_initialized": False,
        "reason": "Memory bank not initialized or initialization failed.",
    }
