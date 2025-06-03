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
    - Database connectivity via minimal query

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

        # Test database connectivity with minimal query
        try:
            # Import here to avoid circular import issues
            from infra_core.memory_system.tools.agent_facing.get_active_work_items_tool import (
                get_active_work_items_tool,
            )

            # This is much more efficient - only gets up to 1 work item with filtering at database level
            result = get_active_work_items_tool(memory_bank=memory_bank, limit=1)

            # If we get here without exception, database is connected
            if result.success:
                health_status["database_connected"] = True
                health_status["details"]["database"] = (
                    f"connected - found {result.total_count} active work items"
                )
                logger.debug(
                    f"Health check passed: database connected, {result.total_count} active work items found"
                )
            else:
                health_status["status"] = "unhealthy"
                health_status["details"]["database"] = f"query failed: {result.error}"
                logger.error(f"Health check failed: database query error - {result.error}")

        except Exception as db_error:
            health_status["status"] = "unhealthy"
            health_status["details"]["database"] = f"connection failed: {str(db_error)}"
            logger.error(f"Health check failed: database connection error - {db_error}")

    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["details"]["error"] = f"unexpected error: {str(e)}"
        logger.error(f"Health check failed with unexpected error: {e}")

    return health_status
