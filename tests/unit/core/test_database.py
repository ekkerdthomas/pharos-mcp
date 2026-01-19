"""Tests for database connection module."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pharos_mcp.core.database import DatabaseConnection, DatabaseRegistry


class TestDatabaseConnection:
    """Test DatabaseConnection functionality."""

    @pytest.fixture
    def db_connection(self, mock_db_config: dict[str, Any]) -> DatabaseConnection:
        """Create a DatabaseConnection with mock config."""
        return DatabaseConnection("test_db", mock_db_config)

    # =========================================================================
    # Properties
    # =========================================================================

    def test_properties_from_config(
        self, db_connection: DatabaseConnection, mock_db_config: dict[str, Any]
    ) -> None:
        """Properties should return values from config."""
        assert db_connection.name == "test_db"
        assert db_connection.server == mock_db_config["server"]
        assert db_connection.database == mock_db_config["database"]
        assert db_connection.user == mock_db_config["user"]
        assert db_connection.password == mock_db_config["password"]
        assert db_connection.readonly == mock_db_config["readonly"]

    def test_timeout_from_settings(
        self, db_connection: DatabaseConnection
    ) -> None:
        """Timeout should come from settings."""
        assert db_connection.timeout == 30

    def test_max_rows_from_settings(
        self, db_connection: DatabaseConnection
    ) -> None:
        """Max rows should come from settings."""
        assert db_connection.max_rows == 100

    def test_default_timeout_when_missing(self) -> None:
        """Timeout should default to 30 when not in config."""
        config = {"server": "test", "database": "db"}
        conn = DatabaseConnection("test", config)
        assert conn.timeout == 30

    def test_default_max_rows_when_missing(self) -> None:
        """Max rows should default to 1000 when not in config."""
        config = {"server": "test", "database": "db"}
        conn = DatabaseConnection("test", config)
        assert conn.max_rows == 1000

    # =========================================================================
    # Connection Management
    # =========================================================================

    def test_initial_connection_is_none(
        self, db_connection: DatabaseConnection
    ) -> None:
        """Connection should be None initially."""
        assert db_connection._connection is None

    @patch("pharos_mcp.core.database.pymssql.connect")
    def test_connect_creates_connection(
        self,
        mock_connect: MagicMock,
        db_connection: DatabaseConnection,
    ) -> None:
        """connect() should create a new pymssql connection."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        result = db_connection.connect()

        assert result == mock_conn
        mock_connect.assert_called_once_with(
            server=db_connection.server,
            user=db_connection.user,
            password=db_connection.password,
            database=db_connection.database,
            timeout=db_connection.timeout,
            login_timeout=db_connection.timeout,
        )

    @patch("pharos_mcp.core.database.pymssql.connect")
    def test_connect_reuses_existing(
        self,
        mock_connect: MagicMock,
        db_connection: DatabaseConnection,
    ) -> None:
        """connect() should reuse existing alive connection."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)
        mock_connect.return_value = mock_conn

        # First connect
        conn1 = db_connection.connect()
        # Second connect should reuse
        conn2 = db_connection.connect()

        assert conn1 == conn2
        assert mock_connect.call_count == 1

    @patch("pharos_mcp.core.database.pymssql.connect")
    def test_connect_force_reconnect(
        self,
        mock_connect: MagicMock,
        db_connection: DatabaseConnection,
    ) -> None:
        """connect(force_reconnect=True) should create new connection."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        # First connect
        db_connection.connect()
        # Force reconnect
        db_connection.connect(force_reconnect=True)

        assert mock_connect.call_count == 2

    def test_disconnect_closes_connection(
        self, db_connection: DatabaseConnection
    ) -> None:
        """disconnect() should close and clear connection."""
        mock_conn = MagicMock()
        db_connection._connection = mock_conn

        db_connection.disconnect()

        mock_conn.close.assert_called_once()
        assert db_connection._connection is None

    def test_disconnect_when_no_connection(
        self, db_connection: DatabaseConnection
    ) -> None:
        """disconnect() should handle no existing connection."""
        db_connection._connection = None
        db_connection.disconnect()  # Should not raise

    # =========================================================================
    # Query Execution
    # =========================================================================

    @patch("pharos_mcp.core.database.pymssql.connect")
    def test_execute_query_returns_results(
        self,
        mock_connect: MagicMock,
        db_connection: DatabaseConnection,
        sample_query_results: list[dict[str, Any]],
    ) -> None:
        """execute_query should return list of dicts."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.__iter__ = lambda _: iter(sample_query_results)
        mock_connect.return_value = mock_conn

        results = db_connection.execute_query("SELECT * FROM Test")

        assert len(results) == len(sample_query_results)

    @patch("pharos_mcp.core.database.pymssql.connect")
    def test_execute_query_respects_max_rows(
        self,
        mock_connect: MagicMock,
        db_connection: DatabaseConnection,
    ) -> None:
        """execute_query should stop at max_rows."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        # Return more rows than limit
        mock_cursor.__iter__ = lambda _: iter(
            [{"id": i} for i in range(1000)]
        )
        mock_connect.return_value = mock_conn

        results = db_connection.execute_query(
            "SELECT * FROM Test", max_rows=10
        )

        assert len(results) == 10

    @patch("pharos_mcp.core.database.pymssql.connect")
    def test_execute_query_with_params(
        self,
        mock_connect: MagicMock,
        db_connection: DatabaseConnection,
    ) -> None:
        """execute_query should pass params to cursor."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.__iter__ = lambda _: iter([])
        mock_connect.return_value = mock_conn

        db_connection.execute_query(
            "SELECT * FROM Test WHERE id = %s",
            params=("ABC",),
        )

        mock_cursor.execute.assert_called_with(
            "SELECT * FROM Test WHERE id = %s", ("ABC",)
        )

    @patch("pharos_mcp.core.database.pymssql.connect")
    def test_execute_scalar_returns_single_value(
        self,
        mock_connect: MagicMock,
        db_connection: DatabaseConnection,
    ) -> None:
        """execute_scalar should return first column of first row."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (42,)
        mock_connect.return_value = mock_conn

        result = db_connection.execute_scalar("SELECT COUNT(*) FROM Test")

        assert result == 42

    @patch("pharos_mcp.core.database.pymssql.connect")
    def test_execute_scalar_returns_none_for_empty(
        self,
        mock_connect: MagicMock,
        db_connection: DatabaseConnection,
    ) -> None:
        """execute_scalar should return None if no rows."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None
        mock_connect.return_value = mock_conn

        result = db_connection.execute_scalar("SELECT * FROM Empty")

        assert result is None


class TestDatabaseRegistry:
    """Test DatabaseRegistry functionality."""

    @pytest.fixture
    def mock_registry_config(
        self, mock_databases_yaml: dict[str, Any]
    ) -> MagicMock:
        """Create a mock config for registry."""
        mock = MagicMock()
        mock.databases = mock_databases_yaml["databases"]
        mock.default_database = mock_databases_yaml["default_database"]
        mock.get_database_config.return_value = {
            "server": "test-server",
            "database": "TestDB",
            "user": "user",
            "password": "pass",
            "readonly": True,
            "settings": {"timeout": 30, "max_rows": 100},
        }
        return mock

    @patch("pharos_mcp.core.database.get_config")
    def test_get_connection_creates_new(
        self, mock_get_config: MagicMock, mock_registry_config: MagicMock
    ) -> None:
        """get_connection should create new DatabaseConnection."""
        mock_get_config.return_value = mock_registry_config

        registry = DatabaseRegistry()
        conn = registry.get_connection("syspro_company")

        assert isinstance(conn, DatabaseConnection)
        assert conn.name == "syspro_company"

    @patch("pharos_mcp.core.database.get_config")
    def test_get_connection_reuses_existing(
        self, mock_get_config: MagicMock, mock_registry_config: MagicMock
    ) -> None:
        """get_connection should reuse existing connection instance."""
        mock_get_config.return_value = mock_registry_config

        registry = DatabaseRegistry()
        conn1 = registry.get_connection("syspro_company")
        conn2 = registry.get_connection("syspro_company")

        assert conn1 is conn2

    @patch("pharos_mcp.core.database.get_config")
    def test_get_connection_uses_default(
        self, mock_get_config: MagicMock, mock_registry_config: MagicMock
    ) -> None:
        """get_connection(None) should use default database."""
        mock_get_config.return_value = mock_registry_config

        registry = DatabaseRegistry()
        registry.get_connection(None)

        mock_registry_config.get_database_config.assert_called_with(
            "syspro_company"
        )

    @patch("pharos_mcp.core.database.get_config")
    def test_list_databases(
        self, mock_get_config: MagicMock, mock_registry_config: MagicMock
    ) -> None:
        """list_databases should return database info."""
        mock_get_config.return_value = mock_registry_config

        registry = DatabaseRegistry()
        databases = registry.list_databases()

        assert len(databases) == 2
        names = [db["name"] for db in databases]
        assert "syspro_company" in names
        assert "syspro_admin" in names

    @patch("pharos_mcp.core.database.get_config")
    def test_close_all_disconnects_all(
        self, mock_get_config: MagicMock, mock_registry_config: MagicMock
    ) -> None:
        """close_all should disconnect all connections."""
        mock_get_config.return_value = mock_registry_config

        registry = DatabaseRegistry()

        # Create some connections with mocked internals
        conn1 = registry.get_connection("syspro_company")
        conn1._connection = MagicMock()

        registry.close_all()

        assert conn1._connection is None
        assert len(registry._connections) == 0
