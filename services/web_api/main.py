"""
Main entry point for the Cogni API application.
This file is targeted by Uvicorn to run the FastAPI application.
"""

import logging
from dotenv import load_dotenv

# Import the FastAPI application instance from app.py
from .app import app  # noqa: F401

# Set up basic logging configuration
# This should be done once, early in the application startup.
logging.basicConfig(
    level=logging.INFO,
    # format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' # Use default for now
)
logger = logging.getLogger(__name__)  # Logger for main.py, if needed for startup messages

# Load environment variables from .env file
load_dotenv()

logger.info("Application instance imported via 'from .app import app'. Ready for Uvicorn.")

# Uvicorn will look for an 'app' variable in this file.
# By importing it from .app, we make it available.
