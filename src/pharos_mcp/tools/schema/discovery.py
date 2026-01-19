"""
Schema discovery tools for finding and listing tables and columns.

Tools: search_tables, get_table_schema, get_table_columns, find_related_tables,
       search_columns, list_tables, list_modules
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from ...core.audit import audit_tool_call
from ...core.database import get_company_db
from ..data import SYSPRO_DOMAIN_MAP, SYSPRO_MODULES, get_module_for_table


def register_discovery_tools(mcp: FastMCP) -> None:
    """Register schema discovery tools with the MCP server."""

    @mcp.tool()
    @audit_tool_call("search_tables")
    async def search_tables(
        search_term: str,
        limit: int = 50,
    ) -> str:
        """Search for SYSPRO tables by name or business concept.

        Understands SYSPRO naming conventions - searches like 'customer' will
        find ArCustomer tables, 'inventory' will find Inv tables, etc.

        Args:
            search_term: Business term or table name to search for.
            limit: Maximum results to return (default 50).

        Returns:
            Formatted list of matching tables with module info.
        """
        db = get_company_db()
        search_lower = search_term.lower().strip()

        # Build list of search patterns
        patterns = [f"%{search_term}%"]  # Always search the literal term

        # Add SYSPRO-specific patterns based on domain knowledge
        if search_lower in SYSPRO_DOMAIN_MAP:
            for prefix in SYSPRO_DOMAIN_MAP[search_lower]:
                patterns.append(f"{prefix}%")

        # Remove duplicates while preserving order
        seen = set()
        unique_patterns = []
        for p in patterns:
            if p.lower() not in seen:
                seen.add(p.lower())
                unique_patterns.append(p)

        # Build query with multiple OR conditions
        conditions = " OR ".join(["t.TABLE_NAME LIKE %s"] * len(unique_patterns))
        sql = f"""
            SELECT DISTINCT TOP %s
                t.TABLE_NAME,
                (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS c
                 WHERE c.TABLE_NAME = t.TABLE_NAME) as ColumnCount
            FROM INFORMATION_SCHEMA.TABLES t
            WHERE t.TABLE_TYPE = 'BASE TABLE'
            AND ({conditions})
            ORDER BY t.TABLE_NAME
        """
        params = tuple([limit] + unique_patterns)

        results = db.execute_query(sql, params)

        if not results:
            # Provide helpful suggestions
            suggestions = []
            if search_lower in ["customer", "customers"]:
                suggestions.append("Try: list_tables with prefix='Ar'")
            elif search_lower in ["inventory", "stock"]:
                suggestions.append("Try: list_tables with prefix='Inv'")
            elif search_lower in ["sales", "order", "orders"]:
                suggestions.append("Try: list_tables with prefix='Sor'")

            msg = f"No tables found matching '{search_term}'."
            if suggestions:
                msg += "\n" + "\n".join(suggestions)
            return msg

        # Group results by module
        lines = [f"Found {len(results)} table(s) for '{search_term}':\n"]

        current_module = None
        for row in results:
            table_name = row.get("TABLE_NAME", "")
            col_count = row.get("ColumnCount", 0)
            module = get_module_for_table(table_name)

            if module != current_module:
                if current_module is not None:
                    lines.append("")
                if module:
                    lines.append(f"[{module}]")
                current_module = module

            lines.append(f"  - {table_name} ({col_count} columns)")

        return "\n".join(lines)

    @mcp.tool()
    @audit_tool_call("get_table_schema")
    async def get_table_schema(table_name: str) -> str:
        """Get complete schema details for a table.

        Args:
            table_name: Name of the table to describe.

        Returns:
            Formatted table schema including columns and keys.
        """
        db = get_company_db()

        # Check table exists
        check_sql = """
            SELECT TABLE_NAME, TABLE_TYPE
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = %s
        """
        table_info = db.execute_query(check_sql, (table_name,))

        if not table_info:
            return f"Table '{table_name}' not found."

        # Get columns
        columns_sql = """
            SELECT
                COLUMN_NAME,
                DATA_TYPE,
                CHARACTER_MAXIMUM_LENGTH,
                NUMERIC_PRECISION,
                NUMERIC_SCALE,
                IS_NULLABLE,
                COLUMN_DEFAULT,
                ORDINAL_POSITION
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """
        columns = db.execute_query(columns_sql, (table_name,))

        # Get primary key columns
        pk_sql = """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
            JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                ON kcu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
            WHERE tc.TABLE_NAME = %s AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            ORDER BY kcu.ORDINAL_POSITION
        """
        pk_cols = db.execute_query(pk_sql, (table_name,))
        pk_names = [r["COLUMN_NAME"] for r in pk_cols]

        # Get foreign keys
        fk_sql = """
            SELECT
                kcu.COLUMN_NAME,
                ccu.TABLE_NAME as REFERENCED_TABLE,
                ccu.COLUMN_NAME as REFERENCED_COLUMN
            FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                ON rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
                ON rc.UNIQUE_CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
            WHERE kcu.TABLE_NAME = %s
        """
        fk_info = db.execute_query(fk_sql, (table_name,))

        # Format output
        module = get_module_for_table(table_name)
        lines = [
            f"Table: {table_name}",
        ]
        if module:
            lines.append(f"Module: {module}")
        lines.extend([
            f"Primary Key: {', '.join(pk_names) if pk_names else 'None'}",
            f"Columns: {len(columns)}",
            "",
            "Column Details:",
            "-" * 70,
        ])

        for col in columns:
            col_name = col.get("COLUMN_NAME", "")
            data_type = col.get("DATA_TYPE", "")
            max_len = col.get("CHARACTER_MAXIMUM_LENGTH")
            precision = col.get("NUMERIC_PRECISION")
            scale = col.get("NUMERIC_SCALE")
            nullable = col.get("IS_NULLABLE", "YES")
            default = col.get("COLUMN_DEFAULT")

            # Build type string
            if max_len and max_len > 0:
                if max_len == -1:
                    type_str = f"{data_type}(max)"
                else:
                    type_str = f"{data_type}({max_len})"
            elif precision is not None and scale is not None:
                type_str = f"{data_type}({precision},{scale})"
            elif precision is not None:
                type_str = f"{data_type}({precision})"
            else:
                type_str = data_type

            null_str = "NULL" if nullable == "YES" else "NOT NULL"
            pk_marker = " [PK]" if col_name in pk_names else ""

            lines.append(f"  {col_name}: {type_str} {null_str}{pk_marker}")
            if default:
                lines.append(f"    Default: {default}")

        if fk_info:
            lines.extend(["", "Foreign Keys:", "-" * 70])
            for fk in fk_info:
                col = fk.get("COLUMN_NAME", "")
                ref_table = fk.get("REFERENCED_TABLE", "")
                ref_col = fk.get("REFERENCED_COLUMN", "")
                lines.append(f"  {col} -> {ref_table}.{ref_col}")

        return "\n".join(lines)

    @mcp.tool()
    @audit_tool_call("get_table_columns")
    async def get_table_columns(table_name: str) -> str:
        """Get column definitions for a table.

        Args:
            table_name: Name of the table.

        Returns:
            Formatted column definitions.
        """
        db = get_company_db()

        sql = """
            SELECT
                COLUMN_NAME,
                DATA_TYPE,
                CHARACTER_MAXIMUM_LENGTH,
                NUMERIC_PRECISION,
                NUMERIC_SCALE,
                IS_NULLABLE,
                COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """
        columns = db.execute_query(sql, (table_name,))

        if not columns:
            return f"No columns found for table '{table_name}'."

        lines = [f"Columns for {table_name}:\n"]

        for col in columns:
            col_name = col.get("COLUMN_NAME", "")
            data_type = col.get("DATA_TYPE", "")
            max_len = col.get("CHARACTER_MAXIMUM_LENGTH")
            precision = col.get("NUMERIC_PRECISION")
            scale = col.get("NUMERIC_SCALE")
            nullable = col.get("IS_NULLABLE", "YES")
            default = col.get("COLUMN_DEFAULT")

            # Build type string
            if max_len and max_len > 0:
                type_str = f"{data_type}({max_len})"
            elif precision is not None and scale is not None and scale > 0:
                type_str = f"{data_type}({precision},{scale})"
            elif precision is not None:
                type_str = f"{data_type}({precision})"
            else:
                type_str = data_type

            null_str = "NULL" if nullable == "YES" else "NOT NULL"

            lines.append(f"{col_name}")
            lines.append(f"  Type: {type_str} {null_str}")
            if default:
                lines.append(f"  Default: {default}")
            lines.append("")

        return "\n".join(lines)

    @mcp.tool()
    @audit_tool_call("find_related_tables")
    async def find_related_tables(table_name: str) -> str:
        """Find tables related via foreign keys.

        Shows which tables this table references and which tables reference it,
        grouped by table name to reduce redundancy from composite keys.

        Args:
            table_name: Name of the table to find relationships for.

        Returns:
            Formatted list of related tables.
        """
        db = get_company_db()

        # Get outgoing FKs grouped by constraint to handle composite keys properly
        outgoing_sql = """
            SELECT DISTINCT
                rc.CONSTRAINT_NAME,
                kcu.COLUMN_NAME,
                ccu.TABLE_NAME as REFERENCED_TABLE,
                ccu.COLUMN_NAME as REFERENCED_COLUMN
            FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                ON rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
                ON rc.UNIQUE_CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
            WHERE kcu.TABLE_NAME = %s
            ORDER BY ccu.TABLE_NAME, kcu.COLUMN_NAME
        """
        outgoing = db.execute_query(outgoing_sql, (table_name,))

        # Get incoming FKs
        incoming_sql = """
            SELECT DISTINCT
                kcu.TABLE_NAME as REFERENCING_TABLE,
                kcu.COLUMN_NAME as REFERENCING_COLUMN
            FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                ON rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
                ON rc.UNIQUE_CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
            WHERE ccu.TABLE_NAME = %s
            ORDER BY kcu.TABLE_NAME
        """
        incoming = db.execute_query(incoming_sql, (table_name,))

        lines = [f"Relationships for {table_name}:\n"]

        if outgoing:
            lines.append("References (this table -> other tables):")
            # Group by referenced table, collect columns
            refs_by_table: dict[str, list[str]] = {}
            for rel in outgoing:
                col = rel.get("COLUMN_NAME", "")
                ref_table = rel.get("REFERENCED_TABLE", "")
                if ref_table not in refs_by_table:
                    refs_by_table[ref_table] = []
                if col not in refs_by_table[ref_table]:
                    refs_by_table[ref_table].append(col)

            for ref_table in sorted(refs_by_table.keys()):
                cols = refs_by_table[ref_table]
                module = get_module_for_table(ref_table)
                module_str = f" [{module}]" if module else ""
                if len(cols) == 1:
                    lines.append(f"  {cols[0]} -> {ref_table}{module_str}")
                else:
                    lines.append(f"  ({', '.join(cols)}) -> {ref_table}{module_str}")
        else:
            lines.append("References: None")

        lines.append("")

        if incoming:
            lines.append(f"Referenced by ({len(set(r.get('REFERENCING_TABLE', '') for r in incoming))} tables):")
            # Group by referencing table
            refs_by_table = {}
            for rel in incoming:
                ref_table = rel.get("REFERENCING_TABLE", "")
                ref_col = rel.get("REFERENCING_COLUMN", "")
                if ref_table not in refs_by_table:
                    refs_by_table[ref_table] = []
                if ref_col not in refs_by_table[ref_table]:
                    refs_by_table[ref_table].append(ref_col)

            for ref_table in sorted(refs_by_table.keys()):
                cols = refs_by_table[ref_table]
                module = get_module_for_table(ref_table)
                module_str = f" [{module}]" if module else ""
                lines.append(f"  {ref_table}{module_str}")
        else:
            lines.append("Referenced by: None")

        return "\n".join(lines)

    @mcp.tool()
    @audit_tool_call("search_columns")
    async def search_columns(
        search_term: str,
        table_pattern: str | None = None,
        limit: int = 50,
    ) -> str:
        """Search for columns across all tables by name.

        Args:
            search_term: Text to search for in column names.
            table_pattern: Optional table name pattern to filter.
            limit: Maximum results to return (default 50).

        Returns:
            Formatted list of matching columns.
        """
        db = get_company_db()

        sql = """
            SELECT TOP %s
                c.TABLE_NAME,
                c.COLUMN_NAME,
                c.DATA_TYPE,
                c.IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS c
            JOIN INFORMATION_SCHEMA.TABLES t ON c.TABLE_NAME = t.TABLE_NAME
            WHERE t.TABLE_TYPE = 'BASE TABLE'
            AND c.COLUMN_NAME LIKE %s
        """
        params: list[Any] = [limit, f"%{search_term}%"]

        if table_pattern:
            sql += " AND c.TABLE_NAME LIKE %s"
            params.append(f"%{table_pattern}%")

        sql += " ORDER BY c.TABLE_NAME, c.COLUMN_NAME"

        results = db.execute_query(sql, tuple(params))

        if not results:
            return f"No columns found matching '{search_term}'."

        lines = [f"Found {len(results)} column(s) matching '{search_term}':\n"]

        current_table = None
        for row in results:
            table = row.get("TABLE_NAME", "")
            if table != current_table:
                if current_table is not None:
                    lines.append("")
                module = get_module_for_table(table)
                module_str = f" [{module}]" if module else ""
                lines.append(f"{table}{module_str}")
                current_table = table

            col_name = row.get("COLUMN_NAME", "")
            data_type = row.get("DATA_TYPE", "")
            lines.append(f"  - {col_name} ({data_type})")

        return "\n".join(lines)

    @mcp.tool()
    @audit_tool_call("list_tables")
    async def list_tables(
        prefix: str | None = None,
        module: str | None = None,
        limit: int = 100,
    ) -> str:
        """List tables in the database.

        Args:
            prefix: Table name prefix filter (e.g., 'Ar', 'Inv', 'Sor').
            module: Module name filter (e.g., 'Accounts Receivable', 'Inventory').
            limit: Maximum results to return (default 100).

        Returns:
            Formatted list of tables.
        """
        db = get_company_db()

        # If module name given, convert to prefix
        if module and not prefix:
            module_lower = module.lower()
            for code, name in SYSPRO_MODULES.items():
                if module_lower in name.lower() or module_lower == code.lower():
                    prefix = code
                    break

        sql = """
            SELECT TOP %s
                t.TABLE_NAME,
                (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS c
                 WHERE c.TABLE_NAME = t.TABLE_NAME) as ColumnCount
            FROM INFORMATION_SCHEMA.TABLES t
            WHERE t.TABLE_TYPE = 'BASE TABLE'
        """
        params: list[Any] = [limit]

        if prefix:
            sql += " AND t.TABLE_NAME LIKE %s"
            params.append(f"{prefix}%")

        sql += " ORDER BY t.TABLE_NAME"

        results = db.execute_query(sql, tuple(params))

        if not results:
            msg = "No tables found"
            if prefix:
                msg += f" with prefix '{prefix}'"
            return msg + "."

        lines = []
        if prefix:
            module_desc = SYSPRO_MODULES.get(prefix, "")
            if module_desc:
                lines.append(f"Tables in {module_desc} ({prefix}):\n")
            else:
                lines.append(f"Tables starting with '{prefix}':\n")
        else:
            lines.append(f"Tables ({len(results)} shown):\n")

        for row in results:
            table_name = row.get("TABLE_NAME", "")
            col_count = row.get("ColumnCount", 0)
            lines.append(f"  {table_name} ({col_count} cols)")

        return "\n".join(lines)

    @mcp.tool()
    @audit_tool_call("list_modules")
    async def list_modules() -> str:
        """List SYSPRO modules with table counts.

        Returns:
            List of SYSPRO modules and their table counts.
        """
        db = get_company_db()

        lines = ["SYSPRO Modules:\n"]

        for prefix, description in sorted(SYSPRO_MODULES.items()):
            sql = """
                SELECT COUNT(*) as cnt
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE'
                AND TABLE_NAME LIKE %s
            """
            result = db.execute_scalar(sql, (f"{prefix}%",))
            count = int(result) if result else 0

            if count > 0:
                lines.append(f"  {prefix} - {description}: {count} tables")

        lines.append("\nUse list_tables(prefix='XX') to see tables in a module.")
        return "\n".join(lines)
