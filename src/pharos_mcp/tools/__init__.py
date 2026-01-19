"""
MCP Tools for SYSPRO integration.

- schema: Schema exploration tools (search_tables, get_table_schema, etc.)
- query: SQL query execution tools (execute_query, preview_table, etc.)
"""

from .schema import register_schema_tools
from .query import register_query_tools

__all__ = [
    "register_schema_tools",
    "register_query_tools",
]
