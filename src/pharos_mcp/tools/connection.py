"""
Database connection management tools for Pharos MCP.

Allows MCP clients to register, manage, and test database connections at runtime.
Supports hybrid mode: server-configured defaults can be supplemented or overridden
by client-registered connections.
"""

from mcp.server.fastmcp import FastMCP

from ..core.audit import audit_tool_call
from ..core.database import get_database_registry


def register_connection_tools(mcp: FastMCP) -> None:
    """Register database connection management tools with the MCP server.

    Args:
        mcp: The FastMCP server instance.
    """

    @mcp.tool()
    @audit_tool_call("register_database")
    async def register_database(
        name: str,
        db_type: str,
        database: str,
        username: str,
        password: str,
        host: str | None = None,
        server: str | None = None,
        port: int | None = None,
        readonly: bool = True,
        timeout: int = 30,
        max_rows: int = 1000,
        description: str | None = None,
    ) -> str:
        """Register a new database connection for this session.

        Allows clients to define their own database connections at runtime.
        Client-registered databases take precedence over server-configured ones.

        Args:
            name: Unique identifier for this database connection.
            db_type: Database type - "mssql" (SQL Server) or "postgresql".
            database: Database name to connect to.
            username: Database username.
            password: Database password.
            host: Database host (required for PostgreSQL).
            server: Database server (required for SQL Server).
            port: Port number (default 5432 for PostgreSQL).
            readonly: Enforce read-only queries (default True, recommended).
            timeout: Query timeout in seconds (default 30).
            max_rows: Maximum rows per query (default 1000).
            description: Optional description for this connection.

        Returns:
            Confirmation message or error description.
        """
        # Validate db_type
        db_type = db_type.lower()
        if db_type not in ("mssql", "sqlserver", "postgresql", "postgres"):
            return f"Error: Unsupported database type '{db_type}'. Use 'mssql' or 'postgresql'."

        # Validate host/server based on type
        if db_type in ("postgresql", "postgres"):
            if not host:
                return "Error: PostgreSQL requires 'host' parameter."
            connection_host = host
        else:
            if not server:
                return "Error: SQL Server requires 'server' parameter."
            connection_host = server

        # Build config
        config = {
            "type": db_type,
            "database": database,
            "user": username,
            "password": password,
            "readonly": readonly,
            "description": description or f"Client-registered {db_type} database",
            "settings": {
                "timeout": timeout,
                "max_rows": max_rows,
            },
        }

        if db_type in ("postgresql", "postgres"):
            config["host"] = host
            config["port"] = port or 5432
        else:
            config["server"] = server

        try:
            registry = get_database_registry()
            registry.register_database(name, config)
            return (
                f"Successfully registered database '{name}' ({db_type}).\n"
                f"Host: {connection_host}\n"
                f"Database: {database}\n"
                f"Read-only: {readonly}\n\n"
                f"You can now use this database with query tools by specifying database='{name}'."
            )
        except ValueError as e:
            return f"Error registering database: {e}"

    @mcp.tool()
    @audit_tool_call("unregister_database")
    async def unregister_database(name: str) -> str:
        """Remove a runtime-registered database connection.

        Only databases registered via register_database tool can be removed.
        Databases configured via env vars or server config cannot be unregistered.

        Args:
            name: Name of the database to unregister.

        Returns:
            Confirmation message or error description.
        """
        try:
            registry = get_database_registry()
            if registry.unregister_database(name):
                return f"Successfully unregistered database '{name}'."
            else:
                return f"Database '{name}' not found in client registrations."
        except ValueError as e:
            return f"Error: {e}"

    @mcp.tool()
    @audit_tool_call("list_databases")
    async def list_databases() -> str:
        """List all available database connections.

        Shows databases from all sources with their priority:
        - Runtime: Registered via register_database tool (highest priority)
        - Client: Configured via PHAROS_CLIENT_CONFIG or PHAROS_DATABASES env vars
        - Server: Configured in server's databases.yaml (lowest priority)

        Returns:
            Formatted list of available databases.
        """
        registry = get_database_registry()
        databases = registry.list_databases()

        if not databases:
            return (
                "No databases configured.\n\n"
                "Use register_database to add a database connection, or configure via:\n"
                "- PHAROS_CLIENT_CONFIG: Path to a YAML file with database definitions\n"
                "- PHAROS_DATABASES: JSON string with database definitions"
            )

        lines = ["# Available Databases\n"]

        # Group by source (in priority order)
        runtime_dbs = [db for db in databases if db["source"] == "runtime"]
        client_dbs = [db for db in databases if db["source"] == "client"]
        server_dbs = [db for db in databases if db["source"] == "server"]

        if runtime_dbs:
            lines.append("## Runtime-Registered (via register_database)")
            for db in runtime_dbs:
                readonly_badge = "[read-only]" if db["readonly"] else "[read-write]"
                lines.append(
                    f"- **{db['name']}** ({db['type']}) {readonly_badge}"
                )
                if db.get("description"):
                    lines.append(f"  {db['description']}")
            lines.append("")

        if client_dbs:
            lines.append("## Client-Configured (via env vars)")
            for db in client_dbs:
                readonly_badge = "[read-only]" if db["readonly"] else "[read-write]"
                lines.append(
                    f"- **{db['name']}** ({db['type']}) {readonly_badge}"
                )
                if db.get("description"):
                    lines.append(f"  {db['description']}")
            lines.append("")

        if server_dbs:
            lines.append("## Server-Configured (from databases.yaml)")
            for db in server_dbs:
                readonly_badge = "[read-only]" if db["readonly"] else "[read-write]"
                lines.append(
                    f"- **{db['name']}** ({db['type']}) {readonly_badge}"
                )
                if db.get("description"):
                    lines.append(f"  {db['description']}")
            lines.append("")

        return "\n".join(lines)

    @mcp.tool()
    @audit_tool_call("test_database_connection")
    async def test_database_connection(name: str) -> str:
        """Test connectivity to a database.

        Attempts to connect and execute a simple test query.

        Args:
            name: Name of the database to test.

        Returns:
            Connection test result.
        """
        registry = get_database_registry()

        # Check if database exists
        if not registry.has_database(name):
            return (
                f"Database '{name}' not found.\n\n"
                f"Use list_databases to see available databases, or "
                f"register_database to add a new one."
            )

        try:
            db = registry.get_connection(name)
            # Force a new connection to truly test
            db.connect(force_reconnect=True)
            return (
                f"✓ Successfully connected to '{name}'\n"
                f"  Type: {db.db_type}\n"
                f"  Database: {db.database}\n"
                f"  Read-only: {db.readonly}"
            )
        except Exception as e:
            return (
                f"✗ Connection to '{name}' failed\n"
                f"  Error: {e}"
            )
