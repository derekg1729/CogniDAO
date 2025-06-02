"""
Test MySQL connector integration with Dolt SQL server.

This test verifies that we can connect to a running Dolt SQL server using
mysql.connector and perform basic operations including branch switching.

Environment Variables:
- MYSQL_HOST / DB_HOST: Database host (default: localhost)
- MYSQL_PORT / DB_PORT: Database port (default: 3306)
- MYSQL_USER / DB_USER: Database user (default: root)
- MYSQL_PASSWORD / DB_PASSWORD: Database password (default: empty)
- MYSQL_DATABASE / DB_NAME: Database name (default: memory_dolt)
"""

import os
import mysql.connector
from mysql.connector import Error
import pytest


class TestMySQLDoltIntegration:
    """Test MySQL connector integration with Dolt SQL server."""

    @pytest.fixture(autouse=True)
    def setup_connection_config(self):
        """Set up connection configuration from environment variables."""
        self.connection_config = {
            "host": os.getenv("MYSQL_HOST") or os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("MYSQL_PORT") or os.getenv("DB_PORT", "3306")),
            "user": os.getenv("MYSQL_USER") or os.getenv("DB_USER", "root"),
            "password": os.getenv("MYSQL_PASSWORD") or os.getenv("DB_PASSWORD", ""),
            "database": os.getenv("MYSQL_DATABASE") or os.getenv("DB_NAME", "memory_dolt"),
            "charset": "utf8mb4",
            "autocommit": True,
            "connection_timeout": 10,
            "use_unicode": True,
            "raise_on_warnings": True,
        }

    def test_connection_to_dolt_server(self):
        """Test that we can connect to the Dolt SQL server."""
        try:
            connection = mysql.connector.connect(**self.connection_config)
            assert connection.is_connected(), "Should be able to connect to Dolt SQL server"

            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT 1 as test_value")
            result = cursor.fetchone()

            assert result is not None, "Should get a result from basic query"
            assert result["test_value"] == 1, "Should get the expected test value"

            cursor.close()
            connection.close()

        except Error as e:
            pytest.fail(f"Failed to connect to Dolt SQL server: {e}")

    def test_show_tables(self):
        """Test that we can see the memory_blocks table."""
        try:
            connection = mysql.connector.connect(**self.connection_config)
            cursor = connection.cursor(dictionary=True)

            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()

            table_names = [table[list(table.keys())[0]] for table in tables]
            assert "memory_blocks" in table_names, (
                f"memory_blocks table should exist. Found tables: {table_names}"
            )

            cursor.close()
            connection.close()

        except Error as e:
            pytest.fail(f"Failed to show tables: {e}")

    def test_count_memory_blocks(self):
        """Test that we can count memory blocks in the database."""
        try:
            connection = mysql.connector.connect(**self.connection_config)
            cursor = connection.cursor(dictionary=True)

            cursor.execute("SELECT COUNT(*) as block_count FROM memory_blocks")
            result = cursor.fetchone()

            assert result is not None, "Should get a count result"
            block_count = result["block_count"]
            assert isinstance(block_count, int), "Block count should be an integer"
            print(f"Found {block_count} memory blocks in the database")

            cursor.close()
            connection.close()

        except Error as e:
            pytest.fail(f"Failed to count memory blocks: {e}")

    def test_branch_switching(self):
        """Test that we can switch branches using DOLT_CHECKOUT."""
        try:
            connection = mysql.connector.connect(**self.connection_config)
            cursor = connection.cursor(dictionary=True)

            # Test switching to main branch
            cursor.execute("CALL DOLT_CHECKOUT('main')")
            cursor.fetchall()  # Consume any results

            # Verify we can still query after branch switch
            cursor.execute("SELECT COUNT(*) as count FROM memory_blocks")
            main_result = cursor.fetchone()
            main_count = main_result["count"]

            print(f"Memory blocks on main branch: {main_count}")

            # Test creating and switching to a test branch
            cursor.execute("CALL DOLT_BRANCH('test-branch')")
            cursor.fetchall()  # Consume any results

            cursor.execute("CALL DOLT_CHECKOUT('test-branch')")
            cursor.fetchall()  # Consume any results

            # Verify we can query on the new branch
            cursor.execute("SELECT COUNT(*) as count FROM memory_blocks")
            test_result = cursor.fetchone()
            test_count = test_result["count"]

            print(f"Memory blocks on test-branch: {test_count}")

            # Switch back to main
            cursor.execute("CALL DOLT_CHECKOUT('main')")
            cursor.fetchall()  # Consume any results

            # Clean up - delete the test branch
            cursor.execute("CALL DOLT_BRANCH('-d', 'test-branch')")
            cursor.fetchall()  # Consume any results

            cursor.close()
            connection.close()

        except Error as e:
            pytest.fail(f"Failed branch switching test: {e}")

    def test_sample_memory_block_read(self):
        """Test reading a sample memory block."""
        try:
            connection = mysql.connector.connect(**self.connection_config)
            cursor = connection.cursor(dictionary=True)

            # Get a sample memory block
            cursor.execute("SELECT * FROM memory_blocks LIMIT 1")
            result = cursor.fetchone()

            if result:
                print(f"Sample memory block keys: {list(result.keys())}")
                assert "id" in result, "Memory block should have an id field"
                assert "text" in result, "Memory block should have a text field"
                assert "type" in result, "Memory block should have a type field"
                print(f"Sample block ID: {result['id']}, Type: {result['type']}")
            else:
                print("No memory blocks found in database")

            cursor.close()
            connection.close()

        except Error as e:
            pytest.fail(f"Failed to read sample memory block: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
