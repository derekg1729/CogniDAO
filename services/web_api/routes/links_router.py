from fastapi import APIRouter, Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import logging
import uuid
import re

from infra_core.memory_system.link_manager import (
    LinkManager,
    LinkError,
    LinkQuery,
    Direction,
)
from infra_core.memory_system.schemas.common import RelationType, BlockLink
from services.web_api.models import ErrorResponse
from pydantic import BaseModel, Field, validator

# Setup logger
logger = logging.getLogger(__name__)

router = APIRouter(tags=["v1/Links"])

# Constants
MAX_LIMIT = 1000
DEFAULT_LIMIT = 100
MAX_CURSOR_LEN = 512


class PaginatedLinksResponse(BaseModel):
    """Response model for paginated links."""

    links: List[BlockLink]
    next_cursor: Optional[str] = None
    page_size: int = Field(..., description="Number of items in this page")
    total_available: Optional[int] = Field(None, description="Total count (if cheaply computable)")

    @validator("links", pre=True)
    def validate_links(cls, v):
        """Ensure all links are properly serializable BlockLink instances."""
        if not isinstance(v, list):
            return v
        # Always round-trip through model_validate to guarantee JSON serializability
        result = []
        for link in v:
            if isinstance(link, BlockLink):
                # Even if it's already a BlockLink, re-validate to ensure serializability
                result.append(BlockLink.model_validate(link))
            elif isinstance(link, dict):
                result.append(BlockLink(**link))
            else:
                # Try to convert dataclass/object to dict then to BlockLink
                result.append(BlockLink.model_validate(link))
        return result


def validate_cursor(cursor: str) -> bool:
    """Validate cursor format - should be alphanumeric, base64url-like, max MAX_CURSOR_LEN chars."""
    if len(cursor) > MAX_CURSOR_LEN:
        return False
    # Allow alphanumeric + base64url safe chars
    return bool(re.match(r"^[A-Za-z0-9_-]+$", cursor))


def validate_limit(limit: int) -> int:
    """Validate and cap the limit parameter."""
    if limit <= 0:
        raise HTTPException(status_code=400, detail="Limit must be a positive integer")
    if limit > MAX_LIMIT:
        raise HTTPException(
            status_code=400, detail=f"Limit cannot exceed {MAX_LIMIT}. Requested: {limit}"
        )
    return limit


async def _paginate_links(
    request: Request,
    query_fn,
    link_manager: LinkManager,
    block_id: Optional[str] = None,
    relation: Optional[RelationType] = None,
    depth: Optional[int] = None,
    direction: Optional[str] = None,
    limit: int = DEFAULT_LIMIT,
    cursor: Optional[str] = None,
) -> JSONResponse:
    """
    Shared pagination logic for link endpoints.

    Args:
        query_fn: Either link_manager.get_all_links, .links_from, or .links_to
        block_id: Required for .links_from and .links_to
        other params: Standard pagination parameters
    """
    # Validate inputs
    if block_id:
        try:
            uuid.UUID(block_id)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid UUID format: block_id must be a valid UUID string"
            )

    limit = validate_limit(limit)
    if cursor and not validate_cursor(cursor):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cursor format. Must be alphanumeric, max {MAX_CURSOR_LEN} characters",
        )

    # Validate direction if provided - fix scoping issue
    direction_enum = None
    if direction:
        try:
            direction_enum = Direction.from_string(direction)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Build query with provided filters
    query = LinkQuery()
    if relation:
        query = query.relation(relation)
    if depth:
        query = query.depth(depth)
    if direction_enum:  # Only call if direction was provided and validated
        query = query.direction(direction_enum)
    query = query.limit(limit)
    if cursor:
        query = query.cursor(cursor)

    # Execute query based on function type
    if block_id:
        result = query_fn(block_id=block_id, query=query)
    else:
        result = query_fn(query=query)

    # Build response
    response_data = PaginatedLinksResponse(
        links=result.links, next_cursor=result.next_cursor, page_size=len(result.links)
    )

    # Determine status code and headers
    headers = {}
    if result.next_cursor:
        # Build next page URL with all relevant parameters
        url_params = {"cursor": result.next_cursor, "limit": limit}
        if relation:
            url_params["relation"] = relation
        if depth:
            url_params["depth"] = depth
        if direction:
            url_params["direction"] = direction

        next_url = str(request.url.include_query_params(**url_params))
        headers["Link"] = f'<{next_url}>; rel="next"'
        status_code = status.HTTP_206_PARTIAL_CONTENT
    else:
        status_code = status.HTTP_200_OK

    return JSONResponse(
        content=response_data.model_dump(mode="json"), status_code=status_code, headers=headers
    )


def get_link_manager(request: Request):
    """Dependency to get the LinkManager from the app state."""
    try:
        memory_bank = request.app.state.memory_bank
        if not memory_bank:
            logger.error("Memory bank not available in app state")
            raise HTTPException(status_code=500, detail="Memory bank service unavailable")

        # Get the LinkManager from the memory_bank
        link_manager = getattr(memory_bank, "link_manager", None)
        if not link_manager:
            logger.error("LinkManager not available on memory bank")
            raise HTTPException(status_code=500, detail="LinkManager service unavailable")

        return link_manager
    except AttributeError:
        logger.error("Memory bank not configured on app state")
        raise HTTPException(status_code=500, detail="Memory bank not configured")


