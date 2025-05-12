from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, List

from infra_core.memory_system.schemas.registry import (
    get_schema_version,
    get_metadata_model,
    SCHEMA_VERSIONS,
)

router = APIRouter()


@router.get(
    "/schemas/{block_type}/{version}",
    summary="Get JSON schema for a block type and version",
    response_class=JSONResponse,
)
def get_schema(block_type: str, version: str):
    """
    Returns the JSON schema for the given block type and version.
    If version is 'latest', resolves to the latest version for the type.
    """
    # Validate block_type
    if block_type not in SCHEMA_VERSIONS:
        raise HTTPException(status_code=404, detail=f"Unknown block type: {block_type}")

    # Resolve version
    if version == "latest":
        resolved_version = get_schema_version(block_type)
    else:
        try:
            resolved_version = int(version)
        except ValueError:
            raise HTTPException(status_code=400, detail="Version must be an integer or 'latest'")
        if resolved_version != get_schema_version(block_type):
            # Only the latest version is supported for now
            raise HTTPException(
                status_code=404,
                detail=f"Version {resolved_version} not found for type {block_type}",
            )

    # Get the model
    model = get_metadata_model(block_type)
    if not model:
        raise HTTPException(
            status_code=404, detail=f"No schema registered for block type: {block_type}"
        )

    # Generate the schema
    schema = model.model_json_schema()
    return JSONResponse(content=schema)


@router.get(
    "/schemas/index.json",
    summary="Get index of all available block schemas",
    response_class=JSONResponse,
)
def get_schema_index():
    """
    Returns a list of all available block schemas with their type, version, and URL.
    """
    index: List[Dict[str, Any]] = []
    for block_type, version in SCHEMA_VERSIONS.items():
        index.append(
            {
                "type": block_type,
                "version": version,
                "url": f"/schemas/{block_type}/{version}",
                "latest_url": f"/schemas/{block_type}/latest",
            }
        )
    return JSONResponse(content={"schemas": index})
