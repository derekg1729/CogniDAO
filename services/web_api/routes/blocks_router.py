from fastapi import APIRouter, Request, HTTPException
from typing import List

from infra_core.memory_system.schemas.memory_block import MemoryBlock
from infra_core.models import ErrorResponse

router = APIRouter()


@router.get(
    "/blocks",
    response_model=List[MemoryBlock],
    summary="Get all memory blocks",
    description="Retrieves all memory blocks currently stored in the system from the main branch.",
    responses={500: {"model": ErrorResponse, "description": "Internal server error"}},
)
async def get_all_blocks(request: Request) -> List[MemoryBlock]:
    """
    Retrieves all memory blocks from the StructuredMemoryBank.
    """
    try:
        memory_bank = request.app.state.memory_bank
        if not memory_bank:
            raise HTTPException(status_code=500, detail="Memory bank not available")

        all_blocks = memory_bank.get_all_memory_blocks()  # Defaults to 'main' branch
        return all_blocks
    except Exception as e:
        # Log the exception details for debugging
        # logger.error(f"Error retrieving all blocks: {e}", exc_info=True) # Assuming logger is available
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