@router.get(
    "/links",
    response_model=PaginatedLinksResponse,
    summary="Get all links",
    description=f"Retrieves all links in the system, with optional filtering by relation type. Max limit: {MAX_LIMIT}, default: {DEFAULT_LIMIT}",
    responses={
        200: {"model": PaginatedLinksResponse, "description": "Complete page of results"},
        206: {
            "model": PaginatedLinksResponse,
            "description": "Partial results, more available via Link header",
        },
        400: {"model": ErrorResponse, "description": "Bad Request - Invalid parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_all_links(
    request: Request,
    relation: Optional[RelationType] = None,
    limit: int = DEFAULT_LIMIT,
    cursor: Optional[str] = None,
    link_manager: LinkManager = Depends(get_link_manager),
):
    """
    Retrieves all links in the system with proper pagination.

    Parameters:
    - relation: Optional filter by relation type
    - limit: Maximum number of results to return (default: 100, max: 1000)
    - cursor: Optional pagination cursor (opaque token)

    Returns:
    - HTTP 200: Complete page (no more results)
    - HTTP 206: Partial page (more results available)
    - Includes RFC-5988 Link header for next page when applicable
    """
    try:
        return await _paginate_links(
            request=request,
            query_fn=link_manager.get_all_links,
            link_manager=link_manager,
            relation=relation,
            limit=limit,
            cursor=cursor,
        )
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log unexpected errors
        logger.exception(f"Unexpected error retrieving all links: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


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
        error_detail = {"code": e.error_type.value, "message": str(e)}
        raise HTTPException(status_code=e.http_status, detail=error_detail)
    except HTTPException:
        # Re-raise HTTPExceptions as-is (for validation errors)
        raise
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

    except HTTPException:
        # Re-raise HTTPExceptions as-is (for validation errors)
        raise
    except ValueError as e:
        # Handle validation errors
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    except Exception as e:
        # Log unexpected errors
        logger.exception(f"Unexpected error deleting link: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.get(
    "/links/from/{block_id}",
    response_model=PaginatedLinksResponse,
    summary="Get links from a block",
    description=f"Retrieves all links originating from a specific block, with optional filtering. Max limit: {MAX_LIMIT}",
    responses={
        200: {"model": PaginatedLinksResponse, "description": "Complete page of results"},
        206: {"model": PaginatedLinksResponse, "description": "Partial results, more available"},
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
    limit: int = DEFAULT_LIMIT,
    cursor: Optional[str] = None,
    link_manager: LinkManager = Depends(get_link_manager),
):
    """
    Retrieves links originating from a specific block with proper pagination.

    Parameters:
    - block_id: ID of the source block
    - relation: Optional filter by relation type
    - depth: Optional maximum traversal depth
    - direction: Optional traversal direction ('outbound', 'inbound', 'both')
    - limit: Maximum number of results to return (default: 100, max: 1000)
    - cursor: Optional pagination cursor (opaque token)

    Returns:
    - HTTP 200: Complete page (no more results)
    - HTTP 206: Partial page (more results available)
    """
    try:
        return await _paginate_links(
            request=request,
            query_fn=link_manager.links_from,
            link_manager=link_manager,
            block_id=block_id,
            relation=relation,
            depth=depth,
            direction=direction,
            limit=limit,
            cursor=cursor,
        )
    except HTTPException:
        # Re-raise HTTPExceptions as-is (for validation errors)
        raise
    except Exception as e:
        # Log unexpected errors
        logger.exception(f"Unexpected error retrieving links: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.get(
    "/links/to/{block_id}",
    response_model=PaginatedLinksResponse,
    summary="Get links to a block",
    description=f"Retrieves all links pointing to a specific block, with optional filtering. Max limit: {MAX_LIMIT}",
    responses={
        200: {"model": PaginatedLinksResponse, "description": "Complete page of results"},
        206: {"model": PaginatedLinksResponse, "description": "Partial results, more available"},
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
    limit: int = DEFAULT_LIMIT,
    cursor: Optional[str] = None,
    link_manager: LinkManager = Depends(get_link_manager),
):
    """
    Retrieves links pointing to a specific block with proper pagination.

    Parameters:
    - block_id: ID of the target block
    - relation: Optional filter by relation type
    - depth: Optional maximum traversal depth
    - direction: Optional traversal direction ('outbound', 'inbound', 'both')
    - limit: Maximum number of results to return (default: 100, max: 1000)
    - cursor: Optional pagination cursor (opaque token)

    Returns:
    - HTTP 200: Complete page (no more results)
    - HTTP 206: Partial page (more results available)
    """
    try:
        return await _paginate_links(
            request=request,
            query_fn=link_manager.links_to,
            link_manager=link_manager,
            block_id=block_id,
            relation=relation,
            depth=depth,
            direction=direction,
            limit=limit,
            cursor=cursor,
        )
    except HTTPException:
        # Re-raise HTTPExceptions as-is (for validation errors)
        raise
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

    except HTTPException:
        # Re-raise HTTPExceptions as-is (for validation errors)
        raise
    except ValueError as e:
        # Handle validation errors
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    except Exception as e:
        # Log unexpected errors
        logger.exception(f"Unexpected error deleting links: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
