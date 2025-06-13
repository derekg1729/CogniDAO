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

    def __post_init__(self):
        """Log connection configuration for debugging."""
        logger.info(
            f"DoltConnectionConfig: host={self.host}, port={self.port}, user={self.user}, database={self.database}"
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
        # Persistent connection support (opt-in)
        self._persistent_connection = None
        self._current_branch = None
        self._use_persistent = False

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

    def _verify_current_branch(self, connection: mysql.connector.MySQLConnection) -> str:
        """
        Verify and return the current branch for this session.

        According to Dolt documentation, each session has its own branch state.
        This method queries the session's current branch to ensure synchronization.

        Returns:
            The name of the current branch for this session
        """
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT active_branch() as current_branch")
            result = cursor.fetchone()
            cursor.close()

            if result and result.get("current_branch"):
                return result["current_branch"]
            else:
                raise Exception("Could not determine current branch from session")

        except Error as e:
            raise Exception(f"Failed to verify current branch: {e}")

    def use_persistent_connection(self, branch: str = "main") -> None:
        """
        Enable persistent connection mode and checkout the specified branch.

        This allows multiple operations to reuse the same connection and maintain
        branch state across operations. Call close_persistent_connection() when done.

        Args:
            branch: Branch to checkout and maintain for all subsequent operations
        """
        if self._persistent_connection:
            logger.warning("Persistent connection already active, closing previous connection")
            self.close_persistent_connection()

        try:
            # Create persistent connection
            self._persistent_connection = self._get_connection()

            # Checkout the specified branch
            self._ensure_branch(self._persistent_connection, branch)

            # Verify the actual branch state according to Dolt session behavior
            actual_branch = self._verify_current_branch(self._persistent_connection)
            self._current_branch = actual_branch
            self._use_persistent = True

            logger.info(
                f"Persistent connection established on branch '{actual_branch}' (requested: '{branch}')"
            )

        except Exception as e:
            # Cleanup on failure
            if self._persistent_connection:
                try:
                    self._persistent_connection.close()
                except Exception:
                    pass
            self._persistent_connection = None
            self._current_branch = None
            self._use_persistent = False
            raise Exception(f"Failed to establish persistent connection: {e}")

    def close_persistent_connection(self) -> None:
        """
        Close the persistent connection and return to per-operation connection mode.
        """
        if self._persistent_connection:
            try:
                self._persistent_connection.close()
                logger.info(
                    f"Closed persistent connection (was on branch '{self._current_branch}')"
                )
            except Exception as e:
                logger.warning(f"Error closing persistent connection: {e}")
            finally:
                self._persistent_connection = None
                self._current_branch = None
                self._use_persistent = False

    def _execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Execute a query and return results as list of dictionaries."""
        # Use persistent connection if available, otherwise create new one
        if self._use_persistent and self._persistent_connection:
            connection = self._persistent_connection
            connection_is_persistent = True
        else:
            connection = self._get_connection()
            connection_is_persistent = False

        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, params or ())
            results = cursor.fetchall()
            cursor.close()
            return results
        except Error as e:
            raise Exception(f"Query failed: {e}")
        finally:
            # Only close if it's not a persistent connection
            if not connection_is_persistent:
                connection.close()

    def _execute_update(self, query: str, params: tuple = None) -> int:
        """Execute an update/insert/delete query and return affected rows."""
        # Use persistent connection if available, otherwise create new one
        if self._use_persistent and self._persistent_connection:
            connection = self._persistent_connection
            connection_is_persistent = True
        else:
            connection = self._get_connection()
            connection_is_persistent = False

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
            # Only close if it's not a persistent connection
            if not connection_is_persistent:
                connection.close()

    @property
    def active_branch(self) -> str:
        """
        Get the active branch for this connection.

        Returns the branch from persistent connection state if available,
        otherwise queries the database to get the active branch using Dolt's active_branch() function.

        Returns:
            The name of the active branch as a string
        """
        # If we have persistent connection state, use that
        if self._use_persistent and self._current_branch:
            return self._current_branch

        # Otherwise query the database using Dolt's native active_branch() function
        try:
            if self._use_persistent and self._persistent_connection:
                connection = self._persistent_connection
                connection_is_persistent = True
            else:
                connection = self._get_connection()
                connection_is_persistent = False

            try:
                cursor = connection.cursor(dictionary=True)
                cursor.execute("SELECT active_branch() as active_branch")
                result = cursor.fetchone()
                cursor.close()

                if result and result.get("active_branch"):
                    return result["active_branch"]
                else:
                    return "main"  # Fallback to main if query fails

            finally:
                if not connection_is_persistent:
                    connection.close()

        except Exception as e:
            logger.warning(f"Failed to get active branch: {e}")
            return "main"  # Fallback to main on error
