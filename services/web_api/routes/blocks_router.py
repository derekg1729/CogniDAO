from fastapi import APIRouter, Request, HTTPException, status
from typing import List
from fastapi.responses import JSONResponse

from infra_core.memory_system.schemas.memory_block import MemoryBlock
from services.web_api.models import ErrorResponse
# Remove direct import of validate_metadata
# from infra_core.memory_system.schemas.registry import validate_metadata

# Add imports for the tool function and its models
from infra_core.memory_system.tools.memory_core.create_memory_block_tool import (
    create_memory_block,
    CreateMemoryBlockInput,
    # CreateMemoryBlockOutput is used implicitly by the function
)

# Import the get_memory_block_tool for retrieving single blocks
from infra_core.memory_system.tools.agent_facing.get_memory_block_tool import (
    get_memory_block_tool,
)
import logging  # Add logging

# Setup logger
logger = logging.getLogger(__name__)

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


@router.get(
    "/blocks/{block_id}",
    response_model=MemoryBlock,
    summary="Get a specific memory block by ID",
    description="Retrieves a specific memory block by its unique identifier.",
    responses={
        404: {"model": ErrorResponse, "description": "Memory block not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_block(request: Request, block_id: str) -> MemoryBlock:
    """
    Retrieves a specific memory block by its ID using the get_memory_block_tool.
    """
    # 1. Get Memory Bank instance
    try:
        memory_bank = request.app.state.memory_bank
        if not memory_bank:
            logger.error("Memory bank not available in app state during block retrieval.")
            raise HTTPException(status_code=500, detail="Memory bank service unavailable")
    except AttributeError:
        logger.error("Memory bank not configured on app state.")
        raise HTTPException(status_code=500, detail="Memory bank not configured")

    # 2. Call the tool function
    try:
        # Call the tool with block_id parameter directly
        output = get_memory_block_tool(block_id=block_id, memory_bank=memory_bank)
    except Exception as e:
        # Catch unexpected errors during the tool execution itself
        logger.exception(f"Unexpected error calling get_memory_block_tool: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred during block retrieval: {str(e)}",
        )

    # 3. Handle the output from the tool
    if output.success and output.block:
        # Return the block with caching headers
        return JSONResponse(
            content=output.block.model_dump(mode="json"),
            headers={"Cache-Control": "max-age=3600, public"},  # Cache for 1 hour
        )
    else:
        # Handle block not found or other errors
        error_msg = output.error or "Unknown error during block retrieval"
        logger.warning(f"Block retrieval failed: {error_msg}")

        if "not found" in error_msg.lower():
            # Block not found - return 404
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Memory block with ID '{block_id}' not found",
            )
        else:
            # Other errors - return 500
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve block: {error_msg}",
            )


@router.post(
    "/blocks",
    response_model=MemoryBlock,  # Keep response model as MemoryBlock
    status_code=status.HTTP_201_CREATED,
    summary="Create a new memory block",
    description="Adds a new memory block to the system using the core creation tool.",  # Updated description
    responses={
        422: {
            "model": ErrorResponse,
            # Updated description for 422
            "description": "Validation Error (invalid input data or metadata)",
        },
        500: {
            "model": ErrorResponse,
            "description": "Internal server error (failed to save or fetch)",
        },
    },
)
# Update function signature to use CreateMemoryBlockInput
async def create_block(request: Request, input_data: CreateMemoryBlockInput) -> MemoryBlock:
    """
    Creates a new memory block using the centralized create_memory_block tool.
    """
    # 1. Get Memory Bank instance
    try:
        memory_bank = request.app.state.memory_bank
        if not memory_bank:
            logger.error("Memory bank not available in app state during block creation.")
            raise HTTPException(status_code=500, detail="Memory bank service unavailable")
    except AttributeError:
        logger.error("Memory bank not configured on app state.")
        raise HTTPException(status_code=500, detail="Memory bank not configured")

    # 2. Call the core tool function
    try:
        # The create_memory_block function now encapsulates validation and persistence
        output = create_memory_block(input_data=input_data, memory_bank=memory_bank)
    except Exception as e:
        # Catch unexpected errors during the tool execution itself
        logger.exception(f"Unexpected error calling create_memory_block tool: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred during block creation process: {str(e)}",
        )

    # 3. Handle the output from the tool
    if output.success:
        # Block created successfully, fetch the full block to return
        if output.id:
            try:
                # Fetch the newly created block using its ID
                created_block = memory_bank.get_memory_block(output.id)
                if created_block:
                    return created_block
                else:
                    # This case is unlikely if creation succeeded, but handle defensively
                    logger.error(
                        f"Block creation reported success (ID: {output.id}), but fetch failed."
                    )
                    raise HTTPException(status_code=500, detail="Failed to retrieve created block")
            except Exception as e:
                logger.exception(f"Error fetching created block (ID: {output.id}): {e}")
                # Return 500 as we can't confirm the final state or return the object
                raise HTTPException(
                    status_code=500, detail="Failed to retrieve created block after creation"
                )
        else:
            # Should not happen if success is True, but log and raise error
            logger.error("Block creation reported success but returned no ID.")
            raise HTTPException(status_code=500, detail="Internal error after block creation")
    else:
        # Creation failed, determine the error type
        error_msg = output.error or "Unknown error during block creation"
        logger.warning(f"Block creation failed: {error_msg}")  # Log the failure reason

        # Check for validation-related errors (adjust keywords as needed based on tool's error messages)
        if "validation failed" in error_msg.lower() or "invalid block type" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Input validation failed: {error_msg}",
            )
        else:
            # Assume other errors (persistence, unexpected) are internal server errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create block: {error_msg}",
            )


# Removed the old implementation logic.
# The new logic uses the create_memory_block tool function directly.
