from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, List

from infra_core.memory_system.schemas.registry import (
    # get_schema_version, # No longer needed directly here
    # get_metadata_model, # No longer needed directly here
    resolve_schema_model_and_version,  # Use the new resolver function
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
    Uses application/schema+json media type.
    """
    try:
        model, resolved_version = resolve_schema_model_and_version(block_type, version)
    except KeyError as e:
        # Unknown block type
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        # Invalid version string or version not found
        raise HTTPException(status_code=400, detail=str(e))
    except TypeError:
        # Internal error: No model registered for a known type
        # Log this ideally
        raise HTTPException(status_code=500, detail="Internal server error: Schema not registered")

    # Generate the schema with by_alias=True to ensure all field aliases are preserved
    schema = model.model_json_schema(by_alias=True)

    # DEBUG
    print(f"Original schema keys: {list(schema.keys())}")

    # Add required metadata for frontend compatibility
    schema["$id"] = f"/schemas/{block_type}/{resolved_version}"
    schema["x_block_type"] = block_type
    schema["x_schema_version"] = resolved_version

    # Ensure title is properly set if not already present
    if "title" not in schema or not schema["title"]:
        # Default to the model class name if no title is set
        schema["title"] = model.__name__

    # DEBUG
    print(f"Schema with custom fields: {list(schema.keys())}")
    print(f"Schema $id: {schema.get('$id')}")
    print(f"Schema x_block_type: {schema.get('x_block_type')}")
    print(f"Schema x_schema_version: {schema.get('x_schema_version')}")

    result = JSONResponse(
        content=schema,
        headers={"Cache-Control": "max-age=86400, public"},
        media_type="application/schema+json",  # Add specific media type
    )

    # DEBUG
    print(f"Content type: {result.media_type}")
    print(f"Headers: {result.headers}")

    return result


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
        # Filter out the 'base' type from the public index
        if block_type == "base":
            continue

        index.append(
            {
                "type": block_type,
                "version": version,
                "latest_version": version,  # Add the latest version number
                "url": f"/schemas/{block_type}/{version}",
                "latest_url": f"/schemas/{block_type}/latest",
            }
        )
    return JSONResponse(
        content={"schemas": index}, headers={"Cache-Control": "max-age=86400, public"}
    )
