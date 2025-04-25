# Cogni Memory System

A composable memory system integrating Dolt for versioned storage, LlamaIndex for semantic and graph indexing, and Pydantic for schema validation.

## Directory Structure

```
memory_system/
├── schemas/                 # Schema definitions and in-memory registry
│   ├── registry.py          # Core in-memory type registry functions
│   ├── metadata.py          # Metadata model definitions for each block type
│   ├── common.py            # Common types and models used across components
│   └── ...
├── dolt_schema_manager.py   # Persistence layer for schemas in Dolt DB
├── memory_block.py          # Core MemoryBlock class definition
├── schema_registry.py       # DEPRECATED - Use dolt_schema_manager.py instead
├── tests/                   # Test files for each component
│   ├── test_dolt_schema_manager.py  # Tests for schema persistence
│   └── ...
└── ...
```

## Key Components

### Core Memory Types
- `memory_block.py`: Defines the central `MemoryBlock` class with properties like `id`, `text`, and `metadata`.

### Schema System
- `schemas/registry.py`: Provides in-memory registry for metadata models with validation and type access.
- `schemas/metadata.py`: Contains Pydantic models for different block types (ProjectMetadata, TaskMetadata, etc.).
- `schemas/common.py`: Defines reusable types like RelationType, BlockLink, and ConfidenceScore.
- `dolt_schema_manager.py`: Handles persistence of schemas to Dolt, including versioning and retrieval.

### Node Type System
- Node types are determined by registered metadata models.
- Current types: project, task, doc, knowledge.
- `get_available_node_types()` in registry.py returns all available types.

### Testing
- `tests/test_dolt_schema_manager.py`: Comprehensive tests for schema persistence functions.
- Tests validate schema registration, retrieval, validation, and node type enumeration.

## Usage Example

```python
# Register schema for a node type
from experiments.src.memory_system.dolt_schema_manager import register_schema

register_schema(
    db_path="/path/to/dolt/db",
    node_type="project",
    schema_version=1,
    json_schema=project_schema
)

# Get available node types
from experiments.src.memory_system.schemas.registry import get_available_node_types

node_types = get_available_node_types()
# ['project', 'task', 'doc', 'knowledge']

# Validate metadata for a block
from experiments.src.memory_system.schemas.registry import validate_metadata

is_valid = validate_metadata("project", metadata_dict)
``` 