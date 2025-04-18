"""
Simple Cogni API

A minimal FastAPI that directly passes user queries to OpenAI.
"""

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from openai import OpenAI

# Create the FastAPI app
app = FastAPI(
    title="Cogni Simple API",
    description="Direct OpenAI query API",
    version="0.1.0",
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
    query: str
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    system_message: Optional[str] = "You are a helpful AI assistant."

class QueryResponse(BaseModel):
    query: str
    response: str

@app.get("/")
async def root():
    """Root endpoint - health check."""
    return {"status": "ok", "service": "Cogni Simple API"}

@app.post("/ask", response_model=QueryResponse)
async def ask_openai(request: QueryRequest):
    """
    Send a query directly to OpenAI and return the response.
    """
    try:
        # Format system message
        if isinstance(request.system_message, str):
            system_message = {"role": "system", "content": request.system_message}
        else:
            system_message = request.system_message
        
        # Create messages array
        messages = [
            system_message,
            {"role": "user", "content": request.query}
        ]
        
        # Call the OpenAI API directly
        response = openai_client.chat.completions.create(
            model=request.model,
            messages=messages,
            temperature=request.temperature
        )
        
        # Extract the response content
        answer = response.choices[0].message.content
        
        return QueryResponse(
            query=request.query,
            response=answer,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI error: {str(e)}")

# Run with: uvicorn infra_core.cogni_api:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 