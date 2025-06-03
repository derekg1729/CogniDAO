from fastapi import APIRouter, Request
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/healthz")
async def health_check(request: Request):
    """
    Health check endpoint that validates both API and database connectivity.

    Tests:
    - Memory bank availability in app state
    - Database connectivity via direct connection test

    Returns detailed status for monitoring.
    """
    health_status = {
        "status": "healthy",
        "memory_bank_available": False,
        "database_connected": False,
        "details": {},
    }

    try:
        # Check if memory bank is available in app state
        memory_bank = getattr(request.app.state, "memory_bank", None)
        if not memory_bank:
            health_status["status"] = "unhealthy"
            health_status["details"]["memory_bank"] = "not available in app.state"
            logger.warning("Health check failed: memory bank not available")
            return health_status

        health_status["memory_bank_available"] = True
        health_status["details"]["memory_bank"] = "available"

        # Test database connectivity with direct connection test
        try:
            # Get the dolt reader from the memory bank to test connectivity directly
            dolt_reader = memory_bank.dolt_reader

            # Test connection by attempting to establish a connection
            # This will fail immediately on authentication errors instead of swallowing them
            connection = dolt_reader._get_connection()

            # If we got a connection, test with a simple query
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            connection.close()

            health_status["database_connected"] = True
            health_status["details"]["database"] = "connection and query successful"
            logger.debug("Health check passed: database connection and query successful")

        except Exception as db_error:
            health_status["status"] = "unhealthy"
            health_status["details"]["database"] = f"connection failed: {str(db_error)}"
            logger.error(f"Health check failed: database connection error - {db_error}")

    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["details"]["error"] = f"unexpected error: {str(e)}"
        logger.error(f"Health check failed with unexpected error: {e}")

    return health_status
