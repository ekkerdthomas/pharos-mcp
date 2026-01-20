"""
Tempo MRP reference tools for query templates.

Tools: get_tempo_query_template
"""

from mcp.server.fastmcp import FastMCP

from ...core.audit import audit_tool_call
from ..data import (
    TEMPO_QUERY_TEMPLATES,
    TEMPO_TEMPLATE_DESCRIPTIONS,
    list_tempo_templates,
)


def register_tempo_reference_tools(mcp: FastMCP) -> None:
    """Register Tempo reference tools with the MCP server."""

    @mcp.tool()
    @audit_tool_call("get_tempo_query_template")
    async def get_tempo_query_template(query_type: str) -> str:
        """Get a template SQL query for common Tempo MRP reporting needs.

        Provides ready-to-use query templates for MRP planning questions
        like demand analysis, supply summaries, suggestions, forecasts, etc.

        Args:
            query_type: Type of query needed. Options:
                MRP Core:
                - demands_summary: Demand totals by stock code
                - demands_detail: Demand records for a stock code
                - supply_summary: Supply totals by stock code
                - supply_detail: Supply records for a stock code
                - suggestions_open: Open MRP suggestions
                - suggestions_critical: Critical suggestions
                - pegging_analysis: Demand-supply pegging
                - supply_demand_balance: Net balance by item

                Forecasting:
                - forecast_results: Latest forecasts
                - forecast_accuracy: Accuracy metrics
                - forecast_poor_performers: Items with poor accuracy

                Inventory:
                - inventory_levels: Current stock levels
                - low_stock_items: Items below safety stock
                - abc_classification: ABC analysis results
                - buffer_penetration: Buffer status analysis

                Analytics:
                - mrp_runs: MRP run history
                - lead_time_analysis: Lead time variance
                - action_messages: MRP action messages

                - list: Show all available templates

        Returns:
            SQL query template with explanatory comments.
        """
        query_type_lower = query_type.lower().strip()

        if query_type_lower == "list":
            return list_tempo_templates()

        if query_type_lower not in TEMPO_QUERY_TEMPLATES:
            available = ", ".join(sorted(TEMPO_QUERY_TEMPLATES.keys()))
            return f"Unknown query type: '{query_type}'.\n\nAvailable types: {available}\n\nUse 'list' to see descriptions."

        template = TEMPO_QUERY_TEMPLATES[query_type_lower]
        description = TEMPO_TEMPLATE_DESCRIPTIONS.get(query_type_lower, "")

        return f"-- {description}\n{template}"
