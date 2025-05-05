#!/usr/bin/env python
"""
Generate JSON schemas from Pydantic models in the Cogni API.
"""

import json
import sys
import inspect
from pathlib import Path
from typing import Dict, Any, Type

# Add the project root to the Python path to enable imports
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Import after path setup - linter exceptions allowed for these imports
# ruff: noqa: E402
from legacy_logseq import models
from pydantic import BaseModel

# Paths
SCHEMA_DIR = Path("schemas/backend")
SCHEMA_DIR.mkdir(exist_ok=True, parents=True)


def is_pydantic_model(obj: Any) -> bool:
    """Check if an object is a Pydantic model class (not an instance)."""
    return inspect.isclass(obj) and issubclass(obj, BaseModel) and obj != BaseModel


def discover_models() -> Dict[str, Type[BaseModel]]:
    """Discover all Pydantic models in the models module."""
    model_dict = {}

    for name, obj in inspect.getmembers(models, is_pydantic_model):
        # Only include models directly defined in models
        if obj.__module__ == models.__name__:
            model_dict[name] = obj

    print(f"🔍 Discovered {len(model_dict)} Pydantic models in models")
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

    # Auto-discover models
    discovered_models = discover_models()

    if not discovered_models:
        print("❌ No models found! Check that models.py contains Pydantic models.")
        return

    # Track changes
    changes = 0

    # Generate schemas for all discovered models
    for name, model in discovered_models.items():
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
