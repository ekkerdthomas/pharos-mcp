"""
SQL query execution tools for Pharos MCP.

Provides safe, validated query execution against SYSPRO databases.
"""

from mcp.server.fastmcp import FastMCP

from ..core.audit import audit_tool_call
from ..core.database import get_company_db, get_database_registry
from ..core.security import QueryValidationError, QueryValidator, sanitize_identifier
from .base import format_count, format_table_results


def register_query_tools(mcp: FastMCP) -> None:
    """Register query execution tools with the MCP server.

    Args:
        mcp: The FastMCP server instance.
    """
    # Create validator for read-only queries
    validator = QueryValidator(readonly=True)

    @mcp.tool()
    @audit_tool_call("execute_query")
    async def execute_query(
        sql: str,
        max_rows: int = 100,
        database: str | None = None,
    ) -> str:
        """Execute a read-only SQL query against the SYSPRO database.

        Args:
            sql: The SELECT query to execute.
            max_rows: Maximum rows to return (default 100, max 1000).
            database: Optional database name (defaults to company database).

        Returns:
            Formatted query results.
        """
        # Validate the query
        try:
            validator.validate_or_raise(sql)
        except QueryValidationError as e:
            return f"Query validation failed: {e}"

        # Enforce max_rows limit
        max_rows = min(max_rows, 1000)

        # Get database connection
        try:
            if database:
                db = get_database_registry().get_connection(database)
            else:
                db = get_company_db()
        except ValueError as e:
            return f"Database error: {e}"

        try:
            results = db.execute_query(sql, max_rows=max_rows)
        except Exception as e:
            return f"Query execution failed: {e}"

        if not results:
            return "Query returned no results."

        # Format results
        output = format_table_results(results)

        # Add row count
        if len(results) >= max_rows:
            output += f"\n\n(Results limited to {max_rows} rows)"
        else:
            output += f"\n\n({len(results)} row(s) returned)"

        return output

    @mcp.tool()
    @audit_tool_call("preview_table")
    async def preview_table(
        table_name: str,
        columns: str | None = None,
        limit: int = 10,
        where: str | None = None,
        order_by: str | None = None,
    ) -> str:
        """Preview data from a SYSPRO table.

        Args:
            table_name: Name of the table to preview.
            columns: Comma-separated column names (default: all columns).
            limit: Number of rows to return (default 10, max 100).
            where: Optional WHERE clause (without 'WHERE' keyword).
            order_by: Optional ORDER BY clause (without 'ORDER BY' keyword).

        Returns:
            Formatted table preview.
        """
        # Sanitize table name
        try:
            table_name = sanitize_identifier(table_name)
        except ValueError as e:
            return f"Invalid table name: {e}"

        # Build column list
        if columns:
            try:
                col_list = ", ".join(
                    sanitize_identifier(c.strip()) for c in columns.split(",")
                )
            except ValueError as e:
                return f"Invalid column name: {e}"
        else:
            col_list = "*"

        # Enforce limit
        limit = min(limit, 100)

        # Build query
        sql = f"SELECT TOP {limit} {col_list} FROM {table_name}"

        if where:
            # Basic validation of WHERE clause
            where_lower = where.lower()
            dangerous = ["drop", "delete", "insert", "update", "exec"]
            if any(kw in where_lower for kw in dangerous):
                return "Invalid WHERE clause: contains disallowed keywords"
            sql += f" WHERE {where}"

        if order_by:
            try:
                # Validate order by columns
                order_parts = []
                for part in order_by.split(","):
                    part = part.strip()
                    # Handle ASC/DESC
                    if part.upper().endswith(" ASC"):
                        col = sanitize_identifier(part[:-4].strip())
                        order_parts.append(f"{col} ASC")
                    elif part.upper().endswith(" DESC"):
                        col = sanitize_identifier(part[:-5].strip())
                        order_parts.append(f"{col} DESC")
                    else:
                        col = sanitize_identifier(part)
                        order_parts.append(col)
                sql += f" ORDER BY {', '.join(order_parts)}"
            except ValueError as e:
                return f"Invalid ORDER BY: {e}"

        # Validate the generated query
        try:
            validator.validate_or_raise(sql)
        except QueryValidationError as e:
            return f"Query validation failed: {e}"

        # Execute
        db = get_company_db()

        try:
            results = db.execute_query(sql, max_rows=limit)
        except Exception as e:
            return f"Query execution failed: {e}"

        if not results:
            return f"Table '{table_name}' is empty or has no matching rows."

        output = f"Preview of {table_name}:\n\n"
        output += format_table_results(results)
        output += f"\n\n({len(results)} row(s) shown)"

        return output

    @mcp.tool()
    @audit_tool_call("count_records")
    async def count_records(
        table_name: str,
        where: str | None = None,
    ) -> str:
        """Count records in a SYSPRO table.

        Args:
            table_name: Name of the table to count.
            where: Optional WHERE clause (without 'WHERE' keyword).

        Returns:
            Record count.
        """
        # Sanitize table name
        try:
            table_name = sanitize_identifier(table_name)
        except ValueError as e:
            return f"Invalid table name: {e}"

        # Build query
        sql = f"SELECT COUNT(*) as RecordCount FROM {table_name}"

        if where:
            # Basic validation
            where_lower = where.lower()
            dangerous = ["drop", "delete", "insert", "update", "exec"]
            if any(kw in where_lower for kw in dangerous):
                return "Invalid WHERE clause: contains disallowed keywords"
            sql += f" WHERE {where}"

        # Validate
        try:
            validator.validate_or_raise(sql)
        except QueryValidationError as e:
            return f"Query validation failed: {e}"

        # Execute
        db = get_company_db()

        try:
            result = db.execute_scalar(sql)
        except Exception as e:
            return f"Query execution failed: {e}"

        count = int(result) if result is not None else 0
        formatted = format_count(count)

        if where:
            return f"Count of {table_name} WHERE {where}: {formatted} record(s)"
        else:
            return f"Total records in {table_name}: {formatted}"
