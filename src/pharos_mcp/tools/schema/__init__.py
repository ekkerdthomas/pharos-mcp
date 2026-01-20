"""
Schema exploration tools for Pharos MCP.

These tools use SQL Server INFORMATION_SCHEMA views to provide
metadata about the SYSPRO and Tempo database schemas, with
domain-specific knowledge built in.
"""

from mcp.server.fastmcp import FastMCP

from .discovery import register_discovery_tools
from .inspection import register_inspection_tools
from .lookup import register_lookup_tools
from .reference import register_reference_tools
from .tempo_reference import register_tempo_reference_tools


def register_schema_tools(mcp: FastMCP) -> None:
    """Register all schema exploration tools with the MCP server."""
    register_discovery_tools(mcp)
    register_inspection_tools(mcp)
    register_lookup_tools(mcp)
    register_reference_tools(mcp)
    register_tempo_reference_tools(mcp)


__all__ = ["register_schema_tools"]
