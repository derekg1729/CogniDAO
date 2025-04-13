# Cogni Memory Architecture Tests

This directory contains tests for the Cogni Memory Architecture components.

## Overview

The tests are structured to cover:

1. Unit tests for individual components:
   - Parser (test_parser.py)
   - Embedder (test_embedder.py)
   - Storage (test_storage.py)
   - Memory Client (test_memory_client.py)
   - Memory Indexer (test_memory_indexer.py)
   - Memory MCP Server (test_memory_mcp_server.py)

2. Integration tests:
   - BroadcastCogni integration (test_integration.py)
   - End-to-end tests (test_end_to_end.py)

## Running Tests

To run the tests:

```bash
# Install test dependencies
pip install -r infra_core/memory/tests/requirements-test.txt

# Run all tests from project root
python test.py

# Run only memory tests from project root
python test.py infra_core/memory/tests

# Run all tests directly with pytest
pytest

# Run with coverage report
pytest --cov=infra_core.memory

# Run a specific test file
python test.py infra_core/memory/tests/test_parser.py

# Run a specific test
python test.py infra_core/memory/tests/test_parser.py::TestLogseqParser::test_extract_blocks_with_tags
```

## Test Fixtures

Common test fixtures are defined in `conftest.py` and include:

- `sample_logseq_dir`: Creates test Logseq markdown files with various tags
- `sample_memory_blocks`: Provides sample memory blocks for testing storage and querying
- `test_storage_dirs`: Sets up temporary directories for ChromaDB and Archive storage

## Adding New Tests

When adding new tests:

1. Create appropriate fixtures in conftest.py if they'll be reused
2. Follow test naming conventions (test_*.py for files, test_* for functions)
3. Use appropriate assertions and mocks
4. Document complex test scenarios with comments 