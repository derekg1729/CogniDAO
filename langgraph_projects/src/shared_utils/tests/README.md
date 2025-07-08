# MCP Client Test Suite

This directory contains comprehensive tests for the updated MCP client functionality that removed fallback_tools support.

## Test Files

### test_mcp_client.py
Core tests for MCPClientManager functionality:
- **No Fallback Tools**: Tests that fallback_tools parameter is removed and fallback logic returns empty lists
- **Connection Management**: Tests successful connections, failures, timeouts, and retries
- **Health Checks**: Tests background health monitoring and reconnection logic
- **Caching**: Tests tool caching and refresh functionality
- **Global Functions**: Tests module-level functions like get_mcp_tools, get_mcp_connection_info
- **State Management**: Tests connection state transitions and properties

### test_mcp_failures.py
Edge cases and failure scenarios:
- **Network Errors**: Connection refused, timeouts, SSL errors
- **Protocol Errors**: JSON decode errors, malformed responses
- **System Errors**: Memory errors, runtime errors
- **Retry Logic**: Intermittent failures, max retries exhausted
- **Concurrency**: Concurrent initialization calls
- **Edge Cases**: Zero retries, very short timeouts, large tool lists

### test_mcp_health_check.py
Health monitoring and reconnection tests:
- **Health Check Loop**: Background task functionality
- **Reconnection Logic**: Automatic reconnection attempts
- **Timing**: Respect for health check intervals
- **Exception Handling**: Graceful error handling in health checks
- **Monitoring Functions**: Tests for mcp_monitor utility functions
- **Cleanup**: Proper shutdown and resource cleanup

### test_mcp_monitor.py
MCP monitoring utilities:
- **Health Reporting**: Individual and aggregate health checks
- **Status Display**: Pretty-printed status output without fallback tools references
- **Force Reconnection**: Manual reconnection triggering
- **Error Handling**: Graceful handling of monitoring errors
- **No Fallback References**: Ensures fallback tools are not displayed

## Key Changes from Previous Implementation

### Removed Functionality
1. **fallback_tools parameter**: No longer accepted in MCPClientManager constructor
2. **is_using_fallback property**: Removed from MCPClientManager
3. **Fallback tool logic**: Connection failures now return empty lists instead of fallback tools
4. **Fallback tool display**: Monitoring output no longer shows fallback tool information

### Updated Behavior
1. **Connection Failures**: Return empty list `[]` instead of fallback tools
2. **Health Checks**: Monitor `ConnectionState.FAILED` instead of `_using_fallback`
3. **Connection Info**: No longer includes `using_fallback` or `fallback_tools_count`
4. **Retry Logic**: Continues to work but returns empty list after max retries

## Test Coverage

The test suite covers:
- ✅ 42 core MCP client tests passing
- ✅ Connection success and failure scenarios
- ✅ Retry logic with exponential backoff
- ✅ Health monitoring and reconnection
- ✅ Edge cases and error handling
- ✅ Monitoring utilities
- ✅ State management and cleanup

## Running Tests

```bash
# Run all MCP tests
python -m pytest src/shared_utils/tests/ -v

# Run specific test files
python -m pytest src/shared_utils/tests/test_mcp_client.py -v
python -m pytest src/shared_utils/tests/test_mcp_monitor.py -v
python -m pytest src/shared_utils/tests/test_mcp_failures.py -v
python -m pytest src/shared_utils/tests/test_mcp_health_check.py -v

# Run with coverage
python -m pytest src/shared_utils/tests/ --cov=src.shared_utils --cov-report=html
```

## Test Philosophy

These tests follow the principle that **MCP should be the primary and only tool source**. When MCP servers are unavailable, the system gracefully returns empty tool lists rather than falling back to external APIs that may not be configured or available.

This approach:
- Eliminates external API dependencies in fallback scenarios
- Provides cleaner error handling
- Reduces configuration complexity
- Maintains consistency with the "MCP-first" architecture