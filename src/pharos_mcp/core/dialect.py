"""
Database dialect abstraction for Pharos MCP.

Provides a unified interface for different database backends (SQL Server, PostgreSQL).
"""

from abc import ABC, abstractmethod
from typing import Any


class DatabaseDialect(ABC):
    """Abstract base class for database dialects."""

    name: str

    @abstractmethod
    def create_connection(self, config: dict[str, Any]) -> Any:
        """Create a database connection.

        Args:
            config: Connection configuration dictionary.

        Returns:
            Database connection object.
        """

    @abstractmethod
    def get_cursor(self, connection: Any, as_dict: bool = True) -> Any:
        """Get a cursor from the connection.

        Args:
            connection: Database connection.
            as_dict: If True, return rows as dictionaries.

        Returns:
            Database cursor.
        """

    @abstractmethod
    def test_connection_sql(self) -> str:
        """Get SQL to test if connection is alive.

        Returns:
            Simple SQL query that returns a single row.
        """

    @abstractmethod
    def get_connection_errors(self) -> tuple[type[Exception], ...]:
        """Get exception types that indicate connection errors.

        Returns:
            Tuple of exception types for connection/operational errors.
        """


class MSSQLDialect(DatabaseDialect):
    """SQL Server dialect using pymssql."""

    name = "mssql"

    def create_connection(self, config: dict[str, Any]) -> Any:
        """Create a SQL Server connection using pymssql."""
        import pymssql

        return pymssql.connect(
            server=config.get("server", ""),
            user=config.get("user", ""),
            password=config.get("password", ""),
            database=config.get("database", ""),
            timeout=config.get("settings", {}).get("timeout", 30),
            login_timeout=config.get("settings", {}).get("timeout", 30),
        )

    def get_cursor(self, connection: Any, as_dict: bool = True) -> Any:
        """Get a pymssql cursor."""
        return connection.cursor(as_dict=as_dict)

    def test_connection_sql(self) -> str:
        """SQL Server test query."""
        return "SELECT 1"

    def get_connection_errors(self) -> tuple[type[Exception], ...]:
        """Get pymssql connection error types."""
        import pymssql

        return (pymssql.OperationalError, pymssql.InterfaceError)


class PostgreSQLDialect(DatabaseDialect):
    """PostgreSQL dialect using psycopg."""

    name = "postgresql"

    def create_connection(self, config: dict[str, Any]) -> Any:
        """Create a PostgreSQL connection using psycopg."""
        import psycopg

        return psycopg.connect(
            host=config.get("host", ""),
            port=config.get("port", 5432),
            user=config.get("user", ""),
            password=config.get("password", ""),
            dbname=config.get("database", ""),
            connect_timeout=config.get("settings", {}).get("timeout", 30),
        )

    def get_cursor(self, connection: Any, as_dict: bool = True) -> Any:
        """Get a psycopg cursor with dict row factory if requested."""
        if as_dict:
            from psycopg.rows import dict_row

            return connection.cursor(row_factory=dict_row)
        return connection.cursor()

    def test_connection_sql(self) -> str:
        """PostgreSQL test query."""
        return "SELECT 1"

    def get_connection_errors(self) -> tuple[type[Exception], ...]:
        """Get psycopg connection error types."""
        import psycopg

        return (psycopg.OperationalError, psycopg.InterfaceError)


# Dialect registry
_DIALECTS: dict[str, type[DatabaseDialect]] = {
    "mssql": MSSQLDialect,
    "sqlserver": MSSQLDialect,
    "postgresql": PostgreSQLDialect,
    "postgres": PostgreSQLDialect,
}


def get_dialect(db_type: str) -> DatabaseDialect:
    """Get a dialect instance by type name.

    Args:
        db_type: Database type (mssql, postgresql, postgres, sqlserver).

    Returns:
        DatabaseDialect instance.

    Raises:
        ValueError: If dialect type is not supported.
    """
    db_type = db_type.lower()
    dialect_class = _DIALECTS.get(db_type)
    if dialect_class is None:
        supported = ", ".join(sorted(_DIALECTS.keys()))
        raise ValueError(f"Unsupported database type: {db_type}. Supported: {supported}")
    return dialect_class()
