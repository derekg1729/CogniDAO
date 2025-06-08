from fastapi import APIRouter, Request
import logging
from datetime import datetime

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


@router.post("/api/v1/refresh")
async def refresh_backend_data(request: Request):
    """
    Refresh backend data by pulling latest changes from remote Dolt repository.

    This endpoint triggers a Dolt pull operation to synchronize the backend
    database with the latest changes from the remote repository.

    Returns:
        JSON response with pull operation status and details
    """
    timestamp = datetime.now()
    refresh_status = {
        "success": False,
        "message": "",
        "timestamp": timestamp.isoformat(),
    }

    try:
        # Check if memory bank is available in app state
        memory_bank = getattr(request.app.state, "memory_bank", None)
        if not memory_bank:
            refresh_status["message"] = "Memory bank not available"
            refresh_status["details"] = {"error": "memory_bank not available in app.state"}
            logger.error("Refresh failed: memory bank not available")
            return refresh_status

        # Import the dolt_pull_tool and input model
        from infra_core.memory_system.tools.agent_facing.dolt_repo_tool import (
            DoltPullInput,
            dolt_pull_tool,
        )

        # Create pull input with default parameters (origin, main branch)
        pull_input = DoltPullInput(
            remote_name="origin",
            branch="main",  # Use explicit main branch (updated default)
            force=False,
            no_ff=False,
            squash=False,
        )

        logger.info("Starting Dolt pull operation for backend refresh")

        # Execute the pull operation using existing infrastructure
        pull_result = dolt_pull_tool(pull_input, memory_bank)

        # Convert result to response format
        refresh_status["success"] = pull_result.success
        refresh_status["message"] = pull_result.message
        refresh_status["timestamp"] = pull_result.timestamp.isoformat()

        if not pull_result.success and pull_result.error:
            refresh_status["error"] = pull_result.error
            logger.error(f"Dolt pull failed: {pull_result.error}")
        else:
            logger.info(f"Dolt pull succeeded: {pull_result.message}")

    except Exception as e:
        refresh_status["message"] = f"Refresh operation failed: {str(e)}"
        refresh_status["error"] = f"unexpected error during refresh: {str(e)}"
        logger.error(f"Refresh operation failed with unexpected error: {e}")

    return refresh_status
