"""Shared test fixtures for Pharos MCP tests.

This module provides common fixtures for testing database connections,
configuration, and security components.
"""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pharos_mcp.core.security import QueryValidator

# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture
def mock_db_config() -> dict[str, Any]:
    """Provide mock database configuration."""
    return {
        "server": "test-server.local",
        "database": "TestDB",
        "user": "test_user",
        "password": "test_password",
        "readonly": True,
        "description": "Test database",
        "settings": {
            "timeout": 30,
            "max_rows": 100,
        },
    }


@pytest.fixture
def mock_databases_yaml() -> dict[str, Any]:
    """Provide mock databases.yaml content."""
    return {
        "default_database": "syspro_company",
        "global_settings": {
            "query_timeout": 30,
            "max_rows": 1000,
            "connection_pool_size": 5,
        },
        "databases": {
            "syspro_company": {
                "type": "mssql",
                "env_prefix": "SYSPRO_DB",
                "description": "SYSPRO Company Database",
                "readonly": True,
            },
            "syspro_admin": {
                "type": "mssql",
                "env_prefix": "SYSPRO_ADMIN_DB",
                "description": "SYSPRO Admin Database",
                "readonly": True,
            },
        },
    }


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture
def mock_db_connection(mock_db_config: dict[str, Any]) -> MagicMock:
    """Create a mock DatabaseConnection."""
    from pharos_mcp.core.database import DatabaseConnection

    conn = MagicMock(spec=DatabaseConnection)
    conn.name = "test_db"
    conn.config = mock_db_config
    conn.readonly = True
    conn.server = mock_db_config["server"]
    conn.database = mock_db_config["database"]
    conn.timeout = mock_db_config["settings"]["timeout"]
    conn.max_rows = mock_db_config["settings"]["max_rows"]
    conn.execute_query = MagicMock(return_value=[])
    conn.execute_scalar = MagicMock(return_value=None)
    return conn


@pytest.fixture
def sample_query_results() -> list[dict[str, Any]]:
    """Provide sample query results for testing."""
    return [
        {"Customer": "ACME Corp", "Balance": 1500.50, "Status": "A"},
        {"Customer": "Beta Inc", "Balance": 2300.00, "Status": "A"},
        {"Customer": "Gamma LLC", "Balance": 750.25, "Status": "I"},
    ]


@pytest.fixture
def sample_table_schema() -> list[dict[str, Any]]:
    """Provide sample INFORMATION_SCHEMA.COLUMNS results."""
    return [
        {
            "COLUMN_NAME": "Customer",
            "DATA_TYPE": "varchar",
            "CHARACTER_MAXIMUM_LENGTH": 15,
            "NUMERIC_PRECISION": None,
            "NUMERIC_SCALE": None,
            "IS_NULLABLE": "NO",
            "ORDINAL_POSITION": 1,
        },
        {
            "COLUMN_NAME": "CustomerName",
            "DATA_TYPE": "varchar",
            "CHARACTER_MAXIMUM_LENGTH": 50,
            "NUMERIC_PRECISION": None,
            "NUMERIC_SCALE": None,
            "IS_NULLABLE": "YES",
            "ORDINAL_POSITION": 2,
        },
        {
            "COLUMN_NAME": "Balance",
            "DATA_TYPE": "decimal",
            "CHARACTER_MAXIMUM_LENGTH": None,
            "NUMERIC_PRECISION": 15,
            "NUMERIC_SCALE": 2,
            "IS_NULLABLE": "YES",
            "ORDINAL_POSITION": 3,
        },
    ]


# =============================================================================
# Security Fixtures
# =============================================================================


@pytest.fixture
def query_validator() -> QueryValidator:
    """Provide a QueryValidator instance in read-only mode."""
    return QueryValidator(readonly=True)


@pytest.fixture
def query_validator_unrestricted() -> QueryValidator:
    """Provide a QueryValidator instance without read-only restriction."""
    return QueryValidator(readonly=False)


