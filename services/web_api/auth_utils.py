import os
from fastapi import Header, HTTPException
import logging

# Set up logger for auth utils
logger = logging.getLogger(__name__)


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
