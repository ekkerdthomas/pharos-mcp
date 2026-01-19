"""
MCP Tools for SYSPRO integration.

- schema: Schema exploration tools (search_tables, get_table_schema, etc.)
- query: SQL query execution tools (execute_query, preview_table, etc.)
"""

from .query import register_query_tools
from .schema import register_schema_tools

__all__ = [
    "register_query_tools",
    "register_schema_tools",
]
