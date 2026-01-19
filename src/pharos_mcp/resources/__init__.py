"""
MCP Resources for SYSPRO integration.

Resources provide context information that can be loaded by MCP clients.
"""

from .schema_resources import register_schema_resources

__all__ = [
    "register_schema_resources",
]
