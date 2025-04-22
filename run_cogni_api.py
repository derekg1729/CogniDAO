#!/usr/bin/env python
"""
Run the Simple Cogni API Server
"""

import uvicorn

if __name__ == "__main__":
    print("Starting Cogni Simple API")
    print("API documentation available at http://localhost:8000/docs")
    
    # Run the FastAPI server
    uvicorn.run(
        "infra_core.cogni_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    ) 