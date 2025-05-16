from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
# from datetime_custom import AwareDateTime # Placeholder if specific datetime handling is needed

# Assuming these enums might be needed from your existing codebase
# from infra_core.memory_system.schemas.metadata.common.enums import ProjectStatus, Priority

# For MVP, we'll use simple string types for status/priority and handle conversion/validation later if needed

from infra_core.memory_system.schemas.memory_block import MemoryBlock
from infra_core.memory_system.schemas.metadata.project import ProjectMetadata
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
import uuid

router = APIRouter()

# --- Pydantic Models for API --- #


class CreateProjectPayload(BaseModel):
    title: str = Field(..., description="The title (name) of the project.")
    description: Optional[str] = Field(None, description="A description of the project.")
    owner: Optional[str] = Field(None, description="The owner of the project.")
    status: Optional[str] = Field(
        None,
        description="The current status of the project (e.g., todo, in-progress). Default: todo",
    )
    priority: Optional[str] = Field(
        None, description="The priority of the project (e.g., low, medium, high). Default: medium"
    )
    acceptance_criteria: Optional[List[str]] = Field(
        default_factory=list, description="List of acceptance criteria."
    )
    tags: Optional[List[str]] = Field(
        default_factory=list, description="Tags associated with the project memory block."
    )


class ProjectResponse(BaseModel):
    block_id: str
    message: str
    project_metadata: ProjectMetadata


# --- Helper to get Memory Bank --- #


def get_memory_bank(request: Request) -> StructuredMemoryBank:
    if not hasattr(request.app.state, "memory_bank") or request.app.state.memory_bank is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory bank is not initialized.",
        )
    return request.app.state.memory_bank


# --- API Endpoints --- #


@router.post(
    "/tools/CreateProjectMemoryBlock",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Memory Tools - Project"],
)
async def create_project_memory_block(
    payload: CreateProjectPayload, memory_bank: StructuredMemoryBank = Depends(get_memory_bank)
):
    """
    Creates a new project memory block.
    """
    block_id = f"project_{uuid.uuid4()}"

    # Map payload to ProjectMetadata
    # For status and priority, you might want to map to your actual enum values here
    # For now, passing strings if defined, or they'll use Pydantic defaults if any in ProjectMetadata
    project_meta = ProjectMetadata(
        title=payload.title,
        description=payload.description,
        owner=payload.owner,
        # Assuming ProjectMetadata's defaults or None are acceptable if payload fields are None
        status=payload.status if payload.status else "todo",  # Example: default to 'todo'
        priority=payload.priority if payload.priority else "medium",  # Example: default to 'medium'
        acceptance_criteria=payload.acceptance_criteria,
        # Ensure all required fields for ProjectMetadata are covered
    )

    memory_block_data = MemoryBlock(
        id=block_id,
        type="project",
        metadata=project_meta,
        tags=payload.tags if payload.tags else [],
    )

    try:
        success = memory_bank.create_memory_block(memory_block_data)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create memory block in the memory bank.",
            )
        return ProjectResponse(
            block_id=block_id,
            message="Project memory block created successfully.",
            project_metadata=project_meta,
        )
    except Exception as e:
        # Log the exception e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )
