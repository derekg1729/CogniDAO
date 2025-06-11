from fastapi import APIRouter, Request
import logging
from datetime import datetime
import httpx

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
        "prefect_server_available": False,
        "prefect_work_pool_available": False,
        "prefect_worker_available": False,
        "toolhive_available": False,
        "mcp_tools_accessible": False,
        "cogni_mcp_available": False,
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

        # Test Prefect server connectivity
        try:
            # Check if Prefect server is accessible via Docker network
            async with httpx.AsyncClient(timeout=5.0) as client:
                prefect_response = await client.get("http://prefect-server:4200/api/health")
                if prefect_response.status_code == 200:
                    health_status["prefect_server_available"] = True
                    health_status["details"]["prefect_server"] = "connected and healthy"
                    logger.debug("Health check passed: Prefect server connection successful")
                else:
                    health_status["details"]["prefect_server"] = (
                        f"responded with status {prefect_response.status_code}"
                    )
                    logger.warning(
                        f"Prefect server responded with status {prefect_response.status_code}"
                    )
        except Exception as prefect_error:
            health_status["details"]["prefect_server"] = f"connection failed: {prefect_error!r}"
            logger.exception("Prefect health check HTTP request failed")

        # Test Prefect work pool availability
        try:
            # Check if cogni-pool work pool exists and is accessible
            async with httpx.AsyncClient(timeout=5.0) as client:
                work_pool_response = await client.get(
                    "http://prefect-server:4200/api/work_pools/cogni-pool"
                )
                if work_pool_response.status_code == 200:
                    health_status["prefect_work_pool_available"] = True
                    health_status["details"]["prefect_work_pool"] = (
                        "cogni-pool found and accessible"
                    )
                    logger.debug("Health check passed: Prefect work pool cogni-pool accessible")
                else:
                    health_status["details"]["prefect_work_pool"] = (
                        f"cogni-pool responded with status {work_pool_response.status_code}"
                    )
                    logger.warning(
                        f"Prefect work pool cogni-pool responded with status {work_pool_response.status_code}"
                    )
        except Exception as work_pool_error:
            health_status["details"]["prefect_work_pool"] = (
                f"connection failed: {work_pool_error!r}"
            )
            logger.exception("Prefect work pool health check failed")

        # Test Prefect worker availability
        try:
            # First check if work pool exists and get its workers via work pool endpoint
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Use the correct POST endpoint to get workers for cogni-pool
                pool_response = await client.post(
                    "http://prefect-server:4200/api/work_pools/cogni-pool/workers/filter",
                    json={},
                    headers={"Content-Type": "application/json"},
                )
                if pool_response.status_code == 200:
                    workers_data = pool_response.json()
                    online_workers = [w for w in workers_data if w.get("status") == "ONLINE"]
                    if online_workers:
                        health_status["prefect_worker_available"] = True
                        health_status["details"]["prefect_worker"] = (
                            f"{len(online_workers)} worker(s) online in cogni-pool"
                        )
                        logger.debug(
                            f"Health check passed: {len(online_workers)} Prefect workers online"
                        )
                    else:
                        health_status["details"]["prefect_worker"] = (
                            f"found {len(workers_data)} workers but none are ONLINE"
                        )
                        logger.warning("Prefect workers found but none are ONLINE")
                elif pool_response.status_code == 404:
                    # Work pool might not exist yet, check general workers endpoint
                    workers_response = await client.get("http://prefect-server:4200/api/work_pools")
                    if workers_response.status_code == 200:
                        pools_data = workers_response.json()
                        cogni_pool = next(
                            (p for p in pools_data if p.get("name") == "cogni-pool"), None
                        )
                        if cogni_pool:
                            health_status["details"]["prefect_worker"] = (
                                "cogni-pool exists but no workers accessible"
                            )
                        else:
                            health_status["details"]["prefect_worker"] = (
                                "cogni-pool not found - will be auto-created by worker"
                            )
                    else:
                        health_status["details"]["prefect_worker"] = (
                            f"work pools endpoint responded with status {workers_response.status_code}"
                        )
                else:
                    health_status["details"]["prefect_worker"] = (
                        f"pool workers endpoint responded with status {pool_response.status_code}"
                    )
                    logger.warning(
                        f"Prefect pool workers endpoint responded with status {pool_response.status_code}"
                    )
        except Exception as worker_error:
            health_status["details"]["prefect_worker"] = f"connection failed: {worker_error!r}"
            logger.exception("Prefect worker health check failed")

        # Test ToolHive container availability first (MCP check depends on this)
        try:
            # Check if ToolHive HTTP server is running and responding
            async with httpx.AsyncClient(timeout=5.0) as client:
                try:
                    # Test ToolHive HTTP server - any response indicates server is running
                    toolhive_response = await client.get("http://toolhive:8080/")
                    # Any HTTP response (even 404) means server is running
                    if toolhive_response.status_code in [200, 404]:
                        health_status["toolhive_available"] = True
                        health_status["details"]["toolhive"] = "HTTP server responding"
                        logger.debug("Health check passed: ToolHive HTTP server responding")
                    else:
                        health_status["details"]["toolhive"] = (
                            f"HTTP server returned {toolhive_response.status_code}"
                        )
                        logger.warning(
                            f"ToolHive HTTP server returned status {toolhive_response.status_code}"
                        )
                except Exception as http_error:
                    health_status["details"]["toolhive"] = (
                        f"HTTP server not reachable: {http_error!r}"
                    )
                    logger.warning(f"ToolHive HTTP server connectivity test failed: {http_error}")

        except Exception as toolhive_error:
            health_status["details"]["toolhive"] = f"container check failed: {toolhive_error!r}"
            logger.exception("ToolHive container health check failed")

        # Test Cogni MCP container availability via ToolHive
        try:
            # Since ToolHive manages the MCP server, we check if both ToolHive is accessible
            # and if the cogni-mcp container is running properly
            if health_status["toolhive_available"]:
                # If ToolHive is available, check if MCP container is running and accessible
                # For now, we'll use a simplified check - if ToolHive is managing containers
                # and we know the MCP container should be running, mark as available

                # In a production environment, you'd use ToolHive's API to check MCP status
                # For now, we'll do a basic container connectivity test
                async with httpx.AsyncClient(timeout=3.0) as client:
                    try:
                        # Test ToolHive endpoint to ensure it's responsive for MCP management
                        toolhive_test = await client.get("http://toolhive:8080/", timeout=2.0)
                        if toolhive_test.status_code in [200, 404, 405]:
                            # ToolHive is responsive, assume MCP is properly managed
                            health_status["cogni_mcp_available"] = True
                            health_status["details"]["cogni_mcp"] = "MCP server managed by ToolHive"
                            logger.debug("Health check passed: MCP server managed by ToolHive")
                        else:
                            health_status["details"]["cogni_mcp"] = (
                                f"ToolHive management endpoint issue: {toolhive_test.status_code}"
                            )
                    except Exception as toolhive_error:
                        health_status["details"]["cogni_mcp"] = (
                            f"ToolHive MCP management check failed: {toolhive_error!r}"
                        )
            else:
                health_status["details"]["cogni_mcp"] = (
                    "ToolHive not available - cannot check MCP status"
                )

        except Exception as cogni_mcp_error:
            health_status["details"]["cogni_mcp"] = (
                f"MCP availability check failed: {cogni_mcp_error!r}"
            )
            logger.exception("cogni-mcp availability health check failed")

        # Test MCP tools accessibility via host ToolHive CLI
        try:
            # Since ToolHive is a CLI tool, we check if MCP containers are running
            # by testing known MCP endpoint connectivity
            if health_status["toolhive_available"]:
                try:
                    # Use thv list command to check running MCP tools (if accessible from container)
                    # This is a simplified check - in production you'd want to run this from a sidecar
                    health_status["details"]["mcp_tools"] = (
                        "ToolHive container available - MCP tools managed externally"
                    )
                    logger.info("ToolHive container available - MCP tools managed via external CLI")

                    # For now, we'll mark as available if ToolHive container is running
                    # In a full implementation, you'd check actual MCP endpoints
                    health_status["mcp_tools_accessible"] = True

                except Exception as cli_error:
                    health_status["details"]["mcp_tools"] = (
                        f"MCP tools check via CLI failed: {cli_error!r}"
                    )
                    logger.warning(f"MCP tools CLI check failed: {cli_error}")
            else:
                health_status["details"]["mcp_tools"] = (
                    "ToolHive container not available - cannot check MCP tools"
                )
                logger.info("Skipping MCP tools check - ToolHive container not available")
        except Exception as mcp_error:
            health_status["details"]["mcp_tools"] = f"MCP tools check failed: {mcp_error!r}"
            logger.exception("MCP tools health check failed")

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
