"""
SYSPRO reference tools for query templates and help documentation.

Tools: get_query_template, get_syspro_help
"""

from mcp.server.fastmcp import FastMCP

from ...core.audit import audit_tool_call
from ..data import QUERY_TEMPLATES, TEMPLATE_DESCRIPTIONS, HELP_TOPICS, TOPIC_ALIASES


def register_reference_tools(mcp: FastMCP) -> None:
    """Register SYSPRO reference tools with the MCP server."""

    @mcp.tool()
    @audit_tool_call("get_query_template")
    async def get_query_template(query_type: str) -> str:
        """Get a template SQL query for common SYSPRO reporting needs.

        Provides ready-to-use query templates for common business questions
        like customer lists, order summaries, inventory levels, etc.

        Args:
            query_type: Type of query needed. Options:
                - customers: Customer master list
                - customer_balances: Customer balances and aging
                - sales_orders: Open sales orders
                - order_details: Sales order with line items
                - inventory: Stock levels by warehouse
                - invoices: Invoice listing
                - suppliers: Supplier master list
                - income_statement: Income statement by GL group
                - income_statement_summary: P&L summary totals
                - balance_sheet: Balance sheet by account type
                - purchase_orders: Open purchase orders
                - jobs: Work in progress jobs
                - list: Show all available templates

        Returns:
            SQL query template with explanatory comments.
        """
        query_type_lower = query_type.lower().strip()

        if query_type_lower == "list":
            lines = ["Available query templates:\n"]
            for name, desc in TEMPLATE_DESCRIPTIONS.items():
                lines.append(f"  {name}: {desc}")
            lines.append("\nUse get_query_template('<name>') to get the SQL.")
            return "\n".join(lines)

        if query_type_lower not in QUERY_TEMPLATES:
            available = ", ".join(QUERY_TEMPLATES.keys())
            return f"Unknown query type: '{query_type}'.\n\nAvailable types: {available}\n\nUse 'list' to see descriptions."

        return QUERY_TEMPLATES[query_type_lower]

    @mcp.tool()
    @audit_tool_call("get_syspro_help")
    async def get_syspro_help(topic: str) -> str:
        """Get quick help on common SYSPRO questions and concepts.

        Provides domain knowledge about SYSPRO tables, relationships,
        and common patterns to help users navigate the database.

        Args:
            topic: Topic to get help on (e.g., 'customer', 'inventory', 'pricing')
                   Use 'list' to see all available topics.

        Returns:
            Helpful information about the topic.
        """
        topic_lower = topic.lower().strip()

        # Apply alias if exists
        topic_lower = TOPIC_ALIASES.get(topic_lower, topic_lower)

        if topic_lower not in HELP_TOPICS:
            return f"Unknown topic: '{topic}'\n\nUse get_syspro_help('list') to see available topics."

        return HELP_TOPICS[topic_lower]
