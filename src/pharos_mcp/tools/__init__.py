"""
MCP Tools for SYSPRO and Tempo integration.

- schema: Schema exploration tools (search_tables, get_table_schema, etc.)
- query: SQL query execution tools (execute_query, preview_table, etc.)
- financial: Financial reporting tools (generate_income_statement, etc.)
- analytics: Business analytics tools (KPIs, health analysis, profitability)
- tempo_analytics: Tempo MRP-specific analytics (dashboard, shortages, data quality)
"""

from .analytics import register_analytics_tools
from .financial import register_financial_tools
from .query import register_query_tools
from .schema import register_schema_tools
from .tempo_analytics import register_tempo_analytics_tools

__all__ = [
    "register_analytics_tools",
    "register_financial_tools",
    "register_query_tools",
    "register_schema_tools",
    "register_tempo_analytics_tools",
]
