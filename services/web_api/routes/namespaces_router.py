from fastapi import APIRouter, Request, HTTPException
import asyncio

from services.web_api.models import ErrorResponse, NamespacesResponse
from infra_core.memory_system.tools.agent_facing.dolt_namespace_tool import (
    list_namespaces_tool,
    ListNamespacesInput,
)
import logging

# Setup logger
logger = logging.getLogger(__name__)

router = APIRouter(tags=["v1/Namespaces"])


@router.get(
    "/namespaces",
    response_model=NamespacesResponse,
    summary="Get all available namespaces with context",
    description="Retrieves list of all available namespaces with their metadata including creation information, ownership, and active status.",
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_all_namespaces(request: Request) -> NamespacesResponse:
    """
    Retrieves all namespaces from the memory bank using the list_namespaces_tool.

    Returns detailed information for each namespace including:
    - Namespace ID, name, and slug
    - Owner information
    - Creation date and description
    - Active status
    """
    try:
        memory_bank = request.app.state.memory_bank
        if not memory_bank:
            logger.error("Memory bank not available in app state during namespaces retrieval.")
            raise HTTPException(status_code=500, detail="Memory bank not available")

        # Use the existing list_namespaces_tool with threadpool to prevent blocking
        input_data = ListNamespacesInput()

        # Wrap blocking I/O in threadpool to prevent event loop blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: list_namespaces_tool(input_data, memory_bank)
        )

        if result.success:
            logger.info(f"Successfully retrieved {len(result.namespaces)} namespaces")

            return NamespacesResponse.create_with_timestamp(
                namespaces=result.namespaces,  # Now properly typed as List[NamespaceInfo]
                total_count=result.total_count,
                active_branch=result.active_branch,
                requested_branch=None,  # No specific branch requested for listing all
            )
        else:
            logger.error(f"Namespace listing failed: {result.error}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve namespaces: {result.error or 'Unknown error'}",
            )

    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        # Log the exception details for debugging
        logger.exception(f"Error retrieving namespaces: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
