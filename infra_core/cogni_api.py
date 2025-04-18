"""
Simple Cogni API

A minimal FastAPI that directly passes user queries to OpenAI.
"""

import os
import logging
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError
from typing import Optional

from openai import OpenAI

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create the FastAPI app
app = FastAPI(
    title="Cogni Simple API",
    description="Direct OpenAI query API",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define a function to initialize OpenAI client without using Prefect
def get_openai_client():
    """Initialize OpenAI client with API key from environment."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
    return OpenAI(api_key=api_key)

# Create the OpenAI client
openai_client = get_openai_client()

# Define request/response models
class QueryRequest(BaseModel):
    message: str
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    system_message: Optional[str] = "You are a helpful AI assistant."

class QueryResponse(BaseModel):
    message: str
    response: str

@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """
    Handle validation errors and log detailed information.
    """
    logger.error(f"Validation error on request: {exc}")
    try:
        body = await request.json()
        logger.error(f"Request body: {json.dumps(body)}")
    except Exception as e:
        logger.error(f"Could not parse request body: {str(e)}")
    
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc)}
    )

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware to log all requests and responses."""
    # Log request
    logger.info(f"Request: {request.method} {request.url}")
    
    # Parse and log request body for POST requests
    if request.method == "POST":
        try:
            body = await request.body()
            body_str = body.decode()
            logger.info(f"Request body: {body_str}")
            # Create a new body stream
            request._body = body
        except Exception as e:
            logger.error(f"Error parsing request body: {str(e)}")
    
    # Process request
    response = await call_next(request)
    
    # Log response
    logger.info(f"Response status: {response.status_code}")
    
    return response

@app.get("/")
async def root():
    """Root endpoint - health check."""
    logger.info("Health check endpoint accessed")
    return {"status": "ok", "service": "Cogni Simple API"}

@app.post("/chat", response_model=QueryResponse)
async def chat_with_openai(request: QueryRequest):
    """
    Send a query directly to OpenAI and return the response.
    """
    logger.info(f"Processing chat request for message: '{request.message}'")
    logger.info(f"Request details: model={request.model}, temp={request.temperature}")
    
    try:
        # Format system message
        if isinstance(request.system_message, str):
            system_message = {"role": "system", "content": request.system_message}
        else:
            system_message = request.system_message
        
        logger.info(f"System message: {system_message}")
        
        # Create messages array
        messages = [
            system_message,
            {"role": "user", "content": request.message}
        ]
        
        logger.info("Calling OpenAI API...")
        
        # Call the OpenAI API directly
        response = openai_client.chat.completions.create(
            model=request.model,
            messages=messages,
            temperature=request.temperature
        )
        
        # Extract the response content
        answer = response.choices[0].message.content
        logger.info(f"Received response from OpenAI (first 50 chars): {answer[:50]}...")
        
        result = QueryResponse(
            message=request.message,
            response=answer,
        )
        
        logger.info("Successfully processed request")
        return result
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"OpenAI error: {str(e)}")

# Run with: uvicorn infra_core.cogni_api:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 