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
- USE_DOLT_POOL: Enable connection pooling (default: false)
- DOLT_POOL_SIZE: Pool size when pooling enabled (default: 10)
"""

import logging
import os
from dataclasses import dataclass, field
from typing import List, Dict, Any

import mysql.connector
from mysql.connector import Error, OperationalError, InterfaceError, DatabaseError
from mysql.connector.pooling import MySQLConnectionPool
from contextlib import contextmanager

# Setup standard Python logger
logger = logging.getLogger(__name__)

# Configuration for protected branches
DEFAULT_PROTECTED_BRANCH = os.getenv("DOLT_PROTECTED_BRANCH", "main")
PROTECTED_BRANCHES = [
    branch.strip().lower()
    for branch in os.getenv("DOLT_PROTECTED_BRANCHES", DEFAULT_PROTECTED_BRANCH).split(",")
    if branch.strip()  # Filter out empty strings
]


class MainBranchProtectionError(Exception):
    """
    Raised when attempting to perform a write operation on a protected branch.

    Protected branches (typically 'main' or 'production') should not allow
    direct write operations to prevent accidental data corruption.
    """

    def __init__(self, operation: str, branch: str, protected_branches: List[str] = None):
        self.operation = operation
        self.branch = branch
        self.protected_branches = protected_branches or PROTECTED_BRANCHES
        super().__init__(
            f"Operation '{operation}' blocked on protected branch '{branch}'. "
            f"Protected branches are read-only. Please find the right feature branch to work on."
        )


class BranchConsistencyError(Exception):
    """
    Raised when branch state becomes inconsistent after reconnection.

    This ensures strict branch consistency by failing fast when the database
    connection ends up on a different branch than expected after reconnection.
    """

    def __init__(self, expected_branch: str, actual_branch: str):
        self.expected_branch = expected_branch
        self.actual_branch = actual_branch
        super().__init__(
            f"Branch consistency violation after reconnection: expected '{expected_branch}', "
            f"but connection is on '{actual_branch}'. This could lead to operations on the wrong branch."
        )


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
    """
    Base class for Dolt MySQL operations with connection management and branch protection.

    Provides common functionality for connecting to Dolt SQL server via MySQL connector,
    including persistent connection support and configurable branch write protection.
    """

    def __init__(self, config: DoltConnectionConfig):
        self.config = config
        self._persistent_connection = None
        self._current_branch = None
        self._use_persistent = False

        # Connection pooling support (feature flagged)
        self._use_pool = os.getenv("USE_DOLT_POOL", "false").lower() == "true"
        self._pool = None
        self._pool_size = int(os.getenv("DOLT_POOL_SIZE", "10"))

        if self._use_pool:
            self._initialize_connection_pool()
            logger.info(
                f"DoltMySQLBase: Connection pooling enabled with {self._pool_size} connections"
            )
        else:
            logger.debug("DoltMySQLBase: Using legacy persistent connection mode")

    def _is_branch_protected(self, branch: str) -> bool:
        """
        Check if a branch is protected from write operations.

        Args:
            branch: Branch name to check

        Returns:
            True if branch is protected, False otherwise
        """
        return branch.lower() in PROTECTED_BRANCHES

    def _check_branch_protection(self, operation: str, target_branch: str) -> None:
        """
        Check if the operation is attempting to write to a protected branch and raise an error if so.

        Args:
            operation: Description of the operation being attempted
            target_branch: The specific branch being targeted

        Raises:
            MainBranchProtectionError: If attempting to write to protected branch
        """
        if self._is_branch_protected(target_branch):
            logger.warning(
                f"Blocked {operation} on protected branch '{target_branch}' - protected branches are read-only"
            )
            raise MainBranchProtectionError(operation, target_branch, PROTECTED_BRANCHES)

        logger.debug(f"Branch protection check passed: {operation} on branch '{target_branch}'")

    def _check_main_branch_protection(self, operation: str, target_branch: str = None) -> None:
        """
        Legacy method for backward compatibility. Use _check_branch_protection instead.

        Args:
            operation: Description of the operation being attempted
            target_branch: The branch being targeted (if None, uses active branch)

        Raises:
            MainBranchProtectionError: If attempting to write to protected branch
        """
        # Determine the effective branch
        if target_branch is not None:
            effective_branch = target_branch
        else:
            # Get the current active branch
            effective_branch = self.active_branch

        self._check_branch_protection(operation, effective_branch)

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

    def _initialize_connection_pool(self) -> None:
        """
        Initialize MySQL connection pool for improved connection management.

        Only called when USE_DOLT_POOL=true. Provides automatic connection
        health management, thread safety, and resource efficiency.
        """
        try:
            pool_config = {
                "pool_name": f"dolt_pool_{self.config.database}",
                "pool_size": self._pool_size,
                "pool_reset_session": True,  # Auto-reset session state
                "host": self.config.host,
                "port": self.config.port,
                "user": self.config.user,
                "password": self.config.password,
                "database": self.config.database,
                "charset": "utf8mb4",
                "autocommit": False,  # Default for transaction control
                "connection_timeout": 10,
                "use_unicode": True,
                "raise_on_warnings": True,
            }

            self._pool = MySQLConnectionPool(**pool_config)
            logger.info(f"Initialized MySQL connection pool: {self._pool_size} connections")

        except Error as e:
            raise Exception(f"Failed to initialize MySQL connection pool: {e}")

    @contextmanager
    def get_connection(self, branch: str = None, autocommit: bool = False):
        """
        Get a healthy connection with branch isolation and transaction control.

        When USE_DOLT_POOL=true: Uses connection pooling with automatic health checks
        When USE_DOLT_POOL=false: Falls back to legacy _get_connection() behavior

        Args:
            branch: Target branch to checkout (None = no branch change)
            autocommit: Transaction mode (False for writers, True for readers)

        Yields:
            mysql.connector.MySQLConnection: Healthy connection on correct branch

        Example:
            with self.get_connection('feature-branch', autocommit=False) as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("INSERT INTO memory_blocks ...")
                conn.commit()  # Explicit commit for writers
        """
        if not self._use_pool:
            # Legacy behavior: use _get_connection()
            connection = self._get_connection()
            try:
                connection.autocommit = autocommit
                if branch:
                    self._ensure_branch(connection, branch)
                yield connection
            finally:
                if connection:
                    connection.close()
            return

        # Pooled behavior: enhanced connection management
        connection = None
        try:
            # Get connection from pool
            connection = self._pool.get_connection()

            # Health check with automatic reconnection
            self._ensure_connection_healthy_pooled(connection)

            # Configure transaction mode
            connection.autocommit = autocommit

            # Branch isolation if specified
            if branch:
                self._ensure_branch(connection, branch)

            logger.debug(f"Acquired pooled connection: branch={branch}, autocommit={autocommit}")
            yield connection

        except Exception as e:
            # Rollback on error (only if not autocommit)
            if connection and not autocommit:
                try:
                    connection.rollback()
                    logger.debug("Rolled back transaction due to error")
                except Exception:
                    pass
            raise e

        finally:
            # Guaranteed cleanup
            if connection:
                try:
                    # Rollback any uncommitted transaction (only if not autocommit)
                    if not autocommit:
                        connection.rollback()
                        logger.debug("Rolled back transaction on context exit")

                    # Return connection to pool
                    connection.close()  # Returns to pool
                    logger.debug("Returned connection to pool")

                except Exception as e:
                    logger.warning(f"Error during connection cleanup: {e}")

    def _ensure_connection_healthy_pooled(
        self, connection: mysql.connector.MySQLConnection
    ) -> None:
        """
        Ensure pooled connection is healthy with ping(reconnect=True) and verification.

        Enhanced health check for pooled connections:
        1. connection.ping(reconnect=True) - MySQL-level health check with auto-reconnect
        2. SELECT 1 - Verify basic query execution

        Args:
            connection: Connection to verify

        Raises:
            Exception: If connection health check fails
        """
        try:
            # Primary health check with automatic reconnection
            connection.ping(reconnect=True)

            # Verification: basic query execution
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()

            if result != (1,):
                raise Exception(f"Health check returned unexpected result: {result}")

            logger.debug("Pooled connection health check passed")

        except Exception as e:
            logger.error(f"Pooled connection health check failed: {e}")
            raise Exception(f"Pooled connection health check failed: {e}")

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

    def _is_connection_healthy(self, connection: mysql.connector.MySQLConnection) -> bool:
        """
        Check if connection is actually usable before attempting operations.

        This prevents the "MySQL Connection not available" error by proactively
        detecting stale connections that report as connected but can't execute queries.

        Args:
            connection: The MySQL connection to check

        Returns:
            True if connection is healthy and can execute queries, False otherwise
        """
        try:
            # First check if connection reports as connected
            if not connection.is_connected():
                logger.debug("Connection health check: connection reports as disconnected")
                return False

            # Try a simple query to verify it's actually usable
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            logger.debug("Connection health check: connection is healthy")
            return True

        except Exception as e:
            logger.debug(f"Connection health check failed: {e}")
            return False

    def use_persistent_connection(self, branch: str = DEFAULT_PROTECTED_BRANCH) -> None:
        """
        Enable persistent connection mode and checkout the specified branch.

        This allows multiple operations to reuse the same connection and maintain
        branch state across operations. Call close_persistent_connection() when done.

        Args:
            branch: Branch to checkout and maintain for all subsequent operations
        """
        if self._use_pool:
            import warnings

            warnings.warn(
                "use_persistent_connection() is deprecated when USE_DOLT_POOL=true. "
                "Use get_connection() context manager instead for better resource management.",
                DeprecationWarning,
                stacklevel=2,
            )
            logger.info(
                f"Legacy persistent connection request ignored (pooling enabled): branch={branch}"
            )
            return

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
        if self._use_pool:
            import warnings

            warnings.warn(
                "close_persistent_connection() is deprecated when USE_DOLT_POOL=true. "
                "Connections are managed automatically.",
                DeprecationWarning,
                stacklevel=2,
            )
            logger.info("Legacy persistent connection close request ignored (pooling enabled)")
            return

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

    def _ensure_branch_and_check_protection(
        self, connection: mysql.connector.MySQLConnection, operation: str, target_branch: str
    ) -> None:
        """
        Safely ensure we're on the target branch and check protection.

        For persistent connections, this ensures the connection is actually switched
        to the target branch before checking protection, preventing bypass attacks.

        Args:
            connection: The database connection
            operation: Description of the operation being attempted
            target_branch: The branch to switch to and check protection for

        Raises:
            MainBranchProtectionError: If attempting to write to protected branch
        """
        # For persistent connections, ensure we're actually on the target branch
        if self._use_persistent and self._persistent_connection:
            if self._current_branch != target_branch:
                self._ensure_branch(connection, target_branch)
                self._current_branch = target_branch
        else:
            # For non-persistent connections, always ensure branch
            self._ensure_branch(connection, target_branch)

        # Now check protection with the actual current branch
        self._check_branch_protection(operation, target_branch)

    def _is_connection_error(self, error: Exception) -> bool:
        """
        Check if an error is connection-related and potentially recoverable.

        Args:
            error: The exception to check

        Returns:
            True if this is a connection error that might be recoverable
        """
        # Check for specific MySQL connector connection errors
        if isinstance(error, (OperationalError, InterfaceError)):
            return True

        # Check for common connection error patterns in the error message
        # TODO: what a silly way to do this.. can we be smarter?
        if isinstance(error, Error):
            error_msg = str(error).lower()
            connection_keywords = [
                "lost connection",
                "connection was killed",
                "connection timeout",
                "connection refused",
                "broken pipe",
                "network error",
                "connection reset",
                "connection aborted",
                "host is unreachable",
                "connection closed",
                "server has gone away",
                "server shutdown",
                "can't connect to mysql server",
                "mysql connection not available",  # FIX: Add Docker-specific error pattern
            ]
            return any(keyword in error_msg for keyword in connection_keywords)

        return False

    def _attempt_reconnection(self) -> bool:
        """
        Attempt to reconnect the persistent connection if it's in use, or validate regular connection capability.

        Returns:
            True if reconnection was successful, False otherwise
        """
        if not self._use_persistent:
            # For regular connections, just validate we can create a working connection
            logger.warning("🔄 Attempting to validate regular connection capability...")
            try:
                test_conn = self._get_connection()
                # Test the connection by creating a cursor
                cursor = test_conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                test_conn.close()
                logger.info("✅ Regular connection validation successful")
                return True
            except Exception as e:
                logger.error(f"❌ Regular connection validation failed: {e}")
                return False

        logger.warning("🔄 Attempting to reconnect persistent connection...")

        try:
            # Close the old connection if it exists
            if self._persistent_connection:
                try:
                    self._persistent_connection.close()
                except Exception:
                    pass  # Ignore errors when closing broken connection

            # Create new persistent connection
            self._persistent_connection = self._get_connection()

            # Restore the branch state if we had one
            if self._current_branch:
                self._ensure_branch(self._persistent_connection, self._current_branch)

                # Verify the branch was restored correctly
                actual_branch = self._verify_current_branch(self._persistent_connection)
                if actual_branch != self._current_branch:
                    logger.error(
                        f"Branch mismatch after reconnection: expected '{self._current_branch}', got '{actual_branch}'"
                    )
                    raise BranchConsistencyError(self._current_branch, actual_branch)

            logger.info(
                f"✅ Persistent connection reconnected successfully on branch '{self._current_branch}'"
            )
            return True

        except DatabaseError as e:
            logger.error(f"❌ Database error during reconnection: {e}")
            # Reset persistent connection state on failure
            self._persistent_connection = None
            self._current_branch = None
            self._use_persistent = False
            return False
        except BranchConsistencyError:
            # Let branch consistency errors bubble up to enforce strict branch consistency
            raise
        except Exception as e:
            # Log unexpected non-database errors separately for troubleshooting
            logger.error(f"❌ Unexpected error during reconnection: {type(e).__name__}: {e}")
            # Reset persistent connection state on failure
            self._persistent_connection = None
            self._current_branch = None
            self._use_persistent = False
            return False

    def _execute_with_retry(self, operation_func, query: str, params: tuple = None):
        """
        Execute a database operation with automatic reconnection retry.

        Args:
            operation_func: The actual operation function to execute
            query: SQL query string
            params: Query parameters

        Returns:
            The result of the operation function

        Raises:
            Exception: If the operation fails even after reconnection attempt
        """
        try:
            # First attempt
            return operation_func(query, params)

        except Exception as e:
            # Check if this is a connection error and if we should retry
            if self._is_connection_error(e):
                logger.warning(f"⚠️ Connection error detected: {e}")

                # Attempt reconnection (only for persistent connections)
                if self._attempt_reconnection():
                    logger.info("🔄 Retrying operation after reconnection...")
                    try:
                        # Second attempt after reconnection
                        return operation_func(query, params)
                    except DatabaseError as retry_db_e:
                        logger.error(
                            f"❌ Database operation failed even after reconnection: {retry_db_e}"
                        )
                        raise Exception(
                            f"Database operation failed after reconnection attempt: {retry_db_e}"
                        )
                    except Exception as retry_e:
                        # Log unexpected non-database errors that occurred during retry
                        logger.error(
                            f"❌ Unexpected error during retry: {type(retry_e).__name__}: {retry_e}"
                        )
                        raise  # Re-raise unexpected errors as-is to preserve stack trace
                else:
                    # Reconnection failed, raise the original error
                    raise e
            else:
                # Not a connection error, re-raise as-is
                raise e

    def _execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Execute a query and return results as list of dictionaries."""
        return self._execute_with_retry(self._execute_query_impl, query, params)

    def _execute_query_impl(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Implementation of query execution (without retry logic)."""
        # Use persistent connection if available, otherwise create new one
        if self._use_persistent and self._persistent_connection:
            # FIX: Check connection health before use to prevent "MySQL Connection not available" errors
            if not self._is_connection_healthy(self._persistent_connection):
                logger.warning(
                    "Persistent connection unhealthy, creating new connection for this operation"
                )
                # Don't reset persistent connection state - let retry logic handle reconnection
                # Just use a new connection for this specific operation
                connection = self._get_connection()
                connection_is_persistent = False
            else:
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
            # FIX: Don't wrap - preserve original error type for proper detection
            # The original Exception wrapping prevented _is_connection_error from detecting
            # OperationalError("MySQL Connection not available") properly
            raise e
        finally:
            # Only close if it's not a persistent connection
            if not connection_is_persistent:
                connection.close()

    def _execute_update(self, query: str, params: tuple = None) -> int:
        """Execute an update/insert/delete query and return affected rows."""
        return self._execute_with_retry(self._execute_update_impl, query, params)

    def _execute_update_impl(self, query: str, params: tuple = None) -> int:
        """Implementation of update execution (without retry logic)."""
        # Use persistent connection if available, otherwise create new one
        if self._use_persistent and self._persistent_connection:
            # FIX: Check connection health before use to prevent "MySQL Connection not available" errors
            if not self._is_connection_healthy(self._persistent_connection):
                logger.warning(
                    "Persistent connection unhealthy, creating new connection for this operation"
                )
                # Don't reset persistent connection state - let retry logic handle reconnection
                # Just use a new connection for this specific operation
                connection = self._get_connection()
                connection_is_persistent = False
            else:
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
            # FIX: Don't wrap - preserve original error type for proper detection
            raise e
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
                    return DEFAULT_PROTECTED_BRANCH  # Fallback to default if query fails

            finally:
                if not connection_is_persistent:
                    connection.close()

        except Exception as e:
            logger.warning(f"Failed to get active branch: {e}")
            return DEFAULT_PROTECTED_BRANCH  # Fallback to default on error
