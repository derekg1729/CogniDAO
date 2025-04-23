# CogniMemorySystem-POC

This directory contains the proof-of-concept implementation for a composable memory and agent system integrating:
- Dolt for versioned storage
- LlamaIndex for semantic and graph indexing
- LangChain for orchestration
- Pydantic for schema validation

## Project Structure

- `src/memory_system/`: Core implementation of the memory system
  - `llama_memory.py`: LlamaMemory class for interacting with LlamaIndex
  - `llamaindex_adapters.py`: Functions for converting between memory blocks and LlamaIndex nodes
  - `schemas/`: Pydantic models for the memory system
- `dolt_data/`: Dolt database files
  - `schema.sql`: **Auto-generated** SQL schema for the Dolt database
- `scripts/`: Utility scripts
  - `generate_dolt_schema.py`: Script to generate the Dolt schema
- `docs/roadmap/`: Project roadmap and task definitions

## Database Schema

The `schema.sql` file in `dolt_data/` defines the database schema for the project. This file is **generated** by the `scripts/generate_dolt_schema.py` script and should not be manually edited.

To update the schema:

1. Make changes to the Pydantic models in `src/memory_system/schemas/memory_block.py`
2. Run the schema generation script:
   ```
   cd experiments
   python scripts/generate_dolt_schema.py
   ```

This ensures that the Dolt database schema stays in sync with the Pydantic models.

## Current Status

The project is under active development. See the project roadmap in `docs/roadmap/project-CogniMemorySystem-POC.json` for details on the implementation plan and progress.

Completed tasks:
- Task 2.0: Established Schema Registry & Versioning
- Task 2.2: Created Basic Retrieval Function
- Task 2.7: Generate Basic Schema SQL

Next tasks:
- Task 2.3: Extend node conversion for type links 