#!/usr/bin/env python3
"""
Register all metadata schemas in the experimental database.
"""

import os
import sys
from pathlib import Path
from infra_core.memorysystem.dolt_schema_manager import register_all_metadata_schemas

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Path to the experimental database
db_path = os.path.join(project_root, "experiments", "dolt_data", "memory_db")

# Register all schemas
print("Registering schemas...")
results = register_all_metadata_schemas(db_path)

# Print results
print("\nRegistration results:")
for node_type, success in results.items():
    status = "Success" if success else "Failed"
    print(f"- {node_type}: {status}")
