"""
Shared MySQL base class and configuration for Dolt memory system.

This module contains the foundational classes used by all Dolt MySQL components:
- DoltConnectionConfig: Configuration for MySQL connections using environment variables
- DoltMySQLBase: Base class with common connection and query execution methods

This allows clear separation between the shared foundation and specialized classes
for reading, writing, and link management.

Environment Variables (used by DoltConnectionConfig):
- MYSQL_HOST / DB_HOST: Database host (default: localhost)
- MYSQL_PORT / DB_PORT: Database port (default: 3306)
- MYSQL_USER / DB_USER: Database user (default: root)
- MYSQL_PASSWORD / DB_PASSWORD: Database password (default: empty)
- MYSQL_DATABASE / DB_NAME: Database name (default: memory_dolt)
"""

import logging
import os
from dataclasses import dataclass, field
from typing import List, Dict, Any

import mysql.connector
from mysql.connector import Error

# Setup standard Python logger
logger = logging.getLogger(__name__)


@dataclass
class DoltConnectionConfig:
    """Configuration for connecting to a Dolt SQL server via MySQL connector.

    Uses standard MySQL environment variables with sensible defaults for Dolt.
    Environment variables checked (in order of precedence):
    - MYSQL_HOST / DB_HOST -> host
    - MYSQL_PORT / DB_PORT -> port
    - MYSQL_USER / DB_USER -> user
    - MYSQL_PASSWORD / DB_PASSWORD -> password
    - MYSQL_DATABASE / DB_NAME -> database
    """

    host: str = field(
        default_factory=lambda: os.getenv("MYSQL_HOST") or os.getenv("DB_HOST", "localhost")
    )
    port: int = field(
        default_factory=lambda: int(os.getenv("MYSQL_PORT") or os.getenv("DB_PORT", "3306"))
    )
    user: str = field(
        default_factory=lambda: os.getenv("MYSQL_USER") or os.getenv("DB_USER", "root")
    )
    password: str = field(
        default_factory=lambda: os.getenv("MYSQL_PASSWORD") or os.getenv("DB_PASSWORD", "")
    )
    database: str = field(
        default_factory=lambda: os.getenv("MYSQL_DATABASE") or os.getenv("DB_NAME", "memory_dolt")
    )


class DoltMySQLBase:
    """Base class providing common MySQL connection and query execution methods for Dolt.

    This class implements the shared functionality for connecting to and executing queries
    against a Dolt SQL server. It can be inherited by specialized classes for different
    purposes (reading, writing, link management).

    Note: Subclasses should override _get_connection() if they need different connection
    settings (e.g., autocommit behavior).
    """

    def __init__(self, config: DoltConnectionConfig):
        """Initialize with connection configuration."""
        self.config = config

    def _get_connection(self):
        """Get a new MySQL connection to the Dolt SQL server.

        This base implementation uses autocommit=True. Subclasses can override
        this method to use different connection settings.
        """
        try:
            conn = mysql.connector.connect(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
                charset="utf8mb4",
                autocommit=True,  # Default for base class
                connection_timeout=10,
                use_unicode=True,
                raise_on_warnings=True,
            )
            return conn
        except Error as e:
            raise Exception(f"Failed to connect to Dolt SQL server: {e}")

    def _ensure_branch(self, connection: mysql.connector.MySQLConnection, branch: str) -> None:
        """Ensure we're on the specified branch."""
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("CALL DOLT_CHECKOUT(%s)", (branch,))
            # Consume any results
            cursor.fetchall()
            cursor.close()
        except Error as e:
            raise Exception(f"Failed to checkout branch '{branch}': {e}")

    def _execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Execute a query and return results as list of dictionaries."""
        connection = self._get_connection()
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, params or ())
            results = cursor.fetchall()
            cursor.close()
            return results
        except Error as e:
            raise Exception(f"Query failed: {e}")
        finally:
            connection.close()

    def _execute_update(self, query: str, params: tuple = None) -> int:
        """Execute an update/insert/delete query and return affected rows."""
        connection = self._get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(query, params or ())
            affected_rows = cursor.rowcount
            connection.commit()
            cursor.close()
            return affected_rows
        except Error as e:
            connection.rollback()
            raise Exception(f"Update failed: {e}")
        finally:
            connection.close()
