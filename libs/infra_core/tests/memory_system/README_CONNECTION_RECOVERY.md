# Connection Recovery Testing

This directory contains comprehensive tests for the MySQL connection recovery functionality in `DoltMySQLBase`.

## Overview

The connection recovery system automatically detects when database connections are lost and attempts to restore them, preserving branch context for persistent connections.

## Test Files

### `test_connection_recovery.py`
**20 comprehensive unit tests** covering:

- **Error Detection**: Tests that connection errors are properly identified
- **Reconnection Logic**: Tests successful and failed reconnection attempts  
- **Retry Mechanism**: Tests the retry logic with various scenarios
- **Branch Preservation**: Tests that branch context is maintained across reconnections
- **Edge Cases**: Tests error conditions and unusual scenarios

**Key Test Classes:**
- `TestConnectionRecovery`: Main functionality tests
- `TestConnectionRecoveryEdgeCases`: Edge cases and error conditions

### `manual_connection_recovery_test.py`
**Interactive manual testing script** that:

- Connects to a real Dolt SQL server
- Creates test branches and persistent connections
- Simulates connection drops by forcibly closing connections
- Verifies that automatic recovery works in real scenarios

## Running Tests

### Automated Unit Tests
```bash
# Run all connection recovery tests
python -m pytest libs/infra_core/tests/memory_system/test_connection_recovery.py -v

# Run specific test
python -m pytest libs/infra_core/tests/memory_system/test_connection_recovery.py::TestConnectionRecovery::test_real_world_scenario_persistent_connection_recovery -v
```

### Manual Testing
```bash
# Set up environment (if needed)
export DOLT_HOST=localhost
export DOLT_PORT=3306
export DOLT_DATABASE=cogni-dao-memory

# Run manual tests
python libs/infra_core/tests/memory_system/manual_connection_recovery_test.py
```

## What Gets Tested

### Error Detection
- `OperationalError` and `InterfaceError` from mysql.connector
- Connection-related keywords in error messages:
  - "lost connection", "server has gone away"
  - "connection timeout", "connection refused"
  - "network error", "connection reset"
  - And 10+ other patterns

### Reconnection Scenarios
- ✅ Successful reconnection with branch restoration
- ❌ Failed reconnection with proper state cleanup
- 🔄 Branch mismatch handling after reconnection
- 🔀 Non-persistent connection (no retry attempted)

### Retry Logic
- First attempt fails → detect connection error → reconnect → retry succeeds
- First attempt fails → detect connection error → reconnect fails → original error
- First attempt fails → non-connection error → immediate re-raise (no retry)

### Branch Preservation
- Branch context maintained across reconnections
- Branch verification after reconnection
- Handling of missing branch context

## Implementation Details

### DRY Architecture
The connection recovery is implemented in **one location** in `DoltMySQLBase`:

```python
# All database operations flow through these methods:
_execute_query() → _execute_with_retry() → _execute_query_impl()
_execute_update() → _execute_with_retry() → _execute_update_impl()
```

This means ALL inheriting classes get automatic reconnection:
- `DoltMySQLReader`
- `DoltMySQLWriter`
- `SQLLinkManager`
- `MigrationRunner`

### Key Methods
- `_is_connection_error()`: Detect connection-related errors
- `_attempt_reconnection()`: Reconnect persistent connections
- `_execute_with_retry()`: Wrap operations with retry logic

## Manual Validation Options

### Option 1: Use the Manual Test Script
The script simulates real connection drops and verifies recovery.

### Option 2: Network-Level Testing
```bash
# Block network traffic to simulate connection loss
# (Advanced - requires network tools)
sudo pfctl -f /dev/stdin <<< "block drop proto tcp from any to any port 3306"
```

### Option 3: Dolt Server Restart
```bash
# Stop Dolt server while MCP is running
dolt sql-server --kill

# Restart server
dolt sql-server &

# MCP should automatically reconnect
```

## Success Criteria

✅ **All 20 unit tests pass**
✅ **Manual test script completes successfully**
✅ **Real-world connection drops are handled gracefully**
✅ **Branch context is preserved across reconnections**
✅ **No infinite retry loops or resource leaks**

## Monitoring

The connection recovery system includes comprehensive logging:
- ⚠️ Connection error detection
- 🔄 Reconnection attempts
- ✅ Successful recovery
- ❌ Failed recovery with state cleanup

Look for these log messages in your MCP server logs to verify recovery is working. 