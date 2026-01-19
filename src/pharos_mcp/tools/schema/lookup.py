"""
SYSPRO code lookup tools.

Tools: get_lookup_value
"""

from mcp.server.fastmcp import FastMCP

from ...core.audit import audit_tool_call
from ...core.database import get_company_db
from ..data import SYSPRO_LOOKUP_TABLES, SYSPRO_STATUS_CODES


def register_lookup_tools(mcp: FastMCP) -> None:
    """Register SYSPRO lookup tools with the MCP server."""

    @mcp.tool()
    @audit_tool_call("get_lookup_value")
    async def get_lookup_value(
        lookup_type: str,
        code: str | None = None,
    ) -> str:
        """Look up the meaning of a SYSPRO code.

        Gets the description for a code value, or lists all values for a lookup type.
        Common lookup types: terms, currency, order_type, customer_class, branch,
        area, warehouse, order_status, document_type, credit_status.

        Args:
            lookup_type: Type of lookup (e.g., 'terms', 'currency', 'order_status').
            code: Optional specific code to look up. If not provided, lists all values.

        Returns:
            Description of the code, or list of all codes and descriptions.
        """
        lookup_lower = lookup_type.lower().strip()

        # Check static status codes first
        if lookup_lower in SYSPRO_STATUS_CODES:
            codes = SYSPRO_STATUS_CODES[lookup_lower]
            if code is not None:
                desc = codes.get(code, codes.get(code.upper(), codes.get(code.strip())))
                if desc:
                    return f"{lookup_type} '{code}' = {desc}"
                return f"Unknown {lookup_type} code: '{code}'. Valid codes: {', '.join(codes.keys())}"
            else:
                lines = [f"{lookup_type} codes:\n"]
                for k, v in codes.items():
                    display_key = repr(k) if k == " " else k
                    lines.append(f"  {display_key}: {v}")
                return "\n".join(lines)

        # Check database lookup tables
        if lookup_lower not in SYSPRO_LOOKUP_TABLES:
            available = sorted(set(list(SYSPRO_LOOKUP_TABLES.keys()) + list(SYSPRO_STATUS_CODES.keys())))
            return f"Unknown lookup type: '{lookup_type}'.\n\nAvailable types:\n  " + "\n  ".join(available)

        table_name, code_col, desc_col = SYSPRO_LOOKUP_TABLES[lookup_lower]
        db = get_company_db()

        if code is not None:
            # Look up specific code
            sql = f"SELECT {desc_col} FROM {table_name} WHERE {code_col} = %s"
            result = db.execute_scalar(sql, (code,))
            if result:
                return f"{lookup_type} '{code}' = {result}"
            return f"Code '{code}' not found in {lookup_type} lookup."
        else:
            # List all codes
            sql = f"SELECT {code_col}, {desc_col} FROM {table_name} ORDER BY {code_col}"
            results = db.execute_query(sql, max_rows=100)

            if not results:
                return f"No values found in {lookup_type} lookup table."

            lines = [f"{lookup_type} codes ({table_name}):\n"]
            for row in results:
                code_val = row.get(code_col, "")
                desc_val = row.get(desc_col, "")
                lines.append(f"  {code_val}: {desc_val}")

            return "\n".join(lines)
