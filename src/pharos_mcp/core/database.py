"""
Database connection management for Pharos MCP.

Provides connection pooling and query execution for multiple databases.
"""

import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from ..config import get_config
from .dialect import DatabaseDialect, get_dialect

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Manages a single database connection with its configuration."""

    def __init__(self, name: str, config: dict[str, Any]):
        """Initialize a database connection.

        Args:
            name: Identifier for this database.
            config: Connection configuration from get_database_config().
        """
        self.name = name
        self.config = config
        self._connection: Any | None = None
        self._dialect: DatabaseDialect = get_dialect(config.get("type", "mssql"))

    @property
    def db_type(self) -> str:
        return self.config.get("type", "mssql")

    @property
    def server(self) -> str:
        # For SQL Server
        return self.config.get("server", "")

    @property
    def host(self) -> str:
        # For PostgreSQL
        return self.config.get("host", "")

    @property
    def port(self) -> int:
        # For PostgreSQL
        return self.config.get("port", 5432)

    @property
    def database(self) -> str:
        return self.config.get("database", "")

    @property
    def user(self) -> str:
        return self.config.get("user", "")

    @property
    def password(self) -> str:
        return self.config.get("password", "")

    @property
    def readonly(self) -> bool:
        return self.config.get("readonly", True)

    @property
    def timeout(self) -> int:
        return self.config.get("settings", {}).get("timeout", 30)

    @property
    def max_rows(self) -> int:
        return self.config.get("settings", {}).get("max_rows", 1000)

    def _is_connection_alive(self) -> bool:
        """Check if the current connection is still alive.

        Returns:
            True if connection is alive, False otherwise.
        """
        if self._connection is None:
            return False
        try:
            # Try a simple query to test connection
            cursor = self._dialect.get_cursor(self._connection, as_dict=False)
            cursor.execute(self._dialect.test_connection_sql())
            cursor.fetchone()
            cursor.close()
            return True
        except Exception:
            return False

    def connect(self, force_reconnect: bool = False) -> Any:
        """Establish database connection with automatic reconnection.

        Args:
            force_reconnect: If True, close existing connection and reconnect.

        Returns:
            Active database connection.

        Raises:
            Exception: If connection fails.
        """
        # Check if we need to reconnect
        if force_reconnect and self._connection is not None:
            self.disconnect()

        # If we have a connection, verify it's still alive
        if self._connection is not None and not self._is_connection_alive():
            logger.warning(f"Connection to {self.name} is dead, reconnecting...")
            self.disconnect()

        # Create new connection if needed
        if self._connection is None:
            logger.info(f"Connecting to database: {self.name} ({self.database})")
            self._connection = self._dialect.create_connection(self.config)
        return self._connection

    def disconnect(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            try:
                self._connection.close()
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
            finally:
                self._connection = None

    @contextmanager
    def cursor(self, as_dict: bool = True) -> Generator[Any, None, None]:
        """Get a cursor for query execution.

        Args:
            as_dict: If True, return rows as dictionaries.

        Yields:
            Database cursor.
        """
        conn = self.connect()
        cursor = self._dialect.get_cursor(conn, as_dict=as_dict)
        try:
            yield cursor
        finally:
            cursor.close()

    def execute_query(
        self,
        sql: str,
        params: tuple[Any, ...] | None = None,
        max_rows: int | None = None,
        max_retries: int = 2,
    ) -> list[dict[str, Any]]:
        """Execute a SQL query and return results.

        Args:
            sql: SQL query to execute.
            params: Optional query parameters.
            max_rows: Maximum rows to return (defaults to config max_rows).
            max_retries: Maximum number of retry attempts on connection failure.

        Returns:
            List of result rows as dictionaries.
        """
        if max_rows is None:
            max_rows = self.max_rows

        connection_errors = self._dialect.get_connection_errors()
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                with self.cursor() as cursor:
                    cursor.execute(sql, params)
                    results = []
                    for row in cursor:
                        results.append(dict(row))
                        if len(results) >= max_rows:
                            break
                    return results
            except connection_errors as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning(f"Query failed (attempt {attempt + 1}), reconnecting: {e}")
                    self.disconnect()  # Force reconnection on next attempt
                else:
                    raise
        raise last_error  # Should not reach here, but for type safety

    def execute_scalar(
        self,
        sql: str,
        params: tuple[Any, ...] | None = None,
        max_retries: int = 2,
    ) -> Any:
        """Execute a query and return a single scalar value.

        Args:
            sql: SQL query to execute.
            params: Optional query parameters.
            max_retries: Maximum number of retry attempts on connection failure.

        Returns:
            First column of first row, or None.
        """
        connection_errors = self._dialect.get_connection_errors()
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                with self.cursor(as_dict=False) as cursor:
                    cursor.execute(sql, params)
                    row = cursor.fetchone()
                    if row:
                        return row[0]
                    return None
            except connection_errors as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning(f"Scalar query failed (attempt {attempt + 1}), reconnecting: {e}")
                    self.disconnect()  # Force reconnection on next attempt
                else:
                    raise
        raise last_error  # Should not reach here, but for type safety


class DatabaseRegistry:
    """Registry managing multiple database connections."""

    def __init__(self):
        """Initialize the database registry."""
        self._connections: dict[str, DatabaseConnection] = {}
        self._config = get_config()

    def get_connection(self, name: str | None = None) -> DatabaseConnection:
        """Get or create a database connection.

        Args:
            name: Database name from config. Defaults to default_database.

        Returns:
            DatabaseConnection instance.

        Raises:
            ValueError: If database not found in config.
        """
        if name is None:
            name = self._config.default_database

        if name not in self._connections:
            db_config = self._config.get_database_config(name)
            self._connections[name] = DatabaseConnection(name, db_config)

        return self._connections[name]

    def list_databases(self) -> list[dict[str, Any]]:
        """List all configured databases.

        Returns:
            List of database info dictionaries.
        """
        result = []
        for name, db_config in self._config.databases.items():
            result.append({
                "name": name,
                "description": db_config.get("description", ""),
                "readonly": db_config.get("readonly", True),
                "type": db_config.get("type", "mssql"),
            })
        return result

    def close_all(self) -> None:
        """Close all database connections."""
        for conn in self._connections.values():
            conn.disconnect()
        self._connections.clear()


# Global registry instance
_registry: DatabaseRegistry | None = None


def get_database_registry() -> DatabaseRegistry:
    """Get the global database registry.

    Returns:
        The DatabaseRegistry singleton instance.
    """
    global _registry
    if _registry is None:
        _registry = DatabaseRegistry()
    return _registry


def get_company_db() -> DatabaseConnection:
    """Get the SYSPRO company database connection.

    Returns:
        DatabaseConnection for the company database.
    """
    return get_database_registry().get_connection("syspro_company")


def get_admin_db() -> DatabaseConnection:
    """Get the SYSPRO admin database connection.

    Returns:
        DatabaseConnection for the admin database.
    """
    return get_database_registry().get_connection("syspro_admin")
