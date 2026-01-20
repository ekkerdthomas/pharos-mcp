"""
Warehouse tools for PostgreSQL data warehouse exploration.

Provides schema exploration and data preview tools for the SYSPRO
analytics warehouse running on PostgreSQL.
"""

from mcp.server.fastmcp import FastMCP

from ..core.database import get_database_registry
from .base import format_table_results

# Schemas to exclude from search by default (noisy/internal)
EXCLUDED_SCHEMAS = (
    "pg_catalog",
    "information_schema",
    "pg_toast",
    "public_dbt_test__audit",  # dbt test audit tables
)


def register_warehouse_tools(mcp: FastMCP) -> None:
    """Register warehouse-specific tools with the MCP server.

    Args:
        mcp: FastMCP server instance.
    """

    @mcp.tool()
    def warehouse_list_schemas(include_empty: bool = False) -> str:
        """List all schemas in the PostgreSQL warehouse.

        Args:
            include_empty: Include schemas with no tables (default: False).

        Returns:
            Formatted list of schemas with table counts.
        """
        db = get_database_registry().get_connection("warehouse")
        excluded = ", ".join(f"'{s}'" for s in EXCLUDED_SCHEMAS)
        sql = f"""
            SELECT
                schema_name,
                (SELECT COUNT(*)
                 FROM information_schema.tables t
                 WHERE t.table_schema = s.schema_name) as table_count
            FROM information_schema.schemata s
            WHERE schema_name NOT IN ({excluded})
            ORDER BY schema_name
        """
        results = db.execute_query(sql)
        if not results:
            return "No user schemas found."

        lines = ["## Warehouse Schemas", ""]
        for row in results:
            table_count = row["table_count"]
            if not include_empty and table_count == 0:
                continue
            lines.append(f"- **{row['schema_name']}**: {table_count} tables")

        return "\n".join(lines)

    @mcp.tool()
    def warehouse_list_tables(schema: str = "raw") -> str:
        """List tables in a warehouse schema.

        Args:
            schema: Schema name to list tables from (default: raw).

        Returns:
            Formatted list of tables with row counts.
        """
        db = get_database_registry().get_connection("warehouse")
        sql = """
            SELECT
                table_name,
                table_type,
                pg_size_pretty(pg_total_relation_size(quote_ident(table_schema) || '.' || quote_ident(table_name))) as size
            FROM information_schema.tables
            WHERE table_schema = %s
            ORDER BY table_name
        """
        results = db.execute_query(sql, (schema,))
        if not results:
            return f"No tables found in schema '{schema}'."

        lines = [f"## Tables in '{schema}' schema", ""]
        lines.append(f"Found {len(results)} tables:")
        lines.append("")

        for row in results:
            table_type = "VIEW" if row["table_type"] == "VIEW" else "TABLE"
            size = row.get("size", "unknown")
            lines.append(f"- **{row['table_name']}** ({table_type}, {size})")

        return "\n".join(lines)

    @mcp.tool()
    def warehouse_get_columns(table_name: str, schema: str = "raw") -> str:
        """Get column definitions for a warehouse table.

        Args:
            table_name: Name of the table.
            schema: Schema name (default: raw).

        Returns:
            Formatted column definitions.
        """
        db = get_database_registry().get_connection("warehouse")
        sql = """
            SELECT
                column_name,
                data_type,
                character_maximum_length,
                numeric_precision,
                numeric_scale,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        results = db.execute_query(sql, (schema, table_name))
        if not results:
            return f"Table '{schema}.{table_name}' not found or has no columns."

        lines = [f"## Columns in '{schema}.{table_name}'", ""]
        lines.append("| Column | Type | Nullable | Default |")
        lines.append("|--------|------|----------|---------|")

        for row in results:
            col_name = row["column_name"]
            data_type = row["data_type"]

            # Add length/precision info
            if row.get("character_maximum_length"):
                data_type += f"({row['character_maximum_length']})"
            elif row.get("numeric_precision"):
                if row.get("numeric_scale"):
                    data_type += f"({row['numeric_precision']},{row['numeric_scale']})"
                else:
                    data_type += f"({row['numeric_precision']})"

            nullable = "YES" if row["is_nullable"] == "YES" else "NO"
            default = row.get("column_default") or ""
            if len(default) > 30:
                default = default[:27] + "..."

            lines.append(f"| {col_name} | {data_type} | {nullable} | {default} |")

        return "\n".join(lines)

    @mcp.tool()
    def warehouse_preview(
        table_name: str,
        schema: str = "raw",
        limit: int = 10,
        columns: str | None = None,
    ) -> str:
        """Preview data from a warehouse table.

        Args:
            table_name: Name of the table to preview.
            schema: Schema name (default: raw).
            limit: Number of rows to return (default 10, max 100).
            columns: Comma-separated column names (default: all).

        Returns:
            Formatted table preview.
        """
        db = get_database_registry().get_connection("warehouse")

        # Validate limit
        limit = min(max(1, limit), 100)

        # Validate columns for dangerous characters/keywords
        if columns:
            dangerous = [";", "--", "/*", "drop", "delete", "insert", "update"]
            cols_lower = columns.lower()
            for kw in dangerous:
                if kw in cols_lower:
                    return f"Invalid column specification: contains disallowed pattern '{kw}'"
            # Quote each column name for safety
            col_list = ", ".join(f'"{c.strip()}"' for c in columns.split(","))
        else:
            col_list = "*"

        # Use safe identifier quoting
        sql = f'SELECT {col_list} FROM "{schema}"."{table_name}" LIMIT %s'

        try:
            results = db.execute_query(sql, (limit,))
        except Exception as e:
            return f"Query failed: {e}"

        if not results:
            return f"No data found in '{schema}.{table_name}'."

        header = f"## Preview: {schema}.{table_name} (showing {len(results)} rows)\n\n"
        return header + format_table_results(results)

    @mcp.tool()
    def warehouse_search(search_term: str, schema: str | None = None) -> str:
        """Search for tables and columns in the warehouse.

        Args:
            search_term: Term to search for in table and column names.
            schema: Optional schema to limit search (default: all user schemas).

        Returns:
            Matching tables and columns.
        """
        db = get_database_registry().get_connection("warehouse")
        search_pattern = f"%{search_term.lower()}%"
        excluded = ", ".join(f"'{s}'" for s in EXCLUDED_SCHEMAS)

        # Search tables
        table_sql = f"""
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_schema NOT IN ({excluded})
              AND LOWER(table_name) LIKE %s
        """
        params: list = [search_pattern]
        if schema:
            table_sql += " AND table_schema = %s"
            params.append(schema)
        table_sql += " ORDER BY table_schema, table_name LIMIT 50"

        tables = db.execute_query(table_sql, tuple(params))

        # Search columns
        col_sql = f"""
            SELECT table_schema, table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema NOT IN ({excluded})
              AND LOWER(column_name) LIKE %s
        """
        params = [search_pattern]
        if schema:
            col_sql += " AND table_schema = %s"
            params.append(schema)
        col_sql += " ORDER BY table_schema, table_name, column_name LIMIT 50"

        columns = db.execute_query(col_sql, tuple(params))

        lines = [f"## Search Results for '{search_term}'", ""]

        if tables:
            lines.append(f"### Matching Tables ({len(tables)})")
            for row in tables:
                table_type = "VIEW" if row["table_type"] == "VIEW" else "TABLE"
                lines.append(f"- {row['table_schema']}.{row['table_name']} ({table_type})")
            lines.append("")

        if columns:
            lines.append(f"### Matching Columns ({len(columns)})")
            for row in columns:
                lines.append(
                    f"- {row['table_schema']}.{row['table_name']}.{row['column_name']} "
                    f"({row['data_type']})"
                )
            lines.append("")

        if not tables and not columns:
            lines.append("No matching tables or columns found.")

        return "\n".join(lines)

    @mcp.tool()
    def warehouse_table_info(table_name: str, schema: str = "raw") -> str:
        """Get detailed information about a warehouse table.

        Includes column definitions, indexes, and constraints.

        Args:
            table_name: Name of the table.
            schema: Schema name (default: raw).

        Returns:
            Comprehensive table information.
        """
        db = get_database_registry().get_connection("warehouse")

        lines = [f"## Table: {schema}.{table_name}", ""]

        # Get table size and row count estimate
        size_sql = """
            SELECT
                pg_size_pretty(pg_total_relation_size(quote_ident(%s) || '.' || quote_ident(%s))) as total_size,
                pg_size_pretty(pg_table_size(quote_ident(%s) || '.' || quote_ident(%s))) as table_size,
                pg_size_pretty(pg_indexes_size(quote_ident(%s) || '.' || quote_ident(%s))) as index_size
        """
        try:
            size_result = db.execute_query(
                size_sql, (schema, table_name, schema, table_name, schema, table_name)
            )
            if size_result:
                r = size_result[0]
                lines.append(f"**Size:** {r['total_size']} total ({r['table_size']} data, {r['index_size']} indexes)")
        except Exception:
            pass

        # Get row count estimate
        count_sql = """
            SELECT reltuples::bigint as row_estimate
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = %s
        """
        try:
            count_result = db.execute_query(count_sql, (schema, table_name))
            if count_result:
                row_est = count_result[0]["row_estimate"]
                if row_est and row_est > 0:
                    lines.append(f"**Estimated Rows:** {row_est:,}")
        except Exception:
            pass

        lines.append("")

        # Get columns
        col_sql = """
            SELECT
                column_name,
                data_type,
                character_maximum_length,
                numeric_precision,
                numeric_scale,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        columns = db.execute_query(col_sql, (schema, table_name))

        if columns:
            lines.append("### Columns")
            lines.append("")
            for row in columns:
                col_name = row["column_name"]
                data_type = row["data_type"]
                if row.get("character_maximum_length"):
                    data_type += f"({row['character_maximum_length']})"
                elif row.get("numeric_precision"):
                    if row.get("numeric_scale"):
                        data_type += f"({row['numeric_precision']},{row['numeric_scale']})"
                nullable = " (nullable)" if row["is_nullable"] == "YES" else ""
                lines.append(f"- **{col_name}**: {data_type}{nullable}")
            lines.append("")

        # Get primary key
        pk_sql = """
            SELECT a.attname as column_name
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = (quote_ident(%s) || '.' || quote_ident(%s))::regclass
              AND i.indisprimary
            ORDER BY array_position(i.indkey, a.attnum)
        """
        try:
            pk_result = db.execute_query(pk_sql, (schema, table_name))
            if pk_result:
                pk_cols = [r["column_name"] for r in pk_result]
                lines.append("### Primary Key")
                lines.append(f"- {', '.join(pk_cols)}")
                lines.append("")
        except Exception:
            pass

        # Get indexes
        idx_sql = """
            SELECT
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname = %s AND tablename = %s
            ORDER BY indexname
        """
        try:
            indexes = db.execute_query(idx_sql, (schema, table_name))
            if indexes:
                lines.append("### Indexes")
                for row in indexes:
                    lines.append(f"- **{row['indexname']}**")
                lines.append("")
        except Exception:
            pass

        return "\n".join(lines)

    @mcp.tool()
    def warehouse_count(table_name: str, schema: str = "raw", where: str | None = None) -> str:
        """Count records in a warehouse table.

        Args:
            table_name: Name of the table.
            schema: Schema name (default: raw).
            where: Optional WHERE clause (without 'WHERE' keyword).

        Returns:
            Record count.
        """
        db = get_database_registry().get_connection("warehouse")

        # Validate WHERE clause for dangerous keywords
        if where:
            where_lower = where.lower()
            dangerous = ["drop", "delete", "insert", "update", "truncate", "alter", "create", ";"]
            for kw in dangerous:
                if kw in where_lower:
                    return f"Invalid WHERE clause: contains disallowed keyword '{kw}'"

        sql = f'SELECT COUNT(*) as count FROM "{schema}"."{table_name}"'
        if where:
            sql += f" WHERE {where}"

        try:
            result = db.execute_query(sql)
        except Exception as e:
            return f"Query failed: {e}"

        if result:
            count = result[0]["count"]
            table_ref = f"{schema}.{table_name}"
            if where:
                return f"**{table_ref}** has **{count:,}** records matching: `{where}`"
            return f"**{table_ref}** has **{count:,}** records"
        return "Could not count records."
