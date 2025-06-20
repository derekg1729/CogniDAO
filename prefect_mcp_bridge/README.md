# Prefect MCP Bridge Package

**Expose MCP HTTP endpoints as reusable Prefect @task wrappers so any flow can trigger Dolt (and future) operations without shell scripts.**

[![Python Version](https://img.shields.io/pypi/pyversions/prefect-mcp-bridge)](https://pypi.org/project/prefect-mcp-bridge/)
[![Package Version](https://img.shields.io/pypi/v/prefect-mcp-bridge)](https://pypi.org/project/prefect-mcp-bridge/)
[![License](https://img.shields.io/pypi/l/prefect-mcp-bridge)](https://github.com/cogni/prefect-mcp-bridge/blob/main/LICENSE)

## Overview

The `prefect-mcp-bridge` package provides a clean, type-safe way to integrate MCP (Model Context Protocol) HTTP endpoints into Prefect workflows. Instead of using shell scripts or subprocess calls, you can now use native Prefect tasks that communicate directly with your MCP server.

### Key Features

- **🔌 Lightweight MCPClient** with base_url + auth header handling
- **🚀 Ready-to-use Dolt tasks**: `dolt_add_task`, `dolt_commit_task`, `dolt_push_task`
- **🔄 Convenience workflows**: Combined `dolt_add_commit_push_task`
- **🧪 Full test coverage** with mocked MCP endpoints using respx
- **📦 Production ready** with proper error handling and logging
- **🔧 Extensible** - easily add new MCP endpoints

## Quick Start

### Installation

```bash
pip install prefect-mcp-bridge
```

For development:
```bash
pip install prefect-mcp-bridge[dev]
```

### Basic Usage

```python
from prefect import flow
from prefect_mcp_bridge import dolt_add_task, dolt_commit_task, dolt_push_task

@flow
def my_data_pipeline():
    # ... your data processing work ...
    
    # Stage changes in Dolt
    dolt_add_task()
    
    # Commit with a descriptive message
    dolt_commit_task(
        message="Auto-commit by Prefect data pipeline",
        author="prefect-pipeline"
    )
    
    # Push to remote
    dolt_push_task(branch="main")
```

### Environment Variables

Configure your MCP connection using environment variables:

```bash
export MCP_URL="http://cogni-mcp:8080"           # Default MCP server URL
export PREFECT_MCP_API_KEY="your-api-key-here"  # Optional authentication
```

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_URL` | `http://cogni-mcp:8080` | Base URL for your MCP server |
| `PREFECT_MCP_API_KEY` | None | Optional API key for authentication |

## API Reference

### Tasks

#### `dolt_add_task(tables=None, mcp_client=None)`
Stage changes in Dolt repository.

**Parameters:**
- `tables` (list, optional): Specific tables to add. Defaults to all changes.
- `mcp_client` (MCPClient, optional): Custom client instance.

**Returns:** Dict with operation results.

#### `dolt_commit_task(message, branch=None, author=None, tables=None, mcp_client=None)`
Commit staged changes to Dolt repository.

**Parameters:**
- `message` (str, required): Commit message
- `branch` (str, optional): Target branch
- `author` (str, optional): Commit author
- `tables` (list, optional): Specific tables to commit
- `mcp_client` (MCPClient, optional): Custom client instance

**Returns:** Dict with commit hash and operation results.

#### `dolt_push_task(branch=None, remote_name="origin", force=False, mcp_client=None)`
Push commits to remote repository.

**Parameters:**
- `branch` (str, optional): Branch to push
- `remote_name` (str): Remote name (default: "origin")
- `force` (bool): Force push flag
- `mcp_client` (MCPClient, optional): Custom client instance

**Returns:** Dict with push operation results.

#### `dolt_add_commit_push_task(...)`
Convenience task that performs add → commit → push in sequence.

Combines all parameters from the individual tasks above.

### MCPClient

Direct HTTP client for MCP server communication:

```python
from prefect_mcp_bridge.client import MCPClient

# Basic usage
client = MCPClient()
result = client.call("dolt.status", {})

# With authentication
client = MCPClient(
    base_url="http://your-mcp:8080",
    api_key="your-key"
)

# Context manager (recommended)
with MCPClient() as client:
    result = client.call("dolt.commit", {
        "commit_message": "My commit",
        "author": "user"
    })
```

## Examples

### Complete Data Pipeline

```python
from prefect import flow, task
from prefect_mcp_bridge import dolt_add_task, dolt_commit_task, dolt_push_task
from prefect_mcp_bridge.utils import setup_mcp_environment

@task
def process_data():
    """Your data processing logic here"""
    # ... transform data, update database, etc ...
    return {"records_processed": 1000}

@flow
def data_pipeline_with_versioning():
    """Complete pipeline with automatic Dolt versioning"""
    
    # Validate MCP environment
    setup_mcp_environment()
    
    # Process your data
    result = process_data()
    
    # Version the changes
    dolt_add_task()
    dolt_commit_task(
        message=f"Pipeline run: {result['records_processed']} records processed",
        author="data-pipeline-bot"
    )
    dolt_push_task()
    
    return result
```

### Using the Combined Task

```python
from prefect import flow
from prefect_mcp_bridge.dolt import dolt_add_commit_push_task

@flow
def simple_versioning_flow():
    """Single task for complete Dolt workflow"""
    
    # ... your work that modifies tracked data ...
    
    # One task does it all
    result = dolt_add_commit_push_task(
        message="Automated commit from Prefect",
        author="prefect-automation",
        branch="main"
    )
    
    if not result["success"]:
        raise Exception(f"Dolt operations failed: {result['error']}")
    
    return result
```

### Error Handling

```python
from prefect import flow
from prefect_mcp_bridge import dolt_commit_task
from requests import HTTPError

@flow
def robust_flow():
    try:
        result = dolt_commit_task(message="Test commit")
        return result
    except HTTPError as e:
        if "nothing to commit" in str(e).lower():
            print("No changes to commit - this is OK")
            return {"skipped": True}
        raise  # Re-raise other HTTP errors
    except Exception as e:
        print(f"Unexpected error: {e}")
        # Could implement retry logic, alerts, etc.
        raise
```

## Development

### Running Tests

```bash
# Install with dev dependencies
pip install -e .[dev]

# Run tests with coverage
pytest

# Run specific test file
pytest tests/test_client.py

# Run tests against live MCP server (if available)
MCP_URL="http://localhost:8080" pytest
```

### Adding New MCP Endpoints

Extend the package to support additional MCP endpoints:

```python
from prefect import task
from .client import MCPClient

@task(name="my_custom_operation")
def my_custom_task(param1: str, mcp_client: MCPClient = None):
    """Custom task for new MCP endpoint"""
    client = mcp_client or MCPClient()
    
    payload = {"param1": param1}
    
    try:
        with client:
            result = client.call("my.custom.endpoint", payload)
            return result
    except Exception as e:
        raise Exception(f"Custom operation failed: {e}") from e
```

### Test Infrastructure

The package includes comprehensive test fixtures using `respx` for mocking HTTP calls:

```python
def test_my_task(mock_mcp_server, test_env_vars):
    """Test with mocked MCP server"""
    result = my_custom_task(param1="test")
    assert result["success"] is True
```

## Integration Examples

### With Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  cogni-mcp:
    image: cogni/mcp-server:latest
    ports:
      - "8080:8080"
    environment:
      - DOLT_ROOT_PATH=/data
    volumes:
      - ./data:/data

  prefect-worker:
    image: prefect/prefect:latest
    environment:
      - MCP_URL=http://cogni-mcp:8080
      - PREFECT_MCP_API_KEY=${API_KEY}
    depends_on:
      - cogni-mcp
```

### CI/CD Pipeline

```yaml
# .github/workflows/pipeline.yml
name: Data Pipeline
on:
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM

jobs:
  pipeline:
    runs-on: ubuntu-latest
    env:
      MCP_URL: ${{ secrets.MCP_URL }}
      PREFECT_MCP_API_KEY: ${{ secrets.MCP_API_KEY }}
    
    steps:
    - uses: actions/checkout@v3
    - name: Run Pipeline
      run: |
        pip install prefect-mcp-bridge
        python -c "
        from my_flows import daily_data_pipeline
        daily_data_pipeline()
        "
```

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
git clone https://github.com/cogni/prefect-mcp-bridge
cd prefect-mcp-bridge
pip install -e .[dev]
pre-commit install
```

### Running the Example

```bash
# Ensure MCP server is running
export MCP_URL="http://localhost:8080"

# Run the sample flow
python examples/sample_flow.py
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- 📚 [Documentation](https://github.com/cogni/prefect-mcp-bridge#readme)
- 🐛 [Issue Tracker](https://github.com/cogni/prefect-mcp-bridge/issues)
- 💬 [Discussions](https://github.com/cogni/prefect-mcp-bridge/discussions)

---

**Built with ❤️ by the Cogni Team** 