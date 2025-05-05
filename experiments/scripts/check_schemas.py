#!/usr/bin/env python3
"""
Check available schemas in the experimental database.
"""

import os
import sys
from pathlib import Path
from experiments.src.memory_system.dolt_schema_manager import list_available_schemas

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Path to the experimental database
db_path = os.path.join(project_root, "experiments", "dolt_data", "memory_db")

# List available schemas
schemas = list_available_schemas(db_path)

if schemas:
    print("Available schemas:")
    for schema in schemas:
        print(
            f"- {schema['node_type']} (v{schema['schema_version']}) created at {schema['created_at']}"
        )
else:
    print("No schemas found in the database.")
