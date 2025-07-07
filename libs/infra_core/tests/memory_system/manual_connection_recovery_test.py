#!/usr/bin/env python3
"""
Manual testing script for MySQL connection recovery functionality.

This script can be used to manually validate that the connection recovery
logic works correctly by simulating various failure scenarios.

Usage:
    python manual_connection_recovery_test.py

Requirements:
    - A running Dolt SQL server
    - Environment variables for connection (DOLT_HOST, DOLT_PORT, etc.)
"""

import os
import sys
import time
from pathlib import Path
import mysql.connector
from mysql.connector import Error, OperationalError

# Add the project root to Python path for imports
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig, DoltMySQLBase # noqa: E402


class ManualConnectionRecoveryTester:
    """Manual tester for connection recovery functionality."""

    def __init__(self):
        """Initialize the tester with connection configuration."""
        self.config = DoltConnectionConfig(
            host=os.getenv("DOLT_HOST", "localhost"),
            port=int(os.getenv("DOLT_PORT", "3306")),
            user=os.getenv("DOLT_USER", "root"),
            password=os.getenv("DOLT_ROOT_PASSWORD", ""),
            database=os.getenv("DOLT_DATABASE", "cogni-dao-memory"),
        )
        self.base = DoltMySQLBase(self.config)
        self.test_branch = f"test/connection-recovery-{int(time.time())}"

    def print_status(self, message: str, status: str = "INFO"):
        """Print a formatted status message."""
        symbols = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️"}
        print(f"{symbols.get(status, 'ℹ️')} [{status}] {message}")

    def test_basic_connection(self) -> bool:
        """Test basic connection to Dolt server."""
        self.print_status("Testing basic connection to Dolt server...")

        try:
            connection = mysql.connector.connect(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
                connection_timeout=5,
            )

            cursor = connection.cursor()
            cursor.execute("SELECT 1 as test")
            result = cursor.fetchone()
            cursor.close()
            connection.close()

            if result and result[0] == 1:
                self.print_status("Basic connection test passed", "SUCCESS")
                return True
            else:
                self.print_status("Basic connection test failed - unexpected result", "ERROR")
                return False

        except Exception as e:
            self.print_status(f"Basic connection test failed: {e}", "ERROR")
            return False

    def setup_test_branch(self) -> bool:
        """Create and switch to a test branch."""
        self.print_status(f"Setting up test branch: {self.test_branch}")

        try:
            # Create test branch
            self.base._execute_query(f"CALL DOLT_BRANCH('{self.test_branch}')")
            self.print_status(f"Created test branch: {self.test_branch}", "SUCCESS")

            # Switch to test branch using persistent connection
            self.base.use_persistent_connection(self.test_branch)
            self.print_status(f"Switched to test branch: {self.test_branch}", "SUCCESS")

            return True

        except Exception as e:
            self.print_status(f"Failed to setup test branch: {e}", "ERROR")
            return False

    def cleanup_test_branch(self):
        """Clean up the test branch."""
        self.print_status(f"Cleaning up test branch: {self.test_branch}")

        try:
            # Close persistent connection
            self.base.close_persistent_connection()

            # Switch to main branch
            self.base._execute_query("CALL DOLT_CHECKOUT('main')")

            # Delete test branch
            self.base._execute_query(f"CALL DOLT_BRANCH('-d', '{self.test_branch}')")

            self.print_status("Test branch cleaned up", "SUCCESS")

        except Exception as e:
            self.print_status(f"Warning: Failed to cleanup test branch: {e}", "WARNING")

    def test_persistent_connection_operations(self) -> bool:
        """Test that persistent connection operations work normally."""
        self.print_status("Testing normal persistent connection operations...")

        try:
            # Test query operation
            result = self.base._execute_query("SELECT active_branch() as branch")
            if result and result[0].get("branch") == self.test_branch:
                self.print_status("Query operation successful", "SUCCESS")
            else:
                self.print_status(f"Query operation failed - unexpected branch: {result}", "ERROR")
                return False

            # Test update operation (create a test table)
            self.base._execute_update("""
                CREATE TABLE IF NOT EXISTS test_recovery (
                    id VARCHAR(255) PRIMARY KEY,
                    message TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Insert test data
            affected = self.base._execute_update(
                "INSERT INTO test_recovery (id, message) VALUES (%s, %s)",
                ("test-1", "Connection recovery test"),
            )

            if affected == 1:
                self.print_status("Update operation successful", "SUCCESS")
            else:
                self.print_status(f"Update operation failed - affected rows: {affected}", "ERROR")
                return False

            return True

        except Exception as e:
            self.print_status(f"Normal operations test failed: {e}", "ERROR")
            return False

    def simulate_connection_drop_manual(self) -> bool:
        """
        Manual simulation of connection drop by using is_connected() check.

        This simulates what happens when a connection becomes stale.
        """
        self.print_status("Simulating connection drop (manual method)...")

        try:
            # Get reference to current persistent connection
            if not self.base._persistent_connection:
                self.print_status("No persistent connection to test with", "ERROR")
                return False

            # Force close the connection to simulate a drop
            old_connection = self.base._persistent_connection
            self.print_status("Forcing connection close to simulate drop...")
            old_connection.close()

            # The connection is now broken, but the base class doesn't know yet
            self.print_status("Connection has been forcibly closed", "WARNING")

            # Now try to perform an operation - this should trigger recovery
            self.print_status("Attempting operation on broken connection...")

            try:
                result = self.base._execute_query("SELECT active_branch() as branch")

                # If we get here, recovery worked
                if result and result[0].get("branch") == self.test_branch:
                    self.print_status(
                        "Connection recovery successful! Operation completed.", "SUCCESS"
                    )
                    return True
                else:
                    self.print_status("Operation succeeded but wrong branch returned", "ERROR")
                    return False

            except Exception as inner_e:
                self.print_status(
                    f"Operation failed even after recovery attempt: {inner_e}", "ERROR"
                )
                return False

        except Exception as e:
            self.print_status(f"Connection drop simulation failed: {e}", "ERROR")
            return False

    def test_error_detection(self) -> bool:
        """Test the error detection logic."""
        self.print_status("Testing connection error detection...")

        # Test error detection with various error types
        test_errors = [
            OperationalError("Lost connection to MySQL server"),
            OperationalError("MySQL server has gone away"),
            Error("Connection timeout"),
            Error("Connection refused"),
            Error("Network error occurred"),
            # Non-connection errors (should not trigger recovery)
            Error("Syntax error in SQL statement"),
            ValueError("Invalid parameter"),
        ]

        connection_errors = 0
        total_errors = len(test_errors)

        for error in test_errors:
            is_connection = self.base._is_connection_error(error)
            error_type = type(error).__name__
            error_msg = str(error)

            if is_connection:
                connection_errors += 1
                self.print_status(f"✓ Detected as connection error: {error_type}: {error_msg}")
            else:
                self.print_status(f"○ Not detected as connection error: {error_type}: {error_msg}")

        # We expect the first 5 to be connection errors, last 2 to not be
        expected_connection_errors = 5
        if connection_errors == expected_connection_errors:
            self.print_status(
                f"Error detection test passed: {connection_errors}/{total_errors} detected correctly",
                "SUCCESS",
            )
            return True
        else:
            self.print_status(
                f"Error detection test failed: {connection_errors}/{total_errors} detected, expected {expected_connection_errors}",
                "ERROR",
            )
            return False

    def run_all_tests(self) -> bool:
        """Run all manual tests."""
        self.print_status("Starting manual connection recovery tests...", "INFO")
        self.print_status(
            f"Target: {self.config.host}:{self.config.port}/{self.config.database}", "INFO"
        )

        tests = [
            ("Basic Connection", self.test_basic_connection),
            ("Error Detection", self.test_error_detection),
            ("Test Branch Setup", self.setup_test_branch),
            ("Normal Operations", self.test_persistent_connection_operations),
            ("Connection Drop Simulation", self.simulate_connection_drop_manual),
        ]

        passed = 0
        total = len(tests)

        for test_name, test_func in tests:
            self.print_status(f"\n--- Running: {test_name} ---")

            try:
                if test_func():
                    passed += 1
                    self.print_status(f"{test_name}: PASSED", "SUCCESS")
                else:
                    self.print_status(f"{test_name}: FAILED", "ERROR")
            except Exception as e:
                self.print_status(f"{test_name}: FAILED with exception: {e}", "ERROR")

        # Always attempt cleanup
        self.cleanup_test_branch()

        self.print_status(f"\n=== Test Results: {passed}/{total} tests passed ===")

        if passed == total:
            self.print_status(
                "All tests passed! Connection recovery is working correctly.", "SUCCESS"
            )
            return True
        else:
            self.print_status("Some tests failed. Please check the output above.", "ERROR")
            return False


def print_usage():
    """Print usage instructions."""
    print("""
Manual Connection Recovery Test Script

This script tests the MySQL connection recovery functionality by:
1. Connecting to your Dolt SQL server
2. Setting up a test branch with persistent connection
3. Simulating connection failures
4. Verifying automatic recovery

Prerequisites:
- Running Dolt SQL server
- Environment variables configured:
  - DOLT_HOST (default: localhost)
  - DOLT_PORT (default: 3306) 
  - DOLT_USER (default: root)
  - DOLT_ROOT_PASSWORD (default: empty)
  - DOLT_DATABASE (default: cogni-dao-memory)

Usage:
    python manual_connection_recovery_test.py

The script will create a temporary test branch and clean it up afterward.
""")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help"]:
        print_usage()
        sys.exit(0)

    # Check if basic environment is set up
    host = os.getenv("DOLT_HOST", "localhost")
    port = os.getenv("DOLT_PORT", "3306")
    database = os.getenv("DOLT_DATABASE", "cogni-dao-memory")

    print(f"""
🔧 Manual Connection Recovery Test
Connection: {host}:{port}/{database}
""")

    tester = ManualConnectionRecoveryTester()

    try:
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
        tester.cleanup_test_branch()
        sys.exit(1)

    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        tester.cleanup_test_branch()
        sys.exit(1)
