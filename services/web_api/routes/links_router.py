from fastapi import APIRouter, Request, HTTPException, status, Depends
from typing import List, Optional, Dict, Any
import logging
import uuid

from infra_core.memory_system.link_manager import LinkManager, LinkError, LinkQuery, BlockLink
from infra_core.memory_system.schemas.common import RelationType
from services.web_api.models import ErrorResponse

# Setup logger
logger = logging.getLogger(__name__)

router = APIRouter(tags=["v1/Links"])


def get_link_manager(request: Request):
    """Dependency to get the LinkManager from the app state."""
    try:
        memory_bank = request.app.state.memory_bank
        if not memory_bank:
            logger.error("Memory bank not available in app state")
            raise HTTPException(status_code=500, detail="Memory bank service unavailable")

        # The LinkManager should be accessible via the memory_bank
        # This will need to be implemented once the concrete LinkManager class exists
        # For now, raise an error as the implementation isn't complete
        raise HTTPException(status_code=501, detail="LinkManager not yet implemented")
    except AttributeError:
        logger.error("Memory bank not configured on app state")
        raise HTTPException(status_code=500, detail="Memory bank not configured")


@router.post(
    "/links",
    response_model=BlockLink,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new link between blocks",
    description="Creates a directed link between two memory blocks with a specified relation type.",
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Bad Request - Invalid parameters or validation error",
        },
        409: {
            "model": ErrorResponse,
            "description": "Conflict - Concurrency issue or link already exists",
        },
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def create_link(
    request: Request,
    from_id: str,
    to_id: str,
    relation: RelationType,
    priority: int = 0,
    link_metadata: Optional[Dict[str, Any]] = None,
    created_by: Optional[str] = None,
    link_manager: LinkManager = Depends(get_link_manager),
) -> BlockLink:
    """
    Creates a new link between two memory blocks.

    Parameters:
    - from_id: ID of the source block
    - to_id: ID of the target block
    - relation: Type of relationship
    - priority: Optional priority value (higher = more important)
    - link_metadata: Optional metadata about the link
    - created_by: Optional ID of the agent/user creating the link
    """
    try:
        # Validate UUIDs
        try:
            uuid.UUID(from_id)
            uuid.UUID(to_id)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid UUID format: IDs must be valid UUID strings"
            )

        # Use LinkManager to create the link
        link = link_manager.create_link(
            from_id=from_id,
            to_id=to_id,
            relation=relation,
            priority=priority,
            link_metadata=link_metadata,
            created_by=created_by,
        )
        return link

    except LinkError as e:
        # Convert LinkError to appropriate HTTP response
        error_detail = {"code": e.code, "message": str(e)}
        raise HTTPException(status_code=e.http_status, detail=error_detail)
    except ValueError as e:
        # Handle validation errors
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    except Exception as e:
        # Log unexpected errors
        logger.exception(f"Unexpected error creating link: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.delete(
    "/links",
    status_code=status.HTTP_200_OK,
    summary="Delete a link between blocks",
    description="Removes a specific link between two memory blocks.",
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request - Invalid parameters"},
        404: {"model": ErrorResponse, "description": "Not Found - Link does not exist"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def delete_link(
    request: Request,
    from_id: str,
    to_id: str,
    relation: RelationType,
    link_manager: LinkManager = Depends(get_link_manager),
) -> Dict[str, Any]:
    """
    Deletes a link between two memory blocks.

    Parameters:
    - from_id: ID of the source block
    - to_id: ID of the target block
    - relation: Type of relationship
    """
    try:
        # Validate UUIDs
        try:
            uuid.UUID(from_id)
            uuid.UUID(to_id)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid UUID format: IDs must be valid UUID strings"
            )

        # Use LinkManager to delete the link
        result = link_manager.delete_link(from_id=from_id, to_id=to_id, relation=relation)

        if result:
            return {"success": True, "message": "Link deleted successfully"}
        else:
            # Link didn't exist
            raise HTTPException(
                status_code=404,
                detail=f"Link not found between {from_id} and {to_id} with relation {relation}",
            )

    except ValueError as e:
        # Handle validation errors
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    except Exception as e:
        # Log unexpected errors
        logger.exception(f"Unexpected error deleting link: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.get(
    "/links/from/{block_id}",
    response_model=List[BlockLink],
    summary="Get links from a block",
    description="Retrieves all links originating from a specific block, with optional filtering.",
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request - Invalid parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_links_from(
    request: Request,
    block_id: str,
    relation: Optional[RelationType] = None,
    depth: Optional[int] = None,
    direction: Optional[str] = None,
    limit: int = 100,
    cursor: Optional[str] = None,
    link_manager: LinkManager = Depends(get_link_manager),
) -> List[BlockLink]:
    """
    Retrieves links originating from a specific block.

    Parameters:
    - block_id: ID of the source block
    - relation: Optional filter by relation type
    - depth: Optional maximum traversal depth
    - direction: Optional traversal direction ('outbound', 'inbound', 'both')
    - limit: Maximum number of results to return
    - cursor: Optional pagination cursor
    """
    try:
        # Validate UUID
        try:
            uuid.UUID(block_id)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid UUID format: block_id must be a valid UUID string"
            )

        # Build query with provided filters
        query = LinkQuery()
        if relation:
            query = query.relation(relation)
        if depth:
            query = query.depth(depth)
        if direction:
            query = query.direction(direction)
        query = query.limit(limit)
        if cursor:
            query = query.cursor(cursor)

        # Get links
        result = link_manager.links_from(block_id=block_id, query=query)

        return result.links

    except ValueError as e:
        # Handle validation errors
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    except Exception as e:
        # Log unexpected errors
        logger.exception(f"Unexpected error retrieving links: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.get(
    "/links/to/{block_id}",
    response_model=List[BlockLink],
    summary="Get links to a block",
    description="Retrieves all links pointing to a specific block, with optional filtering.",
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request - Invalid parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_links_to(
    request: Request,
    block_id: str,
    relation: Optional[RelationType] = None,
    depth: Optional[int] = None,
    direction: Optional[str] = None,
    limit: int = 100,
    cursor: Optional[str] = None,
    link_manager: LinkManager = Depends(get_link_manager),
) -> List[BlockLink]:
    """
    Retrieves links pointing to a specific block.

    Parameters:
    - block_id: ID of the target block
    - relation: Optional filter by relation type
    - depth: Optional maximum traversal depth
    - direction: Optional traversal direction ('outbound', 'inbound', 'both')
    - limit: Maximum number of results to return
    - cursor: Optional pagination cursor
    """
    try:
        # Validate UUID
        try:
            uuid.UUID(block_id)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid UUID format: block_id must be a valid UUID string"
            )

        # Build query with provided filters
        query = LinkQuery()
        if relation:
            query = query.relation(relation)
        if depth:
            query = query.depth(depth)
        if direction:
            query = query.direction(direction)
        query = query.limit(limit)
        if cursor:
            query = query.cursor(cursor)

        # Get links
        result = link_manager.links_to(block_id=block_id, query=query)

        return result.links

    except ValueError as e:
        # Handle validation errors
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    except Exception as e:
        # Log unexpected errors
        logger.exception(f"Unexpected error retrieving links: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.delete(
    "/links/block/{block_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete all links for a block",
    description="Removes all links involving a specific block (as source or target).",
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request - Invalid parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def delete_links_for_block(
    request: Request, block_id: str, link_manager: LinkManager = Depends(get_link_manager)
) -> Dict[str, Any]:
    """
    Deletes all links involving a specific block.

    Parameters:
    - block_id: ID of the block
    """
    try:
        # Validate UUID
        try:
            uuid.UUID(block_id)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid UUID format: block_id must be a valid UUID string"
            )

        # Delete all links for the block
        count = link_manager.delete_links_for_block(block_id=block_id)

        return {"success": True, "message": f"Deleted {count} links for block {block_id}"}

    except ValueError as e:
        # Handle validation errors
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    except Exception as e:
        # Log unexpected errors
        logger.exception(f"Unexpected error deleting links: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
