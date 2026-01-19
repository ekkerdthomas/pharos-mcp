"""
Schema inspection tools for detailed analysis of tables and columns.

Tools: explain_column, get_table_summary, search_data, suggest_join
"""

from mcp.server.fastmcp import FastMCP

from ...core.audit import audit_tool_call
from ...core.database import get_company_db
from ..data import get_module_for_table


def register_inspection_tools(mcp: FastMCP) -> None:
    """Register schema inspection tools with the MCP server."""

    @mcp.tool()
    @audit_tool_call("explain_column")
    async def explain_column(
        table_name: str,
        column_name: str,
    ) -> str:
        """Get detailed information about a column, including sample values.

        Provides the column definition, data type, and sample distinct values
        to help understand what data the column contains.

        Args:
            table_name: Name of the table containing the column.
            column_name: Name of the column to explain.

        Returns:
            Column details with sample values.
        """
        db = get_company_db()

        # Get column info
        col_sql = """
            SELECT
                COLUMN_NAME,
                DATA_TYPE,
                CHARACTER_MAXIMUM_LENGTH,
                NUMERIC_PRECISION,
                NUMERIC_SCALE,
                IS_NULLABLE,
                COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = %s AND COLUMN_NAME = %s
        """
        col_info = db.execute_query(col_sql, (table_name, column_name))

        if not col_info:
            return f"Column '{column_name}' not found in table '{table_name}'."

        col = col_info[0]
        data_type = col.get("DATA_TYPE", "")
        max_len = col.get("CHARACTER_MAXIMUM_LENGTH")
        precision = col.get("NUMERIC_PRECISION")
        scale = col.get("NUMERIC_SCALE")
        nullable = col.get("IS_NULLABLE", "YES")

        # Build type string
        if max_len and max_len > 0:
            type_str = f"{data_type}({max_len})"
        elif precision is not None and scale is not None and scale > 0:
            type_str = f"{data_type}({precision},{scale})"
        elif precision is not None:
            type_str = f"{data_type}({precision})"
        else:
            type_str = data_type

        # Check if it's a primary key
        pk_sql = """
            SELECT 1
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
            JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                ON kcu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
            WHERE tc.TABLE_NAME = %s AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            AND kcu.COLUMN_NAME = %s
        """
        is_pk = bool(db.execute_query(pk_sql, (table_name, column_name)))

        # Get sample distinct values
        # Use explicit column aliases to avoid pymssql as_dict issues with unnamed columns
        sample_sql = f"""
            SELECT TOP 15 [{column_name}] as val, COUNT(*) as cnt
            FROM [{table_name}]
            WHERE [{column_name}] IS NOT NULL AND CAST([{column_name}] AS VARCHAR(MAX)) <> ''
            GROUP BY [{column_name}]
            ORDER BY COUNT(*) DESC
        """
        try:
            samples = db.execute_query(sample_sql, max_rows=15)
        except Exception:
            # Handle edge cases where query fails (binary columns, certain data types, etc.)
            samples = []
            # Try a simpler fallback query without the empty string filter
            try:
                fallback_sql = f"""
                    SELECT TOP 10 [{column_name}] as val, COUNT(*) as cnt
                    FROM [{table_name}]
                    WHERE [{column_name}] IS NOT NULL
                    GROUP BY [{column_name}]
                    ORDER BY COUNT(*) DESC
                """
                samples = db.execute_query(fallback_sql, max_rows=10)
            except Exception:
                samples = []

        # Get total count
        total_sql = f"SELECT COUNT(*) FROM [{table_name}]"
        total = db.execute_scalar(total_sql) or 0

        # Get null count
        null_sql = f"SELECT COUNT(*) FROM [{table_name}] WHERE [{column_name}] IS NULL"
        null_count = db.execute_scalar(null_sql) or 0

        # Build output
        lines = [
            f"Column: {table_name}.{column_name}",
            f"Type: {type_str} {'NULL' if nullable == 'YES' else 'NOT NULL'}",
        ]
        if is_pk:
            lines.append("Role: PRIMARY KEY")

        lines.extend([
            "",
            "Statistics:",
            f"  Total rows: {total:,}",
            f"  Null values: {null_count:,} ({100*null_count/total:.1f}%)" if total > 0 else f"  Null values: {null_count}",
        ])

        if samples:
            lines.extend(["", "Sample values (top 15 by frequency):"])
            for s in samples:
                val = s.get("val", "")
                cnt = s.get("cnt", 0)
                # Truncate long values
                display_val = str(val)[:50] + "..." if len(str(val)) > 50 else str(val)
                lines.append(f"  '{display_val}': {cnt:,} occurrences")

        return "\n".join(lines)

    @mcp.tool()
    @audit_tool_call("get_table_summary")
    async def get_table_summary(table_name: str) -> str:
        """Get a concise summary of a table showing only key columns.

        Shows primary keys, foreign keys, important business columns (names,
        codes, dates, status fields) without overwhelming detail. Useful for
        quickly understanding a table's purpose.

        Args:
            table_name: Name of the table to summarize.

        Returns:
            Condensed table summary with key columns only.
        """
        db = get_company_db()

        # Check table exists and get row count
        check_sql = """
            SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = %s AND TABLE_TYPE = 'BASE TABLE'
        """
        if not db.execute_query(check_sql, (table_name,)):
            return f"Table '{table_name}' not found."

        # Get row count
        count_sql = f"SELECT COUNT(*) FROM [{table_name}]"
        try:
            row_count = db.execute_scalar(count_sql) or 0
        except Exception:
            row_count = "unknown"

        # Get all columns
        columns_sql = """
            SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH,
                   NUMERIC_PRECISION, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """
        all_columns = db.execute_query(columns_sql, (table_name,))

        # Get primary key columns
        pk_sql = """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
            JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                ON kcu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
            WHERE tc.TABLE_NAME = %s AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            ORDER BY kcu.ORDINAL_POSITION
        """
        pk_cols = [r["COLUMN_NAME"] for r in db.execute_query(pk_sql, (table_name,))]

        # Get foreign key columns
        fk_sql = """
            SELECT DISTINCT kcu.COLUMN_NAME, ccu.TABLE_NAME as REF_TABLE
            FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                ON rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
                ON rc.UNIQUE_CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
            WHERE kcu.TABLE_NAME = %s
        """
        fk_info = {r["COLUMN_NAME"]: r["REF_TABLE"] for r in db.execute_query(fk_sql, (table_name,))}

        # Categorize columns by importance
        # Key patterns for important columns
        important_patterns = [
            "Name", "Description", "Desc", "Code", "Number", "No",
            "Status", "Type", "Flag", "Date", "Amount", "Amt",
            "Qty", "Quantity", "Price", "Cost", "Value", "Total",
            "Email", "Phone", "Telephone", "Address", "Currency"
        ]

        key_columns = []
        other_columns = []

        for col in all_columns:
            col_name = col["COLUMN_NAME"]
            data_type = col["DATA_TYPE"]
            max_len = col.get("CHARACTER_MAXIMUM_LENGTH")

            # Build type string
            if max_len and max_len > 0:
                type_str = f"{data_type}({max_len})"
            else:
                type_str = data_type

            col_info = {"name": col_name, "type": type_str}

            # Determine if this is a key column
            is_key = False
            if col_name in pk_cols:
                col_info["role"] = "PK"
                is_key = True
            elif col_name in fk_info:
                col_info["role"] = f"FK->{fk_info[col_name]}"
                is_key = True
            elif any(pattern.lower() in col_name.lower() for pattern in important_patterns):
                is_key = True

            if is_key:
                key_columns.append(col_info)
            else:
                other_columns.append(col_info)

        # Build output
        module = get_module_for_table(table_name)
        lines = [
            f"Table: {table_name}",
        ]
        if module:
            lines.append(f"Module: {module}")
        lines.extend([
            f"Records: {row_count:,}" if isinstance(row_count, int) else f"Records: {row_count}",
            f"Total columns: {len(all_columns)} ({len(key_columns)} key, {len(other_columns)} other)",
            "",
            "Key Columns:",
            "-" * 60,
        ])

        for col in key_columns:
            role = f" [{col['role']}]" if "role" in col else ""
            lines.append(f"  {col['name']}: {col['type']}{role}")

        if other_columns:
            lines.extend([
                "",
                f"Other columns ({len(other_columns)}): " +
                ", ".join(c["name"] for c in other_columns[:10]) +
                ("..." if len(other_columns) > 10 else "")
            ])

        return "\n".join(lines)

    @mcp.tool()
    @audit_tool_call("search_data")
    async def search_data(
        search_value: str,
        table_pattern: str | None = None,
        column_pattern: str | None = None,
        limit: int = 10,
    ) -> str:
        """Search for a specific value across tables and columns.

        Finds which tables contain a specific value. Useful for tracing
        data relationships or finding where a customer/order/item is used.

        Args:
            search_value: The value to search for (exact match).
            table_pattern: Optional pattern to filter tables (e.g., 'Ar%', 'Sor%').
            column_pattern: Optional pattern to filter columns (e.g., 'Customer%').
            limit: Maximum tables to search (default 10).

        Returns:
            List of tables and columns containing the value.
        """
        db = get_company_db()

        # Find candidate columns (varchar/char types that might contain the value)
        col_sql = """
            SELECT TOP 50 c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS c
            JOIN INFORMATION_SCHEMA.TABLES t ON c.TABLE_NAME = t.TABLE_NAME
            WHERE t.TABLE_TYPE = 'BASE TABLE'
            AND c.DATA_TYPE IN ('varchar', 'char', 'nvarchar', 'nchar')
        """
        params: list = []

        if table_pattern:
            col_sql += " AND c.TABLE_NAME LIKE %s"
            params.append(table_pattern)

        if column_pattern:
            col_sql += " AND c.COLUMN_NAME LIKE %s"
            params.append(column_pattern)

        col_sql += " ORDER BY c.TABLE_NAME, c.COLUMN_NAME"

        candidates = db.execute_query(col_sql, tuple(params) if params else None, max_rows=50)

        if not candidates:
            return "No candidate columns found matching the criteria."

        # Search each candidate
        found = []
        searched = 0

        for cand in candidates:
            if searched >= limit:
                break

            table = cand["TABLE_NAME"]
            column = cand["COLUMN_NAME"]

            # Check if value exists in this column
            search_sql = f"""
                SELECT TOP 1 1 FROM [{table}]
                WHERE [{column}] = %s
            """
            try:
                result = db.execute_query(search_sql, (search_value,), max_rows=1)
                if result:
                    # Get count
                    count_sql = f"SELECT COUNT(*) FROM [{table}] WHERE [{column}] = %s"
                    count = db.execute_scalar(count_sql, (search_value,)) or 0
                    found.append({
                        "table": table,
                        "column": column,
                        "count": count,
                    })
            except Exception:
                pass  # Skip tables/columns that can't be queried

            searched += 1

        if not found:
            return f"Value '{search_value}' not found in searched tables."

        lines = [f"Found '{search_value}' in {len(found)} location(s):\n"]
        for f in found:
            module = get_module_for_table(f["table"])
            module_str = f" [{module}]" if module else ""
            lines.append(f"  {f['table']}.{f['column']}: {f['count']} row(s){module_str}")

        if searched >= limit:
            lines.append(f"\n(Searched {searched} tables, limit reached)")

        return "\n".join(lines)

    @mcp.tool()
    @audit_tool_call("suggest_join")
    async def suggest_join(
        table1: str,
        table2: str,
    ) -> str:
        """Suggest how to join two tables based on foreign key relationships.

        Analyzes the relationship between two tables and suggests the
        appropriate JOIN conditions.

        Args:
            table1: First table name.
            table2: Second table name.

        Returns:
            Suggested JOIN syntax and explanation.
        """
        db = get_company_db()

        # Check both tables exist
        for t in [table1, table2]:
            check_sql = "SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = %s"
            if not db.execute_query(check_sql, (t,)):
                return f"Table '{t}' not found."

        # Check for direct FK from table1 to table2
        fk_sql = """
            SELECT kcu.COLUMN_NAME as FK_COL, ccu.COLUMN_NAME as PK_COL
            FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                ON rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
                ON rc.UNIQUE_CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
            WHERE kcu.TABLE_NAME = %s AND ccu.TABLE_NAME = %s
        """

        # Check table1 -> table2
        fk_1_to_2 = db.execute_query(fk_sql, (table1, table2))

        # Check table2 -> table1
        fk_2_to_1 = db.execute_query(fk_sql, (table2, table1))

        lines = [f"Join analysis: {table1} <-> {table2}\n"]

        if fk_1_to_2:
            lines.append(f"Direct relationship: {table1} references {table2}")
            join_conditions = []
            for fk in fk_1_to_2:
                join_conditions.append(f"{table1}.{fk['FK_COL']} = {table2}.{fk['PK_COL']}")

            lines.extend([
                "",
                "Suggested JOIN:",
                "  SELECT *",
                f"  FROM {table1}",
                f"  INNER JOIN {table2}",
                "    ON " + "\n    AND ".join(join_conditions),
            ])

        elif fk_2_to_1:
            lines.append(f"Direct relationship: {table2} references {table1}")
            join_conditions = []
            for fk in fk_2_to_1:
                join_conditions.append(f"{table2}.{fk['FK_COL']} = {table1}.{fk['PK_COL']}")

            lines.extend([
                "",
                "Suggested JOIN:",
                "  SELECT *",
                f"  FROM {table1}",
                f"  INNER JOIN {table2}",
                "    ON " + "\n    AND ".join(join_conditions),
            ])

        else:
            # Look for common columns (might be implicit relationship)
            common_sql = """
                SELECT c1.COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS c1
                JOIN INFORMATION_SCHEMA.COLUMNS c2
                    ON c1.COLUMN_NAME = c2.COLUMN_NAME
                    AND c1.DATA_TYPE = c2.DATA_TYPE
                WHERE c1.TABLE_NAME = %s AND c2.TABLE_NAME = %s
                AND c1.COLUMN_NAME NOT IN ('TimeStamp')
            """
            common_cols = db.execute_query(common_sql, (table1, table2))

            if common_cols:
                lines.append("No direct FK relationship found.")
                lines.append("")
                lines.append("Common columns (possible join candidates):")
                for col in common_cols:
                    lines.append(f"  - {col['COLUMN_NAME']}")

                # Suggest based on common columns
                if common_cols:
                    col = common_cols[0]["COLUMN_NAME"]
                    lines.extend([
                        "",
                        "Possible JOIN (verify relationship):",
                        "  SELECT *",
                        f"  FROM {table1}",
                        f"  INNER JOIN {table2}",
                        f"    ON {table1}.{col} = {table2}.{col}",
                    ])
            else:
                lines.append("No direct relationship or common columns found.")
                lines.append("These tables may need an intermediate table to join.")

        return "\n".join(lines)
