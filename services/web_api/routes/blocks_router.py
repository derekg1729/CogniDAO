from fastapi import APIRouter, Request, HTTPException, status, Query
import asyncio

from infra_core.memory_system.schemas.memory_block import MemoryBlock
from services.web_api.models import ErrorResponse, BlocksResponse, SingleBlockResponse
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

# Import branch validation function
from infra_core.memory_system.tools.agent_facing.dolt_repo_tool import validate_branch_name

import logging  # Add logging

# Setup logger
logger = logging.getLogger(__name__)

router = APIRouter(tags=["v1/Blocks"])


@router.get(
    "/blocks",
    response_model=BlocksResponse,
    summary="Get all memory blocks with branch context",
    description="Retrieves memory blocks from specified Dolt branch with active branch context. Defaults to 'main' branch.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid branch name format"},
        404: {"model": ErrorResponse, "description": "Branch not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_all_blocks(
    request: Request,
    type: str = Query(
        None, description="Filter by block type (e.g., 'project', 'knowledge', 'task')"
    ),
    case_insensitive: bool = Query(False, description="Case-insensitive type filtering"),
    branch: str = Query("main", description="Dolt branch to read from (default: 'main')"),
    namespace: str = Query("legacy", description="Filter by namespace (default: 'legacy')"),
) -> BlocksResponse:
    """
    Retrieves memory blocks from the StructuredMemoryBank with branch context.

    Parameters:
    - type: Optional filter for block type (e.g., "project", "knowledge", "task")
    - case_insensitive: If True, type filtering will be case-insensitive
    - branch: Dolt branch to read from (default: "main")
    - namespace: Filter by namespace (default: "legacy")
    """
    # Validate branch name for security
    try:
        validate_branch_name(branch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        memory_bank = request.app.state.memory_bank
        if not memory_bank:
            logger.error("Memory bank not available in app state during blocks retrieval.")
            raise HTTPException(status_code=500, detail="Memory bank not available")

        # Wrap blocking I/O in threadpool to prevent event loop blocking
        loop = asyncio.get_event_loop()
        all_blocks = await loop.run_in_executor(
            None, lambda: memory_bank.get_all_memory_blocks(branch=branch)
        )

        # Track original count before filtering
        original_count = len(all_blocks)
        filters_applied = {}

        # Filter blocks by type if specified (use block_type_filter to avoid shadowing built-in type)
        block_type_filter = type
        if block_type_filter:
            logger.info(
                f"Filtering blocks by type: {block_type_filter} (case_insensitive={case_insensitive})"
            )
            filters_applied["type"] = block_type_filter
            filters_applied["case_insensitive"] = case_insensitive
            if case_insensitive:
                all_blocks = [
                    block for block in all_blocks if block.type.lower() == block_type_filter.lower()
                ]
            else:
                all_blocks = [block for block in all_blocks if block.type == block_type_filter]

        # Filter blocks by namespace (always applied, defaults to 'legacy')
        if namespace:
            logger.info(f"Filtering blocks by namespace: {namespace}")
            filters_applied["namespace"] = namespace
            all_blocks = [block for block in all_blocks if block.namespace_id == namespace]

        logger.info(f"Retrieved {len(all_blocks)} blocks (filtered from {original_count})")

        # Get active branch from memory bank
        active_branch = getattr(memory_bank.dolt_writer, "active_branch", "unknown")

        return BlocksResponse.create_with_timestamp(
            blocks=all_blocks,  # Now properly typed as List[MemoryBlock]
            total_count=len(all_blocks),
            filters_applied=filters_applied if filters_applied else None,
            namespace_context=namespace,
            active_branch=active_branch,
            requested_branch=branch,
        )
    except Exception as e:
        # Log the exception details for debugging
        logger.exception(f"Error retrieving blocks: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.get(
    "/blocks/{block_id}",
    response_model=SingleBlockResponse,
    summary="Get a specific memory block by ID with branch context",
    description="Retrieves a specific memory block by its unique identifier from specified Dolt branch with active branch context.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid branch name format"},
        404: {"model": ErrorResponse, "description": "Memory block or branch not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_block(
    request: Request,
    block_id: str,
    branch: str = Query("main", description="Dolt branch to read from (default: 'main')"),
    namespace: str = Query("legacy", description="Filter by namespace (default: 'legacy')"),
) -> SingleBlockResponse:
    """
    Retrieves a specific memory block by its ID using the get_memory_block_tool with branch context.
    """
    # Validate branch name for security
    try:
        validate_branch_name(branch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 1. Get Memory Bank instance
    try:
        memory_bank = request.app.state.memory_bank
        if not memory_bank:
            logger.error("Memory bank not available in app state during block retrieval.")
            raise HTTPException(status_code=500, detail="Memory bank service unavailable")
    except AttributeError:
        logger.error("Memory bank not configured on app state.")
        raise HTTPException(status_code=500, detail="Memory bank not configured")

    # 2. Call the tool function with threadpool to prevent blocking
    try:
        # Wrap blocking I/O in threadpool to prevent event loop blocking
        loop = asyncio.get_event_loop()
        # Don't pass namespace_id to avoid validation error - we'll filter after retrieval
        output = await loop.run_in_executor(
            None,
            lambda: get_memory_block_tool(
                block_id=block_id, memory_bank=memory_bank, branch=branch
            ),
        )
    except Exception as e:
        # Catch unexpected errors during the tool execution itself
        logger.exception(f"Unexpected error calling get_memory_block_tool: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred during block retrieval: {str(e)}",
        )

    # 3. Handle the output from the tool
    if output.success and len(output.blocks) > 0:
        block = output.blocks[0]

        # Validate namespace if specified
        if namespace and block.namespace_id != namespace:
            logger.warning(
                f"Block {block_id} found but belongs to namespace '{block.namespace_id}', not '{namespace}'"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Memory block with ID '{block_id}' not found in namespace '{namespace}'",
            )

        # Get active branch from memory bank
        active_branch = getattr(memory_bank.dolt_writer, "active_branch", "unknown")

        # Return the enhanced response with branch context
        return SingleBlockResponse.create_with_timestamp(
            block=block,  # Now properly typed as MemoryBlock
            active_branch=active_branch,
            requested_branch=branch,
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
        # Wrap blocking I/O in threadpool to prevent event loop blocking
        loop = asyncio.get_event_loop()
        output = await loop.run_in_executor(
            None, lambda: create_memory_block(input_data=input_data, memory_bank=memory_bank)
        )
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
                # Wrap blocking I/O in threadpool to prevent event loop blocking
                loop = asyncio.get_event_loop()
                created_block = await loop.run_in_executor(
                    None, lambda: memory_bank.get_memory_block(output.id)
                )
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