# =============================================================================
# Singleton Reset Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_singletons() -> Generator[None, None, None]:
    """Reset singleton instances between tests.

    This ensures test isolation by clearing global state.
    """
    import pharos_mcp.config as config_module
    import pharos_mcp.core.audit as audit_module
    import pharos_mcp.core.database as db_module
    import pharos_mcp.core.phx_client as phx_module

    # Store originals
    orig_registry = db_module._registry
    orig_audit = audit_module._audit_logger
    orig_config = config_module._config
    orig_phx = phx_module._phx_client

    # Reset to None
    db_module._registry = None
    audit_module._audit_logger = None
    config_module._config = None
    phx_module._phx_client = None

    yield

    # Restore originals (in case tests depend on them persisting)
    db_module._registry = orig_registry
    audit_module._audit_logger = orig_audit
    config_module._config = orig_config
    phx_module._phx_client = orig_phx


@pytest.fixture
def mock_config(mock_databases_yaml: dict[str, Any]) -> Generator[MagicMock, None, None]:
    """Mock the Config class for testing without real config files."""
    with patch("pharos_mcp.config.Config") as mock_class:
        mock_instance = MagicMock()
        mock_instance.databases = mock_databases_yaml["databases"]
        mock_instance.default_database = mock_databases_yaml["default_database"]
        mock_instance.global_settings = mock_databases_yaml["global_settings"]
        mock_class.return_value = mock_instance

        with patch("pharos_mcp.config._config", mock_instance):
            yield mock_instance


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def valid_select_queries() -> list[str]:
    """Provide a list of valid SELECT queries."""
    return [
        "SELECT * FROM Customers",
        "SELECT TOP 10 Name, Balance FROM ArCustomer",
        "  SELECT * FROM Orders  ",  # with whitespace
        "select customer from arcustomer",  # lowercase
        "SELECT c.* FROM Customers c WHERE c.Status = 'A'",
        "SELECT COUNT(*) FROM Products",
        """
        SELECT
            Customer,
            SUM(Amount) as Total
        FROM Orders
        GROUP BY Customer
        """,
    ]


@pytest.fixture
def valid_cte_queries() -> list[str]:
    """Provide valid WITH (CTE) queries."""
    return [
        """
        WITH CustomerTotals AS (
            SELECT Customer, SUM(Amount) as Total
            FROM Orders
            GROUP BY Customer
        )
        SELECT * FROM CustomerTotals
        """,
        """
        WITH
            ActiveCustomers AS (SELECT * FROM Customers WHERE Status = 'A'),
            RecentOrders AS (SELECT * FROM Orders WHERE OrderDate > '2024-01-01')
        SELECT * FROM ActiveCustomers ac
        JOIN RecentOrders ro ON ac.Customer = ro.Customer
        """,
    ]


@pytest.fixture
def dangerous_queries() -> list[tuple[str, str]]:
    """Provide dangerous queries with expected blocked patterns.

    Returns:
        List of (query, expected_blocked_pattern) tuples.
    """
    return [
        ("DROP TABLE Customers", "DROP"),
        ("DELETE FROM Customers WHERE 1=1", "DELETE"),
        ("INSERT INTO Customers VALUES ('X', 'Y')", "INSERT"),
        ("UPDATE Customers SET Name = 'Hacked'", "UPDATE"),
        ("TRUNCATE TABLE Logs", "TRUNCATE"),
        ("EXEC sp_executesql 'SELECT 1'", "EXEC"),
        ("EXECUTE sp_help 'Customers'", "EXECUTE"),
        ("ALTER TABLE Customers ADD Column1 INT", "ALTER"),
        ("CREATE TABLE Hack (id INT)", "CREATE"),
        ("GRANT SELECT ON Customers TO hacker", "GRANT"),
        ("REVOKE SELECT ON Customers FROM user1", "REVOKE"),
        ("BACKUP DATABASE master TO DISK='C:\\hack.bak'", "BACKUP"),
        ("xp_cmdshell 'dir'", "xp_"),
        ("sp_configure 'show advanced options', 1", "sp_"),
        ("SELECT * FROM Customers; DROP TABLE Orders", ";"),
        ("SELECT * FROM Customers -- comment injection", "--"),
        ("SELECT * FROM Customers /* block comment */ WHERE 1=1", "/*"),
    ]
