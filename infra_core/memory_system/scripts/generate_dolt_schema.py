#!/usr/bin/env python3
"""
Generate Dolt schema from Pydantic models.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Type, Union, get_args, get_origin

# Add the project root to the Python path to enable imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

try:
    from infra_core.memory_system.schemas.memory_block import MemoryBlock
    from infra_core.memory_system.schemas.common import BlockLink
    from infra_core.constants import MEMORY_DOLT_ROOT
    from pydantic import BaseModel
except ImportError as e:
    print(f"Error importing required modules: {e}")
    sys.exit(1)

# --- Configure logging --- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# --- Define SQL Type Mappings --- #
SQL_TYPE_MAPPINGS = {
    str: "VARCHAR(255)",
    int: "INT",
    float: "FLOAT",
    bool: "BOOLEAN",
    dict: "JSON",
    list: "JSON",
    Any: "JSON",
    datetime: "DATETIME",
}

# Field-specific type overrides
FIELD_TYPE_OVERRIDES = {
    "text": "LONGTEXT",
    "embedding": "LONGTEXT",
    "id": "VARCHAR(255)",
    "type": "VARCHAR(50)",
    "state": "VARCHAR(50)",
    "visibility": "VARCHAR(50)",
    "relation": "VARCHAR(50)",
}

# --- Constants --- #
DOLT_DATA_DIR = Path(__file__).parent.parent / "dolt_data"


def get_sql_type(field_type: Type, field_name: str) -> str:
    """Map Python type to SQL type.

    Args:
        field_type: The Python type to map
        field_name: The name of the field being mapped

    Returns:
        The corresponding SQL type as a string
    """
    # Check field-specific override first
    if field_name in FIELD_TYPE_OVERRIDES:
        return FIELD_TYPE_OVERRIDES[field_name]

    # Handle Optional types
    if get_origin(field_type) is Union:
        args = get_args(field_type)
        if type(None) in args:
            # Get the non-None type
            non_none_type = next(t for t in args if t is not type(None))
            return get_sql_type(non_none_type, field_name)

    # Handle List types
    if get_origin(field_type) is list:
        return "JSON"

    # Handle basic types
    if field_type in SQL_TYPE_MAPPINGS:
        return SQL_TYPE_MAPPINGS[field_type]

    # Handle Literal types (enums)
    if get_origin(field_type) is Literal:
        values = get_args(field_type)
        if all(isinstance(v, str) for v in values):
            return "VARCHAR(50)"

    # Default to JSON for complex types
    return "JSON"


def format_default_value(value: Any) -> str:
    """Format default value for SQL.

    Args:
        value: The default value to format

    Returns:
        The formatted default value as a string
    """
    if value is None or value == ...:  # ... is Pydantic's Required marker
        return ""
    if isinstance(value, str):
        return f"DEFAULT '{value}'"
    if isinstance(value, (int, float)):
        return f"DEFAULT {value}"
    if isinstance(value, bool):
        return f"DEFAULT {str(value).upper()}"
    return ""


def generate_table_schema(model: Type[BaseModel], table_name: str) -> str:
    """Generate CREATE TABLE statement for a Pydantic model.

    Args:
        model: The Pydantic model to generate schema for
        table_name: The name of the table to create

    Returns:
        The CREATE TABLE statement as a string
    """
    columns = []
    primary_keys = []

    # Special handling for block_links table
    if table_name == "block_links":
        columns.append("    from_id VARCHAR(255) NOT NULL")
        primary_keys.append("from_id")

    for field_name, field in model.model_fields.items():
        field_type = field.annotation
        sql_type = get_sql_type(field_type, field_name)

        # Handle primary key
        if field_name == "id":
            columns.append(f"    {field_name} {sql_type} PRIMARY KEY")
            continue

        # Handle nullable fields
        is_optional = get_origin(field_type) is Union and type(None) in get_args(field_type)

        # Make specific fields nullable based on their names if they're Optional in Pydantic
        if (
            field_name
            in [
                "source_file",
                "source_uri",
                "confidence",
                "embedding",
                "created_by",
                "schema_version",
            ]
            and is_optional
        ):
            null_constraint = "NULL"
        else:
            null_constraint = "NULL" if is_optional else "NOT NULL"

        # Handle default values
        default = format_default_value(field.default)

        # Special handling for specific fields
        if field_name == "state":
            columns.append(f"    {field_name} {sql_type} NULL DEFAULT 'draft'")
        elif field_name == "visibility":
            columns.append(f"    {field_name} {sql_type} NULL DEFAULT 'internal'")
        elif field_name == "block_version":
            columns.append(f"    {field_name} INT NULL DEFAULT 1")
        else:
            columns.append(f"    {field_name} {sql_type} {null_constraint} {default}".rstrip())

        # Track primary key fields for BlockLinks
        if table_name == "block_links" and field_name in ["to_id", "relation"]:
            primary_keys.append(field_name)

    # Add constraints for MemoryBlocks
    if table_name == "memory_blocks":
        columns.append(
            "    CONSTRAINT chk_valid_state CHECK (state IN ('draft', 'published', 'archived'))"
        )
        columns.append(
            "    CONSTRAINT chk_valid_visibility CHECK (visibility IN ('internal', 'public', 'restricted'))"
        )
        columns.append("    CONSTRAINT chk_block_version_positive CHECK (block_version > 0)")

    # Add composite primary key for BlockLinks
    if table_name == "block_links" and primary_keys:
        columns.append(f"    PRIMARY KEY ({', '.join(primary_keys)})")

    # Create the table statement
    columns_str = ",\n".join(columns)
    return f"CREATE TABLE IF NOT EXISTS {table_name} (\n{columns_str}\n);"


def generate_schema_file(output_path: Path) -> None:
    """Generate schema.sql file with table definitions.

    Args:
        output_path: The path where the schema file should be written
    """
    # Ensure the output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    schema_statements = []

    # Generate schema for MemoryBlock
    schema_statements.append(generate_table_schema(MemoryBlock, "memory_blocks"))
    schema_statements.append(
        "\nCREATE INDEX idx_memory_blocks_type_state_visibility "
        "ON memory_blocks (type, state, visibility);"
    )

    # Generate schema for BlockLink
    schema_statements.append("\n" + generate_table_schema(BlockLink, "block_links"))
    schema_statements.append("\nCREATE INDEX idx_block_links_to_id ON block_links (to_id);")

    # Write to file
    with open(output_path, "w") as f:
        f.write("\n".join(schema_statements))

    logger.info(f"Generated schema file: {output_path}")


def main() -> None:
    """Main entry point."""
    # Define output path - place in memory_dolt directory
    output_path = MEMORY_DOLT_ROOT / "schema.sql"

    # Ensure the directory exists
    MEMORY_DOLT_ROOT.mkdir(parents=True, exist_ok=True)

    # Generate schema
    generate_schema_file(output_path)


if __name__ == "__main__":
    main()
