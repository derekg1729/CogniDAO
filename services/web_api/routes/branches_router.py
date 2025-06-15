from fastapi import APIRouter, Request, HTTPException
from typing import List

from services.web_api.models import ErrorResponse
from infra_core.memory_system.tools.agent_facing.dolt_repo_tool import (
    dolt_list_branches_tool,
    DoltListBranchesInput,
    DoltBranchInfo,
)
import logging

# Setup logger
logger = logging.getLogger(__name__)

router = APIRouter(tags=["v1/Branches"])


@router.get(
    "/branches",
    response_model=List[DoltBranchInfo],
    summary="Get all Dolt branches",
    description="Retrieves list of all available Dolt branches with their metadata including commit information and status.",
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_all_branches(request: Request) -> List[DoltBranchInfo]:
    """
    Retrieves all Dolt branches from the memory bank using the dolt_list_branches_tool.

    Returns detailed information for each branch including:
    - Branch name and latest commit hash
    - Latest committer information
    - Commit date and message
    - Remote tracking information
    - Dirty status (uncommitted changes)
    """
    try:
        memory_bank = request.app.state.memory_bank
        if not memory_bank:
            logger.error("Memory bank not available in app state during branches retrieval.")
            raise HTTPException(status_code=500, detail="Memory bank not available")

        # Use the existing dolt_list_branches_tool
        input_data = DoltListBranchesInput()
        result = dolt_list_branches_tool(input_data, memory_bank)

        if result.success:
            logger.info(f"Successfully retrieved {len(result.branches)} branches")
            return result.branches
        else:
            logger.error(f"Branch listing failed: {result.error}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve branches: {result.error or 'Unknown error'}",
            )

    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        # Log the exception details for debugging
        logger.exception(f"Error retrieving branches: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
