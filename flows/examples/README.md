# Prefect MCP Examples

This directory contains focused examples demonstrating different aspects of MCP (Model Context Protocol) integration with Prefect.

## Architecture Overview

The examples have been split into three focused files to address specific concerns (addressing ARCH-01):

### 1. `echo_tool.py` - Minimal MCP Tool Calling
**Purpose**: Demonstrates the simplest possible MCP integration
- ✅ Connect to MCP server via stdio
- ✅ List available tools
- ✅ Call one tool
- ✅ Exit cleanly

**Key Features**:
- Uses official `mcp` Python SDK only (addressing SIM-01)
- Environment-configurable server parameters (addressing ENV-01)
- Returns only serializable data (addressing SER-01)
- Conditional emoji logging (addressing OBS-01)

**Usage**:
```bash
# Direct execution
python flows/examples/echo_tool.py

# As Prefect flow
python -c "import asyncio; from flows.examples.echo_tool import echo_tool_flow; asyncio.run(echo_tool_flow())"
```

### 2. `autogen_work_reader.py` - Multi-Agent MCP Demo
**Purpose**: Shows collaborative agent workflow with MCP tool integration
- ✅ Setup MCP connection (dependency injected)
- ✅ Create specialized analysis agents
- ✅ Run collaborative workflows
- ✅ Return structured results

**Key Features**:
- Dependency injection for MCP client (not global imports)
- Specialized agents for different analysis tasks
- Focused on agent orchestration only
- Uses shared tasks for MCP connection

**Usage**:
```bash
# Direct execution
python flows/examples/autogen_work_reader.py

# As Prefect flow
python -c "import asyncio; from flows.examples.autogen_work_reader import autogen_work_reader_flow; asyncio.run(autogen_work_reader_flow())"
```

### 3. `dolt_ops.py` - Version Control Operations
**Purpose**: Demonstrates Dolt workflow automation via MCP tools
- ✅ Check repository status
- ✅ Stage changes
- ✅ Commit with messages
- ✅ Push to remote
- ✅ Automated workflows

**Key Features**:
- Individual operations and combined workflows
- Configurable parameters (tables, remotes, branches)
- Uses official MCP SDK for all Dolt operations
- Parameterized flow for different operations

**Usage**:
```bash
# Direct execution (status check)
python flows/examples/dolt_ops.py

# Specific operations via flow
python -c "
import asyncio
from flows.examples.dolt_ops import dolt_ops_flow

# Check status
result = asyncio.run(dolt_ops_flow(operation='status'))
print(result)

# Full workflow
result = asyncio.run(dolt_ops_flow(
    operation='auto', 
    commit_message='Example commit',
    author='demo_user'
))
print(result)
"
```

## Environment Configuration

All examples support environment-based configuration (addressing ENV-01):

```bash
export MCP_SERVER_COMMAND="python"
export MCP_SERVER_ARGS="-m,services.mcp_server.app.mcp_server"
```

## Key Improvements

This split addresses the architectural feedback:

- **ARCH-01**: ✅ Separated orthogonal concerns into focused files
- **SER-01**: ✅ Tasks return only serializable primitive data
- **SIM-01**: ✅ Uses only official MCP SDK (no custom wrapper)
- **ENV-01**: ✅ Environment-configurable server parameters
- **OBS-01**: ✅ Conditional emoji logging with debug levels
- **STYLE-01**: ⚠️ Still uses sys.path patching (will be addressed with proper packaging)

## Next Steps

1. **Unit Testing**: Add tests with `MockServerSession` from MCP SDK
2. **Remove Custom Bridge**: Delete the `prefect_mcp_bridge` package
3. **Proper Packaging**: Set up editable installs for shared libraries
4. **Documentation**: Add environment variable documentation to main README

## Development Notes

- Each file can be run independently for testing
- All files use the same MCP server connection pattern
- Results are designed to be serializable for Prefect persistence
- Logging is structured and production-friendly 