#!/usr/bin/env python
"""
Generate JSON schemas from Pydantic models in the Cogni API.
"""

import json
import sys
import inspect
import importlib  # Added for dynamic imports
from pathlib import Path
from typing import Dict, Any, Type

# Add the project root to the Python path to enable imports
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Import after path setup - linter exceptions allowed for these imports
# ruff: noqa: E402
# Remove legacy_logseq import, we'll specify modules dynamically
# from legacy_logseq import models
from pydantic import BaseModel

# Paths
SCHEMA_DIR = Path("schemas/backend")
SCHEMA_DIR.mkdir(exist_ok=True, parents=True)


def is_pydantic_model(obj: Any) -> bool:
    """Check if an object is a Pydantic model class (not an instance)."""
    return inspect.isclass(obj) and issubclass(obj, BaseModel) and obj != BaseModel


def is_api_response_model(model_name: str) -> bool:
    """Check if a model is an API response model that FastAPI handles automatically."""
    api_response_patterns = [
        "Response",  # BlocksResponse, BranchesResponse, SingleBlockResponse, etc.
        "ChatResponse",  # Chat-specific responses
    ]

    # Exclude models ending with these patterns
    for pattern in api_response_patterns:
        if model_name.endswith(pattern):
            return True

    return False


def discover_models_in_module(module: Any) -> Dict[str, Type[BaseModel]]:
    """Discover all Pydantic models in the given module, excluding API response models."""
    model_dict = {}

    for name, obj in inspect.getmembers(module, is_pydantic_model):
        # Only include models directly defined in the target module
        if obj.__module__ == module.__name__:
            # Skip API response models that FastAPI handles automatically
            if is_api_response_model(name):
                print(f"⏭️  Skipped API response model: {name} (handled by FastAPI OpenAPI)")
                continue

            model_dict[name] = obj

    print(f"🔍 Discovered {len(model_dict)} Pydantic models in {module.__name__}")
    return model_dict


def generate_schema(model: Type[BaseModel], filename: str) -> bool:
    """
    Generate JSON schema from a Pydantic model and save it to a file.
    Returns True if file was written, False if unchanged.
    """
    schema_path = SCHEMA_DIR / filename

    # Get the JSON schema using the new recommended method for Pydantic v2
    schema_dict = model.model_json_schema()
    new_schema = json.dumps(schema_dict, indent=2)

    # Check if file exists and has the same content
    if schema_path.exists():
        with open(schema_path, "r") as f:
            current_schema = f.read()

        if current_schema == new_schema:
            print(f"⏭️  Skipped unchanged schema: {schema_path}")
            return False

    # Write the schema to a file
    with open(schema_path, "w") as f:
        f.write(new_schema)

    print(f"✅ Generated schema: {schema_path}")
    return True


def main():
    """Generate all schemas."""
    print("🔄 Generating JSON schemas from Pydantic models...")

    # List of modules/packages to scan for Pydantic models
    module_strings_to_scan = [
        "infra_core.memory_system.schemas.memory_block",  # For MemoryBlock
        "infra_core.memory_system.schemas.common",  # For BlockLink, ConfidenceScore, etc.
        "services.web_api.models",  # For ErrorResponse, ChatResponse etc. (new location)
        # Models from router files will be added manually below
    ]

    all_discovered_models: Dict[str, Type[BaseModel]] = {}

    for module_str in module_strings_to_scan:
        try:
            module = importlib.import_module(module_str)
            discovered = discover_models_in_module(module)
            all_discovered_models.update(discovered)
        except ImportError as e:
            print(f"⚠️ Could not import module {module_str}: {e}. Skipping.")
        except Exception as e:
            print(f"⚠️ Error processing module {module_str}: {e}. Skipping.")

    # Manually add models from router files
    try:
        # Assuming QueryRequest is in services.web_api.routes.chat
        # Note: CompleteQueryRequest is already in infra_core.models and will be picked up.
        # The /chat endpoint uses CompleteQueryRequest as its body.
        # If there was a simpler QueryRequest, we would add it here.
        # For now, we'll ensure CompleteQueryRequest from infra_core.models is covered.

        # Let's confirm if any specific request model from chat router needs adding.
        # The current chat router uses `CompleteQueryRequest` from `infra_core.models`.
        # If QueryRequest was a distinct model in chat.py, it would be:
        # from services.web_api.routes.chat import QueryRequest
        # if is_pydantic_model(QueryRequest) and "QueryRequest" not in all_discovered_models:
        #     all_discovered_models["QueryRequest"] = QueryRequest
        #     print(f"🔍 Manually added QueryRequest from services.web_api.routes.chat")
        pass  # No specific, unique models from chat router to add manually for now as per current structure.

    except ImportError:
        print("⚠️ Could not import models from services.web_api.routes.chat. Skipping.")
    except NameError:
        print(
            "⚠️ One of the models (e.g. QueryRequest) not found in services.web_api.routes.chat. Skipping manual add."
        )

    if not all_discovered_models:
        print(
            "❌ No models found! Check the specified modules and ensure they contain Pydantic models."
        )
        return

    # Track changes
    changes = 0

    # Generate schemas for all discovered models
    for name, model in all_discovered_models.items():
        schema_filename = f"{name.lower()}.schema.json"
        if generate_schema(model, schema_filename):
            changes += 1

    # Output summary
    if changes > 0:
        print(f"✅ Generated/updated {changes} schemas successfully.")
    else:
        print("✅ All schemas are up to date.")

    print("📝 Note: These schemas should be committed to the repository.")
    print("   Frontend developers can use these schemas to generate TypeScript types.")


if __name__ == "__main__":
    main()
